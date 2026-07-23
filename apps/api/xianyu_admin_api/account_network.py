"""Single policy boundary for account-scoped platform network routes."""

from __future__ import annotations

from typing import Literal, Protocol

from integrations.xianyu_core import ProxyConfig

from .schemas import ProxyConfigPayload


AccountNetworkMode = Literal["direct", "socks5"]


class AccountNetworkPolicyError(ValueError):
    """An account route is ambiguous or could silently bypass its binding."""


class AccountNetworkRecord(Protocol):
    proxy_id: str | None
    proxy: ProxyConfigPayload


def validate_account_network_route(
    proxy_id: str | None,
    proxy: ProxyConfigPayload,
) -> AccountNetworkMode:
    """Return the explicit route while rejecting hidden or broken proxy states."""

    if proxy_id is None:
        if proxy.enabled or any(
            value not in (None, "")
            for value in (proxy.host, proxy.port, proxy.username, proxy.password)
        ):
            raise AccountNetworkPolicyError(
                "账户存在未绑定代理节点的旧代理配置，禁止使用隐藏代理或自动直连；"
                "请在代理管理中重新绑定节点"
            )
        return "direct"

    if not proxy.enabled:
        raise AccountNetworkPolicyError("账户绑定代理已停用，禁止直连，不得回退本地网络")
    if proxy.scheme not in {"socks5", "socks5h"}:
        raise AccountNetworkPolicyError("账户绑定代理协议无效，仅支持 socks5/socks5h")
    if not proxy.host or not proxy.port:
        raise AccountNetworkPolicyError("账户绑定代理配置不完整，禁止直连，不得回退本地网络")
    return "socks5"


def account_network_mode(account: AccountNetworkRecord) -> AccountNetworkMode:
    return validate_account_network_route(account.proxy_id, account.proxy)


def build_core_account_proxy(account: AccountNetworkRecord) -> ProxyConfig:
    mode = account_network_mode(account)
    if mode == "direct":
        return ProxyConfig(enabled=False, required=False)
    return ProxyConfig(
        enabled=True,
        required=True,
        scheme=account.proxy.scheme,
        host=account.proxy.host or "",
        port=account.proxy.port,
        username=account.proxy.username,
        password=account.proxy.password,
    )
