"""Resolve persisted account browser settings into one effective client identity."""

from __future__ import annotations

from integrations.xianyu_core.identity import ClientIdentity

from .browser_binaries import browser_binary_manager
from .schemas import AccountBrowserIdentityPayload


def resolve_client_identity(raw: AccountBrowserIdentityPayload) -> ClientIdentity:
    effective_version = browser_binary_manager.effective_version(
        raw.browser_engine,
        raw.browser_version,
    )
    return ClientIdentity(
        browser_engine=raw.browser_engine,
        browser_binary_source=(
            "fingerprint"
            if raw.browser_engine == "fingerprint_chromium"
            else "managed" if raw.browser_version else "system"
        ),
        fingerprint_seed=raw.fingerprint_seed,
        browser_version=effective_version or raw.browser_version or "133.0.0.0",
        platform=raw.platform,
        platform_version=raw.platform_version,
        brand=raw.brand,
        language=raw.language,
        accept_language=raw.accept_language,
        timezone=raw.timezone,
        hardware_concurrency=raw.hardware_concurrency,
        spoof_canvas=raw.spoof_canvas,
        spoof_webgl=raw.spoof_webgl,
        spoof_audio=raw.spoof_audio,
        spoof_fonts=raw.spoof_fonts,
        spoof_client_rects=raw.spoof_client_rects,
        webrtc_policy=raw.webrtc_policy,
        config_revision=raw.config_revision,
    )
