import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests
from pydantic import ValidationError

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from apps.api.xianyu_admin_api.account_network import (
    AccountNetworkPolicyError,
    build_core_account_proxy,
    validate_account_network_route,
)
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    AccountUpdatePayload,
    ProxyConfigPayload,
)
from integrations.xianyu_core.client import XianyuAccountSession
from integrations.xianyu_core.models import AccountConfig, ProxyConfig


class _FakeXianyuApis:
    def __init__(self, _cookies: dict[str, str], _device_id: str) -> None:
        self.session = requests.Session()


def _upstream() -> SimpleNamespace:
    return SimpleNamespace(
        trans_cookies=lambda _cookie: {"unb": "seller-1"},
        XianyuApis=_FakeXianyuApis,
    )


class AccountNetworkPolicyTests(unittest.TestCase):
    def test_unbound_account_is_explicit_direct(self) -> None:
        account = SimpleNamespace(proxy_id=None, proxy=ProxyConfigPayload())

        proxy = build_core_account_proxy(account)

        self.assertFalse(proxy.enabled)
        self.assertFalse(proxy.required)

    def test_bound_account_builds_required_proxy(self) -> None:
        account = SimpleNamespace(
            proxy_id="proxy-1",
            proxy=ProxyConfigPayload(
                enabled=True,
                scheme="socks5h",
                host="127.0.0.1",
                port=1080,
            ),
        )

        proxy = build_core_account_proxy(account)

        self.assertTrue(proxy.enabled)
        self.assertTrue(proxy.required)
        self.assertEqual(proxy.scheme, "socks5h")

    def test_bound_disabled_proxy_cannot_become_direct(self) -> None:
        with self.assertRaisesRegex(AccountNetworkPolicyError, "禁止直连"):
            validate_account_network_route(
                "proxy-1",
                ProxyConfigPayload(enabled=False),
            )

    def test_unbound_inline_proxy_is_rejected(self) -> None:
        with self.assertRaisesRegex(AccountNetworkPolicyError, "旧代理配置"):
            validate_account_network_route(
                None,
                ProxyConfigPayload(enabled=True, host="127.0.0.1", port=1080),
            )

    def test_account_input_only_accepts_managed_proxy_id(self) -> None:
        with self.assertRaisesRegex(ValidationError, "proxy_id"):
            AccountCreatePayload(proxy=ProxyConfigPayload(enabled=True, host="127.0.0.1", port=1080),
            )
        with self.assertRaisesRegex(ValidationError, "proxy_id"):
            AccountUpdatePayload(proxy=ProxyConfigPayload())


class AccountWebSocketRouteTests(unittest.TestCase):
    def _connect_proxy(self, proxy: ProxyConfig) -> str | None:
        captured: dict[str, object] = {}

        def connect(
            _url: str,
            *,
            additional_headers: dict[str, str] | None = None,
            proxy: str | None = None,
            ping_interval: int,
            ping_timeout: int,
            open_timeout: int,
            close_timeout: int,
        ) -> object:
            captured["proxy"] = proxy
            return object()

        session = XianyuAccountSession(
            AccountConfig(account_id="account-1", cookie="unb=seller-1", proxy=proxy),
            _upstream(),
        )
        try:
            with patch.dict("sys.modules", {"websockets": SimpleNamespace(connect=connect)}):
                session._connect({})
        finally:
            session.xianyu.session.close()
        return captured.get("proxy")  # type: ignore[return-value]

    def test_direct_websocket_disables_environment_proxy_discovery(self) -> None:
        self.assertIsNone(self._connect_proxy(ProxyConfig()))

    def test_bound_websocket_uses_required_socks_proxy(self) -> None:
        self.assertEqual(
            self._connect_proxy(
                ProxyConfig(
                    enabled=True,
                    required=True,
                    scheme="socks5h",
                    host="127.0.0.1",
                    port=1080,
                )
            ),
            "socks5h://127.0.0.1:1080",
        )


if __name__ == "__main__":
    unittest.main()
