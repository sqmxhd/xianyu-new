"""SOCKS proxy helpers for account-scoped outbound traffic."""

from __future__ import annotations

from urllib.parse import quote

from .models import ProxyConfig


SUPPORTED_SOCKS_SCHEMES = {"socks5", "socks5h"}


def build_socks_proxy_url(proxy: ProxyConfig | None) -> str | None:
    """Build a websockets/python-socks compatible SOCKS proxy URL.

    Returns ``None`` when the proxy is disabled. Raises ``ValueError`` for
    incomplete or unsupported proxy settings so callers can mark the account as
    ``proxy_failed`` instead of silently falling back to direct networking.
    """

    if proxy is None:
        return None
    if not proxy.enabled:
        if proxy.required:
            raise ValueError("bound proxy is disabled")
        return None

    scheme = (proxy.scheme or "socks5h").lower()
    if scheme not in SUPPORTED_SOCKS_SCHEMES:
        raise ValueError(f"unsupported proxy scheme: {proxy.scheme!r}")
    if not proxy.host:
        raise ValueError("proxy host is required")
    if not proxy.port:
        raise ValueError("proxy port is required")

    auth = ""
    if proxy.username:
        auth = quote(proxy.username, safe="")
        if proxy.password:
            auth += f":{quote(proxy.password, safe='')}"
        auth += "@"

    return f"{scheme}://{auth}{proxy.host}:{proxy.port}"
