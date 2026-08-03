import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.account_migrations import (
    AccountMigrationArchiveService,
    AccountMigrationError,
)
from apps.api.xianyu_admin_api.browser_profiles import BrowserProfileStorage
from apps.api.xianyu_admin_api.orm import Base
from apps.api.xianyu_admin_api.schemas import (
    AccountBrowserIdentityPayload,
    AccountCreatePayload,
    ProxyConfigPayload,
    ProxyCreatePayload,
)
from apps.api.xianyu_admin_api.store import AccountRecord, AccountStore


class AccountMigrationArchiveTests(unittest.TestCase):
    def test_encrypted_round_trip_preserves_identity_and_profile_without_cache(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            storage = BrowserProfileStorage(root_path / "profiles")
            profile = storage.prepare_account(
                "source-account",
                "咸鱼主账号",
                browser_engine="fingerprint_chromium",
                config_revision=1,
            )
            (profile / "Default").mkdir(exist_ok=True)
            (profile / "Default" / "Cookies").write_bytes(b"browser-cookie-db")
            (profile / "Cache").mkdir()
            (profile / "Cache" / "cache.data").write_bytes(b"do-not-export")
            (profile / "SingletonLock").write_text("lock", encoding="utf-8")

            identity = AccountBrowserIdentityPayload(
                browser_engine="fingerprint_chromium",
                fingerprint_seed=1_234_567,
                browser_version="148.0.7778.215",
                timezone="Asia/Shanghai",
            )
            account = AccountRecord(
                account_id="source-account",
                platform_user_id="seller-100",
                platform_display_name="咸鱼主账号",
                platform_avatar_url="https://example.invalid/avatar.png",
                remark="迁移测试",
                cookie="unb=seller-100; _m_h5_tk=secret-token",
                enabled=True,
                chat_enabled=True,
                proxy_id="proxy-1",
                proxy_name="上海代理",
                proxy=ProxyConfigPayload(
                    enabled=True,
                    scheme="socks5h",
                    host="127.0.0.1",
                    port=1080,
                    username="proxy-user",
                    password="proxy-password",
                ),
                browser_identity=identity,
            )
            service = AccountMigrationArchiveService(
                storage,
                staging_root=root_path / "staging",
            )

            package = service.create_package(account, "transfer-password")
            self.assertTrue(package.path.is_file())
            self.assertTrue(package.filename.endswith(".xianyu.zip"))

            with package.path.open("rb") as stream:
                staged = service.inspect_package(
                    stream,
                    package.filename,
                    "transfer-password",
                )

            self.assertEqual(staged.account.platform_user_id, "seller-100")
            self.assertEqual(staged.account.cookie, account.cookie)
            self.assertEqual(staged.account.proxy.password, "proxy-password")
            self.assertEqual(staged.account.browser_identity.fingerprint_seed, 1_234_567)
            self.assertTrue(staged.profile_path)
            self.assertTrue((staged.profile_path / "Default" / "Cookies").is_file())
            self.assertFalse((staged.profile_path / "Cache").exists())
            self.assertFalse((staged.profile_path / "SingletonLock").exists())

            imported = AccountRecord(
                account_id="target-account",
                platform_user_id="seller-100",
                platform_display_name="咸鱼主账号",
                browser_identity=identity,
            )
            self.assertTrue(service.install_profile(staged, imported))
            target = storage.account_path("target-account")
            self.assertEqual(
                (target / "Default" / "Cookies").read_bytes(),
                b"browser-cookie-db",
            )
            self.assertFalse((target / "Cache").exists())

            service.complete_session(staged.session_id)
            service.remove_export(package)

    def test_wrong_password_does_not_leave_staged_session(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            storage = BrowserProfileStorage(root_path / "profiles")
            service = AccountMigrationArchiveService(
                storage,
                staging_root=root_path / "staging",
            )
            account = AccountRecord(
                account_id="source-account",
                platform_user_id="seller-100",
                cookie="unb=seller-100; token=secret",
            )
            package = service.create_package(account, "correct-password")

            with package.path.open("rb") as stream:
                with self.assertRaisesRegex(AccountMigrationError, "密码错误|篡改"):
                    service.inspect_package(stream, package.filename, "wrong-password")

            self.assertEqual(service._sessions, {})
            service.remove_export(package)


class AccountMigrationStoreTests(unittest.IsolatedAsyncioTestCase):
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

    async def asyncTearDown(self) -> None:
        self.engine.dispose()

    async def test_import_is_atomic_and_rejects_duplicate_identity_or_seed(self) -> None:
        identity = AccountBrowserIdentityPayload(
            browser_engine="fingerprint_chromium",
            fingerprint_seed=8_765_432,
            browser_version="148.0.7778.215",
        )
        payload = AccountCreatePayload(
            remark="迁移账户",
            cookie="unb=seller-200; _m_h5_tk=token",
            enabled=False,
            chat_enabled=False,
            browser_identity=identity,
        )
        proxy = ProxyCreatePayload(
            name="迁移代理",
            enabled=True,
            scheme="socks5h",
            host="127.0.0.1",
            port=1080,
            username="user",
            password="password",
        )

        imported = await self.store.import_migrated_account(
            payload,
            platform_user_id="seller-200",
            platform_display_name="卖家 200",
            platform_avatar_url="https://example.invalid/avatar.png",
            proxy=proxy,
        )

        self.assertNotEqual(imported.account_id, "seller-200")
        self.assertEqual(imported.platform_user_id, "seller-200")
        self.assertEqual(imported.platform_identity_source, "account_import")
        self.assertFalse(imported.enabled)
        self.assertFalse(imported.chat_enabled)
        self.assertEqual(imported.runtime.state, "disabled")
        self.assertEqual(imported.proxy.password, "password")
        self.assertEqual(imported.browser_identity.fingerprint_seed, 8_765_432)

        with self.assertRaisesRegex(ValueError, "已经存在"):
            await self.store.import_migrated_account(
                payload,
                platform_user_id="seller-200",
                platform_display_name="重复账户",
                platform_avatar_url=None,
                proxy=None,
            )

        with self.assertRaisesRegex(ValueError, "指纹"):
            await self.store.import_migrated_account(
                payload.model_copy(
                    update={"cookie": "unb=seller-201; _m_h5_tk=token"}
                ),
                platform_user_id="seller-201",
                platform_display_name="另一账户",
                platform_avatar_url=None,
                proxy=None,
            )

        self.assertEqual(len(await self.store.list_accounts()), 1)
        self.assertEqual(len(await self.store.list_proxies()), 1)


if __name__ == "__main__":
    unittest.main()
