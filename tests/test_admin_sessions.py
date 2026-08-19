import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from fastapi import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from apps.api.xianyu_admin_api import main
from apps.api.xianyu_admin_api.orm import AdminSessionORM, Base
from apps.api.xianyu_admin_api.schemas import (
    AuthLoginPayload,
    UserCreatePayload,
    UserUpdatePayload,
)
from apps.api.xianyu_admin_api.security import create_access_token, verify_access_token
from apps.api.xianyu_admin_api.settings import settings
from apps.api.xianyu_admin_api.store import AccountStore


def request(path: str = "/api/auth/login", *, forwarded_proto: str = "https") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(b"x-forwarded-proto", forwarded_proto.encode())],
            "query_string": b"",
            "scheme": "http",
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 50000),
        }
    )


class AdminSessionStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.store = AccountStore(session_factory=self.factory, initialize=False)
        self.user = await self.store.create_user(
            UserCreatePayload(
                username="session-admin",
                password="strong-test-password",
                role="admin",
            )
        )

    async def asyncTearDown(self) -> None:
        self.engine.dispose()

    async def test_session_is_sliding_and_server_revocable(self) -> None:
        created = await self.store.create_admin_session(
            self.user.user_id,
            client_ip="203.0.113.5",
            login_source="remote_addr",
        )
        assert created is not None
        session_id, refresh_token = created
        token, expires_in = create_access_token(
            user_id=self.user.user_id,
            username=self.user.username,
            role=self.user.role,
            session_id=session_id,
        )
        payload = verify_access_token(token)
        assert payload is not None
        self.assertEqual(payload["sid"], session_id)
        self.assertEqual(payload["token_type"], "admin_access")
        self.assertEqual(expires_in, settings.access_token_expires_minutes * 60)
        self.assertIsNotNone(
            await self.store.get_user_for_admin_session(self.user.user_id, session_id)
        )

        with self.factory() as session:
            row = session.get(AdminSessionORM, session_id)
            assert row is not None
            row.expires_at = datetime.now(UTC) + timedelta(days=1)
            session.commit()

        refreshed = await self.store.refresh_admin_session(refresh_token)
        assert refreshed is not None
        refreshed_user, refreshed_session_id = refreshed
        self.assertEqual(refreshed_user.user_id, self.user.user_id)
        self.assertEqual(refreshed_session_id, session_id)
        with self.factory() as session:
            row = session.get(AdminSessionORM, session_id)
            assert row is not None
            self.assertGreater(
                row.expires_at,
                datetime.now(UTC) + timedelta(days=settings.admin_session_expires_days - 1),
            )

        self.assertTrue(await self.store.revoke_admin_session(refresh_token))
        self.assertIsNone(await self.store.refresh_admin_session(refresh_token))
        self.assertIsNone(
            await self.store.get_user_for_admin_session(self.user.user_id, session_id)
        )

    async def test_password_change_revokes_all_sessions(self) -> None:
        first = await self.store.create_admin_session(self.user.user_id)
        second = await self.store.create_admin_session(self.user.user_id)
        assert first is not None and second is not None

        await self.store.update_user(
            self.user.user_id,
            UserUpdatePayload(password="another-strong-password"),
        )

        self.assertIsNone(await self.store.refresh_admin_session(first[1]))
        self.assertIsNone(await self.store.refresh_admin_session(second[1]))

        after_password_change = await self.store.create_admin_session(self.user.user_id)
        assert after_password_change is not None
        await self.store.update_user(
            self.user.user_id,
            UserUpdatePayload(enabled=False),
        )
        self.assertIsNone(
            await self.store.refresh_admin_session(after_password_change[1])
        )


class AdminSessionRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_sets_secure_http_only_year_cookie(self) -> None:
        user = main.UserPayload(
            user_id="user-1",
            username="admin",
            role="admin",
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        fake_store = AsyncMock()
        fake_store.authenticate_user.return_value = user
        fake_store.create_admin_session.return_value = ("session-1", "refresh-secret")
        response = Response()

        with patch.object(main, "store", fake_store):
            result = await main.login(
                request(),
                response,
                AuthLoginPayload(username="admin", password="password"),
            )

        payload = verify_access_token(result.access_token)
        assert payload is not None
        self.assertEqual(payload["sid"], "session-1")
        cookie = response.headers["set-cookie"]
        self.assertIn("xianyu_admin_session=refresh-secret", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertIn("Path=/api/auth", cookie)
        self.assertIn(
            f"Max-Age={settings.admin_session_expires_days * 24 * 60 * 60}",
            cookie,
        )

    async def test_expired_refresh_clears_cookie(self) -> None:
        fake_store = AsyncMock()
        fake_store.refresh_admin_session.return_value = None
        response = Response()
        expired_request = request("/api/auth/refresh")
        expired_request._cookies = {main.ADMIN_SESSION_COOKIE: "expired-token"}

        with patch.object(main, "store", fake_store):
            result = await main.refresh_auth(expired_request, response)

        self.assertEqual(result.status_code, 401)
        body = json.loads(bytes(result.body))
        self.assertEqual(body["detail"]["code"], "SESSION_EXPIRED")
        self.assertIn("Max-Age=0", result.headers["set-cookie"])

    async def test_revoked_browser_session_is_rejected_but_internal_token_still_works(self) -> None:
        user = main.UserPayload(
            user_id="user-1",
            username="admin",
            role="admin",
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        browser_token, _ = create_access_token(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            session_id="revoked-session",
        )
        protected_request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/accounts",
                "headers": [(b"authorization", f"Bearer {browser_token}".encode())],
                "query_string": b"",
                "scheme": "http",
                "server": ("127.0.0.1", 8000),
                "client": ("127.0.0.1", 50000),
            }
        )
        fake_store = AsyncMock()
        fake_store.get_user_for_admin_session.return_value = None
        call_next = AsyncMock(return_value=Response(status_code=200))
        with patch.object(main, "store", fake_store):
            rejected = await main.require_jwt(protected_request, call_next)
        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(json.loads(bytes(rejected.body))["detail"]["code"], "SESSION_EXPIRED")
        call_next.assert_not_awaited()

        internal_token, _ = create_access_token(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
        )
        internal_request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/accounts",
                "headers": [(b"authorization", f"Bearer {internal_token}".encode())],
                "query_string": b"",
                "scheme": "http",
                "server": ("127.0.0.1", 8000),
                "client": ("127.0.0.1", 50000),
            }
        )
        fake_store.get_user.return_value = user
        call_next = AsyncMock(return_value=Response(status_code=200))
        with patch.object(main, "store", fake_store):
            accepted = await main.require_jwt(internal_request, call_next)
        self.assertEqual(accepted.status_code, 200)
        call_next.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
