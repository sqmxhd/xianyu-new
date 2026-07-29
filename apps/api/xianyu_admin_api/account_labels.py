"""Canonical display labels for platform accounts."""

from __future__ import annotations


def platform_account_display_name(
    account_id: str,
    platform_display_name: str | None,
    platform: str | None = "xianyu",
) -> str:
    """Return the platform nickname or a stable, non-editable fallback."""

    normalized = str(platform_display_name or "").strip()
    if normalized:
        return normalized
    platform_name = "闲鱼" if str(platform or "").strip().lower() == "xianyu" else "平台"
    return f"{platform_name}账户-{str(account_id or '')[:8]}"
