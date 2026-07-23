"""Account-scoped browser and protocol identity helpers.

The fingerprint seed is consumed only by the browser binary.  Protocol clients
reuse the textual parts of the same identity (UA, language and DingTalk UA),
while TLS impersonation is selected separately from the browser major version.
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_BROWSER_VERSION = "133.0.0.0"


def normalize_browser_version(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return DEFAULT_BROWSER_VERSION
    parts = raw.split(".")
    if not parts[0].isdigit():
        return DEFAULT_BROWSER_VERSION
    normalized = [str(int(part)) if part.isdigit() else "0" for part in parts[:4]]
    while len(normalized) < 4:
        normalized.append("0")
    return ".".join(normalized)


def platform_user_agent_token(platform: str, platform_version: str) -> str:
    normalized = str(platform or "windows").lower()
    if normalized == "linux":
        return "X11; Linux x86_64"
    if normalized == "macos":
        version = str(platform_version or "14.0.0").replace(".", "_")
        return f"Macintosh; Intel Mac OS X {version}"
    # Chrome keeps the Windows NT token at 10.0 for Windows 10 and 11.
    return "Windows NT 10.0; Win64; x64"


def sec_ch_platform(platform: str) -> str:
    return {
        "linux": "Linux",
        "macos": "macOS",
        "windows": "Windows",
    }.get(str(platform or "").lower(), "Windows")


BRAND_UA_SUFFIX = {
    "Chrome": None,
    "Edge": "Edg",
    "Opera": "OPR",
    "Vivaldi": "Vivaldi",
}

BRAND_CLIENT_HINT = {
    "Chrome": "Google Chrome",
    "Edge": "Microsoft Edge",
    "Opera": "Opera",
    "Vivaldi": "Vivaldi",
}


@dataclass(frozen=True, slots=True)
class ClientIdentity:
    browser_engine: str = "system_chromium"
    browser_binary_source: str = "system"
    fingerprint_seed: int | None = None
    browser_version: str = DEFAULT_BROWSER_VERSION
    platform: str = "windows"
    platform_version: str = "10.0.0"
    brand: str = "Chrome"
    language: str = "zh-CN"
    accept_language: str = "zh-CN,zh;q=0.9,en;q=0.8"
    timezone: str = "Asia/Shanghai"
    hardware_concurrency: int | None = None
    spoof_canvas: bool = True
    spoof_webgl: bool = True
    spoof_audio: bool = True
    spoof_fonts: bool = True
    spoof_client_rects: bool = True
    webrtc_policy: str = "proxy_only"
    config_revision: int = 1

    @property
    def normalized_browser_version(self) -> str:
        return normalize_browser_version(self.browser_version)

    @property
    def browser_major(self) -> int:
        return int(self.normalized_browser_version.split(".", 1)[0])

    @property
    def user_agent(self) -> str:
        platform_token = platform_user_agent_token(self.platform, self.platform_version)
        base = (
            f"Mozilla/5.0 ({platform_token}) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{self.normalized_browser_version} Safari/537.36"
        )
        suffix = BRAND_UA_SUFFIX.get(self.brand)
        return (
            f"{base} {suffix}/{self.normalized_browser_version}"
            if suffix
            else base
        )

    @property
    def dingtalk_user_agent(self) -> str:
        os_name = {
            "linux": "Linux",
            "macos": "MacOS",
            "windows": "Windows",
        }.get(self.platform.lower(), "Windows")
        os_version = self.platform_version or "10"
        return (
            f"{self.user_agent} DingTalk(2.1.5) OS({os_name}/{os_version}) "
            f"Browser({self.brand}/{self.normalized_browser_version}) "
            "DingWeb/2.1.5 IMPaaS DingWeb/2.1.5"
        )

    @property
    def transport_profile(self) -> str:
        # TLS/HTTP2 identity follows the browser build, not the per-account seed.
        return f"chrome{self.browser_major}"

    @property
    def sec_ch_ua_platform(self) -> str:
        return sec_ch_platform(self.platform)

    @property
    def user_agent_brands(self) -> tuple[dict[str, str], ...]:
        major = str(self.browser_major)
        return (
            {"brand": "Not/A)Brand", "version": "8"},
            {"brand": "Chromium", "version": major},
            {"brand": BRAND_CLIENT_HINT.get(self.brand, self.brand), "version": major},
        )

    @property
    def sec_ch_ua(self) -> str:
        return ", ".join(
            f'"{item["brand"]}";v="{item["version"]}"'
            for item in self.user_agent_brands
        )

    @property
    def disabled_spoofing_modules(self) -> tuple[str, ...]:
        if self.browser_engine != "fingerprint_chromium" or self.browser_major < 144:
            return ()
        enabled = {
            "canvas": self.spoof_canvas,
            "gpu": self.spoof_webgl,
            "audio": self.spoof_audio,
            "font": self.spoof_fonts,
            "clientrects": self.spoof_client_rects,
        }
        return tuple(name for name, active in enabled.items() if not active)

    @property
    def restrict_webrtc_to_proxy(self) -> bool:
        return self.webrtc_policy in {
            "proxy_only",
            "disabled",
            "disable_non_proxied_udp",
        }

    @property
    def disable_webrtc(self) -> bool:
        return self.webrtc_policy == "disabled"


DEFAULT_CLIENT_IDENTITY = ClientIdentity()
