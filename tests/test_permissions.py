import os
import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from starlette.requests import Request
from fastapi import HTTPException, Response

from apps.api.xianyu_admin_api import main
from apps.api.xianyu_admin_api.main import _first_header_ip, _has_permission
from apps.api.xianyu_admin_api.schemas import AccountUpdatePayload, UserPayload
from apps.api.xianyu_admin_api.store import AccountRecord


def _request(method: str, path: str) -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": [], "query_string": b""})


def _user(role: str) -> UserPayload:
    now = datetime.now(UTC)
    return UserPayload(
        user_id=f"{role}-id",
        username=role,
        role=role,
        enabled=True,
        created_at=now,
        updated_at=now,
    )


class PermissionTests(unittest.TestCase):
    def test_viewer_is_read_only(self) -> None:
        viewer = _user("viewer")
        self.assertTrue(_has_permission(viewer, _request("GET", "/api/accounts")))
        self.assertFalse(_has_permission(viewer, _request("PUT", "/api/accounts/a")))

    def test_operator_cannot_access_admin_only_resources(self) -> None:
        operator = _user("operator")
        self.assertTrue(_has_permission(operator, _request("POST", "/api/accounts")))
        self.assertTrue(_has_permission(operator, _request("PUT", "/api/accounts/order")))
        self.assertTrue(
            _has_permission(
                operator,
                _request("POST", "/api/accounts/a/cookie/reveal"),
            )
        )
        self.assertTrue(
            _has_permission(
                operator,
                _request("POST", "/api/accounts/a/browser-session"),
            )
        )
        self.assertFalse(_has_permission(operator, _request("GET", "/api/users")))
        self.assertFalse(_has_permission(operator, _request("GET", "/api/audit-logs")))
        self.assertFalse(
            _has_permission(
                operator,
                _request("GET", "/api/settings/message-services/chatwoot"),
            )
        )
        self.assertFalse(
            _has_permission(
                operator,
                _request("POST", "/api/account-migrations/inspect"),
            )
        )

    def test_web_notification_playback_is_readable_but_configuration_is_admin_only(self) -> None:
        operator = _user("operator")
        viewer = _user("viewer")
        self.assertTrue(_has_permission(operator, _request("GET", "/api/web-notification")))
        self.assertTrue(
            _has_permission(viewer, _request("GET", "/api/web-notification/sound"))
        )
        self.assertFalse(
            _has_permission(
                operator,
                _request("PUT", "/api/settings/message-services/web-notification"),
            )
        )

    def test_viewer_cannot_reorder_accounts(self) -> None:
        viewer = _user("viewer")
        self.assertFalse(_has_permission(viewer, _request("PUT", "/api/accounts/order")))

    def test_viewer_cannot_reveal_account_cookie(self) -> None:
        viewer = _user("viewer")
        self.assertFalse(
            _has_permission(
                viewer,
                _request("POST", "/api/accounts/a/cookie/reveal"),
            )
        )

    def test_viewer_cannot_start_account_browser(self) -> None:
        viewer = _user("viewer")
        self.assertFalse(
            _has_permission(
                viewer,
                _request("POST", "/api/accounts/a/browser-session"),
            )
        )
        self.assertFalse(
            _has_permission(
                viewer,
                _request("DELETE", "/api/accounts/a/browser-profile"),
            )
        )
        self.assertTrue(
            _has_permission(
                viewer,
                _request("GET", "/api/browser-sessions"),
            )
        )
        self.assertTrue(
            _has_permission(
                viewer,
                _request("GET", "/api/browser-profiles"),
            )
        )
        self.assertFalse(
            _has_permission(
                viewer,
                _request("POST", "/api/browser-profiles/account%3Aa/stop"),
            )
        )
        self.assertFalse(
            _has_permission(
                viewer,
                _request("DELETE", "/api/browser-profiles/account%3Aa"),
            )
        )

    def test_viewer_can_mark_own_conversation_read(self) -> None:
        viewer = _user("viewer")
        self.assertTrue(
            _has_permission(
                viewer,
                _request("POST", "/api/im/conversations/a/conversation-1/read"),
            )
        )

    def test_forwarded_ip_parser_rejects_invalid_values(self) -> None:
        self.assertEqual(_first_header_ip("203.0.113.9, 10.0.0.2"), "203.0.113.9")
        self.assertIsNone(_first_header_ip("not-an-ip"))


class AccountActionGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_chatwoot_config_with_plaintext_token_is_not_cached(self) -> None:
        config = object()
        response = Response()
        with patch.object(
            main.chatwoot_repository,
            "get_config_payload",
            AsyncMock(return_value=config),
        ):
            result = await main.get_chatwoot_config(response)
        self.assertIs(result, config)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")

    async def test_chatwoot_account_structure_resync_queues_enabled_accounts(self) -> None:
        enabled = AccountRecord(
            account_id="account-enabled",
            platform_display_name="enabled",
            chat_enabled=True,
        )
        disabled = AccountRecord(
            account_id="account-disabled",
            platform_display_name="disabled",
            chat_enabled=False,
        )
        enqueue = AsyncMock()
        with (
            patch.object(
                main.store,
                "list_accounts",
                AsyncMock(return_value=[enabled, disabled]),
            ),
            patch.object(main, "enqueue_account_metadata_sync", enqueue),
        ):
            result = await main.resync_chatwoot_account_structure()
        self.assertTrue(result.success)
        enqueue.assert_awaited_once_with(
            main.store,
            account_id=enabled.account_id,
            reason="manual-platform-resync",
        )

    async def test_browser_profile_cleanup_is_account_scoped(self) -> None:
        account = AccountRecord(
            account_id="account-1",
            platform_display_name="seller",
            cookie="unb=seller-1",
        )
        cleanup = AsyncMock(return_value=True)
        with (
            patch.object(main.store, "get_account", AsyncMock(return_value=account)),
            patch.object(
                main.im_verification_manager,
                "clear_account_browser_profile",
                cleanup,
            ),
        ):
            result = await main.clear_account_browser_profile(account.account_id)
        cleanup.assert_awaited_once_with(account.account_id)
        self.assertTrue(result.deleted)

    async def test_cookie_reveal_is_explicit_and_not_cached(self) -> None:
        account = AccountRecord(
            account_id="account-1",
            platform_display_name="seller",
            cookie="unb=seller-1; _m_h5_tk=secret-token",
            enabled=True,
        )
        response = Response()
        with patch.object(main.store, "get_account", AsyncMock(return_value=account)):
            payload = await main.reveal_account_cookie(account.account_id, response)
        self.assertEqual(payload.cookie, account.cookie)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("cookie", account.to_payload().model_dump())

    async def test_unchanged_revealed_cookie_is_not_reapplied(self) -> None:
        previous = AccountRecord(
            account_id="account-1",
            platform_display_name="seller",
            cookie="unb=seller-1; _m_h5_tk=secret-token",
            enabled=True,
        )
        updated = AccountRecord(
            account_id="account-1",
            platform_display_name="renamed-seller",
            cookie=previous.cookie,
            enabled=True,
        )
        replace_cookie = AsyncMock(return_value=True)
        with (
            patch.object(main.store, "get_account", AsyncMock(side_effect=[previous, updated])),
            patch.object(main.store, "update_account", AsyncMock(return_value=updated)),
            patch.object(main.runtime_manager, "replace_cookie", replace_cookie),
            patch.object(main.realtime_broker, "publish", AsyncMock()),
        ):
            await main.update_account(
                previous.account_id,
                AccountUpdatePayload(cookie=previous.cookie),
            )
        replace_cookie.assert_not_awaited()

    async def test_disabled_account_cannot_report_successful_start(self) -> None:
        account = AccountRecord(
            account_id="account-1",
            platform_display_name="seller",
            cookie="unb=seller-1; _m_h5_tk=token",
            enabled=False,
        )
        account.runtime.state = "disabled"  # type: ignore[union-attr]
        with patch.object(main.store, "get_account", AsyncMock(return_value=account)):
            with self.assertRaises(HTTPException) as raised:
                await main.start_account(account.account_id)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("已禁用", str(raised.exception.detail))

    async def test_verification_cannot_start_without_risk_state(self) -> None:
        account = AccountRecord(
            account_id="account-1",
            platform_display_name="seller",
            cookie="unb=seller-1; _m_h5_tk=token",
            enabled=True,
        )
        account.runtime.state = "offline"  # type: ignore[union-attr]
        request = _request("POST", f"/api/accounts/{account.account_id}/im-verification/start")
        with patch.object(main.store, "get_account", AsyncMock(return_value=account)):
            with self.assertRaises(HTTPException) as raised:
                await main.start_account_im_verification(account.account_id, request)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("没有需要处理", str(raised.exception.detail))


if __name__ == "__main__":
    unittest.main()
