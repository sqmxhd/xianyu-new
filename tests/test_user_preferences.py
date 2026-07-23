import os
import unittest

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base, _apply_lightweight_migrations
from apps.api.xianyu_admin_api.schemas import UserCreatePayload, UserPreferenceUpdatePayload
from apps.api.xianyu_admin_api.store import AccountStore


class UserPreferenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        factory = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
        self.store = AccountStore(session_factory=factory, initialize=False)

    async def test_privacy_mask_preference_is_persisted_per_user(self) -> None:
        first = await self.store.create_user(
            UserCreatePayload(username="privacy-first", password="password-123")
        )
        second = await self.store.create_user(
            UserCreatePayload(username="privacy-second", password="password-123")
        )

        self.assertFalse(first.privacy_mask_enabled)
        updated = await self.store.update_user_preferences(
            first.user_id,
            UserPreferenceUpdatePayload(privacy_mask_enabled=True),
        )

        assert updated is not None
        self.assertTrue(updated.privacy_mask_enabled)
        self.assertTrue((await self.store.get_user(first.user_id)).privacy_mask_enabled)  # type: ignore[union-attr]
        self.assertFalse((await self.store.get_user(second.user_id)).privacy_mask_enabled)  # type: ignore[union-attr]

    async def test_existing_users_receive_disabled_privacy_default(self) -> None:
        engine = create_engine("sqlite://", future=True)
        with engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE xianyu_users (
                    user_id VARCHAR(64) PRIMARY KEY,
                    username VARCHAR(80) NOT NULL,
                    password_hash VARCHAR(500) NOT NULL,
                    role VARCHAR(32) NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    last_login_at DATETIME NULL,
                    last_login_ip VARCHAR(64) NULL,
                    last_login_source VARCHAR(32) NULL
                )
            """))
            connection.execute(text("""
                INSERT INTO xianyu_users (
                    user_id, username, password_hash, role, enabled, created_at, updated_at
                ) VALUES (
                    'legacy-user', 'legacy', 'hash', 'operator', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """))

        added = _apply_lightweight_migrations(engine)

        self.assertIn(("xianyu_users", "privacy_mask_enabled"), added)
        with engine.connect() as connection:
            value = connection.execute(text(
                "SELECT privacy_mask_enabled FROM xianyu_users WHERE user_id = 'legacy-user'"
            )).scalar_one()
        self.assertFalse(bool(value))
