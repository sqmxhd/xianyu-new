import os
import unittest
from unittest.mock import patch

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base, _ensure_proxy_assignment_index
from apps.api.xianyu_admin_api.proxy_location import ProxyIPLocation
from apps.api.xianyu_admin_api.runtime import AccountRuntimeManager
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    AccountUpdatePayload,
    ProxyConfigPayload,
    ProxyCreatePayload,
    ProxyUpdatePayload,
)
from apps.api.xianyu_admin_api.orm import AccountORM
from apps.api.xianyu_admin_api.store import AccountStore, ProxyAssignmentConflict
from integrations.xianyu_core.models import ProxyConfig
from integrations.xianyu_core.proxy import build_socks_proxy_url


class ProxyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_proxy_test_never_uses_direct_network(self) -> None:
        runtime = AccountRuntimeManager(object())  # type: ignore[arg-type]
        with patch.object(runtime, "_probe_proxy") as probe:
            result = await runtime.test_proxy(ProxyConfigPayload(enabled=False))

        self.assertFalse(result.ok)
        self.assertIn("已停用", result.message)
        probe.assert_not_called()

    async def test_authenticated_probe_uses_real_encoded_credentials_but_masks_response(self) -> None:
        runtime = AccountRuntimeManager(object())  # type: ignore[arg-type]
        proxy = ProxyConfigPayload(
            enabled=True,
            scheme="socks5h",
            host="127.0.0.1",
            port=1080,
            username="user@name",
            password="p:a/ss",
        )
        with (
            patch.object(
                runtime,
                "_probe_proxy",
                return_value=(200, "8.8.8.8", None, []),
            ) as probe,
            patch(
                "apps.api.xianyu_admin_api.runtime.lookup_proxy_ip",
                return_value=ProxyIPLocation(
                    country="美国", region="加利福尼亚", city="山景城", isp="Google"
                ),
            ),
        ):
            result = await runtime.test_proxy(proxy)

        probe.assert_called_once_with(
            "socks5h://user%40name:p%3Aa%2Fss@127.0.0.1:1080"
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.proxy_url, "socks5h://user%40name:******@127.0.0.1:1080")
        self.assertNotIn("p:a/ss", result.proxy_url or "")
        self.assertEqual(result.exit_ip, "8.8.8.8")
        self.assertEqual(result.exit_ipv4, "8.8.8.8")
        self.assertEqual(result.platform_status_code, 200)

    async def test_platform_success_is_not_failed_when_all_ip_probes_fail(self) -> None:
        runtime = AccountRuntimeManager(object())  # type: ignore[arg-type]
        proxy = ProxyConfigPayload(
            enabled=True,
            scheme="socks5h",
            host="127.0.0.1",
            port=1080,
        )
        with patch.object(
            runtime,
            "_probe_proxy",
            return_value=(200, None, None, ["probe-1", "probe-2"]),
        ):
            result = await runtime.test_proxy(proxy)

        self.assertTrue(result.ok)
        self.assertEqual(result.platform_status_code, 200)
        self.assertIsNone(result.exit_ip)
        self.assertIn("出口 IP 获取失败", result.message)

    def test_required_bound_proxy_cannot_fall_back_when_disabled(self) -> None:
        with self.assertRaisesRegex(ValueError, "bound proxy is disabled"):
            build_socks_proxy_url(ProxyConfig(enabled=False, required=True))


class ProxyAssignmentMigrationTests(unittest.TestCase):
    @staticmethod
    def make_legacy_engine():
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE xianyu_accounts ("
                    "account_id VARCHAR(64) PRIMARY KEY, "
                    "account_name VARCHAR(80) NOT NULL, "
                    "proxy_id VARCHAR(64), "
                    "created_at DATETIME NOT NULL)"
                )
            )
        return engine

    def test_unique_index_is_added_to_existing_database(self) -> None:
        engine = self.make_legacy_engine()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO xianyu_accounts "
                    "(account_id, account_name, proxy_id, created_at) "
                    "VALUES ('account-1', 'seller-a', 'proxy-1', '2026-01-01')"
                )
            )

        _ensure_proxy_assignment_index(engine)

        target = next(
            index
            for index in inspect(engine).get_indexes("xianyu_accounts")
            if index["name"] == "uq_xianyu_accounts_proxy_id"
        )
        self.assertTrue(target["unique"])
        self.assertEqual(target["column_names"], ["proxy_id"])
        engine.dispose()

    def test_duplicate_legacy_assignments_abort_without_changing_data(self) -> None:
        engine = self.make_legacy_engine()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO xianyu_accounts "
                    "(account_id, account_name, proxy_id, created_at) VALUES "
                    "('account-1', 'seller-a', 'proxy-1', '2026-01-01'), "
                    "('account-2', 'seller-b', 'proxy-1', '2026-01-02')"
                )
            )

        with self.assertRaisesRegex(RuntimeError, "seller-a.*seller-b"):
            _ensure_proxy_assignment_index(engine)

        with engine.connect() as connection:
            count = connection.execute(
                text("SELECT COUNT(*) FROM xianyu_accounts WHERE proxy_id = 'proxy-1'")
            ).scalar_one()
        self.assertEqual(count, 2)
        self.assertNotIn(
            "uq_xianyu_accounts_proxy_id",
            {index["name"] for index in inspect(engine).get_indexes("xianyu_accounts")},
        )
        engine.dispose()


class ProxyPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        self.factory = factory
        self.store = AccountStore(session_factory=factory, initialize=False)

    async def test_assigned_proxy_cannot_be_disabled(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(
                name="node-1",
                enabled=True,
                scheme="socks5h",
                host="127.0.0.1",
                port=1080,
            )
        )
        await self.store.create_account(
            AccountCreatePayload(account_name="seller", proxy_id=proxy.proxy_id)
        )

        with self.assertRaisesRegex(ValueError, "cannot be disabled"):
            await self.store.update_proxy(
                proxy.proxy_id, ProxyUpdatePayload(enabled=False)
            )

    async def test_disabled_proxy_cannot_be_assigned(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(
                name="node-2",
                enabled=False,
                scheme="socks5h",
                host="127.0.0.1",
                port=1080,
            )
        )

        with self.assertRaisesRegex(ValueError, "proxy is disabled"):
            await self.store.create_account(
                AccountCreatePayload(account_name="seller", proxy_id=proxy.proxy_id)
            )

    async def test_proxy_cannot_be_assigned_to_two_accounts(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="exclusive", host="127.0.0.1", port=1080)
        )
        await self.store.create_account(
            AccountCreatePayload(account_name="seller-a", proxy_id=proxy.proxy_id)
        )

        with self.assertRaisesRegex(
            ProxyAssignmentConflict,
            "已绑定账户.*seller-a",
        ):
            await self.store.create_account(
                AccountCreatePayload(account_name="seller-b", proxy_id=proxy.proxy_id)
            )

    async def test_failed_proxy_switch_preserves_existing_binding(self) -> None:
        first_proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="first", host="127.0.0.1", port=1081)
        )
        occupied_proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="occupied", host="127.0.0.1", port=1082)
        )
        first_account = await self.store.create_account(
            AccountCreatePayload(account_name="seller-a", proxy_id=first_proxy.proxy_id)
        )
        await self.store.create_account(
            AccountCreatePayload(account_name="seller-b", proxy_id=occupied_proxy.proxy_id)
        )

        with self.assertRaises(ProxyAssignmentConflict):
            await self.store.update_account(
                first_account.account_id,
                AccountUpdatePayload(proxy_id=occupied_proxy.proxy_id),
            )

        unchanged = await self.store.get_account(first_account.account_id)
        self.assertIsNotNone(unchanged)
        self.assertEqual(unchanged.proxy_id, first_proxy.proxy_id)  # type: ignore[union-attr]

    async def test_same_account_can_keep_its_proxy(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="retained", host="127.0.0.1", port=1083)
        )
        account = await self.store.create_account(
            AccountCreatePayload(account_name="seller", proxy_id=proxy.proxy_id)
        )

        updated = await self.store.update_account(
            account.account_id,
            AccountUpdatePayload(proxy_id=proxy.proxy_id),
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.proxy_id, proxy.proxy_id)  # type: ignore[union-attr]

    async def test_unbinding_releases_proxy(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="released", host="127.0.0.1", port=1084)
        )
        first = await self.store.create_account(
            AccountCreatePayload(account_name="seller-a", proxy_id=proxy.proxy_id)
        )
        await self.store.update_account(
            first.account_id,
            AccountUpdatePayload(proxy_id=None),
        )

        second = await self.store.create_account(
            AccountCreatePayload(account_name="seller-b", proxy_id=proxy.proxy_id)
        )

        self.assertEqual(second.proxy_id, proxy.proxy_id)

    async def test_unbinding_clears_legacy_proxy_residue_for_direct_mode(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="legacy-residue", host="127.0.0.1", port=1089)
        )
        account = await self.store.create_account(
            AccountCreatePayload(account_name="seller", proxy_id=proxy.proxy_id)
        )
        with self.factory() as session:
            row = session.get(AccountORM, account.account_id)
            assert row is not None
            row.proxy_enabled = True
            row.proxy_host = "legacy.invalid"
            row.proxy_port = 9999
            session.commit()

        await self.store.update_account(
            account.account_id,
            AccountUpdatePayload(proxy_id=None),
        )

        updated = await self.store.get_account(account.account_id)
        assert updated is not None
        self.assertIsNone(updated.proxy_id)
        self.assertFalse(updated.proxy.enabled)
        self.assertIsNone(updated.proxy.host)
        self.assertIsNone(updated.proxy.port)
        self.assertEqual(updated.to_payload().network_mode, "direct")

    async def test_disabled_account_still_owns_proxy(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="disabled-owner", host="127.0.0.1", port=1085)
        )
        await self.store.create_account(
            AccountCreatePayload(
                account_name="disabled-seller",
                enabled=False,
                proxy_id=proxy.proxy_id,
            )
        )

        with self.assertRaises(ProxyAssignmentConflict):
            await self.store.create_account(
                AccountCreatePayload(account_name="other", proxy_id=proxy.proxy_id)
            )

    async def test_database_unique_index_is_final_assignment_guard(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="db-guard", host="127.0.0.1", port=1086)
        )
        await self.store.create_account(
            AccountCreatePayload(account_name="seller-a", proxy_id=proxy.proxy_id)
        )

        with self.factory() as session:
            session.add(
                AccountORM(
                    account_id="bypass-store",
                    account_name="seller-b",
                    platform="xianyu",
                    cookie="",
                    enabled=True,
                    proxy_id=proxy.proxy_id,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    async def test_qr_cookie_and_proxy_update_roll_back_together_on_conflict(self) -> None:
        first_proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="qr-first", host="127.0.0.1", port=1087)
        )
        occupied_proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="qr-occupied", host="127.0.0.1", port=1088)
        )
        first = await self.store.create_account(
            AccountCreatePayload(
                account_name="seller-a",
                cookie="old-cookie",
                proxy_id=first_proxy.proxy_id,
            )
        )
        await self.store.create_account(
            AccountCreatePayload(account_name="seller-b", proxy_id=occupied_proxy.proxy_id)
        )

        with self.assertRaises(ProxyAssignmentConflict):
            await self.store.compare_and_set_account_cookie(
                first.account_id,
                "old-cookie",
                "new-cookie",
                source="qr_login",
                proxy_id=occupied_proxy.proxy_id,
            )

        unchanged = await self.store.get_account(first.account_id)
        self.assertIsNotNone(unchanged)
        self.assertEqual(unchanged.cookie, "old-cookie")  # type: ignore[union-attr]
        self.assertEqual(unchanged.proxy_id, first_proxy.proxy_id)  # type: ignore[union-attr]

    async def test_successful_probe_persists_egress_metadata(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(
                name="node-3",
                scheme="socks5h",
                host="127.0.0.1",
                port=1080,
            )
        )
        updated = await self.store.record_proxy_test(
            proxy.proxy_id,
            ok=True,
            message="ok",
            latency_ms=123,
            exit_ip="8.8.8.8",
            exit_ipv4="8.8.8.8",
            exit_ipv6="2001:4860:4860::8888",
            exit_country="美国",
            exit_region="加利福尼亚",
            exit_city="山景城",
            exit_isp="Google",
            exit_ipv6_country="United States",
            exit_ipv6_continent="North America",
            platform_status=200,
        )

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.exit_ip, "8.8.8.8")
        self.assertEqual(updated.exit_ipv4, "8.8.8.8")
        self.assertEqual(updated.exit_ipv6, "2001:4860:4860::8888")
        self.assertEqual(updated.exit_city, "山景城")
        self.assertEqual(updated.last_platform_status, 200)
        self.assertIsNotNone(updated.exit_checked_at)

    async def test_non_connection_edit_preserves_probe_result(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="rename-source", host="127.0.0.1", port=1090)
        )
        tested = await self.store.record_proxy_test(
            proxy.proxy_id,
            ok=True,
            message="ok",
            latency_ms=88,
            exit_ip="8.8.4.4",
            exit_ipv4="8.8.4.4",
            platform_status=200,
        )
        assert tested is not None

        updated = await self.store.update_proxy(
            proxy.proxy_id,
            ProxyUpdatePayload(name="renamed", enabled=False),
        )

        assert updated is not None
        self.assertTrue(updated.last_test_ok)
        self.assertEqual(updated.last_test_latency_ms, 88)
        self.assertEqual(updated.exit_ipv4, "8.8.4.4")
        self.assertEqual(updated.last_test_at, tested.last_test_at)
        self.assertEqual(updated.exit_checked_at, tested.exit_checked_at)

    async def test_identical_connection_fields_preserve_probe_result(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(
                name="same-config",
                scheme="socks5h",
                host="127.0.0.1",
                port=1091,
                username="user",
            )
        )
        tested = await self.store.record_proxy_test(
            proxy.proxy_id,
            ok=True,
            message="ok",
            latency_ms=66,
            exit_ip="1.1.1.1",
            exit_ipv4="1.1.1.1",
            platform_status=200,
        )
        assert tested is not None

        updated = await self.store.update_proxy(
            proxy.proxy_id,
            ProxyUpdatePayload(
                scheme="socks5h",
                host="127.0.0.1",
                port=1091,
                username="user",
            ),
        )

        assert updated is not None
        self.assertTrue(updated.last_test_ok)
        self.assertEqual(updated.last_test_at, tested.last_test_at)
        self.assertEqual(updated.exit_ipv4, "1.1.1.1")

    async def test_connection_edit_invalidates_current_result_but_keeps_last_exit(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="changed-config", host="127.0.0.1", port=1092)
        )
        tested = await self.store.record_proxy_test(
            proxy.proxy_id,
            ok=True,
            message="ok",
            latency_ms=77,
            exit_ip="9.9.9.9",
            exit_ipv4="9.9.9.9",
            platform_status=200,
        )
        assert tested is not None

        updated = await self.store.update_proxy(
            proxy.proxy_id,
            ProxyUpdatePayload(host="127.0.0.2"),
        )

        assert updated is not None
        self.assertIsNone(updated.last_test_ok)
        self.assertIsNone(updated.last_test_at)
        self.assertIsNone(updated.last_platform_status)
        self.assertEqual(updated.exit_ipv4, "9.9.9.9")
        self.assertEqual(updated.exit_checked_at, tested.exit_checked_at)

    async def test_probe_result_is_not_saved_after_connection_changes(self) -> None:
        proxy = await self.store.create_proxy(
            ProxyCreatePayload(name="probe-race", host="127.0.0.1", port=1093)
        )
        tested_connection = proxy.connection_signature()
        await self.store.update_proxy(
            proxy.proxy_id,
            ProxyUpdatePayload(port=2093),
        )

        current = await self.store.record_proxy_test(
            proxy.proxy_id,
            ok=True,
            message="stale result",
            latency_ms=55,
            exit_ip="4.4.4.4",
            exit_ipv4="4.4.4.4",
            platform_status=200,
            expected_connection=tested_connection,
        )

        assert current is not None
        self.assertEqual(current.port, 2093)
        self.assertIsNone(current.last_test_ok)
        self.assertIsNone(current.exit_ipv4)


if __name__ == "__main__":
    unittest.main()
