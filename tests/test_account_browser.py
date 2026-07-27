import tempfile
import time
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from integrations.xianyu_core.identity import ClientIdentity

from apps.api.xianyu_admin_api.browser_profiles import BrowserProfileStorage
from apps.api.xianyu_admin_api.cookie_renewal import (
    CookieRenewalError,
    CookieRenewalResult,
)
from apps.api.xianyu_admin_api.im_verification import (
    IMVerificationBusyError,
    IMVerificationError,
    IMVerificationManager,
    _ActiveSession,
    _VisualDesktop,
)
from apps.api.xianyu_admin_api.browser_binaries import BrowserBinaryError
from apps.api.xianyu_admin_api.qr_login import QRLoginSession
from apps.api.xianyu_admin_api.store import AccountRecord
from apps.api.xianyu_admin_api.settings import settings as app_settings
from apps.api.xianyu_admin_api.schemas import (
    AccountBrowserSessionPayload,
    BrowserFingerprintSnapshotPayload,
    ProxyConfigPayload,
)


class _FakeKeyboard:
    def __init__(self) -> None:
        self.inserted_texts: list[str] = []

    async def insert_text(self, text: str) -> None:
        self.inserted_texts.append(text)


class _FakePage:
    def __init__(self) -> None:
        self.url = "about:blank"
        self.keyboard = _FakeKeyboard()

    async def goto(self, url: str, **_: object) -> None:
        self.url = url


class _FakeContext:
    def __init__(self) -> None:
        self.pages = [_FakePage()]
        self.added_cookies: list[dict[str, object]] = []
        self.clear_count = 0
        self.closed = False
        self.init_scripts: list[str] = []

    async def add_init_script(self, *, script: str) -> None:
        self.init_scripts.append(script)

    async def cookies(self, *_: object) -> list[dict[str, str]]:
        return [
            {"name": str(cookie["name"]), "value": str(cookie["value"])}
            for cookie in self.added_cookies
        ]

    async def clear_cookies(self) -> None:
        self.clear_count += 1
        self.added_cookies = []

    async def add_cookies(self, cookies: list[dict[str, object]]) -> None:
        self.added_cookies = cookies

    async def close(self) -> None:
        self.closed = True


class _CookieCoordinator:
    def __init__(self, outcomes: dict[str, object]) -> None:
        self.outcomes = outcomes
        self.persist_calls: list[dict[str, object]] = []
        self.auth_calls: list[dict[str, object]] = []
        self.persist_results: list[bool] = []

    async def validate_cookie(self, account: AccountRecord, cookie: str) -> object:
        outcome = self.outcomes[cookie]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def persist_validated_cookie(
        self,
        account: AccountRecord,
        **kwargs: object,
    ) -> bool:
        self.persist_calls.append({"account": account, **kwargs})
        return self.persist_results.pop(0) if self.persist_results else True

    async def handle_auth_expired(self, account_id: str, **kwargs: object) -> None:
        self.auth_calls.append({"account_id": account_id, **kwargs})


class _FakeCDPSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []
        self.detached = False
        self.handlers: dict[str, object] = {}

    def on(self, event: str, handler: object) -> None:
        self.handlers[event] = handler

    async def send(self, method: str, params: object | None = None) -> dict[str, int]:
        self.calls.append((method, params))
        return {"windowId": 42} if method == "Browser.getWindowForTarget" else {}

    async def detach(self) -> None:
        self.detached = True


class AccountBrowserManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_managed_standard_chrome_never_falls_back_to_system(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        identity = ClientIdentity(
            browser_engine="system_chromium",
            browser_binary_source="managed",
            browser_version="150.0.7871.124",
        )
        with (
            patch(
                "apps.api.xianyu_admin_api.im_verification.standard_browser_binary_manager.resolve_executable",
                side_effect=BrowserBinaryError("missing"),
            ),
            patch("apps.api.xianyu_admin_api.im_verification.shutil.which") as discover,
        ):
            self.assertIsNone(manager.browser_path(identity))
        discover.assert_not_called()

    async def test_existing_account_qr_browser_injects_database_cookie(self) -> None:
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1; token=current",
        )
        session = QRLoginSession(
            account_id=account.account_id,
            account_name=account.account_name,
            proxy_id=None,
            proxy=ProxyConfigPayload(),
        )
        context = _FakeContext()
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        inject = AsyncMock()
        browser_settings = SimpleNamespace(im_verification_session_seconds=600)
        with (
            patch.object(manager, "availability_error", return_value=None),
            patch.object(manager, "_ensure_visual_desktop", AsyncMock()),
            patch.object(manager, "_start_proxy_bridge_config", AsyncMock(return_value=None)),
            patch.object(manager, "_prepare_account_browser_profile", AsyncMock()),
            patch.object(manager, "_launch_browser", AsyncMock(return_value=context)),
            patch.object(manager, "_inject_account_cookies", inject),
            patch("apps.api.xianyu_admin_api.im_verification.settings", browser_settings),
        ):
            payload = await manager.start_qr_login(session, account, "operator-1")
            self.assertEqual(payload.status, "ready")
            inject.assert_awaited_once_with(context, account)
            self.assertEqual(context.clear_count, 0)
            await manager.cancel_qr_login(session.session_id)

    async def test_browser_profile_list_maps_accounts_and_orphans(self) -> None:
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1",
        )
        store = SimpleNamespace(list_accounts=AsyncMock(return_value=[account]))
        manager = IMVerificationManager(store, SimpleNamespace())
        with tempfile.TemporaryDirectory() as root:
            storage = BrowserProfileStorage(root)
            storage.prepare_account(account.account_id, account.account_name)
            (storage.root / "legacy-profile").mkdir()
            with patch(
                "apps.api.xianyu_admin_api.im_verification.browser_profile_storage",
                storage,
            ):
                profiles = await manager.list_browser_profiles()

        indexed = {profile.profile_key: profile for profile in profiles}
        self.assertEqual(indexed["account:account-1"].status, "stopped")
        self.assertEqual(indexed["account:account-1"].account_name, "seller")
        self.assertEqual(indexed["account:legacy-profile"].status, "orphaned")
        self.assertFalse(indexed["account:legacy-profile"].account_exists)

    async def test_directory_manager_stops_only_active_account_browser(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        context = _FakeContext()
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=context,
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
        )
        manager._account_actives[active.verification_id] = active
        manager._account_browser_sessions["session-1"] = AccountBrowserSessionPayload(
            session_id="session-1",
            account_id="account-1",
            status="ready",
        )
        with tempfile.TemporaryDirectory() as root:
            storage = BrowserProfileStorage(root)
            storage.prepare_account("account-1", "seller")
            with patch(
                "apps.api.xianyu_admin_api.im_verification.browser_profile_storage",
                storage,
            ):
                stopped = await manager.stop_browser_profile("account:account-1")

        self.assertTrue(stopped)
        self.assertTrue(context.closed)
        self.assertEqual(manager._account_actives, {})
        self.assertEqual(manager._account_browser_sessions["session-1"].status, "closed")

    async def test_start_injects_cookie_exposes_vnc_and_closes(self) -> None:
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1; _m_h5_tk=token",
            enabled=False,
        )
        context = _FakeContext()
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        browser_settings = SimpleNamespace(
            account_browser_cdp_enabled=True,
            account_browser_session_seconds=1800,
            account_browser_max_sessions=3,
        )
        desktop = _VisualDesktop(slot=1, display=":100", vnc_port=5902, cdp_port=9223)
        cookie_parser = SimpleNamespace(
            trans_cookies=lambda _: {"unb": "seller-1", "_m_h5_tk": "token"}
        )
        with (
            patch(
                "apps.api.xianyu_admin_api.im_verification.load_upstream_modules",
                return_value=cookie_parser,
            ),
            patch.object(manager, "availability_error", return_value=None),
            patch.object(
                manager,
                "_start_account_visual_desktop_locked",
                AsyncMock(return_value=desktop),
            ),
            patch.object(manager, "_start_proxy_bridge", AsyncMock(return_value=None)),
            patch.object(
                manager,
                "_launch_account_browser",
                AsyncMock(return_value=context),
            ),
            patch.object(manager, "_ensure_cdp_port_available", AsyncMock()),
            patch.object(manager, "_wait_for_cdp", AsyncMock()),
            patch(
                "apps.api.xianyu_admin_api.im_verification.settings",
                browser_settings,
            ),
        ):
            payload = await manager.start_account_browser(account, "operator-1")
            self.assertEqual(payload.status, "ready")
            self.assertTrue(payload.vnc_available)
            self.assertTrue(payload.cdp_available)
            self.assertFalse(payload.proxy_enabled)
            self.assertEqual(payload.current_url, "https://www.goofish.com/")
            active_sessions = await manager.list_active_account_browsers()
            self.assertEqual([item.session_id for item in active_sessions], [payload.session_id])
            self.assertEqual(
                {item["name"] for item in context.added_cookies},
                {"unb", "_m_h5_tk"},
            )
            self.assertEqual(context.clear_count, 1)

            ticket, _ = await manager.issue_account_browser_vnc_ticket(
                payload.session_id, "operator-1"
            )
            self.assertEqual(await manager.consume_vnc_ticket(ticket), 5902)
            closed = await manager.close_account_browser(payload.session_id)
            self.assertEqual(closed.status, "closed")
            self.assertFalse(closed.vnc_available)
            self.assertFalse(closed.cdp_available)
            self.assertTrue(context.closed)
            self.assertEqual(manager._account_actives, {})
            self.assertEqual(await manager.list_active_account_browsers(), [])

    async def test_account_browser_cookie_reconcile_uses_four_way_decision(self) -> None:
        browser_cookie = "unb=seller-1; _m_h5_tk=browser-token"
        local_cookie = "unb=seller-1; _m_h5_tk=local-token"
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=_FakeContext(),
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
            baseline_cookie=local_cookie,
        )

        cases = (
            ("valid", "invalid", "updated_from_browser", "account_browser", False),
            ("valid", "valid", "updated_from_browser", "account_browser", False),
            ("invalid", "valid", "kept_local", "account_browser_local_validation", False),
            ("invalid", "invalid", "auth_recovery", None, True),
        )
        for browser_state, local_state, expected_status, expected_source, auth_called in cases:
            with self.subTest(browser=browser_state, local=local_state):
                account = AccountRecord(
                    account_id="account-1",
                    account_name="seller",
                    cookie=local_cookie,
                )

                def outcome(state: str, cookie: str) -> object:
                    if state == "valid":
                        return CookieRenewalResult(
                            new_cookie=cookie,
                            message="Cookie 轻量保活验证成功",
                        )
                    return CookieRenewalError(
                        "闲鱼平台要求完成安全验证",
                        kind="verification_required",
                    )

                coordinator = _CookieCoordinator(
                    {
                        browser_cookie: outcome(browser_state, browser_cookie),
                        local_cookie: outcome(local_state, local_cookie),
                    }
                )
                store = SimpleNamespace(get_account=AsyncMock(return_value=account))
                manager = IMVerificationManager(
                    store,
                    SimpleNamespace(),
                    coordinator,
                )

                result = await manager._reconcile_account_browser_cookie(
                    active,
                    browser_cookie,
                )

                self.assertEqual(result.sync_status, expected_status)
                self.assertEqual(result.browser_status, browser_state)
                self.assertEqual(result.local_status, local_state)
                self.assertEqual(bool(coordinator.auth_calls), auth_called)
                if expected_source is None:
                    self.assertEqual(coordinator.persist_calls, [])
                else:
                    self.assertEqual(
                        coordinator.persist_calls[0]["source"],
                        expected_source,
                    )

    async def test_account_browser_cookie_reconcile_rejects_account_mismatch(self) -> None:
        local_cookie = "unb=seller-1; _m_h5_tk=local-token"
        browser_cookie = "unb=another-seller; _m_h5_tk=browser-token"
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie=local_cookie,
        )
        coordinator = _CookieCoordinator({})
        manager = IMVerificationManager(
            SimpleNamespace(get_account=AsyncMock(return_value=account)),
            SimpleNamespace(),
            coordinator,
        )
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=_FakeContext(),
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
            baseline_cookie=local_cookie,
        )

        result = await manager._reconcile_account_browser_cookie(
            active,
            browser_cookie,
        )

        self.assertEqual(result.sync_status, "account_mismatch")
        self.assertEqual(coordinator.persist_calls, [])
        self.assertEqual(coordinator.auth_calls, [])

    async def test_account_browser_cookie_reconcile_keeps_unknown_out_of_auth_recovery(
        self,
    ) -> None:
        browser_cookie = "unb=seller-1; _m_h5_tk=browser-token"
        local_cookie = "unb=seller-1; _m_h5_tk=local-token"
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie=local_cookie,
        )
        coordinator = _CookieCoordinator(
            {
                browser_cookie: CookieRenewalError(
                    "浏览器验证请求超时",
                    kind="failed",
                ),
                local_cookie: CookieRenewalError(
                    "本地验证请求超时",
                    kind="failed",
                ),
            }
        )
        manager = IMVerificationManager(
            SimpleNamespace(get_account=AsyncMock(return_value=account)),
            SimpleNamespace(),
            coordinator,
        )
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=_FakeContext(),
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
            baseline_cookie=local_cookie,
        )

        result = await manager._reconcile_account_browser_cookie(
            active,
            browser_cookie,
        )

        self.assertEqual(result.sync_status, "unknown")
        self.assertEqual(result.browser_status, "unknown")
        self.assertEqual(result.local_status, "unknown")
        self.assertEqual(coordinator.persist_calls, [])
        self.assertEqual(coordinator.auth_calls, [])

    async def test_account_browser_cookie_reconcile_retries_atomic_update_once(self) -> None:
        browser_cookie = "unb=seller-1; _m_h5_tk=browser-token"
        local_cookie = "unb=seller-1; _m_h5_tk=local-token"
        latest_cookie = "unb=seller-1; _m_h5_tk=concurrent-token"
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie=local_cookie,
        )
        latest = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie=latest_cookie,
        )
        coordinator = _CookieCoordinator(
            {
                browser_cookie: CookieRenewalResult(
                    new_cookie=browser_cookie,
                    message="Cookie 轻量保活验证成功",
                ),
                local_cookie: CookieRenewalResult(
                    new_cookie=local_cookie,
                    message="Cookie 轻量保活验证成功",
                ),
            }
        )
        coordinator.persist_results = [False, True]
        store = SimpleNamespace(
            get_account=AsyncMock(side_effect=[account, latest]),
        )
        manager = IMVerificationManager(store, SimpleNamespace(), coordinator)
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=_FakeContext(),
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
            baseline_cookie=local_cookie,
        )

        result = await manager._reconcile_account_browser_cookie(
            active,
            browser_cookie,
        )

        self.assertEqual(result.sync_status, "updated_from_browser")
        self.assertEqual(len(coordinator.persist_calls), 2)
        self.assertEqual(
            coordinator.persist_calls[1]["expected_cookie"],
            latest_cookie,
        )

    async def test_two_accounts_run_in_isolated_vnc_slots(self) -> None:
        accounts = [
            AccountRecord(
                account_id=f"account-{index}",
                account_name=f"seller-{index}",
                cookie=f"unb=seller-{index}",
            )
            for index in (1, 2)
        ]
        contexts = [_FakeContext(), _FakeContext()]
        desktops = [
            _VisualDesktop(slot=1, display=":100", vnc_port=5902, cdp_port=9223),
            _VisualDesktop(slot=2, display=":101", vnc_port=5903, cdp_port=9224),
        ]
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        browser_settings = SimpleNamespace(
            account_browser_cdp_enabled=True,
            account_browser_session_seconds=1800,
            account_browser_max_sessions=3,
        )
        cookie_parser = SimpleNamespace(
            trans_cookies=lambda value: {"unb": value.split("unb=", 1)[1].split(";", 1)[0]}
        )
        with (
            patch(
                "apps.api.xianyu_admin_api.im_verification.load_upstream_modules",
                return_value=cookie_parser,
            ),
            patch.object(manager, "availability_error", return_value=None),
            patch.object(
                manager,
                "_start_account_visual_desktop_locked",
                AsyncMock(side_effect=desktops),
            ),
            patch.object(manager, "_start_proxy_bridge", AsyncMock(return_value=None)),
            patch.object(
                manager,
                "_launch_account_browser",
                AsyncMock(side_effect=contexts),
            ),
            patch.object(manager, "_wait_for_cdp", AsyncMock()),
            patch("apps.api.xianyu_admin_api.im_verification.settings", browser_settings),
        ):
            sessions = [
                await manager.start_account_browser(account, "operator-1")
                for account in accounts
            ]
            self.assertEqual(len(await manager.list_active_account_browsers()), 2)
            self.assertEqual(
                set(manager.active_visual_account_ids),
                {"account-1", "account-2"},
            )

            ports: list[int | None] = []
            for session in sessions:
                ticket, _ = await manager.issue_account_browser_vnc_ticket(
                    session.session_id, "operator-1"
                )
                ports.append(await manager.consume_vnc_ticket(ticket))
            self.assertEqual(ports, [5902, 5903])

            await manager.close_account_browser(sessions[0].session_id)
            self.assertTrue(contexts[0].closed)
            self.assertFalse(contexts[1].closed)
            remaining = await manager.list_active_account_browsers()
            self.assertEqual([item.account_id for item in remaining], ["account-2"])
            await manager.close_account_browser(sessions[1].session_id)

    async def test_account_vnc_pool_enforces_configured_capacity(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        for index in (1, 2):
            active = _ActiveSession(
                verification_id=f"account-browser:session-{index}",
                purpose="account_browser",
                account_id=f"account-{index}",
                context=_FakeContext(),
                page=_FakePage(),
                bridge=None,
                expires_at=time.time() + 60,
            )
            manager._account_actives[active.verification_id] = active
        account = AccountRecord(
            account_id="account-3",
            account_name="seller-3",
            cookie="unb=seller-3",
        )
        browser_settings = SimpleNamespace(account_browser_max_sessions=2)
        cookie_parser = SimpleNamespace(trans_cookies=lambda _: {"unb": "seller-3"})
        with (
            patch(
                "apps.api.xianyu_admin_api.im_verification.load_upstream_modules",
                return_value=cookie_parser,
            ),
            patch.object(manager, "availability_error", return_value=None),
            patch("apps.api.xianyu_admin_api.im_verification.settings", browser_settings),
            self.assertRaisesRegex(IMVerificationBusyError, "并发数已达到上限 2"),
        ):
            await manager.start_account_browser(account, "operator-1")

    async def test_profile_cleanup_rejects_active_account(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=_FakeContext(),
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
        )
        manager._account_actives[active.verification_id] = active
        with self.assertRaisesRegex(IMVerificationBusyError, "先结束会话"):
            await manager.clear_account_browser_profile("account-1")

    async def test_account_deletion_closes_active_browser(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        context = _FakeContext()
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=context,
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
        )
        manager._account_actives[active.verification_id] = active
        manager._account_browser_by_account["account-1"] = "session-1"
        manager._account_browser_sessions["session-1"] = AccountBrowserSessionPayload(
            session_id="session-1",
            account_id="account-1",
            status="ready",
        )
        await manager.prepare_account_deletion("account-1")
        self.assertTrue(context.closed)
        self.assertEqual(manager._account_actives, {})
        status = await manager.account_browser_status("account-1")
        self.assertIsNotNone(status)
        self.assertEqual(status.status, "closed")  # type: ignore[union-attr]

    async def test_reserved_verification_for_other_account_does_not_block_vnc(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        manager._active = _ActiveSession(
            verification_id="other-verification",
            purpose="im_recovery",
            account_id="account-2",
            context=_FakeContext(),
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
        )
        context = _FakeContext()
        desktop = _VisualDesktop(slot=1, display=":100", vnc_port=5902, cdp_port=9223)
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1",
        )
        cookie_parser = SimpleNamespace(trans_cookies=lambda _: {"unb": "seller-1"})
        with (
            patch(
                "apps.api.xianyu_admin_api.im_verification.load_upstream_modules",
                return_value=cookie_parser,
            ),
            patch.object(manager, "availability_error", return_value=None),
            patch.object(
                manager,
                "_start_account_visual_desktop_locked",
                AsyncMock(return_value=desktop),
            ),
            patch.object(manager, "_start_proxy_bridge", AsyncMock(return_value=None)),
            patch.object(manager, "_launch_account_browser", AsyncMock(return_value=context)),
            patch.object(manager, "_wait_for_cdp", AsyncMock()),
        ):
            payload = await manager.start_account_browser(account, "operator-1")
            self.assertEqual(payload.status, "ready")
            self.assertEqual(manager._active.account_id, "account-2")  # type: ignore[union-attr]
            await manager.close_account_browser(payload.session_id)

    async def test_reserved_verification_for_same_account_blocks_vnc(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        manager._active = _ActiveSession(
            verification_id="other-verification",
            purpose="im_recovery",
            account_id="account-1",
            context=_FakeContext(),
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
        )
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1",
        )
        cookie_parser = SimpleNamespace(trans_cookies=lambda _: {"unb": "seller-1"})
        with (
            patch(
                "apps.api.xianyu_admin_api.im_verification.load_upstream_modules",
                return_value=cookie_parser,
            ),
            patch.object(manager, "availability_error", return_value=None),
            self.assertRaisesRegex(IMVerificationBusyError, "该账户正在"),
        ):
            await manager.start_account_browser(account, "operator-1")

    async def test_disabled_bound_proxy_never_falls_back_to_direct(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1",
            proxy_id="proxy-1",
            proxy=ProxyConfigPayload(enabled=False, host="127.0.0.1", port=1080),
        )
        cookie_parser = SimpleNamespace(trans_cookies=lambda _: {"unb": "seller-1"})
        with (
            patch(
                "apps.api.xianyu_admin_api.im_verification.load_upstream_modules",
                return_value=cookie_parser,
            ),
            patch.object(manager, "availability_error", return_value=None),
            self.assertRaisesRegex(IMVerificationError, "禁止直连"),
        ):
            await manager.start_account_browser(account, "operator-1")

    async def test_qr_browser_rejects_disabled_bound_proxy_before_launch(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        session = QRLoginSession(
            account_id="account-1",
            account_name="seller",
            proxy_id="proxy-1",
            proxy=ProxyConfigPayload(enabled=False),
        )
        with (
            patch.object(manager, "availability_error", return_value=None),
            patch.object(manager, "_ensure_visual_desktop", AsyncMock()) as desktop,
            self.assertRaisesRegex(IMVerificationError, "禁止直连"),
        ):
            await manager.start_qr_login(session, None, "operator-1")
        desktop.assert_not_awaited()

    async def test_account_browser_rejects_profile_owned_by_residual_process(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1",
        )
        with (
            patch(
                "apps.api.xianyu_admin_api.im_verification.browser_profile_storage.profile_in_use",
                return_value=True,
            ),
            patch.object(manager, "_launch_browser", AsyncMock()) as launch,
            self.assertRaisesRegex(IMVerificationBusyError, "目录管理中停止"),
        ):
            await manager._launch_account_browser(account, None)
        launch.assert_not_awaited()

    async def test_cdp_launch_flags_are_loopback_only(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        context = _FakeContext()
        launch = AsyncMock(return_value=context)
        manager._playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch_persistent_context=launch)
        )
        browser_settings = SimpleNamespace(
            im_verification_profile_dir="",
            im_verification_display=":99",
            im_verification_allow_no_sandbox=False,
            account_browser_cdp_port=9222,
        )
        with (
            tempfile.TemporaryDirectory() as profile_dir,
            patch(
                "apps.api.xianyu_admin_api.im_verification.settings",
                browser_settings,
            ),
            patch.object(manager, "browser_path", return_value="/usr/bin/chromium"),
        ):
            browser_settings.im_verification_profile_dir = profile_dir
            await manager._launch_browser("account-1", None, enable_cdp=True)
        args = launch.await_args.kwargs["args"]
        self.assertIn("--remote-debugging-address=127.0.0.1", args)
        self.assertIn("--remote-debugging-port=9222", args)
        self.assertIn("--lang=zh-CN", args)
        self.assertIn("--accept-lang=zh-CN,zh;q=0.9,en;q=0.8", args)
        self.assertIn("--start-maximized", args)
        self.assertIn("--disable-quic", args)
        self.assertIn(
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            args,
        )
        self.assertFalse(any(value.startswith("--window-size=") for value in args))
        self.assertFalse(any(value.startswith("--window-position=") for value in args))
        self.assertNotIn("--remote-debugging-address=0.0.0.0", args)
        self.assertEqual(launch.await_args.kwargs["locale"], "zh-CN")
        self.assertEqual(launch.await_args.kwargs["timezone_id"], "Asia/Shanghai")
        browser_env = launch.await_args.kwargs["env"]
        self.assertEqual(browser_env["LANG"], "zh_CN.UTF-8")
        self.assertEqual(browser_env["LC_ALL"], "zh_CN.UTF-8")
        self.assertEqual(browser_env["LANGUAGE"], "zh_CN:zh:en_US:en")
        self.assertEqual(
            launch.await_args.kwargs["extra_http_headers"]["Sec-CH-UA-Platform"],
            '"Windows"',
        )
        self.assertTrue(any("Win32" in script for script in context.init_scripts))

    async def test_system_chrome_platform_and_default_webrtc_are_selectable(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        context = _FakeContext()
        launch = AsyncMock(return_value=context)
        manager._playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch_persistent_context=launch)
        )
        browser_settings = SimpleNamespace(
            im_verification_profile_dir="",
            im_verification_display=":99",
            im_verification_allow_no_sandbox=False,
            account_browser_cdp_port=9222,
        )
        identity = ClientIdentity(
            browser_engine="system_chromium",
            browser_version="136.0.0.0",
            platform="linux",
            platform_version="6.8.0",
            brand="Edge",
            webrtc_policy="browser_default",
        )
        with (
            tempfile.TemporaryDirectory() as profile_dir,
            patch(
                "apps.api.xianyu_admin_api.im_verification.settings",
                browser_settings,
            ),
            patch.object(manager, "browser_path", return_value="/usr/bin/chromium"),
        ):
            browser_settings.im_verification_profile_dir = profile_dir
            await manager._launch_browser("account-1", None, identity=identity)

        args = launch.await_args.kwargs["args"]
        self.assertNotIn("--disable-non-proxied-udp", args)
        self.assertFalse(
            any(value.startswith("--force-webrtc-ip-handling-policy=") for value in args)
        )
        self.assertIn("X11; Linux x86_64", launch.await_args.kwargs["user_agent"])
        self.assertIn("Edg/136.0.0.0", launch.await_args.kwargs["user_agent"])
        self.assertIn(
            "Microsoft Edge",
            launch.await_args.kwargs["extra_http_headers"]["Sec-CH-UA"],
        )
        self.assertEqual(
            launch.await_args.kwargs["extra_http_headers"]["Sec-CH-UA-Platform"],
            '"Linux"',
        )
        self.assertTrue(any("Linux x86_64" in script for script in context.init_scripts))
        self.assertTrue(any("Microsoft Edge" in script for script in context.init_scripts))

    async def test_webrtc_disabled_installs_page_block_and_network_policy(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        context = _FakeContext()
        launch = AsyncMock(return_value=context)
        manager._playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch_persistent_context=launch)
        )
        browser_settings = SimpleNamespace(
            im_verification_profile_dir="",
            im_verification_display=":99",
            im_verification_allow_no_sandbox=False,
            account_browser_cdp_port=9222,
        )
        identity = ClientIdentity(webrtc_policy="disabled")
        with (
            tempfile.TemporaryDirectory() as profile_dir,
            patch("apps.api.xianyu_admin_api.im_verification.settings", browser_settings),
            patch.object(manager, "browser_path", return_value="/usr/bin/chromium"),
        ):
            browser_settings.im_verification_profile_dir = profile_dir
            await manager._launch_browser("account-1", None, identity=identity)

        args = launch.await_args.kwargs["args"]
        self.assertIn("--disable-non-proxied-udp", args)
        self.assertIn(
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            args,
        )
        self.assertTrue(any("RTCPeerConnection" in script for script in context.init_scripts))

    async def test_fingerprint_browser_passes_brand_and_disabled_modules(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        context = _FakeContext()
        launch = AsyncMock(return_value=context)
        manager._playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch_persistent_context=launch)
        )
        browser_settings = SimpleNamespace(
            im_verification_profile_dir="",
            im_verification_display=":99",
            im_verification_allow_no_sandbox=False,
            account_browser_cdp_port=9222,
        )
        identity = ClientIdentity(
            browser_engine="fingerprint_chromium",
            fingerprint_seed=12345,
            browser_version="148.0.7778.215",
            brand="Vivaldi",
            spoof_canvas=False,
            spoof_fonts=False,
        )
        with (
            tempfile.TemporaryDirectory() as profile_dir,
            patch(
                "apps.api.xianyu_admin_api.im_verification.settings",
                browser_settings,
            ),
            patch.object(manager, "browser_path", return_value="/opt/fingerprint/chrome"),
        ):
            browser_settings.im_verification_profile_dir = profile_dir
            await manager._launch_browser("account-1", None, identity=identity)

        args = launch.await_args.kwargs["args"]
        self.assertIn("--fingerprint-brand=Vivaldi", args)
        self.assertIn("--fingerprint-brand-version=148.0.7778.215", args)
        self.assertIn("--disable-spoofing=canvas,font", args)

    async def test_browser_fingerprint_snapshot_uses_observed_values(self) -> None:
        page = SimpleNamespace(
            evaluate=AsyncMock(
                return_value={
                    "observedPlatform": "Win32",
                    "userAgent": "Mozilla/5.0 Chrome/136.0.0.0",
                    "uaChPlatform": "Windows",
                    "uaChBrands": ["Chromium/148", "Microsoft Edge/148"],
                    "language": "zh-CN",
                    "languages": ["zh-CN", "zh", "en"],
                    "timezone": "Asia/Shanghai",
                    "hardwareConcurrency": 8,
                    "deviceMemory": 8,
                    "canvasHash": "canvas",
                    "webglVendor": "vendor",
                    "webglRenderer": "renderer",
                    "webglHash": "webgl",
                    "audioHash": "audio",
                    "fontsHash": "fonts",
                    "detectedFonts": ["Arial"],
                    "clientRectsHash": "rects",
                    "webrtcCandidateTypes": ["host"],
                    "webrtcApiAvailable": True,
                    "webrtcBlocked": False,
                    "webrtcGatheringState": "complete",
                    "webrtcPrivateCandidateDetected": False,
                    "webrtcPublicCandidateDetected": False,
                    "navigatorWebdriver": False,
                    "automationWindowMarkers": [],
                    "hasWindowChrome": True,
                    "pluginsCount": 5,
                    "notificationPermission": "prompt",
                    "iframeWebdriver": False,
                    "workerWebdriver": False,
                    "cdpStackProbeDetected": False,
                }
            )
        )
        snapshot = await IMVerificationManager._capture_browser_fingerprint_snapshot(
            page,
            ClientIdentity(
                browser_version="148.0.7778.215",
                brand="Edge",
                spoof_canvas=False,
                config_revision=3,
            ),
        )
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.hardware_concurrency, 8)
        self.assertEqual(snapshot.device_memory, 8)
        self.assertEqual(snapshot.detected_fonts, ["Arial"])
        self.assertEqual(snapshot.languages, ["zh-CN", "zh", "en"])
        self.assertEqual(snapshot.brand, "Edge")
        self.assertEqual(snapshot.ua_ch_brands[-1], "Microsoft Edge/148")
        self.assertFalse(snapshot.spoof_canvas)
        self.assertEqual(snapshot.config_revision, 3)
        self.assertFalse(snapshot.navigator_webdriver)
        self.assertFalse(snapshot.cdp_stack_probe_detected)
        self.assertEqual(snapshot.plugins_count, 5)
        self.assertEqual(snapshot.risk_status, "warning")

    async def test_browser_fingerprint_snapshot_compares_webrtc_with_proxy_exit(self) -> None:
        observed = {
            "userAgent": "Mozilla/5.0 Chrome/148.0.0.0",
            "webrtcCandidateTypes": ["srflx"],
            "webrtcCandidateAddresses": ["8.8.8.8"],
            "webrtcApiAvailable": True,
            "webrtcBlocked": False,
            "webrtcGatheringState": "complete",
            "webrtcPrivateCandidateDetected": False,
            "webrtcPublicCandidateDetected": True,
            "navigatorWebdriver": False,
            "automationWindowMarkers": [],
            "cdpStackProbeDetected": False,
        }
        page = SimpleNamespace(evaluate=AsyncMock(return_value=observed))
        probe_settings = SimpleNamespace(
            browser_fingerprint_probe_stun_url="stun:probe.example.test:3478"
        )

        with patch("apps.api.xianyu_admin_api.im_verification.settings", probe_settings):
            matched = await IMVerificationManager._capture_browser_fingerprint_snapshot(
                page,
                ClientIdentity(webrtc_policy="proxy_only"),
                proxy_enabled=True,
                expected_proxy_ips={"8.8.8.8"},
            )
            mismatched = await IMVerificationManager._capture_browser_fingerprint_snapshot(
                page,
                ClientIdentity(webrtc_policy="proxy_only"),
                proxy_enabled=True,
                expected_proxy_ips={"1.1.1.1"},
            )

        self.assertIsNotNone(matched)
        self.assertTrue(matched.webrtc_proxy_match)
        self.assertTrue(matched.webrtc_probe_configured)
        self.assertEqual(matched.risk_status, "pass")
        self.assertIsNotNone(mismatched)
        self.assertFalse(mismatched.webrtc_proxy_match)
        self.assertEqual(mismatched.risk_status, "risk")
        self.assertIn("WebRTC 公网候选地址与账户代理出口不一致", mismatched.risk_findings)

    async def test_browser_http_egress_replaces_required_stun_probe(self) -> None:
        observed = {
            "userAgent": "Mozilla/5.0 Chrome/148.0.0.0",
            "webrtcCandidateTypes": [],
            "webrtcCandidateAddresses": [],
            "webrtcApiAvailable": True,
            "webrtcBlocked": False,
            "webrtcGatheringState": "complete",
            "webrtcPrivateCandidateDetected": False,
            "webrtcPublicCandidateDetected": False,
            "navigatorWebdriver": False,
            "automationWindowMarkers": [],
            "cdpStackProbeDetected": False,
        }
        response = SimpleNamespace(
            status=200,
            json=AsyncMock(return_value={"ip": "8.8.8.8"}),
            text=AsyncMock(return_value="8.8.8.8"),
            dispose=AsyncMock(),
        )
        page = SimpleNamespace(
            evaluate=AsyncMock(return_value=observed),
            request=SimpleNamespace(get=AsyncMock(return_value=response)),
        )
        probe_settings = SimpleNamespace(
            browser_fingerprint_probe_stun_url="",
            proxy_ip_check_urls=("https://probe.example.test/ip",),
        )

        with patch("apps.api.xianyu_admin_api.im_verification.settings", probe_settings):
            matched = await IMVerificationManager._capture_browser_fingerprint_snapshot(
                page,
                ClientIdentity(webrtc_policy="proxy_only"),
                proxy_enabled=True,
                expected_proxy_ips={"8.8.8.8"},
            )
            mismatched = await IMVerificationManager._capture_browser_fingerprint_snapshot(
                page,
                ClientIdentity(webrtc_policy="proxy_only"),
                proxy_enabled=True,
                expected_proxy_ips={"1.1.1.1"},
            )

        self.assertIsNotNone(matched)
        self.assertEqual(matched.browser_egress_ips, ["8.8.8.8"])
        self.assertEqual(matched.proxy_expected_ips, ["8.8.8.8"])
        self.assertTrue(matched.browser_egress_match)
        self.assertFalse(matched.webrtc_probe_configured)
        self.assertEqual(matched.risk_status, "pass")
        self.assertNotIn("STUN", "；".join(matched.risk_findings))
        self.assertIsNotNone(mismatched)
        self.assertFalse(mismatched.browser_egress_match)
        self.assertEqual(mismatched.risk_status, "risk")
        self.assertIn(
            "Chromium HTTP 出口与账户代理出口不一致",
            mismatched.risk_findings,
        )

    async def test_browser_ipv6_without_proxy_ipv6_baseline_is_warning(self) -> None:
        observed = {
            "userAgent": "Mozilla/5.0 Chrome/148.0.0.0",
            "webrtcCandidateTypes": [],
            "webrtcCandidateAddresses": [],
            "webrtcApiAvailable": True,
            "webrtcBlocked": False,
            "webrtcGatheringState": "complete",
            "webrtcPrivateCandidateDetected": False,
            "webrtcPublicCandidateDetected": False,
            "navigatorWebdriver": False,
            "automationWindowMarkers": [],
            "cdpStackProbeDetected": False,
        }

        def response(address: str) -> SimpleNamespace:
            return SimpleNamespace(
                status=200,
                json=AsyncMock(return_value={"ip": address}),
                text=AsyncMock(return_value=address),
                dispose=AsyncMock(),
            )

        page = SimpleNamespace(
            evaluate=AsyncMock(return_value=observed),
            request=SimpleNamespace(
                get=AsyncMock(
                    side_effect=[
                        response("111.30.204.73"),
                        response("2409:8a02:482a:7c10:a027:60c3:5705:8a99"),
                    ]
                )
            ),
        )
        probe_settings = SimpleNamespace(
            browser_fingerprint_probe_stun_url="",
            proxy_ip_check_urls=(
                "https://ipv4-probe.example.test/ip",
                "https://ipv6-probe.example.test/ip",
            ),
        )

        with patch("apps.api.xianyu_admin_api.im_verification.settings", probe_settings):
            snapshot = await IMVerificationManager._capture_browser_fingerprint_snapshot(
                page,
                ClientIdentity(webrtc_policy="proxy_only"),
                proxy_enabled=True,
                expected_proxy_ips={"111.30.204.73"},
            )

        self.assertIsNotNone(snapshot)
        self.assertIsNone(snapshot.browser_egress_match)
        self.assertEqual(snapshot.risk_status, "warning")
        self.assertIn(
            "Chromium IPv6 出口缺少账户代理基线，需复核",
            snapshot.risk_findings,
        )
        self.assertNotIn(
            "Chromium HTTP 出口与账户代理出口不一致",
            snapshot.risk_findings,
        )

    async def test_browser_probe_refreshes_stale_proxy_exit_baseline(self) -> None:
        proxy = SimpleNamespace(
            exit_ip="1.1.1.1",
            exit_ipv4="1.1.1.1",
            exit_ipv6=None,
            exit_checked_at=datetime.now(UTC) - timedelta(hours=1),
            to_config=lambda: ProxyConfigPayload(
                enabled=True,
                host="127.0.0.1",
                port=1080,
            ),
            connection_signature=lambda: (
                "socks5h",
                "127.0.0.1",
                1080,
                None,
                None,
            ),
        )
        tested = SimpleNamespace(
            ok=True,
            message="代理出口已刷新",
            latency_ms=10,
            exit_ip="8.8.8.8",
            exit_ipv4="8.8.8.8",
            exit_ipv6=None,
            exit_country=None,
            exit_region=None,
            exit_city=None,
            exit_isp=None,
            exit_ipv6_country=None,
            exit_ipv6_continent=None,
            platform_status_code=200,
        )
        store = SimpleNamespace(
            get_proxy=AsyncMock(return_value=proxy),
            record_proxy_test=AsyncMock(),
        )
        runtime = SimpleNamespace(test_proxy=AsyncMock(return_value=tested))
        manager = IMVerificationManager(store, runtime)

        result = await manager._account_proxy_exit_ips(
            AccountRecord(
                account_id="account-1",
                account_name="seller",
                proxy_id="proxy-1",
            )
        )

        self.assertEqual(result, {"8.8.8.8"})
        runtime.test_proxy.assert_awaited_once()
        store.record_proxy_test.assert_awaited_once()

    async def test_activity_extends_idle_deadline_without_exceeding_hard_limit(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        page = _FakePage()
        now = time.time()
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=_FakeContext(),
            page=page,
            bridge=None,
            expires_at=now + 70,
            max_expires_at=now + 90,
        )
        manager._account_actives[active.verification_id] = active
        manager._account_browser_sessions["session-1"] = AccountBrowserSessionPayload(
            session_id="session-1",
            account_id="account-1",
            status="ready",
        )
        with patch(
            "apps.api.xianyu_admin_api.im_verification.settings",
            replace(app_settings, account_browser_idle_seconds=120),
        ):
            result = await manager.touch_account_browser_session("session-1")

        self.assertIsNotNone(result.last_activity_at)
        self.assertIsNotNone(result.idle_expires_at)
        self.assertIsNotNone(result.max_expires_at)
        self.assertLessEqual(result.idle_expires_at, result.max_expires_at)  # type: ignore[operator]
        self.assertAlmostEqual(active.expires_at, active.max_expires_at, delta=0.1)
        await manager.close_account_browser("session-1")

    async def test_text_paste_preserves_unicode_and_refreshes_activity(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        page = _FakePage()
        now = time.time()
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id="account-1",
            context=_FakeContext(),
            page=page,
            bridge=None,
            expires_at=now + 60,
            max_expires_at=now + 600,
        )
        manager._account_actives[active.verification_id] = active
        manager._account_browser_sessions["session-1"] = AccountBrowserSessionPayload(
            session_id="session-1",
            account_id="account-1",
            status="ready",
        )
        pasted = "中文内容\n第二行🙂"
        with patch(
            "apps.api.xianyu_admin_api.im_verification.settings",
            replace(app_settings, account_browser_idle_seconds=180),
        ):
            result = await manager.paste_account_browser_text("session-1", pasted)

        self.assertEqual(page.keyboard.inserted_texts, [pasted])
        self.assertIsNotNone(result.last_activity_at)
        await manager.close_account_browser("session-1")

    async def test_manual_fingerprint_detection_updates_running_session(self) -> None:
        snapshot = BrowserFingerprintSnapshotPayload(
            browser_engine="system_chromium",
            browser_version="148.0.0.0",
            target_platform="windows",
            user_agent="Mozilla/5.0 Chrome/148.0.0.0",
            config_revision=1,
            observed_at="2026-07-20T00:00:00Z",
        )
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1",
        )
        store = SimpleNamespace(
            get_account=AsyncMock(return_value=account),
            save_account_browser_fingerprint_snapshot=AsyncMock(return_value=snapshot),
        )
        manager = IMVerificationManager(store, SimpleNamespace())
        active = _ActiveSession(
            verification_id="account-browser:session-1",
            purpose="account_browser",
            account_id=account.account_id,
            context=_FakeContext(),
            page=_FakePage(),
            bridge=None,
            expires_at=time.time() + 60,
        )
        manager._account_actives[active.verification_id] = active
        manager._account_browser_sessions["session-1"] = AccountBrowserSessionPayload(
            session_id="session-1",
            account_id=account.account_id,
            status="ready",
        )
        with patch.object(
            manager,
            "_capture_browser_fingerprint_snapshot",
            AsyncMock(return_value=snapshot),
        ):
            result = await manager.detect_account_browser_fingerprint("session-1")
        self.assertEqual(result.fingerprint_detection_status, "ready")
        self.assertEqual(result.fingerprint_snapshot, snapshot)
        store.save_account_browser_fingerprint_snapshot.assert_awaited_once()

    async def test_visual_page_is_maximized_through_cdp(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        context = _FakeContext()
        session = _FakeCDPSession()
        context.new_cdp_session = AsyncMock(return_value=session)  # type: ignore[attr-defined]

        page = await manager._prepare_visual_page(context)

        self.assertIs(page, context.pages[0])
        self.assertEqual(
            session.calls,
            [
                ("Browser.getWindowForTarget", None),
                (
                    "Browser.setWindowBounds",
                    {"windowId": 42, "bounds": {"windowState": "maximized"}},
                ),
            ],
        )
        self.assertTrue(session.detached)

    async def test_visual_desktop_hides_fluxbox_toolbar(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        process = SimpleNamespace(returncode=None)
        create_process = AsyncMock(side_effect=[process, process])
        browser_settings = SimpleNamespace(
            im_verification_display=":99",
            im_verification_vnc_port=5901,
        )
        with (
            patch("apps.api.xianyu_admin_api.im_verification.settings", browser_settings),
            patch("apps.api.xianyu_admin_api.im_verification.Path.exists", return_value=True),
            patch("apps.api.xianyu_admin_api.im_verification.shutil.which", return_value="/usr/bin/fluxbox"),
            patch("apps.api.xianyu_admin_api.im_verification.asyncio.sleep", AsyncMock()),
            patch(
                "apps.api.xianyu_admin_api.im_verification.asyncio.create_subprocess_exec",
                create_process,
            ),
        ):
            await manager._ensure_visual_desktop()

        fluxbox_args = create_process.await_args_list[0].args
        self.assertEqual(fluxbox_args[:4], ("fluxbox", "-display", ":99", "-no-toolbar"))
        self.assertIn("-no-slit", fluxbox_args)

    async def test_account_visual_desktop_allocates_isolated_endpoints(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        processes = [SimpleNamespace(returncode=None) for _ in range(3)]
        create_process = AsyncMock(side_effect=processes)
        browser_settings = SimpleNamespace(
            im_verification_display=":99",
            im_verification_vnc_port=5901,
            account_browser_cdp_port=9222,
            account_browser_cdp_enabled=True,
            account_browser_max_sessions=3,
        )
        with (
            patch("apps.api.xianyu_admin_api.im_verification.settings", browser_settings),
            patch("apps.api.xianyu_admin_api.im_verification.Path.exists", return_value=False),
            patch("apps.api.xianyu_admin_api.im_verification.shutil.which", return_value="/usr/bin/fluxbox"),
            patch("apps.api.xianyu_admin_api.im_verification.asyncio.sleep", AsyncMock()),
            patch(
                "apps.api.xianyu_admin_api.im_verification.asyncio.create_subprocess_exec",
                create_process,
            ),
            patch.object(manager, "_port_is_available", AsyncMock(return_value=True)),
        ):
            desktop = await manager._start_account_visual_desktop_locked()

        self.assertEqual(desktop.display, ":100")
        self.assertEqual(desktop.vnc_port, 5902)
        self.assertEqual(desktop.cdp_port, 9223)
        self.assertEqual(create_process.await_args_list[0].args[:2], ("Xvfb", ":100"))
        self.assertIn("5902", create_process.await_args_list[2].args)

    async def test_cookie_injection_replaces_profile_cookie_with_database_cookie(self) -> None:
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=current-user; token=current-token",
        )
        context = _FakeContext()
        context.added_cookies = [
            {"name": "unb", "value": "stale-user"},
            {"name": "token", "value": "stale-token"},
        ]
        cookie_parser = SimpleNamespace(
            trans_cookies=lambda _: {
                "unb": "current-user",
                "token": "current-token",
            }
        )
        with patch(
            "apps.api.xianyu_admin_api.im_verification.load_upstream_modules",
            return_value=cookie_parser,
        ):
            await manager._inject_account_cookies(context, account)

        self.assertEqual(context.clear_count, 1)
        self.assertEqual(
            {item["name"]: item["value"] for item in context.added_cookies},
            {"unb": "current-user", "token": "current-token"},
        )


if __name__ == "__main__":
    unittest.main()
