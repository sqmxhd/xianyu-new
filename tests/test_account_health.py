import unittest
from datetime import UTC, datetime, timedelta

from apps.api.xianyu_admin_api.store import AccountRecord, RuntimeStatusRecord


class AccountHealthTests(unittest.TestCase):
    def test_missing_cookie_and_offline_im_are_independent(self) -> None:
        payload = AccountRecord(
            account_id="missing-cookie",
            platform_display_name="missing-cookie",
            cookie="",
            runtime=RuntimeStatusRecord(account_id="missing-cookie", state="auth_expired"),
        ).to_payload()

        self.assertEqual(payload.cookie_health.state, "missing")
        self.assertFalse(payload.im_health.available)
        self.assertEqual(payload.im_health.state, "auth_expired")

    def test_online_im_does_not_claim_http_cookie_was_verified(self) -> None:
        checked_at = datetime.now(UTC)
        payload = AccountRecord(
            account_id="online",
            platform_display_name="online",
            cookie="unb=seller-1",
            runtime=RuntimeStatusRecord(
                account_id="online",
                state="online",
                last_online_at=checked_at,
            ),
        ).to_payload()

        self.assertEqual(payload.cookie_health.state, "unchecked")
        self.assertIsNone(payload.cookie_health.checked_at)
        self.assertTrue(payload.im_health.available)

    def test_network_failure_does_not_invalidate_last_known_cookie(self) -> None:
        checked_at = datetime.now(UTC) - timedelta(minutes=2)
        payload = AccountRecord(
            account_id="proxy-failed",
            platform_display_name="proxy-failed",
            cookie="unb=seller-1",
            cookie_renewal_last_verified_at=checked_at,
            cookie_renewal_last_verified_source="scheduled_renewal",
            runtime=RuntimeStatusRecord(
                account_id="proxy-failed",
                state="proxy_failed",
                last_online_at=checked_at,
                message="proxy timeout",
            ),
        ).to_payload()

        self.assertEqual(payload.cookie_health.state, "valid")
        self.assertEqual(payload.cookie_health.checked_at, checked_at)
        self.assertFalse(payload.im_health.available)
        self.assertEqual(payload.im_health.state, "proxy_failed")

    def test_authoritative_auth_failure_invalidates_cookie(self) -> None:
        failed_at = datetime.now(UTC)
        payload = AccountRecord(
            account_id="expired",
            platform_display_name="expired",
            cookie="unb=seller-1",
            cookie_renewal_state="failed",
            cookie_renewal_error_kind="auth_expired",
            cookie_renewal_last_failed_at=failed_at,
            runtime=RuntimeStatusRecord(account_id="expired", state="offline"),
        ).to_payload()

        self.assertEqual(payload.cookie_health.state, "invalid")
        self.assertEqual(payload.cookie_health.checked_at, failed_at)
        self.assertTrue(payload.cookie_health.manual_action_required)
        self.assertFalse(payload.im_health.available)


if __name__ == "__main__":
    unittest.main()
