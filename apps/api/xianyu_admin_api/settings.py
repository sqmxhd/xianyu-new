"""Application settings for the Xianyu admin API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """Environment-backed settings.

    ``XIANYU_DATABASE_URL`` accepts any SQLAlchemy URL. Production should use
    MySQL, for example:

    ``mysql+pymysql://user:password@127.0.0.1:3306/xianyu_admin?charset=utf8mb4``
    """

    database_url: str = required_env("XIANYU_DATABASE_URL")
    jwt_secret: str = required_env("XIANYU_JWT_SECRET")
    jwt_expires_minutes: int = int(os.getenv("XIANYU_JWT_EXPIRES_MINUTES", "10080"))
    redis_url: str = required_env("XIANYU_REDIS_URL")
    api_health_url: str = os.getenv("XIANYU_API_HEALTH_URL", "http://127.0.0.1:8000/api/health")
    internal_api_url: str = os.getenv(
        "XIANYU_INTERNAL_API_URL", "http://127.0.0.1:8000"
    ).rstrip("/")
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv(
            "XIANYU_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if item.strip()
    )
    trusted_proxy_ips: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("XIANYU_TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
        if item.strip()
    )
    cookie_renewal_enabled: bool = env_bool("XIANYU_COOKIE_RENEWAL_ENABLED", True)
    cookie_renewal_interval_hours: float = float(
        os.getenv("XIANYU_COOKIE_RENEWAL_INTERVAL_HOURS", "1")
    )
    cookie_keepalive_interval_seconds: int = int(
        os.getenv("XIANYU_COOKIE_KEEPALIVE_INTERVAL_SECONDS", "600")
    )
    cookie_renewal_scan_seconds: int = int(
        os.getenv("XIANYU_COOKIE_RENEWAL_SCAN_SECONDS", "60")
    )
    cookie_renewal_manual_cooldown_seconds: int = int(
        os.getenv("XIANYU_COOKIE_RENEWAL_MANUAL_COOLDOWN_SECONDS", "3600")
    )
    conversation_sync_interval_seconds: int = int(
        os.getenv("XIANYU_CONVERSATION_SYNC_INTERVAL_SECONDS", "180")
    )
    conversation_full_sync_max_pages: int = max(
        1, int(os.getenv("XIANYU_CONVERSATION_FULL_SYNC_MAX_PAGES", "50"))
    )
    qr_login_workers: int = min(
        4, max(1, int(os.getenv("XIANYU_QR_LOGIN_WORKERS", "2")))
    )
    qr_login_max_active_sessions: int = min(
        8, max(1, int(os.getenv("XIANYU_QR_LOGIN_MAX_ACTIVE_SESSIONS", "4")))
    )
    db_blocking_workers: int = min(
        16, max(1, int(os.getenv("XIANYU_DB_BLOCKING_WORKERS", "6")))
    )
    db_blocking_queue: int = min(
        512, max(0, int(os.getenv("XIANYU_DB_BLOCKING_QUEUE", "64")))
    )
    platform_blocking_workers: int = min(
        16, max(1, int(os.getenv("XIANYU_PLATFORM_BLOCKING_WORKERS", "8")))
    )
    platform_blocking_queue: int = min(
        200, max(0, int(os.getenv("XIANYU_PLATFORM_BLOCKING_QUEUE", "40")))
    )
    media_blocking_workers: int = min(
        8, max(1, int(os.getenv("XIANYU_MEDIA_BLOCKING_WORKERS", "3")))
    )
    media_blocking_queue: int = min(
        100, max(0, int(os.getenv("XIANYU_MEDIA_BLOCKING_QUEUE", "12")))
    )
    external_blocking_workers: int = min(
        8, max(1, int(os.getenv("XIANYU_EXTERNAL_BLOCKING_WORKERS", "4")))
    )
    external_blocking_queue: int = min(
        100, max(0, int(os.getenv("XIANYU_EXTERNAL_BLOCKING_QUEUE", "20")))
    )
    browser_blocking_workers: int = min(
        4, max(1, int(os.getenv("XIANYU_BROWSER_BLOCKING_WORKERS", "2")))
    )
    browser_blocking_queue: int = min(
        20, max(0, int(os.getenv("XIANYU_BROWSER_BLOCKING_QUEUE", "8")))
    )
    runtime_start_concurrency: int = min(
        10, max(1, int(os.getenv("XIANYU_RUNTIME_START_CONCURRENCY", "3")))
    )
    runtime_start_jitter_seconds: float = max(
        0.0, float(os.getenv("XIANYU_RUNTIME_START_JITTER_SECONDS", "3"))
    )
    conversation_sync_concurrency: int = min(
        10, max(1, int(os.getenv("XIANYU_CONVERSATION_SYNC_CONCURRENCY", "3")))
    )
    cookie_renewal_concurrency: int = min(
        4, max(1, int(os.getenv("XIANYU_COOKIE_RENEWAL_CONCURRENCY", "2")))
    )
    worker_concurrency: int = min(
        16, max(1, int(os.getenv("XIANYU_WORKER_CONCURRENCY", "4")))
    )
    worker_lease_seconds: int = min(
        900, max(30, int(os.getenv("XIANYU_WORKER_LEASE_SECONDS", "120")))
    )
    worker_lease_renew_seconds: int = min(
        300, max(5, int(os.getenv("XIANYU_WORKER_LEASE_RENEW_SECONDS", "30")))
    )
    event_loop_monitor_interval_seconds: float = max(
        0.2, float(os.getenv("XIANYU_EVENT_LOOP_MONITOR_INTERVAL_SECONDS", "1"))
    )
    event_loop_lag_warning_seconds: float = max(
        0.05, float(os.getenv("XIANYU_EVENT_LOOP_LAG_WARNING_SECONDS", "0.5"))
    )
    proxy_ip_check_urls: tuple[str, ...] = tuple(
        dict.fromkeys(
            item
            for item in (
                *(
                    value.strip()
                    for value in os.getenv("XIANYU_PROXY_IP_CHECK_URLS", "").split(",")
                    if value.strip()
                ),
                os.getenv("XIANYU_PROXY_IP_CHECK_URL", "").strip(),
                "https://ipinfo.io/ip",
                "https://api64.ipify.org?format=json",
                "https://api6.ipify.org?format=json",
            )
            if item
        )
    )
    ip2region_db_path: str = os.getenv(
        "XIANYU_IP2REGION_DB_PATH",
        str(Path(__file__).resolve().parent / "data" / "ip2region_v4.xdb"),
    )
    geoip_db_path: str = os.getenv(
        "XIANYU_GEOIP_DB_PATH",
        str(Path(__file__).resolve().parent / "data" / "geoip.db"),
    )
    product_image_dir: str = os.getenv(
        "XIANYU_PRODUCT_IMAGE_DIR",
        str(Path(__file__).resolve().parents[3] / "data" / "product-images"),
    )
    im_verification_browser_enabled: bool = env_bool(
        "XIANYU_IM_VERIFICATION_BROWSER_ENABLED", True
    )
    im_verification_browser_path: str = os.getenv(
        "XIANYU_IM_VERIFICATION_BROWSER_PATH", ""
    ).strip()
    fingerprint_browser_root: str = os.getenv(
        "XIANYU_FINGERPRINT_BROWSER_ROOT",
        str(Path(__file__).resolve().parents[3] / "third_party" / "fingerprint-chromium"),
    ).strip()
    standard_browser_root: str = os.getenv(
        "XIANYU_STANDARD_BROWSER_ROOT",
        str(Path(__file__).resolve().parents[3] / "third_party" / "standard-chromium"),
    ).strip()
    fingerprint_browser_download_timeout_seconds: int = int(
        os.getenv("XIANYU_FINGERPRINT_BROWSER_DOWNLOAD_TIMEOUT_SECONDS", "600")
    )
    fingerprint_browser_max_archive_bytes: int = int(
        os.getenv("XIANYU_FINGERPRINT_BROWSER_MAX_ARCHIVE_BYTES", str(512 * 1024 * 1024))
    )
    fingerprint_browser_max_extracted_bytes: int = int(
        os.getenv("XIANYU_FINGERPRINT_BROWSER_MAX_EXTRACTED_BYTES", str(1024 * 1024 * 1024))
    )
    im_verification_profile_dir: str = os.getenv(
        "XIANYU_IM_VERIFICATION_PROFILE_DIR",
        str(Path(__file__).resolve().parents[3] / "data" / "browser-profiles"),
    )
    im_verification_display: str = os.getenv(
        "XIANYU_IM_VERIFICATION_DISPLAY", ":99"
    ).strip()
    im_verification_vnc_port: int = int(
        os.getenv("XIANYU_IM_VERIFICATION_VNC_PORT", "5901")
    )
    im_verification_session_seconds: int = int(
        os.getenv("XIANYU_IM_VERIFICATION_SESSION_SECONDS", "600")
    )
    account_browser_idle_seconds: int = max(
        60,
        int(
            os.getenv(
                "XIANYU_ACCOUNT_BROWSER_IDLE_SECONDS",
                os.getenv("XIANYU_ACCOUNT_BROWSER_SESSION_SECONDS", "1800"),
            )
        ),
    )
    account_browser_max_session_seconds: int = max(
        account_browser_idle_seconds,
        int(os.getenv("XIANYU_ACCOUNT_BROWSER_MAX_SESSION_SECONDS", "28800")),
    )
    # Backward-compatible alias for deployments and tests that still reference
    # the former fixed-duration setting.
    account_browser_session_seconds: int = account_browser_idle_seconds
    account_browser_max_sessions: int = min(
        8, max(1, int(os.getenv("XIANYU_ACCOUNT_BROWSER_MAX_SESSIONS", "3")))
    )
    account_browser_cdp_enabled: bool = env_bool(
        "XIANYU_ACCOUNT_BROWSER_CDP_ENABLED", True
    )
    account_browser_cdp_port: int = int(
        os.getenv("XIANYU_ACCOUNT_BROWSER_CDP_PORT", "9222")
    )
    browser_fingerprint_probe_stun_url: str = os.getenv(
        "XIANYU_BROWSER_FINGERPRINT_PROBE_STUN_URL", ""
    ).strip()
    browser_fingerprint_proxy_exit_ttl_seconds: int = max(
        60,
        int(os.getenv("XIANYU_BROWSER_FINGERPRINT_PROXY_EXIT_TTL_SECONDS", "600")),
    )
    im_verification_allow_no_sandbox: bool = env_bool(
        "XIANYU_IM_VERIFICATION_ALLOW_NO_SANDBOX", False
    )


settings = Settings()
