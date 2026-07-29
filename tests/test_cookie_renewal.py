import os
import unittest
from unittest.mock import AsyncMock
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.cookie_renewal import (
    HAS_LOGIN_URL,
    KEEPALIVE_URL,
    MTOP_NAV_URL,
    SET_LOGIN_SETTINGS_URL,
    SILENT_HAS_LOGIN_URL,
    CookieRenewalError,
    CookieRenewalResult,
    CookieRenewalService,
    parse_cookie_header,
)
from apps.api.xianyu_admin_api.cookie_renewal_manager import (
    CookieRenewalCooldownError,
    CookieRenewalManager,
)
from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    AccountUpdatePayload,
    ProxyConfigPayload,
)
from apps.api.xianyu_admin_api.store import AccountStore


def _response(success: bool = True) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = (
        b'{"content":{"success":true}}'
        if success
        else b'{"content":{"success":false}}'
    )
    response.encoding = "utf-8"
    return response


class _RenewalSession(requests.Session):
    def __init__(self, *, change_account: bool = False) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.change_account = change_account

    def post(self, url: str, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(url)
        response = _response()
        if url == HAS_LOGIN_URL:
            response.cookies.set("sgcookie", "renewed", domain="passport.goofish.com", path="/")
        elif url == SILENT_HAS_LOGIN_URL and self.change_account:
            response.cookies.set("unb", "other-user", domain="passport.goofish.com", path="/")
        elif url == SET_LOGIN_SETTINGS_URL:
            response.cookies.set("havana_lgc2_77", "long-token", domain=".goofish.com", path="/")
        elif url == MTOP_NAV_URL:
            response.cookies.set("_m_h5_tk", "new-mtop-token", domain=".goofish.com", path="/")
            response._content = b'{"ret":["SUCCESS::call succeeds"],"data":{}}'
        return response


class _FailingRenewalSession(requests.Session):
    def post(self, _url: str, **_kwargs):  # type: ignore[no-untyped-def]
        raise requests.exceptions.SSLError("tls failed")


class _KeepaliveSession(requests.Session):
    def __init__(self, *, expired: bool = False) -> None:
        super().__init__()
        self.expired = expired

    def post(self, url: str, **_kwargs):  # type: ignore[no-untyped-def]
        self.assert_keepalive_url = url
        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = (
            b'{"ret":["FAIL_SYS_SESSION_EXPIRED::Session expired"]}'
            if self.expired
            else b'{"ret":["SUCCESS::call succeeds"],"data":{"userId":"seller-1"}}'
        )
        response.cookies.set("_m_h5_tk", "kept-token", domain=".goofish.com", path="/")
        return response


class CookieRenewalServiceTests(unittest.TestCase):
    def test_cookie_parser_preserves_values_containing_equals(self) -> None:
        self.assertEqual(
            parse_cookie_header("unb=123; token=a=b=c; malformed"),
            {"unb": "123", "token": "a=b=c"},
        )

    def test_http_chain_renews_and_validates_web_cookie(self) -> None:
        http = _RenewalSession()
        service = CookieRenewalService(session_factory=lambda: http)

        result = service.renew(
            "unb=seller-1; _m_h5_tk=old-token; cookie2=session; sgcookie=old",
            ProxyConfigPayload(
                enabled=True,
                scheme="socks5h",
                host="127.0.0.1",
                port=1080,
                username="user@name",
                password="p:a",
            ),
        )

        self.assertEqual(
            http.calls,
            [HAS_LOGIN_URL, SILENT_HAS_LOGIN_URL, SET_LOGIN_SETTINGS_URL, MTOP_NAV_URL],
        )
        self.assertEqual(http.proxies["https"], "socks5h://user%40name:p%3Aa@127.0.0.1:1080")
        self.assertIn("_m_h5_tk=new-mtop-token", result.new_cookie)
        self.assertIn("havana_lgc2_77", result.updated_cookie_names)
        self.assertIn("Web Cookie 交叉验证", result.message)
        self.assertNotIn("new-mtop-token", result.message)

    def test_changed_account_is_rejected(self) -> None:
        service = CookieRenewalService(
            session_factory=lambda: _RenewalSession(change_account=True)
        )
        with self.assertRaisesRegex(CookieRenewalError, "账户标识不一致"):
            service.renew("unb=seller-1; _m_h5_tk=old-token")

    def test_missing_unb_requires_login(self) -> None:
        with self.assertRaisesRegex(CookieRenewalError, "缺少 unb"):
            CookieRenewalService().renew("_m_h5_tk=token")

    def test_network_errors_are_classified_without_internal_error(self) -> None:
        service = CookieRenewalService(session_factory=_FailingRenewalSession)

        with self.assertRaisesRegex(CookieRenewalError, "网络请求失败"):
            service.renew("unb=seller-1; _m_h5_tk=old-token")

    def test_lightweight_keepalive_validates_and_merges_cookie(self) -> None:
        http = _KeepaliveSession()
        result = CookieRenewalService(session_factory=lambda: http).keep_alive(
            "unb=seller-1; _m_h5_tk=old-token"
        )

        self.assertEqual(http.assert_keepalive_url, KEEPALIVE_URL)
        self.assertIn("_m_h5_tk=kept-token", result.new_cookie)
        self.assertEqual(result.message, "Cookie 轻量保活验证成功")

    def test_lightweight_keepalive_classifies_session_expiry(self) -> None:
        service = CookieRenewalService(session_factory=lambda: _KeepaliveSession(expired=True))

        with self.assertRaises(CookieRenewalError) as raised:
            service.keep_alive("unb=seller-1; _m_h5_tk=old-token")
        self.assertEqual(raised.exception.kind, "suspected_expired")


class _RuntimeRecorder:
    def __init__(self) -> None:
        self.replacements: list[tuple[str, str, bool]] = []

    async def replace_cookie(self, account_id: str, cookie: str, *, mark_online: bool = False) -> bool:
        self.replacements.append((account_id, cookie, mark_online))
        return True


class _SuccessfulService:
    def renew(self, _cookie: str, _proxy: ProxyConfigPayload) -> CookieRenewalResult:
        return CookieRenewalResult(
            new_cookie="unb=seller-1; _m_h5_tk=new-token; havana_lgc2_77=long",
            updated_cookie_names=["_m_h5_tk", "havana_lgc2_77"],
        )


class _AuthExpiredService:
    def renew(self, _cookie: str, _proxy: ProxyConfigPayload) -> CookieRenewalResult:
        raise CookieRenewalError("登录状态已失效", kind="auth_expired")


class _KeepaliveSequenceService:
    def __init__(self, outcomes: list[CookieRenewalResult | CookieRenewalError]) -> None:
        self.outcomes = list(outcomes)
        self.keepalive_calls = 0
        self.renew_calls = 0

    def keep_alive(
        self,
        _cookie: str,
        _proxy: ProxyConfigPayload,
    ) -> CookieRenewalResult:
        self.keepalive_calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, CookieRenewalError):
            raise outcome
        return outcome

    def renew(
        self,
        _cookie: str,
        _proxy: ProxyConfigPayload,
    ) -> CookieRenewalResult:
        self.renew_calls += 1
        return CookieRenewalResult(
            new_cookie="unb=seller-1; _m_h5_tk=confirmed-web-token",
            updated_cookie_names=["_m_h5_tk"],
            message="Passport/MTOP Web 交叉验证成功",
        )


class _UnavailableRuntime:
    async def replace_cookie(
        self, _account_id: str, _cookie: str, *, mark_online: bool = False
    ) -> bool:
        return False

    async def start(self, _account, *, force_restart: bool = False):  # type: ignore[no-untyped-def]
        return SimpleNamespace(runtime=SimpleNamespace(state="reconnecting"))

    def connection_health(self, _account_id: str) -> dict[str, bool]:
        return {"running": True, "online": False}


class CookieRenewalPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        self.store = AccountStore(session_factory=factory, initialize=False)
        self.account = await self.store.create_account(
            AccountCreatePayload(cookie="unb=seller-1; _m_h5_tk=old-token",
                enabled=True,
            )
        )

    async def test_compare_and_set_does_not_overwrite_manual_cookie(self) -> None:
        await self.store.begin_cookie_renewal(self.account.account_id, "manual")
        await self.store.update_account(
            self.account.account_id,
            AccountUpdatePayload(cookie="unb=seller-1; _m_h5_tk=manual-token"),
        )

        status, persisted = await self.store.complete_cookie_renewal(
            self.account.account_id,
            expected_cookie=self.account.cookie,
            new_cookie="unb=seller-1; _m_h5_tk=renewed-token",
            updated_cookie_names=["_m_h5_tk"],
            message="done",
            next_attempt_at=datetime.now(UTC) + timedelta(days=1),
        )

        latest = await self.store.get_account(self.account.account_id)
        self.assertFalse(persisted)
        self.assertEqual(status.state, "conflict")
        self.assertIn("manual-token", latest.cookie)

    async def test_manager_persists_and_updates_running_session(self) -> None:
        runtime = _RuntimeRecorder()
        manager = CookieRenewalManager(
            self.store,
            runtime,
            service=_SuccessfulService(),  # type: ignore[arg-type]
            enabled=False,
        )

        started = await manager.trigger(self.account.account_id)
        self.assertEqual(started.state, "running")
        await manager._tasks[self.account.account_id]

        status = await self.store.get_cookie_renewal_status(self.account.account_id)
        latest = await self.store.get_account(self.account.account_id)
        self.assertEqual(status.state, "succeeded")
        self.assertEqual(status.phase, "completed")
        self.assertTrue(status.runtime_applied)
        self.assertEqual(status.cookie_update_source, "manual_renewal")
        self.assertEqual(len(status.recent_attempts), 1)
        self.assertEqual(status.recent_attempts[0].state, "succeeded")
        self.assertTrue(status.recent_attempts[0].runtime_applied)
        serialized_success = status.model_dump(mode="json")["last_succeeded_at"]
        self.assertTrue(
            serialized_success.endswith("Z") or serialized_success.endswith("+00:00")
        )
        self.assertIn("new-token", latest.cookie)
        self.assertEqual(runtime.replacements, [(self.account.account_id, latest.cookie, True)])
        await manager.shutdown()

    async def test_runtime_refresh_updates_cookie_anchor_and_source(self) -> None:
        persisted = await self.store.compare_and_set_account_cookie(
            self.account.account_id,
            self.account.cookie,
            "unb=seller-1; _m_h5_tk=runtime-token",
        )
        latest = await self.store.get_account(self.account.account_id)
        status = await self.store.get_cookie_renewal_status(self.account.account_id)

        self.assertTrue(persisted)
        self.assertIsNotNone(latest.cookie_updated_at)
        self.assertEqual(latest.cookie_update_source, "runtime_refresh")
        self.assertEqual(status.cookie_update_source, "runtime_refresh")
        self.assertEqual(status.cookie_updated_at.utcoffset(), timedelta(0))

    async def test_successful_manual_renewal_has_server_side_cooldown(self) -> None:
        runtime = _RuntimeRecorder()
        manager = CookieRenewalManager(
            self.store,
            runtime,
            service=_SuccessfulService(),  # type: ignore[arg-type]
            enabled=False,
            manual_cooldown_seconds=3600,
        )

        await manager.trigger(self.account.account_id)
        await manager._tasks[self.account.account_id]
        await self.store.begin_cookie_renewal(self.account.account_id, "scheduled")
        with self.assertRaises(CookieRenewalCooldownError) as raised:
            await manager.trigger(self.account.account_id)

        status = await self.store.get_cookie_renewal_status(self.account.account_id)
        self.assertGreater(raised.exception.remaining_seconds, 3500)
        self.assertEqual(status.state, "running")
        self.assertEqual(len(status.recent_attempts), 2)
        self.assertEqual(len(runtime.replacements), 1)
        await manager.shutdown()

    async def test_single_full_web_failure_stays_suspected_until_rechecked(self) -> None:
        manager = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=_AuthExpiredService(),  # type: ignore[arg-type]
            enabled=False,
        )

        await manager.trigger(self.account.account_id)
        await manager._tasks[self.account.account_id]
        status = await self.store.get_cookie_renewal_status(self.account.account_id)

        self.assertEqual(status.state, "failed")
        self.assertEqual(status.last_error_kind, "suspected_expired")
        self.assertIsNotNone(status.next_attempt_at)
        self.assertFalse(status.manual_action_required)

        await manager.trigger(self.account.account_id)
        await manager._tasks[self.account.account_id]
        status = await self.store.get_cookie_renewal_status(self.account.account_id)

        self.assertEqual(status.state, "failed")
        self.assertEqual(status.last_error_kind, "auth_expired")
        self.assertEqual(status.recent_attempts[0].error_kind, "auth_expired")
        self.assertIn("重新扫码登录", status.recent_attempts[0].message)
        self.assertIsNone(status.next_attempt_at)
        self.assertTrue(status.manual_action_required)
        await manager.shutdown()

    async def test_authoritative_failure_after_recent_success_stops_schedule(self) -> None:
        successful = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=_SuccessfulService(),  # type: ignore[arg-type]
            enabled=False,
            interval_hours=24,
            manual_cooldown_seconds=0,
        )
        await successful.trigger(self.account.account_id)
        await successful._tasks[self.account.account_id]
        await successful.shutdown()

        failing = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=_AuthExpiredService(),  # type: ignore[arg-type]
            enabled=False,
            interval_hours=24,
            manual_cooldown_seconds=0,
        )
        await failing.trigger(self.account.account_id, trigger="auth_recovery")
        await failing._tasks[self.account.account_id]
        status = await self.store.get_cookie_renewal_status(self.account.account_id)

        self.assertEqual(status.state, "failed")
        self.assertIsNone(status.next_attempt_at)
        self.assertTrue(status.manual_action_required)
        await failing.shutdown()

    async def test_database_success_is_not_final_when_runtime_stays_offline(self) -> None:
        manager = CookieRenewalManager(
            self.store,
            _UnavailableRuntime(),
            service=_SuccessfulService(),  # type: ignore[arg-type]
            enabled=False,
        )

        await manager.trigger(self.account.account_id)
        await manager._tasks[self.account.account_id]
        status = await self.store.get_cookie_renewal_status(self.account.account_id)
        latest = await self.store.get_account(self.account.account_id)

        self.assertIn("new-token", latest.cookie)
        self.assertEqual(status.state, "succeeded")
        self.assertEqual(status.phase, "completed")
        self.assertIsNone(status.last_error_kind)
        self.assertFalse(status.runtime_applied)
        self.assertEqual(status.recent_attempts[0].phase, "completed")
        await manager.shutdown()

    async def test_business_cookie_merge_preserves_independent_schedule(self) -> None:
        next_attempt = datetime.now(UTC) + timedelta(minutes=45)
        await self.store.reschedule_cookie_renewal(self.account.account_id, next_attempt)
        persisted = await self.store.compare_and_set_account_cookie(
            self.account.account_id,
            self.account.cookie,
            "unb=seller-1; _m_h5_tk=product-token",
            source="product_management",
        )

        status = await self.store.get_cookie_renewal_status(self.account.account_id)
        self.assertTrue(persisted)
        self.assertEqual(status.next_attempt_at, next_attempt)

    async def test_qr_login_clears_manual_state_and_resumes_schedule(self) -> None:
        manager = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=_AuthExpiredService(),  # type: ignore[arg-type]
            enabled=False,
        )
        await manager.trigger(self.account.account_id, trigger="auth_recovery")
        await manager._tasks[self.account.account_id]

        status = await manager.mark_login_success(self.account.account_id)
        self.assertEqual(status.state, "idle")
        self.assertFalse(status.manual_action_required)
        self.assertIsNotNone(status.last_verified_at)
        self.assertIsNotNone(status.next_attempt_at)
        await manager.shutdown()

    async def test_auth_failure_reports_are_deduplicated_per_account(self) -> None:
        manager = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=_AuthExpiredService(),  # type: ignore[arg-type]
            enabled=False,
        )
        await manager.handle_auth_expired(
            self.account.account_id,
            source="conversation_headinfo",
            message="Session过期",
        )
        await manager.handle_auth_expired(
            self.account.account_id,
            source="conversation_blacklist_query",
            message="Session过期",
        )
        await manager._tasks[self.account.account_id]

        status = await self.store.get_cookie_renewal_status(self.account.account_id)
        self.assertEqual(len(status.recent_attempts), 1)
        self.assertEqual(status.last_error_source, "conversation_headinfo")
        await manager.shutdown()

    async def test_scheduler_clamps_legacy_daily_schedule_to_hourly(self) -> None:
        manager = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=_SuccessfulService(),  # type: ignore[arg-type]
            enabled=False,
            interval_hours=1,
            manual_cooldown_seconds=0,
        )
        await manager.trigger(self.account.account_id)
        await manager._tasks[self.account.account_id]
        await self.store.reschedule_cookie_renewal(
            self.account.account_id,
            datetime.now(UTC) + timedelta(hours=24),
        )

        await manager._scan_due_accounts()
        status = await self.store.get_cookie_renewal_status(self.account.account_id)
        self.assertLess(status.next_attempt_at, datetime.now(UTC) + timedelta(hours=2))
        await manager.shutdown()

    async def test_scheduler_checks_keepalive_while_regular_renewal_is_deferred(self) -> None:
        manager = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=_SuccessfulService(),  # type: ignore[arg-type]
            enabled=False,
            interval_hours=1,
            manual_cooldown_seconds=0,
        )
        await manager.trigger(self.account.account_id)
        await manager._tasks[self.account.account_id]
        manager._start_keepalive_if_due = AsyncMock()  # type: ignore[method-assign]

        await manager._scan_due_accounts()

        manager._start_keepalive_if_due.assert_awaited_once()  # type: ignore[attr-defined]
        await manager.shutdown()

    async def test_keepalive_rechecks_once_before_accepting_recovery(self) -> None:
        service = _KeepaliveSequenceService(
            [
                CookieRenewalError("首次疑似过期", kind="suspected_expired"),
                CookieRenewalResult(
                    new_cookie="unb=seller-1; _m_h5_tk=recovered-token",
                    message="Cookie 延迟复核成功",
                ),
            ]
        )
        manager = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=service,  # type: ignore[arg-type]
            enabled=False,
            keepalive_recheck_min_seconds=0,
            keepalive_recheck_max_seconds=0,
        )

        await manager._run_keepalive(self.account.account_id)
        status = await self.store.get_cookie_renewal_status(self.account.account_id)

        self.assertEqual(service.keepalive_calls, 2)
        self.assertEqual(service.renew_calls, 0)
        self.assertEqual(status.last_verified_source, "cookie_keepalive")
        self.assertFalse(status.manual_action_required)
        await manager.shutdown()

    async def test_two_keepalive_failures_start_web_only_confirmation(self) -> None:
        service = _KeepaliveSequenceService(
            [
                CookieRenewalError("首次疑似过期", kind="suspected_expired"),
                CookieRenewalError("再次疑似过期", kind="suspected_expired"),
            ]
        )
        manager = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=service,  # type: ignore[arg-type]
            enabled=False,
            keepalive_recheck_min_seconds=0,
            keepalive_recheck_max_seconds=0,
        )

        await manager._run_keepalive(self.account.account_id)
        await manager._tasks[self.account.account_id]
        status = await self.store.get_cookie_renewal_status(self.account.account_id)

        self.assertEqual(service.keepalive_calls, 2)
        self.assertEqual(service.renew_calls, 1)
        self.assertEqual(status.state, "succeeded")
        self.assertFalse(status.manual_action_required)
        await manager.shutdown()

    async def test_im_runtime_auth_state_does_not_probe_web_cookie(self) -> None:
        service = _KeepaliveSequenceService([])
        manager = CookieRenewalManager(
            self.store,
            _RuntimeRecorder(),
            service=service,  # type: ignore[arg-type]
            enabled=False,
        )

        status = await manager.handle_auth_expired(
            self.account.account_id,
            source="im_runtime",
            message="IM access token 已过期",
        )

        self.assertIsNotNone(status)
        self.assertNotIn(self.account.account_id, manager._tasks)
        self.assertEqual(service.renew_calls, 0)
        await manager.shutdown()


if __name__ == "__main__":
    unittest.main()
