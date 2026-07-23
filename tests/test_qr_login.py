import asyncio
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests
from fastapi import HTTPException

from apps.api.xianyu_admin_api.face_verification import FaceVerificationChallenge
from apps.api.xianyu_admin_api.im_verification import (
    IMVerificationError,
    IMVerificationManager,
    _ActiveSession,
)
from apps.api.xianyu_admin_api.qr_login import LOGIN_TOKEN_URL, QRLoginSession
from apps.api.xianyu_admin_api.schemas import (
    ProxyConfigPayload,
    XianyuQRBrowserVerificationPayload,
    XianyuQRStartPayload,
)
from apps.api.xianyu_admin_api.store import ProxyAssignmentConflict


class _FakeResponse:
    def __init__(
        self,
        payload: dict | None = None,
        *,
        text: str = "",
        url: str = "https://passport.goofish.com/",
    ) -> None:
        self._payload = payload or {}
        self.text = text
        self.url = url

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeHttp:
    def __init__(
        self,
        responses: list[_FakeResponse] | None = None,
        *,
        get_responses: list[_FakeResponse] | None = None,
    ) -> None:
        self.cookies = requests.cookies.RequestsCookieJar()
        self.responses = list(responses or [])
        self.get_responses = list(get_responses or [])
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected HTTP POST: {url}")
        return self.responses.pop(0)

    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append((url, kwargs))
        if not self.get_responses:
            raise AssertionError(f"unexpected HTTP GET: {url}")
        return self.get_responses.pop(0)

    def close(self) -> None:
        return None


class QRLoginSessionTests(unittest.TestCase):
    def make_session(self) -> QRLoginSession:
        return QRLoginSession(
            account_id="account-1",
            account_name="seller",
            proxy_id=None,
            proxy=ProxyConfigPayload(),
        )

    def test_confirmed_poll_enters_finalizing_and_captures_login_token(self) -> None:
        session = self.make_session()
        session._query_base = {"appName": "xianyu"}
        session.token_t = "token-t"
        session.token_ck = "token-ck"
        session._http = _FakeHttp(
            [
                _FakeResponse(
                    {
                        "content": {
                            "data": {
                                "qrCodeStatus": "CONFIRMED",
                                "token": "login-token",
                            }
                        }
                    }
                )
            ]
        )

        self.assertEqual(session.poll(), "finalizing")
        self.assertEqual(session.login_token, "login-token")
        _, request = session._http.calls[0]
        self.assertEqual(request["data"]["t"], "token-t")
        self.assertEqual(request["data"]["ck"], "token-ck")

    def test_scanned_poll_does_not_finalize_early(self) -> None:
        session = self.make_session()
        session._http = _FakeHttp(
            [_FakeResponse({"content": {"data": {"qrCodeStatus": "SCANED"}}})]
        )

        self.assertEqual(session.poll(), "scanned")
        self.assertFalse(session.finalized)

    def test_confirmed_redirect_enters_face_verification_before_finalizing(self) -> None:
        session = self.make_session()
        session._http = _FakeHttp(
            [
                _FakeResponse(
                    {
                        "content": {
                            "data": {
                                "qrCodeStatus": "CONFIRMED",
                                "token": "login-token",
                                "iframeRedirect": True,
                                "iframeRedirectUrl": "https://passport.goofish.com/iv/entry",
                            }
                        }
                    }
                )
            ]
        )
        challenge = FaceVerificationChallenge(
            htoken="face-token",
            code_content="https://passport.goofish.com/face-qr",
            referer="https://passport.goofish.com/iv/mini/identity_verify.htm",
        )

        with patch(
            "apps.api.xianyu_admin_api.qr_login.prepare_face_verification",
            return_value=challenge,
        ) as prepare:
            self.assertEqual(session.poll(), "verification_required")

        prepare.assert_called_once()
        self.assertEqual(session.face_code_content, challenge.code_content)
        self.assertEqual(session.login_token, "")
        self.assertEqual(session.ttl_seconds, 300)

    def test_face_verification_poll_moves_to_finalizing_only_after_success(self) -> None:
        session = self.make_session()
        session.status = "verification_required"
        session._face_challenge = FaceVerificationChallenge(
            htoken="face-token",
            code_content="face-content",
            referer="https://passport.goofish.com/iv/mini/identity_verify.htm",
        )

        with patch(
            "apps.api.xianyu_admin_api.qr_login.poll_face_verification",
            side_effect=[False, True],
        ):
            self.assertEqual(session.poll(), "verification_required")
            self.assertEqual(session.poll(), "finalizing")

    def test_browser_verification_pauses_http_polling(self) -> None:
        session = self.make_session()
        session.status = "browser_verification"
        session._http = _FakeHttp()

        self.assertEqual(session.poll(), "browser_verification")
        self.assertEqual(session._http.calls, [])

    def test_browser_cookies_use_allowlisted_domains_and_existing_validation(self) -> None:
        session = self.make_session()
        session._http = _FakeHttp()
        cookies = [
            {"name": "unb", "value": "seller-1", "domain": ".goofish.com", "path": "/"},
            {"name": "_m_h5_tk", "value": "token", "domain": ".goofish.com", "path": "/"},
            {"name": "foreign", "value": "secret", "domain": ".example.com", "path": "/"},
        ]

        with (
            patch.object(QRLoginSession, "_refresh_login_cookies"),
            patch.object(QRLoginSession, "_validate_access_token") as validate,
        ):
            cookie = session.finalize_browser_credentials(cookies)

        validate.assert_called_once()
        self.assertIn("unb=seller-1", cookie)
        self.assertIn("_m_h5_tk=token", cookie)
        self.assertNotIn("foreign", cookie)
        self.assertNotIn("secret", cookie)

    def test_extract_view_data_reads_nested_login_form_json(self) -> None:
        document = (
            '<script>window.viewData = {"loginFormData": '
            '{"appName": "xianyu", "nested": {"enabled": true}}};</script>'
        )

        view_data = QRLoginSession._extract_view_data(document)

        self.assertEqual(view_data["loginFormData"]["appName"], "xianyu")
        self.assertTrue(view_data["loginFormData"]["nested"]["enabled"])

    def test_terminal_error_is_not_rewritten_as_expired(self) -> None:
        session = self.make_session()
        session.status = "error"
        session.error = "credential validation failed"
        session.created_at = time.time() - session.ttl_seconds - 1
        session._http = _FakeHttp()

        self.assertEqual(session.poll(), "error")
        self.assertEqual(session.error, "credential validation failed")

    def test_finalize_exchanges_login_token_then_serializes_only_goofish_cookies(self) -> None:
        session = self.make_session()
        session.status = "finalizing"
        session.login_token = "login-token"
        session._cna = "device-id"
        http = _FakeHttp([_FakeResponse()])
        http.cookies.set("unb", "passport-value", domain="passport.goofish.com", path="/")
        http.cookies.set("unb", "account-value", domain=".goofish.com", path="/")
        http.cookies.set("_m_h5_tk", "mtop-token", domain=".goofish.com", path="/")
        http.cookies.set("cna", "analytics-id", domain=".mmstat.com", path="/")
        http.cookies.set("foreign", "must-not-leak", domain=".taobao.com", path="/")
        session._http = http

        with (
            patch.object(QRLoginSession, "_refresh_login_cookies"),
            patch.object(QRLoginSession, "_validate_access_token"),
        ):
            cookie = session.finalize_credentials()

        self.assertEqual(http.calls[0][0], LOGIN_TOKEN_URL)
        self.assertIn("unb=account-value", cookie)
        self.assertIn("_m_h5_tk=mtop-token", cookie)
        self.assertIn("cna=analytics-id", cookie)
        self.assertNotIn("passport-value", cookie)
        self.assertNotIn("foreign", cookie)
        self.assertNotIn("must-not-leak", cookie)


class _FailingFinalizeSession:
    session_id = "failing-session"
    account_id = "account-1"
    account_name = "seller"
    proxy_id = None
    finalized = False
    status = "finalizing"
    runtime_state = None
    error = None
    code_content = ""
    face_code_content = ""
    expires_in = 120

    def poll(self) -> str:
        return "finalizing"

    def finalize_credentials(self) -> str:
        from apps.api.xianyu_admin_api.qr_login import QRLoginError

        raise QRLoginError("credential validation failed")

    def fail(self, error: str) -> None:
        self.status = "error"
        self.error = error


class _StoreThatMustNotPersist:
    def __init__(self) -> None:
        self.cookie = "old-cookie"
        self.update_called = False
        self.create_called = False

    async def update_account(self, *_: object, **__: object) -> None:
        self.update_called = True
        self.cookie = "overwritten"

    async def create_account(self, *_: object, **__: object) -> None:
        self.create_called = True


class QRLoginPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_rejects_proxy_owned_by_another_account(self) -> None:
        from apps.api.xianyu_admin_api import main

        with patch.object(
            main.store,
            "validate_proxy_assignment",
            side_effect=ProxyAssignmentConflict(
                "代理“node-1”已绑定账户“seller-a”，请先解绑后再操作"
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await main.start_xianyu_qr_login(
                    XianyuQRStartPayload(
                        account_name="seller-b",
                        proxy_id="proxy-1",
                    )
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("seller-a", str(raised.exception.detail))

    async def test_http_initialization_error_keeps_session_for_browser_fallback(self) -> None:
        from apps.api.xianyu_admin_api import main
        from apps.api.xianyu_admin_api.qr_login import QRLoginError

        with patch.object(QRLoginSession, "start", side_effect=QRLoginError("blocked")):
            result = await main.start_xianyu_qr_login(
                XianyuQRStartPayload(account_name="browser-fallback")
            )
            self.assertEqual(result.status, "initializing")
            await main.qr_initialize_tasks[result.session_id]
            result = main._qr_status_payload(main.qr_login_sessions[result.session_id])
        try:
            self.assertEqual(result.status, "error")
            self.assertIn("HTTP 扫码登录初始化失败", result.error or "")
            self.assertIn(result.session_id, main.qr_login_sessions)
        finally:
            main._discard_qr_session(result.session_id)

    async def test_repeated_start_reuses_initializing_session(self) -> None:
        from apps.api.xianyu_admin_api import main

        with patch.object(QRLoginSession, "start", return_value=None) as start:
            first = await main.start_xianyu_qr_login(
                XianyuQRStartPayload(account_name="same-account")
            )
            second = await main.start_xianyu_qr_login(
                XianyuQRStartPayload(account_name="same-account")
            )
            await main.qr_initialize_tasks[first.session_id]
        try:
            self.assertEqual(first.session_id, second.session_id)
            start.assert_called_once()
        finally:
            main._discard_qr_session(first.session_id)

    async def test_new_account_qr_start_does_not_require_a_name(self) -> None:
        from apps.api.xianyu_admin_api import main

        with patch.object(QRLoginSession, "start", return_value=None) as start:
            first = await main.start_xianyu_qr_login(
                XianyuQRStartPayload(client_request_id="new-account-request")
            )
            second = await main.start_xianyu_qr_login(
                XianyuQRStartPayload(client_request_id="new-account-request")
            )
            await main.qr_initialize_tasks[first.session_id]
        try:
            self.assertEqual(first.session_id, second.session_id)
            self.assertIsNone(main.qr_login_sessions[first.session_id].account_name)
            start.assert_called_once()
        finally:
            main._discard_qr_session(first.session_id)

    async def test_overlapping_polls_execute_only_one_platform_request(self) -> None:
        from apps.api.xianyu_admin_api import main

        session = QRLoginSession(
            account_id="account-single-flight",
            account_name="single-flight",
            proxy_id=None,
            proxy=ProxyConfigPayload(),
        )
        started = threading.Event()
        release = threading.Event()
        calls = 0

        def slow_poll(_: QRLoginSession) -> str:
            nonlocal calls
            calls += 1
            started.set()
            release.wait(timeout=2)
            return "pending"

        main.qr_login_sessions[session.session_id] = session
        main.qr_finalize_locks[session.session_id] = asyncio.Lock()
        main.qr_poll_locks[session.session_id] = asyncio.Lock()
        try:
            with patch.object(QRLoginSession, "poll", slow_poll):
                first = asyncio.create_task(main.poll_xianyu_qr_login(session.session_id))
                while not started.is_set():
                    await asyncio.sleep(0.01)
                second = await main.poll_xianyu_qr_login(session.session_id)
                release.set()
                await first
            self.assertEqual(second.status, "pending")
            self.assertEqual(calls, 1)
        finally:
            release.set()
            main._discard_qr_session(session.session_id)

    async def test_failed_validation_does_not_overwrite_existing_cookie(self) -> None:
        from apps.api.xianyu_admin_api import main

        session = _FailingFinalizeSession()
        fake_store = _StoreThatMustNotPersist()
        main.qr_login_sessions[session.session_id] = session  # type: ignore[assignment]
        main.qr_finalize_locks[session.session_id] = asyncio.Lock()
        try:
            with patch.object(main, "store", fake_store):
                result = await main.poll_xianyu_qr_login(session.session_id)
        finally:
            main._discard_qr_session(session.session_id)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error, "credential validation failed")
        self.assertFalse(fake_store.update_called)
        self.assertFalse(fake_store.create_called)
        self.assertEqual(fake_store.cookie, "old-cookie")


class QRBrowserVerificationManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_mismatched_existing_account_is_rejected_without_closing_browser(self) -> None:
        session = QRLoginSession(
            account_id="account-1",
            account_name="seller",
            proxy_id=None,
            proxy=ProxyConfigPayload(),
        )
        session.status = "browser_verification"

        async def browser_cookies(*_: object) -> list[dict[str, str]]:
            return []

        context = SimpleNamespace(cookies=browser_cookies)
        manager = IMVerificationManager(SimpleNamespace(), SimpleNamespace())
        verification_id = f"qr:{session.session_id}"
        manager._active = _ActiveSession(
            verification_id=verification_id,
            purpose="qr_login",
            account_id="account-1",
            context=context,
            page=SimpleNamespace(),
            bridge=None,
            expires_at=time.time() + 300,
        )
        manager._qr_verifications[session.session_id] = XianyuQRBrowserVerificationPayload(
            session_id=session.session_id,
            status="ready",
        )

        with (
            patch.object(
                QRLoginSession,
                "finalize_browser_credentials",
                return_value="unb=other-account; _m_h5_tk=token",
            ),
            self.assertRaisesRegex(IMVerificationError, "与当前账户不一致"),
        ):
            await manager.prepare_qr_login_completion(
                session,
                SimpleNamespace(cookie="unb=expected-account; _m_h5_tk=old"),
            )

        status = await manager.qr_status(session.session_id)
        self.assertEqual(status.status, "ready")
        self.assertIsNotNone(manager._active)


if __name__ == "__main__":
    unittest.main()
