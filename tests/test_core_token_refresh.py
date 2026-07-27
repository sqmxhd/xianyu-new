import unittest

import requests

from integrations.xianyu_core.client import (
    AuthenticationExpiredError,
    RiskControlError,
    XianyuAccountSession,
)
from integrations.xianyu_core.models import AccountConfig, ConnectionState


class _TokenApi:
    response = {"ret": ["SUCCESS::调用成功"]}

    def __init__(self, cookies: dict[str, str], _device_id: str) -> None:
        self.session = requests.Session()
        self.session.cookies.update(cookies)

    def refresh_token(self):  # type: ignore[no-untyped-def]
        self.session.cookies.set("_m_h5_tk", "renewed-token")
        return self.response

    def get_token(self):  # type: ignore[no-untyped-def]
        return self.response


class _TokenUpstream:
    XianyuApis = _TokenApi

    @staticmethod
    def trans_cookies(cookie: str) -> dict[str, str]:
        return dict(item.strip().split("=", 1) for item in cookie.split(";") if "=" in item)

    @staticmethod
    def generate_device_id(_user_id: str) -> str:
        return "device-id"

    @staticmethod
    def get_session_cookies_str(session: requests.Session) -> str:
        return "; ".join(f"{name}={value}" for name, value in session.cookies.get_dict().items())


class CoreTokenRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_validates_and_reports_changed_cookie(self) -> None:
        callbacks: list[tuple[str, str, str]] = []
        session = XianyuAccountSession(
            AccountConfig("account-1", "unb=seller-1; _m_h5_tk=old-token"),
            _TokenUpstream(),
        )

        async def on_cookie(account_id: str, expected: str, renewed: str) -> None:
            callbacks.append((account_id, expected, renewed))

        session._on_cookie = on_cookie
        await session.refresh_token()

        self.assertEqual(callbacks[0][0], "account-1")
        self.assertIn("old-token", callbacks[0][1])
        self.assertIn("renewed-token", callbacks[0][2])

    async def test_refresh_rejects_business_failure(self) -> None:
        original_response = _TokenApi.response
        _TokenApi.response = {"ret": ["FAIL_SYS_SESSION_EXPIRED::登录已过期"]}
        try:
            session = XianyuAccountSession(
                AccountConfig("account-1", "unb=seller-1; _m_h5_tk=old-token"),
                _TokenUpstream(),
            )
            with self.assertRaisesRegex(RuntimeError, "token refresh rejected"):
                await session.refresh_token()
        finally:
            _TokenApi.response = original_response

    async def test_replace_cookie_rejects_different_account(self) -> None:
        session = XianyuAccountSession(
            AccountConfig("account-1", "unb=seller-1; _m_h5_tk=old-token"),
            _TokenUpstream(),
        )
        with self.assertRaisesRegex(ValueError, "different account"):
            await session.replace_cookie("unb=seller-2; _m_h5_tk=new-token")

    async def test_im_token_risk_response_preserves_verification_url(self) -> None:
        original_response = _TokenApi.response
        _TokenApi.response = {
            "ret": ["FAIL_SYS_USER_VALIDATE::需要安全验证"],
            "data": {"url": "https://passport.goofish.com/verify?id=secret"},
        }
        try:
            session = XianyuAccountSession(
                AccountConfig("account-1", "unb=seller-1; _m_h5_tk=old-token"),
                _TokenUpstream(),
            )
            with self.assertRaises(RiskControlError) as raised:
                await session._get_im_token()
            self.assertEqual(raised.exception.verification.account_id, "account-1")
            self.assertEqual(
                raised.exception.verification.reason_code,
                "FAIL_SYS_USER_VALIDATE",
            )
            self.assertEqual(
                raised.exception.verification.verification_url,
                "https://passport.goofish.com/verify?id=secret",
            )
            self.assertNotIn("passport.goofish.com", str(raised.exception))
        finally:
            _TokenApi.response = original_response

    async def test_im_token_session_expiry_is_terminal_auth_error(self) -> None:
        original_response = _TokenApi.response
        _TokenApi.response = {"ret": ["FAIL_SYS_SESSION_EXPIRED::登录已过期"]}
        try:
            session = XianyuAccountSession(
                AccountConfig("account-1", "unb=seller-1; _m_h5_tk=old-token"),
                _TokenUpstream(),
            )
            with self.assertRaises(AuthenticationExpiredError):
                await session._get_im_token()
        finally:
            _TokenApi.response = original_response

    async def test_im_token_url_in_network_error_is_not_auth_expired(self) -> None:
        session = XianyuAccountSession(
            AccountConfig("account-1", "unb=seller-1; _m_h5_tk=old-token"),
            _TokenUpstream(),
        )

        state = session._classify_connection_error(
            requests.exceptions.SSLError(
                "HTTPSConnectionPool(host='h5api.m.goofish.com', "
                "url='/h5/mtop.taobao.idlemessage.pc.login.token/1.0/'): "
                "UNEXPECTED_EOF_WHILE_READING"
            )
        )

        self.assertEqual(state, ConnectionState.ERROR)

    async def test_explicit_im_auth_exception_remains_auth_expired(self) -> None:
        session = XianyuAccountSession(
            AccountConfig("account-1", "unb=seller-1; _m_h5_tk=old-token"),
            _TokenUpstream(),
        )

        state = session._classify_connection_error(
            AuthenticationExpiredError("IM access token session expired")
        )

        self.assertEqual(state, ConnectionState.AUTH_EXPIRED)


if __name__ == "__main__":
    unittest.main()
