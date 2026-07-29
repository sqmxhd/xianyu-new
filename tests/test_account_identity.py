import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.orm import AccountBrowserIdentityORM, Base
from apps.api.xianyu_admin_api.schemas import (
    AccountBrowserIdentityPayload,
    BrowserFingerprintSnapshotPayload,
    AccountCreatePayload,
    AccountUpdatePayload,
)
from apps.api.xianyu_admin_api.store import AccountStore


class AccountBrowserIdentityPersistenceTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_identity_is_account_scoped_and_revision_changes_only_with_config(self) -> None:
        identity = AccountBrowserIdentityPayload(
            browser_engine="fingerprint_chromium",
            fingerprint_seed=1_234_567,
            browser_version="148.0.7778.215",
            timezone="Asia/Shanghai",
        )
        account = await self.store.create_account(
            AccountCreatePayload(browser_identity=identity)
        )

        self.assertEqual(account.browser_identity.fingerprint_seed, 1_234_567)
        self.assertEqual(account.browser_identity.config_revision, 1)
        self.assertIn("Chrome/148.0.7778.215", account.client_identity.user_agent)

        unchanged = await self.store.update_account(
            account.account_id,
            AccountUpdatePayload(browser_identity=identity),
        )
        self.assertIsNotNone(unchanged)
        self.assertEqual(unchanged.browser_identity.config_revision, 1)

        changed = await self.store.update_account(
            account.account_id,
            AccountUpdatePayload(
                browser_identity=identity.model_copy(
                    update={"platform_version": "11.0.0", "spoof_audio": False}
                )
            ),
        )
        self.assertIsNotNone(changed)
        self.assertEqual(changed.browser_identity.config_revision, 2)
        self.assertFalse(changed.browser_identity.spoof_audio)
        self.assertFalse(changed.client_identity.spoof_audio)
        self.assertEqual(changed.client_identity.disabled_spoofing_modules, ("audio",))

    async def test_browser_brand_updates_protocol_identity(self) -> None:
        identity = AccountBrowserIdentityPayload(
            browser_engine="fingerprint_chromium",
            fingerprint_seed=9_876_543,
            browser_version="148.0.7778.215",
            brand="Edge",
        )
        account = await self.store.create_account(
            AccountCreatePayload(browser_identity=identity)
        )
        self.assertIn("Chrome/148.0.7778.215", account.client_identity.user_agent)
        self.assertIn("Edg/148.0.7778.215", account.client_identity.user_agent)
        self.assertIn("Microsoft Edge", account.client_identity.sec_ch_ua)
        self.assertIn("Browser(Edge/148.0.7778.215)", account.client_identity.dingtalk_user_agent)

    async def test_fingerprint_snapshot_tracks_stability_for_same_revision(self) -> None:
        account = await self.store.create_account(
            AccountCreatePayload()
        )
        snapshot = BrowserFingerprintSnapshotPayload(
            browser_engine="system_chromium",
            browser_version="136.0.0.0",
            target_platform="linux",
            observed_platform="Linux x86_64",
            user_agent="Mozilla/5.0 Chrome/136.0.0.0",
            canvas_hash="canvas-1",
            config_revision=1,
            observed_at=datetime.now(UTC),
        )
        baseline = await self.store.save_account_browser_fingerprint_snapshot(
            account.account_id,
            snapshot,
        )
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline.stability_status, "baseline")

        stable = await self.store.save_account_browser_fingerprint_snapshot(
            account.account_id,
            snapshot,
        )
        self.assertIsNotNone(stable)
        self.assertEqual(stable.stability_status, "stable")

        network_changed = await self.store.save_account_browser_fingerprint_snapshot(
            account.account_id,
            snapshot.model_copy(
                update={
                    "webrtc_candidate_types": ["srflx"],
                    "webrtc_public_candidate_detected": True,
                    "webrtc_proxy_match": False,
                    "browser_egress_ips": ["8.8.8.8"],
                    "proxy_expected_ips": ["1.1.1.1"],
                    "browser_egress_match": False,
                    "risk_status": "risk",
                    "risk_findings": ["出口变化"],
                }
            ),
        )
        self.assertIsNotNone(network_changed)
        self.assertEqual(network_changed.stability_status, "stable")
        self.assertEqual(network_changed.changed_fields, [])

        changed = await self.store.save_account_browser_fingerprint_snapshot(
            account.account_id,
            network_changed.model_copy(update={"canvas_hash": "canvas-2"}),
        )
        self.assertIsNotNone(changed)
        self.assertEqual(changed.stability_status, "changed")
        self.assertEqual(changed.changed_fields, ["canvas_hash"])
        reloaded = await self.store.get_account(account.account_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(
            reloaded.browser_identity.fingerprint_snapshot.canvas_hash,
            "canvas-2",
        )

    def test_legacy_webrtc_policy_is_normalized(self) -> None:
        identity = AccountBrowserIdentityPayload(
            webrtc_policy="disable_non_proxied_udp",  # type: ignore[arg-type]
        )
        self.assertEqual(identity.webrtc_policy, "proxy_only")

    def test_webrtc_disabled_policy_is_persistable(self) -> None:
        identity = AccountBrowserIdentityPayload(webrtc_policy="disabled")
        self.assertEqual(identity.webrtc_policy, "disabled")

    async def test_standard_browser_source_distinguishes_system_and_managed(self) -> None:
        system = await self.store.create_account(
            AccountCreatePayload()
        )
        managed = await self.store.create_account(
            AccountCreatePayload(browser_identity=AccountBrowserIdentityPayload(
                    browser_version="149.0.7827.55"
                ),
            )
        )

        self.assertEqual(system.client_identity.browser_binary_source, "system")
        self.assertEqual(managed.client_identity.browser_binary_source, "managed")
        self.assertIsNone(system.to_payload().browser_identity.browser_version)
        self.assertEqual(
            managed.to_payload().browser_identity.browser_version,
            "149.0.7827.55",
        )

    async def test_fingerprint_seed_cannot_be_shared_by_two_accounts(self) -> None:
        identity = AccountBrowserIdentityPayload(
            browser_engine="fingerprint_chromium",
            fingerprint_seed=88,
            browser_version="136.0.7103.49",
        )
        await self.store.create_account(
            AccountCreatePayload(browser_identity=identity)
        )

        with self.assertRaisesRegex(ValueError, "Seed"):
            await self.store.create_account(
                AccountCreatePayload(browser_identity=identity)
            )

    async def test_account_delete_cascades_identity_row(self) -> None:
        account = await self.store.create_account(
            AccountCreatePayload()
        )
        self.assertTrue(await self.store.delete_account(account.account_id))

        with self.factory() as session:
            identity = session.scalar(
                select(AccountBrowserIdentityORM).where(
                    AccountBrowserIdentityORM.account_id == account.account_id
                )
            )
        self.assertIsNone(identity)


if __name__ == "__main__":
    unittest.main()
