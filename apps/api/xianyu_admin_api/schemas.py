"""API schemas for the phase-1 web admin backend."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, field_validator, model_validator


class BaseModel(PydanticBaseModel):
    """API model base that makes every datetime an explicit UTC instant."""

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def normalize_datetime_to_utc(cls, value: object) -> object:
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


MessageDirection = Literal["inbound", "outbound"]
MessageType = Literal["text", "image", "audio", "card", "system", "unknown"]
MessageSendStatus = Literal["uploading", "sending", "sent", "failed"]
BrowserEngine = Literal["system_chromium", "fingerprint_chromium"]
BrowserBrand = Literal["Chrome", "Edge", "Opera", "Vivaldi"]
WebRTCPolicy = Literal["proxy_only", "disabled", "browser_default"]
BrowserFingerprintDetectionStatus = Literal["pending", "collecting", "ready", "failed"]
DeliveryStatus = Literal["pending", "sending", "sent", "failed", "uncertain", "cancelled"]
DeliveryAutomationMode = Literal["manual_only", "ws_text", "platform_api"]


class BrowserFingerprintSnapshotPayload(BaseModel):
    schema_version: int = Field(default=3, ge=1)
    browser_engine: BrowserEngine
    browser_version: str
    target_platform: Literal["windows", "linux", "macos"]
    brand: BrowserBrand = "Chrome"
    observed_platform: str | None = None
    user_agent: str
    ua_ch_platform: str | None = None
    ua_ch_brands: list[str] = Field(default_factory=list)
    language: str | None = None
    languages: list[str] = Field(default_factory=list)
    accept_language: str = ""
    timezone: str | None = None
    hardware_concurrency: int | None = None
    device_memory: float | None = None
    canvas_hash: str | None = None
    webgl_vendor: str | None = None
    webgl_renderer: str | None = None
    webgl_hash: str | None = None
    audio_hash: str | None = None
    fonts_hash: str | None = None
    detected_fonts: list[str] = Field(default_factory=list)
    client_rects_hash: str | None = None
    spoof_canvas: bool = True
    spoof_webgl: bool = True
    spoof_audio: bool = True
    spoof_fonts: bool = True
    spoof_client_rects: bool = True
    webrtc_policy: WebRTCPolicy = "proxy_only"
    webrtc_candidate_types: list[str] = Field(default_factory=list)
    webrtc_api_available: bool | None = None
    webrtc_blocked: bool = False
    webrtc_gathering_state: str | None = None
    webrtc_private_candidate_detected: bool = False
    webrtc_public_candidate_detected: bool = False
    webrtc_proxy_match: bool | None = None
    webrtc_probe_configured: bool = False
    browser_egress_ips: list[str] = Field(default_factory=list)
    proxy_expected_ips: list[str] = Field(default_factory=list)
    browser_egress_match: bool | None = None
    browser_egress_probe_source: str | None = None
    navigator_webdriver: bool | None = None
    automation_window_markers: list[str] = Field(default_factory=list)
    has_window_chrome: bool | None = None
    plugins_count: int | None = None
    notification_permission: str | None = None
    iframe_webdriver: bool | None = None
    worker_webdriver: bool | None = None
    cdp_stack_probe_detected: bool | None = None
    automation_protection_level: Literal[
        "fingerprint_kernel", "system_compatibility"
    ] = "system_compatibility"
    risk_status: Literal["pass", "warning", "risk", "inconclusive"] = "inconclusive"
    risk_findings: list[str] = Field(default_factory=list)
    config_revision: int = Field(ge=1)
    stability_status: Literal["baseline", "stable", "changed"] = "baseline"
    changed_fields: list[str] = Field(default_factory=list)
    observed_at: datetime


class AccountBrowserIdentityPayload(BaseModel):
    browser_engine: BrowserEngine = "system_chromium"
    fingerprint_seed: int | None = Field(default=None, ge=1, le=4_294_967_295)
    browser_version: str | None = Field(default=None, max_length=64)
    platform: Literal["windows", "linux", "macos"] = "windows"
    platform_version: str = Field(default="10.0.0", max_length=32)
    brand: BrowserBrand = "Chrome"
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    accept_language: str = Field(
        default="zh-CN,zh;q=0.9,en;q=0.8", min_length=2, max_length=160
    )
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    hardware_concurrency: Literal[4, 8, 12, 16] | None = None
    spoof_canvas: bool = True
    spoof_webgl: bool = True
    spoof_audio: bool = True
    spoof_fonts: bool = True
    spoof_client_rects: bool = True
    webrtc_policy: WebRTCPolicy = "proxy_only"
    config_revision: int = Field(default=1, ge=1)
    user_agent: str | None = None
    dingtalk_user_agent: str | None = None
    transport_profile: str | None = None
    fingerprint_snapshot: BrowserFingerprintSnapshotPayload | None = None

    @field_validator(
        "browser_version",
        "platform_version",
        "language",
        "accept_language",
        "timezone",
        mode="before",
    )
    @classmethod
    def normalize_identity_string(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("webrtc_policy", mode="before")
    @classmethod
    def normalize_legacy_webrtc_policy(cls, value: object) -> object:
        if value == "disable_non_proxied_udp":
            return "proxy_only"
        return value

    @model_validator(mode="after")
    def validate_fingerprint_seed(self) -> "AccountBrowserIdentityPayload":
        if self.browser_engine == "fingerprint_chromium" and self.fingerprint_seed is None:
            raise ValueError("Fingerprint Chromium 必须配置稳定指纹 Seed")
        return self

    def writable_copy(self) -> "AccountBrowserIdentityPayload":
        return self.model_copy(
            update={
                "user_agent": None,
                "dingtalk_user_agent": None,
                "transport_profile": None,
                "fingerprint_snapshot": None,
            }
        )
MessageCardType = Literal["product", "order"]
OrderStatus = Literal[
    "pending_payment",
    "waiting_seller_delivery",
    "paid_waiting_delivery",
    "shipped",
    "completed",
    "closed",
    "refunding",
    "refunded",
    "unknown",
]
OrderTradeRole = Literal["seller", "buyer", "unknown"]
OrderSyncState = Literal["provisional", "confirmed", "stale", "error"]
OrderAction = Literal[
    "confirm_shipping",
    "offline_shipping",
    "free_shipping",
    "close_order",
    "rate_buyer",
    "refuse_refund",
]
OrderOperationStatus = Literal["processing", "succeeded", "failed", "uncertain"]
OrderSyncMode = Literal["full", "pending"]
OrderSyncScope = Literal["bought", "sold"]
ProductDraftStatus = Literal["draft", "ready", "archived"]
ProductLocationMode = Literal["account_default", "region", "selected", "group_random"]
ProductPublishMode = Literal["manual_export", "platform_api", "browser_automation"]
ProductDeliveryChoice = Literal["free_shipping", "distance", "fixed", "pickup_only"]
ProductPublishTaskStatus = Literal[
    "pending",
    "running",
    "success",
    "verification_required",
    "failed",
    "cancelled",
]
BackgroundTaskStatus = Literal["pending", "running", "success", "failed", "cancelled"]
UserRole = Literal["admin", "operator", "viewer"]
AutoReplyMatchStrategy = Literal["priority_first", "first_created", "all_join"]
RuntimeState = Literal[
    "disabled",
    "deleting",
    "stopped",
    "connecting",
    "online",
    "reconnecting",
    "offline",
    "auth_expired",
    "risk_blocked",
    "proxy_failed",
    "error",
]
AccountNetworkMode = Literal["direct", "socks5"]
RuntimeRecoveryAction = Literal[
    "none",
    "reconnect",
    "verify",
    "relogin",
    "fix_proxy",
]
IMVerificationState = Literal[
    "required",
    "starting",
    "ready",
    "completing",
    "completed",
    "failed",
    "expired",
    "cancelled",
]
BrowserVerificationState = Literal[
    "idle",
    "starting",
    "ready",
    "completing",
    "completed",
    "failed",
    "expired",
    "cancelled",
]
AccountBrowserState = Literal[
    "starting",
    "ready",
    "closing",
    "closed",
    "expired",
    "failed",
]
AccountBrowserCookieCheckState = Literal[
    "not_checked",
    "valid",
    "invalid",
    "unknown",
]
AccountBrowserCookieSyncState = Literal[
    "pending",
    "updated_from_browser",
    "refreshed_from_browser",
    "kept_local",
    "auth_recovery",
    "account_mismatch",
    "unknown",
    "failed",
]


def _validate_product_money(name: str, value: str | None, *, required: bool = False) -> None:
    if value in (None, ""):
        if required:
            raise ValueError(f"{name} 不能为空")
        return
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} 格式无效") from exc
    if amount < 0 or (required and amount <= 0):
        raise ValueError(f"{name} 必须大于 0" if required else f"{name} 不能小于 0")


class UserPayload(BaseModel):
    user_id: str
    username: str
    role: UserRole = "operator"
    enabled: bool = True
    privacy_mask_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
    last_login_ip: str | None = None
    last_login_source: str | None = None


class UserCreatePayload(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)
    role: UserRole = "operator"
    enabled: bool = True

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UserUpdatePayload(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=200)
    role: UserRole | None = None
    enabled: bool | None = None


class UserPreferenceUpdatePayload(BaseModel):
    privacy_mask_enabled: bool


class AuthLoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AuthBootstrapPayload(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AuthTokenPayload(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPayload


class RealtimeTicketPayload(BaseModel):
    ticket: str
    expires_in: int = 30


class ClientAccessPayload(BaseModel):
    ip: str | None = None
    source: str
    remote_addr: str | None = None
    cf_connecting_ip: str | None = None
    true_client_ip: str | None = None
    x_real_ip: str | None = None
    x_forwarded_for: str | None = None


class AuthSetupStatusPayload(BaseModel):
    initialized: bool
    client: ClientAccessPayload


class XianyuQRStartPayload(BaseModel):
    account_id: str | None = Field(default=None, max_length=64)
    remark: str | None = Field(default=None, max_length=500)
    client_request_id: str | None = Field(default=None, max_length=128)
    proxy_id: str | None = Field(default=None, max_length=64)
    browser_identity: AccountBrowserIdentityPayload | None = None

    @field_validator(
        "account_id",
        "remark",
        "client_request_id",
        "proxy_id",
        mode="before",
    )
    @classmethod
    def normalize_qr_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class XianyuQRStatusPayload(BaseModel):
    session_id: str
    status: Literal[
        "initializing",
        "pending",
        "scanned",
        "verification_required",
        "browser_verification",
        "finalizing",
        "completed",
        "expired",
        "error",
    ]
    code_content: str | None = None
    face_code_content: str | None = None
    challenge_type: Literal["none", "face", "slider", "interactive", "unknown"] = "none"
    expires_in: int
    account_id: str | None = None
    runtime_state: RuntimeState | None = None
    error: str | None = None


class XianyuQRBrowserVerificationPayload(BaseModel):
    session_id: str
    status: BrowserVerificationState = "idle"
    message: str | None = None
    expires_at: datetime | None = None
    browser_available: bool = False
    browser_error: str | None = None
    vnc_available: bool = False


class AccountBrowserSessionPayload(BaseModel):
    session_id: str
    account_id: str
    status: AccountBrowserState
    message: str | None = None
    current_url: str | None = None
    proxy_enabled: bool = False
    browser_available: bool = False
    browser_error: str | None = None
    vnc_available: bool = False
    cdp_available: bool = False
    cookie_sync_status: AccountBrowserCookieSyncState = "pending"
    browser_cookie_status: AccountBrowserCookieCheckState = "not_checked"
    local_cookie_status: AccountBrowserCookieCheckState = "not_checked"
    fingerprint_snapshot: BrowserFingerprintSnapshotPayload | None = None
    fingerprint_detection_status: BrowserFingerprintDetectionStatus = "pending"
    fingerprint_detection_error: str | None = None
    started_at: datetime | None = None
    last_activity_at: datetime | None = None
    idle_expires_at: datetime | None = None
    max_expires_at: datetime | None = None
    expires_at: datetime | None = None


class AccountBrowserTextPastePayload(BaseModel):
    text: str = Field(max_length=20_000)

    @field_validator("text")
    @classmethod
    def require_visible_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("粘贴内容不能为空")
        return value


class BrowserProfileCleanupPayload(BaseModel):
    account_id: str
    deleted: bool
    message: str


class BrowserProfilePayload(BaseModel):
    profile_key: str
    directory_name: str
    profile_type: Literal["account", "qr", "orphan"]
    account_id: str | None = None
    account_name: str | None = None
    account_exists: bool = False
    size_bytes: int = 0
    created_at: datetime
    updated_at: datetime
    status: Literal["running", "stopped", "busy", "orphaned", "temporary"]
    session_id: str | None = None
    session_purpose: str | None = None
    vnc_available: bool = False
    current_url: str | None = None
    manageable: bool = True
    browser_engine: BrowserEngine | None = None
    config_revision: int | None = None


class BrowserProfileActionPayload(BaseModel):
    profile_key: str
    stopped: bool = False
    deleted: bool = False
    message: str


class BrowserBinaryPayload(BaseModel):
    version: str
    executable_path: str
    source: Literal["upload", "download", "bundled", "unknown"] = "unknown"
    sha256: str | None = None
    size_bytes: int = 0
    installed_at: datetime | None = None
    active: bool = False
    valid: bool = True
    validation_message: str | None = None


class SystemBrowserPayload(BaseModel):
    executable_path: str | None = None
    version: str | None = None
    available: bool = False
    validation_message: str | None = None


class BrowserRuntimeSettingPayload(BaseModel):
    root_directory: str
    standard_root_directory: str
    system_browser: SystemBrowserPayload
    standard_browsers: list[BrowserBinaryPayload] = Field(default_factory=list)
    active_standard_version: str | None = None
    fingerprint_browsers: list[BrowserBinaryPayload] = Field(default_factory=list)
    active_fingerprint_version: str | None = None
    official_project_url: str = "https://github.com/adryfish/fingerprint-chromium"
    official_standard_project_url: str = (
        "https://github.com/GoogleChromeLabs/chrome-for-testing"
    )
    active_vnc_account_id: str | None = None
    active_vnc_account_ids: list[str] = Field(default_factory=list)
    active_vnc_session_count: int = 0
    max_vnc_session_count: int = 1
    vnc_idle_timeout_seconds: int = 1800
    vnc_max_session_seconds: int = 28800
    http_transport: Literal["requests"] = "requests"
    wss_transport: Literal["websockets"] = "websockets"
    tls_fingerprint_mode: Literal["native_client"] = "native_client"
    transport_alignment: list[str] = Field(
        default_factory=lambda: ["cookie", "proxy", "user_agent", "accept_language"]
    )
    transport_warning: str = (
        "后台 HTTP/WSS 与账户同步 Cookie、代理、UA 和语言；"
        "TLS/JA3/HTTP2 使用各客户端原生实现，不等同于 Chromium。"
    )


class BrowserBinaryActivatePayload(BaseModel):
    version: str = Field(min_length=1, max_length=64)


class StandardBrowserActivatePayload(BaseModel):
    version: str | None = Field(default=None, max_length=64)

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class ProxyConfigPayload(BaseModel):
    """Account-scoped SOCKS proxy settings."""

    enabled: bool = False
    scheme: Literal["socks5", "socks5h"] = "socks5h"
    host: str | None = ""
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None

    @field_validator("host", "username", "password", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ProxyCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    scheme: Literal["socks5", "socks5h"] = "socks5h"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)

    @field_validator("name", "host", "username", "password", mode="before")
    @classmethod
    def normalize_proxy_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ProxyUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    scheme: Literal["socks5", "socks5h"] | None = None
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)

    @field_validator("name", "host", "username", "password", mode="before")
    @classmethod
    def normalize_proxy_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ProxyPayload(BaseModel):
    proxy_id: str
    name: str
    enabled: bool
    scheme: Literal["socks5", "socks5h"]
    host: str
    port: int
    username: str | None = None
    has_password: bool = False
    last_test_ok: bool | None = None
    last_test_message: str | None = None
    last_test_latency_ms: int | None = None
    last_test_at: datetime | None = None
    exit_ip: str | None = None
    exit_ipv4: str | None = None
    exit_ipv6: str | None = None
    exit_country: str | None = None
    exit_region: str | None = None
    exit_city: str | None = None
    exit_isp: str | None = None
    exit_ipv6_country: str | None = None
    exit_ipv6_continent: str | None = None
    exit_checked_at: datetime | None = None
    last_platform_status: int | None = None
    created_at: datetime
    updated_at: datetime


class AccountCreatePayload(BaseModel):
    remark: str | None = Field(default=None, max_length=500)
    cookie: str = Field(default="", max_length=10000)
    enabled: bool = True
    conversation_visible: bool = True
    chat_enabled: bool = False
    order_management_visible: bool = True
    product_management_visible: bool = True
    proxy_id: str | None = Field(default=None, max_length=64)
    proxy: ProxyConfigPayload = Field(default_factory=ProxyConfigPayload)
    browser_identity: AccountBrowserIdentityPayload = Field(
        default_factory=AccountBrowserIdentityPayload
    )

    @field_validator("remark", "cookie", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def reject_legacy_inline_proxy(self) -> "AccountCreatePayload":
        if self.proxy.enabled or any(
            value not in (None, "")
            for value in (
                self.proxy.host,
                self.proxy.port,
                self.proxy.username,
                self.proxy.password,
            )
        ):
            raise ValueError("账户代理必须通过 proxy_id 绑定代理管理中的节点")
        return self


class AccountReorderPayload(BaseModel):
    account_ids: list[str] = Field(min_length=1, max_length=10000)

    @field_validator("account_ids", mode="before")
    @classmethod
    def normalize_account_ids(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(normalized) != len(value):
            raise ValueError("账户顺序中不能包含空 ID")
        if len(normalized) != len(set(normalized)):
            raise ValueError("账户顺序中不能包含重复 ID")
        return normalized


class AccountUpdatePayload(BaseModel):
    remark: str | None = Field(default=None, max_length=500)
    cookie: str | None = Field(default=None, max_length=10000)
    enabled: bool | None = None
    proxy_id: str | None = Field(default=None, max_length=64)
    proxy: ProxyConfigPayload | None = None
    browser_identity: AccountBrowserIdentityPayload | None = None

    @field_validator("remark", "cookie", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def reject_legacy_inline_proxy(self) -> "AccountUpdatePayload":
        if "proxy" in self.model_fields_set:
            raise ValueError("账户代理必须通过 proxy_id 绑定或解绑")
        return self


class AccountWorkspaceVisibilityUpdatePayload(BaseModel):
    conversation_visible: bool | None = None
    chat_enabled: bool | None = None
    order_management_visible: bool | None = None
    product_management_visible: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "AccountWorkspaceVisibilityUpdatePayload":
        if not self.model_fields_set:
            raise ValueError("at least one workspace visibility field is required")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("workspace visibility fields cannot be null")
        return self


class AccountCookiePayload(BaseModel):
    account_id: str
    cookie: str
    cookie_updated_at: datetime | None = None


class AccountMigrationPreviewPayload(BaseModel):
    session_id: str
    expires_at: datetime
    exported_at: datetime
    source_account_id: str
    platform_user_id: str | None = None
    platform_display_name: str | None = None
    remark: str | None = None
    cookie_present: bool
    browser_identity: AccountBrowserIdentityPayload
    browser_available: bool
    profile_present: bool
    profile_size_bytes: int = 0
    profile_file_count: int = 0
    proxy_included: bool = False
    proxy_name: str | None = None
    desired_enabled: bool = True
    desired_chat_enabled: bool = False
    conflicts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    can_import: bool = True


class AccountMigrationImportPayload(BaseModel):
    session_id: str = Field(min_length=32, max_length=64)
    import_proxy: bool = True
    enable_after_import: bool = False
    enable_chatwoot_after_import: bool = False

    @model_validator(mode="after")
    def validate_enablement(self) -> "AccountMigrationImportPayload":
        if self.enable_chatwoot_after_import and not self.enable_after_import:
            raise ValueError("启用 Chatwoot 前必须先启用导入账户")
        return self


class RuntimeStatusPayload(BaseModel):
    account_id: str
    state: RuntimeState = "stopped"
    recovery_action: RuntimeRecoveryAction = "none"
    message: str | None = None
    last_error: str | None = None
    last_state_at: datetime | None = None
    last_online_at: datetime | None = None
    last_message_at: datetime | None = None
    message_count: int = 0


class IMVerificationPayload(BaseModel):
    verification_id: str
    account_id: str
    status: IMVerificationState
    reason_code: str
    message: str | None = None
    x5_cookie_names: list[str] = Field(default_factory=list)
    triggered_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    browser_available: bool = False
    browser_error: str | None = None
    vnc_available: bool = False


class IMVerificationTicketPayload(BaseModel):
    ticket: str
    expires_in: int = 60


class CookieRenewalAttemptPayload(BaseModel):
    attempt_id: str
    trigger: Literal["manual", "scheduled", "auth_recovery"]
    state: Literal["running", "applying", "succeeded", "failed", "conflict"]
    phase: Literal["renewing", "persisting", "runtime", "completed"]
    message: str | None = None
    error_kind: str | None = None
    updated_cookie_names: list[str] = Field(default_factory=list)
    runtime_applied: bool | None = None
    started_at: datetime
    finished_at: datetime | None = None
    next_attempt_at: datetime | None = None
    duration_ms: int | None = None


class CookieRenewalStatusPayload(BaseModel):
    account_id: str
    state: Literal["idle", "running", "applying", "succeeded", "failed", "conflict"] = "idle"
    phase: Literal["idle", "renewing", "persisting", "runtime", "completed"] = "idle"
    trigger: Literal["manual", "scheduled", "auth_recovery"] | None = None
    active_attempt_id: str | None = None
    message: str | None = None
    updated_cookie_names: list[str] = Field(default_factory=list)
    attempt_count: int = 0
    last_started_at: datetime | None = None
    last_succeeded_at: datetime | None = None
    last_verified_at: datetime | None = None
    last_verified_source: str | None = None
    last_failed_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_error_kind: str | None = None
    last_error_source: str | None = None
    manual_action_required: bool = False
    runtime_applied: bool | None = None
    next_attempt_at: datetime | None = None
    cookie_updated_at: datetime | None = None
    cookie_update_source: str | None = None
    recent_attempts: list[CookieRenewalAttemptPayload] = Field(default_factory=list)
    updated_at: datetime | None = None


class RuntimeEventPayload(BaseModel):
    event_id: str
    account_id: str
    level: Literal["info", "warning", "error"] = "info"
    state: RuntimeState
    message: str | None = None
    created_at: datetime


class ConversationPayload(BaseModel):
    account_id: str
    account_name: str | None = None
    account_display_name: str | None = None
    account_remark: str | None = None
    platform: str = "xianyu"
    conversation_key: str | None = None
    conversation_id: str
    peer_user_id: str | None = None
    peer_name: str | None = None
    peer_avatar_url: str | None = None
    item_id: str | None = None
    item_title: str | None = None
    item_price: str | None = None
    item_image_url: str | None = None
    item_url: str | None = None
    item_context_source: str | None = None
    item_context_at: datetime | None = None
    last_message_content: str | None = None
    last_message_type: MessageType = "unknown"
    last_message_direction: MessageDirection | None = None
    last_message_at: datetime | None = None
    last_activity_at: datetime | None = None
    last_activity_content: str | None = None
    last_activity_type: MessageType | None = None
    last_activity_direction: MessageDirection | None = None
    message_count: int = 0
    unread_count: int = 0
    platform_unread_count: int = 0
    viewer_unread_count: int | None = None
    needs_reply: bool = False
    last_inbound_at: datetime | None = None
    last_outbound_at: datetime | None = None
    manual_takeover_until: datetime | None = None
    manual_takeover_mode: Literal["auto", "temporary", "permanent"] = "auto"
    created_at: datetime
    updated_at: datetime


ConversationSyncState = Literal[
    "pending",
    "syncing",
    "healthy",
    "empty",
    "error",
    "offline",
]


class ConversationAccountSyncPayload(BaseModel):
    account_id: str
    state: ConversationSyncState = "pending"
    conversation_count: int = 0
    rpc_healthy: bool = False
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


class MessageAttachmentPayload(BaseModel):
    attachment_id: str
    attachment_type: Literal["image", "audio"] = "image"
    remote_url: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    status: MessageSendStatus
    error: str | None = None


class MessageCardPayload(BaseModel):
    card_id: str
    account_id: str
    conversation_id: str
    message_pk: str
    card_type: MessageCardType
    item_id: str | None = None
    order_id: str | None = None
    title: str | None = None
    price: str | None = None
    status: str | None = None
    image_url: str | None = None
    url: str | None = None
    raw_summary: dict | list | str | int | float | bool | None = None
    created_at: datetime


class MessagePayload(BaseModel):
    message_pk: str
    account_id: str
    conversation_id: str
    message_id: str | None = None
    client_request_id: str | None = None
    direction: MessageDirection
    message_type: MessageType = "unknown"
    content: str = ""
    peer_user_id: str | None = None
    peer_name: str | None = None
    item_id: str | None = None
    send_success: bool | None = None
    send_status: MessageSendStatus | None = None
    send_error: str | None = None
    recalled_at: datetime | None = None
    attachments: list[MessageAttachmentPayload] = Field(default_factory=list)
    cards: list[MessageCardPayload] = Field(default_factory=list)
    raw_payload: dict | list | str | int | float | bool | None = None
    created_at_ms: int | None = None
    received_at_ms: int | None = None
    created_at: datetime
    received_at: datetime | None = None


class ConversationPagePayload(BaseModel):
    items: list[ConversationPayload] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: int | str | None = None
    source: Literal["live", "cache"] = "cache"
    connection_state: RuntimeState = "stopped"
    stale: bool = True
    error: str | None = None
    account_statuses: list[ConversationAccountSyncPayload] = Field(default_factory=list)


class MessagePagePayload(BaseModel):
    items: list[MessagePayload] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: int | None = None
    source: Literal["live", "cache"] = "cache"
    connection_state: RuntimeState = "stopped"
    stale: bool = True
    error: str | None = None


class SendTextPayload(BaseModel):
    receiver_user_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4000)
    client_request_id: str | None = Field(default=None, min_length=8, max_length=64)

    @field_validator("receiver_user_id", "text", "client_request_id", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class SendTextResultPayload(BaseModel):
    success: bool
    account_id: str
    conversation_id: str
    message_id: str | None = None
    error: str | None = None
    message: MessagePayload | None = None
    client_request_id: str | None = None


class SendImageResultPayload(SendTextResultPayload):
    client_request_id: str


class RecallMessageResultPayload(BaseModel):
    success: bool
    account_id: str
    conversation_id: str
    message_pk: str
    error: str | None = None
    message: MessagePayload | None = None


class PlatformBlacklistUpdatePayload(BaseModel):
    blocked: bool


class PlatformBlacklistPayload(BaseModel):
    success: bool
    account_id: str
    conversation_id: str
    blocked: bool | None = None
    error: str | None = None


class QuickPhrasePayload(BaseModel):
    phrase_id: str
    title: str
    content: str
    group_name: str = "默认"
    sort_order: int = 0
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class QuickPhraseCreatePayload(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=2000)
    group_name: str = Field(default="默认", min_length=1, max_length=80)
    sort_order: int = Field(default=0, ge=-100000, le=100000)

    @field_validator("title", "content", "group_name", mode="before")
    @classmethod
    def normalize_quick_phrase_string(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class QuickPhraseUpdatePayload(QuickPhraseCreatePayload):
    pass


class AccountAutoReplyUpdatePayload(BaseModel):
    enabled: bool


class AccountAutoReplyStatusPayload(BaseModel):
    account_id: str
    enabled: bool


class AIProviderSettingPayload(BaseModel):
    base_url: str | None = None
    model: str | None = None
    has_api_key: bool = False
    created_at: datetime
    updated_at: datetime


class AIProviderSettingUpdatePayload(BaseModel):
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, max_length=1000)
    clear_api_key: bool = False

    @field_validator("base_url", "model", "api_key", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class AutoReplySettingPayload(BaseModel):
    account_id: str | None = None
    user_id: str | None = None
    excluded_account_ids: list[str] = Field(default_factory=list)
    enabled: bool = False
    default_reply_enabled: bool = False
    default_reply_text: str = ""
    cooldown_seconds: int = 0
    match_strategy: AutoReplyMatchStrategy = "priority_first"
    allowlist_conversation_ids: list[str] = Field(default_factory=list)
    blocklist_conversation_ids: list[str] = Field(default_factory=list)
    ai_enabled: bool = False
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_system_prompt: str = ""
    ai_context_messages: int = 10
    ai_include_images: bool = False
    ai_temperature: float = 0.4
    has_ai_api_key: bool = False
    created_at: datetime
    updated_at: datetime


class AutoReplySettingUpdatePayload(BaseModel):
    enabled: bool = False
    default_reply_enabled: bool = False
    default_reply_text: str = Field(default="", max_length=4000)
    cooldown_seconds: int = Field(default=0, ge=0, le=86400)
    match_strategy: AutoReplyMatchStrategy = "priority_first"
    allowlist_conversation_ids: list[str] = Field(default_factory=list)
    blocklist_conversation_ids: list[str] = Field(default_factory=list)
    excluded_account_ids: list[str] = Field(default_factory=list)
    ai_enabled: bool = False
    ai_base_url: str | None = Field(default=None, max_length=500)
    ai_api_key: str | None = Field(default=None, max_length=1000)
    ai_model: str | None = Field(default=None, max_length=200)
    ai_system_prompt: str = Field(default="", max_length=8000)
    ai_context_messages: int = Field(default=10, ge=1, le=50)
    ai_include_images: bool = False
    ai_temperature: float = Field(default=0.4, ge=0, le=2)
    clear_ai_api_key: bool = False

    @field_validator("default_reply_text", "ai_base_url", "ai_api_key", "ai_model", "ai_system_prompt", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator(
        "allowlist_conversation_ids",
        "blocklist_conversation_ids",
        "excluded_account_ids",
        mode="before",
    )
    @classmethod
    def normalize_id_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.splitlines() if item.strip()]
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return value


class ManualTakeoverPayload(BaseModel):
    mode: Literal["auto", "temporary", "permanent"] | None = None
    active: bool | None = None
    minutes: int = Field(default=30, ge=1, le=10080)

    @property
    def resolved_mode(self) -> Literal["auto", "temporary", "permanent"]:
        if self.mode is not None:
            return self.mode
        return "temporary" if self.active else "auto"


class ManualTakeoverStatusPayload(BaseModel):
    account_id: str
    conversation_id: str
    active: bool
    mode: Literal["auto", "temporary", "permanent"] = "auto"
    until: datetime | None = None


class AutoReplyRulePayload(BaseModel):
    rule_id: str
    account_id: str | None = None
    user_id: str | None = None
    account_ids: list[str] = Field(default_factory=list)
    platform: str | None = None
    enabled: bool = True
    group_name: str | None = None
    keyword: str = ""
    trigger_type: Literal["keyword", "always", "fallback"] = "keyword"
    match_mode: Literal["contains", "exact"] = "contains"
    case_sensitive: bool = False
    message_type: str | None = None
    sender_user_id: str | None = None
    conversation_id: str | None = None
    item_id: str | None = None
    cooldown_seconds: int = 0
    action_type: Literal["template", "ai", "skip"] = "template"
    reply_text: str
    priority: int = 100
    continue_matching: bool = False
    context_message_count: int = 10
    context_fields: list[str] = Field(default_factory=list)
    ai_system_prompt: str = ""
    ai_temperature: float = 0.4
    created_at: datetime
    updated_at: datetime


class AutoReplyRuleCreatePayload(BaseModel):
    enabled: bool = True
    group_name: str | None = Field(default=None, max_length=120)
    keyword: str = Field(default="", max_length=200)
    trigger_type: Literal["keyword", "always", "fallback"] = "keyword"
    match_mode: Literal["contains", "exact"] = "contains"
    case_sensitive: bool = False
    account_ids: list[str] = Field(default_factory=list)
    platform: str | None = Field(default=None, max_length=32)
    message_type: str | None = Field(default=None, max_length=32)
    sender_user_id: str | None = Field(default=None, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    item_id: str | None = Field(default=None, max_length=128)
    cooldown_seconds: int = Field(default=0, ge=0, le=86400)
    action_type: Literal["template", "ai", "skip"] = "template"
    reply_text: str = Field(default="", max_length=4000)
    priority: int = Field(default=100, ge=0, le=100000)
    continue_matching: bool = False
    context_message_count: int = Field(default=10, ge=1, le=50)
    context_fields: list[str] = Field(default_factory=list)
    ai_system_prompt: str = Field(default="", max_length=8000)
    ai_temperature: float = Field(default=0.4, ge=0, le=2)

    @field_validator(
        "group_name", "platform", "message_type", "sender_user_id",
        "conversation_id", "item_id", mode="before"
    )
    @classmethod
    def normalize_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("keyword", "ai_system_prompt", mode="before")
    @classmethod
    def normalize_required_string(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("reply_text", mode="before")
    @classmethod
    def normalize_reply_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("account_ids", mode="before")
    @classmethod
    def normalize_account_ids(cls, value: object) -> object:
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return value

    @field_validator("context_fields", mode="before")
    @classmethod
    def normalize_context_fields(cls, value: object) -> object:
        if isinstance(value, list):
            return list(dict.fromkeys(
                item.strip() for item in value if isinstance(item, str) and item.strip()
            ))
        return value

    @model_validator(mode="after")
    def validate_action(self) -> "AutoReplyRuleCreatePayload":
        if self.trigger_type == "keyword" and not self.keyword:
            raise ValueError("关键词触发规则必须填写关键词")
        if self.action_type == "template" and not self.reply_text:
            raise ValueError("模板回复内容不能为空")
        if self.action_type != "template":
            self.continue_matching = False
        return self


class AutoReplyRuleUpdatePayload(BaseModel):
    enabled: bool | None = None
    group_name: str | None = Field(default=None, max_length=120)
    keyword: str | None = Field(default=None, max_length=200)
    trigger_type: Literal["keyword", "always", "fallback"] | None = None
    match_mode: Literal["contains", "exact"] | None = None
    case_sensitive: bool | None = None
    account_ids: list[str] | None = None
    platform: str | None = Field(default=None, max_length=32)
    message_type: str | None = Field(default=None, max_length=32)
    sender_user_id: str | None = Field(default=None, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    item_id: str | None = Field(default=None, max_length=128)
    cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)
    action_type: Literal["template", "ai", "skip"] | None = None
    reply_text: str | None = Field(default=None, max_length=4000)
    priority: int | None = Field(default=None, ge=0, le=100000)
    continue_matching: bool | None = None
    context_message_count: int | None = Field(default=None, ge=1, le=50)
    context_fields: list[str] | None = None
    ai_system_prompt: str | None = Field(default=None, max_length=8000)
    ai_temperature: float | None = Field(default=None, ge=0, le=2)

    @field_validator(
        "group_name", "platform", "message_type", "sender_user_id",
        "conversation_id", "item_id", mode="before"
    )
    @classmethod
    def normalize_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("keyword", "reply_text", "ai_system_prompt", mode="before")
    @classmethod
    def normalize_content_string(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("account_ids", "context_fields", mode="before")
    @classmethod
    def normalize_string_list(cls, value: object) -> object:
        if isinstance(value, list):
            return list(dict.fromkeys(
                item.strip() for item in value if isinstance(item, str) and item.strip()
            ))
        return value

    @model_validator(mode="after")
    def validate_action(self) -> "AutoReplyRuleUpdatePayload":
        if self.trigger_type == "keyword" and not self.keyword:
            raise ValueError("关键词触发规则必须填写关键词")
        if self.action_type == "template" and not self.reply_text:
            raise ValueError("模板回复内容不能为空")
        if self.action_type is not None and self.action_type != "template":
            self.continue_matching = False
        return self


class AutoReplyRuleReorderPayload(BaseModel):
    rule_ids: list[str] = Field(min_length=1, max_length=1000)

    @field_validator("rule_ids", mode="before")
    @classmethod
    def normalize_rule_ids(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("规则顺序中不能包含重复 ID")
        return normalized


class AutoReplyRuleIssuePayload(BaseModel):
    severity: Literal["warning", "error"]
    code: str
    message: str
    rule_ids: list[str] = Field(default_factory=list)


class AutoReplyPreviewRequestPayload(BaseModel):
    account_id: str = Field(min_length=1, max_length=64)
    content: str = Field(default="", max_length=4000)
    message_type: MessageType = "text"
    sender_user_id: str | None = Field(default=None, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    item_id: str | None = Field(default=None, max_length=128)

    @field_validator("account_id", "sender_user_id", "conversation_id", "item_id", mode="before")
    @classmethod
    def normalize_preview_ids(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class AutoReplyPreviewGatePayload(BaseModel):
    key: str
    passed: bool
    message: str


class AutoReplyPreviewRuleTracePayload(BaseModel):
    rule_id: str
    name: str
    matched: bool
    selected: bool = False
    message: str


class AutoReplyPreviewResultPayload(BaseModel):
    account_id: str
    executable: bool
    should_reply: bool
    reason: str
    action_type: Literal["template", "ai", "skip"] | None = None
    matched_rule_ids: list[str] = Field(default_factory=list)
    reply_preview: str | None = None
    ai_context: dict[str, object] = Field(default_factory=dict)
    gates: list[AutoReplyPreviewGatePayload] = Field(default_factory=list)
    traces: list[AutoReplyPreviewRuleTracePayload] = Field(default_factory=list)


class AutoReplyDecisionPayload(BaseModel):
    should_reply: bool
    rule_id: str | None = None
    matched_keyword: str | None = None
    reply_text: str | None = None
    reason: str | None = None


class AutoReplyLogPayload(BaseModel):
    log_id: str
    user_id: str | None = None
    account_id: str
    conversation_id: str
    inbound_message_pk: str | None = None
    outbound_message_pk: str | None = None
    rule_id: str | None = None
    matched_keyword: str | None = None
    reply_text: str
    success: bool
    error: str | None = None
    created_at: datetime


class DeliveryTemplatePayload(BaseModel):
    template_id: str
    account_id: str
    name: str
    enabled: bool = True
    content: str
    priority: int = 100
    created_at: datetime
    updated_at: datetime


class DeliveryTemplateCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    content: str = Field(min_length=1, max_length=4000)
    priority: int = Field(default=100, ge=0, le=100000)

    @field_validator("name", "content", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class DeliveryTemplateUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    priority: int | None = Field(default=None, ge=0, le=100000)

    @field_validator("name", "content", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class DeliveryPreparePayload(BaseModel):
    receiver_user_id: str = Field(min_length=1, max_length=128)
    template_id: str | None = Field(default=None, max_length=64)
    content: str | None = Field(default=None, max_length=4000)
    card_id: str | None = Field(default=None, max_length=64)
    source_message_pk: str | None = Field(default=None, max_length=64)
    item_id: str | None = Field(default=None, max_length=128)
    order_id: str | None = Field(default=None, max_length=128)
    peer_name: str | None = Field(default=None, max_length=255)

    @field_validator(
        "receiver_user_id",
        "template_id",
        "content",
        "card_id",
        "source_message_pk",
        "item_id",
        "order_id",
        "peer_name",
        mode="before",
    )
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class DeliveryRecordPayload(BaseModel):
    record_id: str
    order_pk: str | None = None
    account_id: str
    conversation_id: str
    receiver_user_id: str
    template_id: str | None = None
    card_id: str | None = None
    source_message_pk: str | None = None
    send_message_pk: str | None = None
    item_id: str | None = None
    order_id: str | None = None
    content: str
    status: DeliveryStatus = "pending"
    send_error: str | None = None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None


class DeliverySendResultPayload(BaseModel):
    success: bool
    record: DeliveryRecordPayload
    message: MessagePayload | None = None
    error: str | None = None


class DeliveryAutomationSettingPayload(BaseModel):
    account_id: str
    enabled: bool = False
    mode: DeliveryAutomationMode = "manual_only"
    require_order_card: bool = True
    duplicate_guard_enabled: bool = True
    order_status_allowlist: list[str] = Field(default_factory=lambda: ["WAIT_SELLER_SEND_GOODS", "待发货", "待卖家发货"])
    created_at: datetime
    updated_at: datetime


class DeliveryAutomationSettingUpdatePayload(BaseModel):
    enabled: bool = False
    mode: DeliveryAutomationMode = "manual_only"
    require_order_card: bool = True
    duplicate_guard_enabled: bool = True
    order_status_allowlist: list[str] = Field(default_factory=lambda: ["WAIT_SELLER_SEND_GOODS", "待发货", "待卖家发货"])

    @field_validator("order_status_allowlist", mode="before")
    @classmethod
    def normalize_allowlist(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class DeliveryPreflightPayload(BaseModel):
    eligible: bool
    account_id: str
    record_id: str
    mode: DeliveryAutomationMode
    reasons: list[str] = Field(default_factory=list)
    record: DeliveryRecordPayload


class OrderEventPayload(BaseModel):
    event_pk: str
    order_pk: str | None = None
    account_id: str
    conversation_id: str
    message_pk: str
    platform_order_id: str | None = None
    item_id: str | None = None
    event_type: str
    status: OrderStatus = "unknown"
    status_text: str | None = None
    raw_summary: dict | list | str | int | float | bool | None = None
    created_at: datetime


class OrderPayload(BaseModel):
    order_pk: str
    account_id: str
    account_name: str | None = None
    platform: str = "xianyu"
    platform_order_id: str | None = None
    trade_role: OrderTradeRole = "unknown"
    data_source: str | None = None
    first_seen_source: str | None = None
    platform_confirmed: bool = False
    sync_state: OrderSyncState = "provisional"
    conversation_id: str
    peer_user_id: str | None = None
    peer_name: str | None = None
    buyer_user_id: str | None = None
    buyer_name: str | None = None
    receiver_name: str | None = None
    receiver_phone: str | None = None
    receiver_address: str | None = None
    item_id: str | None = None
    title: str | None = None
    price: str | None = None
    quantity: int | None = None
    image_url: str | None = None
    status: OrderStatus = "unknown"
    status_text: str | None = None
    platform_status: str | None = None
    platform_created_at: datetime | None = None
    platform_paid_at: datetime | None = None
    platform_completed_at: datetime | None = None
    is_bargain: bool = False
    seller_rate_status: str | None = None
    refund_status: str | None = None
    refund_id: str | None = None
    platform_refund_actions: list[str] = Field(default_factory=list)
    refund_refuse_options: list[dict[str, object]] = Field(default_factory=list)
    logistics_type: str | None = None
    carrier_code: str | None = None
    tracking_no: str | None = None
    platform_shipping_methods: list[str] = Field(default_factory=list)
    platform_shipping_context: dict[str, object] = Field(default_factory=dict)
    source_message_pk: str | None = None
    last_event_at: datetime | None = None
    last_synced_at: datetime | None = None
    last_detail_synced_at: datetime | None = None
    headinfo_confirmed_at: datetime | None = None
    platform_capabilities: list[str] = Field(default_factory=list)
    platform_action_links: dict[str, str] = Field(default_factory=dict)
    sync_error: str | None = None
    available_actions: list["OrderActionAvailabilityPayload"] = Field(default_factory=list)
    raw_summary: dict | list | str | int | float | bool | None = None
    created_at: datetime
    updated_at: datetime


class OrderDetailPayload(OrderPayload):
    events: list[OrderEventPayload] = Field(default_factory=list)
    delivery_records: list[DeliveryRecordPayload] = Field(default_factory=list)
    operations: list["OrderOperationPayload"] = Field(default_factory=list)


class OrderActionAvailabilityPayload(BaseModel):
    action: OrderAction
    enabled: bool
    reason: str = ""
    label: str
    danger: bool = False


class OrderOperationPreviewRequest(BaseModel):
    action: OrderAction


class OrderOperationPreviewPayload(BaseModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    action: OrderActionAvailabilityPayload
    order: OrderPayload


class OrderOperationExecuteRequest(BaseModel):
    action: OrderAction
    idempotency_key: str = Field(min_length=8, max_length=160)
    feedback: str | None = Field(default=None, max_length=500)
    close_reason: str | None = Field(default=None, max_length=120)
    tracking_no: str | None = Field(default=None, max_length=128)
    carrier_code: str | None = Field(default=None, max_length=64)
    carrier_brand_code: str | None = Field(default=None, max_length=64)
    sender_address_id: str | None = Field(default=None, max_length=128)
    refund_reason_id: str | None = Field(default=None, max_length=64)
    refund_proof: dict[str, object] | None = None
    refund_logistic_info: dict[str, object] | None = None
    refund_negotiation_apply: dict[str, object] | None = None

    @field_validator(
        "idempotency_key",
        "feedback",
        "close_reason",
        "tracking_no",
        "carrier_code",
        "carrier_brand_code",
        "sender_address_id",
        "refund_reason_id",
        mode="before",
    )
    @classmethod
    def normalize_order_operation_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class OrderOperationPayload(BaseModel):
    operation_id: str
    order_pk: str
    account_id: str
    platform_order_id: str
    action: OrderAction
    status: OrderOperationStatus
    idempotency_key: str
    requested_by: str | None = None
    pre_status: str | None = None
    post_status: str | None = None
    message: str | None = None
    error: str | None = None
    platform_code: str | None = None
    request_summary: dict | list | str | int | float | bool | None = None
    response_summary: dict | list | str | int | float | bool | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class OrderOperationExecutePayload(BaseModel):
    operation: OrderOperationPayload
    order: OrderDetailPayload


class OrderDeliveryPreviewRequest(BaseModel):
    template_id: str | None = Field(default=None, max_length=64)
    content: str | None = Field(default=None, max_length=4000)

    @field_validator("template_id", "content", mode="before")
    @classmethod
    def normalize_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class OrderDeliveryPreviewPayload(BaseModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    order: OrderPayload
    template_id: str | None = None
    content: str


class ProductLocationPayload(BaseModel):
    prov: str = Field(min_length=1, max_length=80)
    city: str = Field(min_length=1, max_length=80)
    area: str = Field(default="", max_length=80)
    division_id: str = Field(min_length=1, max_length=64)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    poi_id: str = Field(default="", max_length=160)
    poi_name: str = Field(min_length=1, max_length=200)

    @field_validator("prov", "city", "area", "division_id", "poi_id", "poi_name", mode="before")
    @classmethod
    def normalize_location_string(cls, value: object) -> object:
        if value is None:
            return ""
        return value.strip() if isinstance(value, str) else str(value)


class ProductLocationOptionPayload(ProductLocationPayload):
    location_id: str
    label: str
    source: str = "platform_common"


class ProductLocationListPayload(BaseModel):
    items: list[ProductLocationOptionPayload] = Field(default_factory=list)
    data_source: Literal["live", "cache", "stale"]
    fetched_at: datetime
    warning: str | None = None


class ProductRegionPayload(BaseModel):
    region_code: str
    parent_code: str
    name: str
    level: Literal["province", "city", "district"]
    longitude: float
    latitude: float
    selectable: bool
    prov: str
    city: str
    area: str


class ProductRegionCatalogPayload(BaseModel):
    source: str
    version: str
    items: list[ProductRegionPayload]


class PublishAddressGroupPayload(BaseModel):
    group_id: str
    name: str
    enabled: bool = True
    avoid_recent_count: int = 3
    account_ids: list[str] = Field(default_factory=list)
    address_count: int = 0
    created_at: datetime
    updated_at: datetime


class PublishAddressGroupCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    avoid_recent_count: int = Field(default=3, ge=0, le=100)
    account_ids: list[str] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PublishAddressGroupUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    avoid_recent_count: int | None = Field(default=None, ge=0, le=100)
    account_ids: list[str] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PublishAddressPayload(ProductLocationPayload):
    address_id: str
    group_id: str
    source_account_id: str | None = None
    platform_location_id: str | None = None
    region_code: str | None = None
    label: str
    source: str
    enabled: bool = True
    use_count: int = 0
    last_used_at: datetime | None = None
    last_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PublishAddressCreatePayload(BaseModel):
    source_account_id: str = Field(min_length=1, max_length=64)
    location_id: str = Field(min_length=1, max_length=64)


class PublishAddressUpdatePayload(BaseModel):
    enabled: bool


class PublishAddressRegionSelectionPayload(BaseModel):
    region_codes: list[str] = Field(default_factory=list, max_length=4000)

    @field_validator("region_codes")
    @classmethod
    def normalize_region_codes(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


class PublishAddressRegionSelectionResultPayload(BaseModel):
    region_codes: list[str] = Field(default_factory=list)
    address_count: int = 0


class ProductDraftPayload(BaseModel):
    draft_id: str
    account_id: str
    title: str
    description: str = ""
    price: str
    original_price: str | None = None
    stock: int = 1
    category_id: str | None = None
    category_hint: str | None = None
    images: list[str] = Field(default_factory=list)
    delivery_choice: ProductDeliveryChoice = "free_shipping"
    post_price: str | None = None
    can_self_pickup: bool = False
    location_mode: ProductLocationMode = "account_default"
    location: ProductLocationPayload | None = None
    location_group_id: str | None = None
    status: ProductDraftStatus = "draft"
    created_at: datetime
    updated_at: datetime


class ProductImageAssetPayload(BaseModel):
    asset_id: str
    account_id: str
    image_ref: str
    original_filename: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    sha256: str
    upload_session_id: str | None = None
    state: str = "staged"
    expires_at: datetime | None = None
    last_referenced_at: datetime | None = None
    created_at: datetime


class ProductImageArchiveRejectedPayload(BaseModel):
    filename: str
    reason: str


class ProductImageArchiveUploadPayload(BaseModel):
    assets: list[ProductImageAssetPayload] = Field(default_factory=list)
    ignored_non_image_count: int = 0
    rejected_images: list[ProductImageArchiveRejectedPayload] = Field(default_factory=list)
    skipped_limit_count: int = 0


class ProductDraftCreatePayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    price: str = Field(min_length=1, max_length=64)
    original_price: str | None = Field(default=None, max_length=64)
    stock: int = Field(default=1, ge=1, le=100000)
    category_id: str | None = Field(default=None, max_length=128)
    category_hint: str | None = Field(default=None, max_length=120)
    images: list[str] = Field(default_factory=list, min_length=1, max_length=9)
    delivery_choice: ProductDeliveryChoice = "free_shipping"
    post_price: str | None = Field(default=None, max_length=64)
    can_self_pickup: bool = False
    location_mode: ProductLocationMode = "account_default"
    location: ProductLocationPayload | None = None
    location_group_id: str | None = Field(default=None, max_length=64)
    status: ProductDraftStatus = "draft"

    @field_validator("title", "description", "price", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("category_id", "category_hint", "original_price", "post_price", mode="before")
    @classmethod
    def normalize_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("images", mode="before")
    @classmethod
    def normalize_images(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.splitlines() if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_publish_values(self) -> "ProductDraftCreatePayload":
        _validate_product_money("price", self.price, required=True)
        _validate_product_money("original_price", self.original_price)
        _validate_product_money("post_price", self.post_price)
        if self.delivery_choice == "fixed" and self.post_price is None:
            raise ValueError("固定运费方式必须填写邮费")
        if self.location_mode in {"region", "selected"} and self.location is None:
            raise ValueError("指定宝贝所在地时必须选择有效地址")
        if self.location_mode == "group_random" and not self.location_group_id:
            raise ValueError("随机地址模式必须选择地址分组")
        return self


class ProductDraftUpdatePayload(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    price: str | None = Field(default=None, min_length=1, max_length=64)
    original_price: str | None = Field(default=None, max_length=64)
    stock: int | None = Field(default=None, ge=1, le=100000)
    category_id: str | None = Field(default=None, max_length=128)
    category_hint: str | None = Field(default=None, max_length=120)
    images: list[str] | None = Field(default=None, min_length=1, max_length=9)
    delivery_choice: ProductDeliveryChoice | None = None
    post_price: str | None = Field(default=None, max_length=64)
    can_self_pickup: bool | None = None
    location_mode: ProductLocationMode | None = None
    location: ProductLocationPayload | None = None
    location_group_id: str | None = Field(default=None, max_length=64)
    status: ProductDraftStatus | None = None

    @field_validator(
        "title",
        "description",
        "price",
        "original_price",
        "category_id",
        "category_hint",
        "post_price",
        mode="before",
    )
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("images", mode="before")
    @classmethod
    def normalize_images(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.splitlines() if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_publish_values(self) -> "ProductDraftUpdatePayload":
        _validate_product_money("price", self.price, required=self.price is not None)
        _validate_product_money("original_price", self.original_price)
        _validate_product_money("post_price", self.post_price)
        if self.delivery_choice == "fixed" and self.post_price is None:
            raise ValueError("固定运费方式必须填写邮费")
        if self.location_mode in {"region", "selected"} and self.location is None:
            raise ValueError("指定宝贝所在地时必须选择有效地址")
        if self.location_mode == "group_random" and not self.location_group_id:
            raise ValueError("随机地址模式必须选择地址分组")
        return self


class ProductPublishTaskPayload(BaseModel):
    task_id: str
    account_id: str
    draft_id: str | None = None
    mode: ProductPublishMode = "manual_export"
    status: ProductPublishTaskStatus = "pending"
    phase: str = "pending"
    unique_code: str
    idempotency_key: str
    snapshot: dict
    item_id: str | None = None
    item_url: str | None = None
    failure_kind: str | None = None
    error: str | None = None
    raw_result: dict | None = None
    retry_of_task_id: str | None = None
    attempt_no: int = 1
    retryable: bool = False
    result_certainty: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ProductPublishTaskCreatePayload(BaseModel):
    draft_id: str = Field(min_length=1, max_length=64)
    mode: ProductPublishMode = "manual_export"
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class ProductPublishJobCreatePayload(ProductDraftCreatePayload):
    upload_session_id: str | None = Field(default=None, min_length=8, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=128)
    mode: Literal["platform_api"] = "platform_api"

    @model_validator(mode="after")
    def validate_local_assets(self) -> "ProductPublishJobCreatePayload":
        if any(not image.startswith("asset:") for image in self.images):
            raise ValueError("发布任务仅支持已上传到本系统的图片素材")
        return self


class ProductPublishRetryPayload(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)


class BackgroundTaskPayload(BaseModel):
    task_id: str
    account_id: str | None = None
    task_type: str
    dedupe_key: str | None = None
    status: BackgroundTaskStatus = "pending"
    payload: dict | list | str | int | float | bool | None = None
    result: dict | list | str | int | float | bool | None = None
    error: str | None = None
    worker_id: str | None = None
    lease_expires_at: datetime | None = None
    run_after: datetime | None = None
    attempt_count: int = 0
    created_at: datetime
    updated_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BackgroundTaskCreatePayload(BaseModel):
    account_id: str | None = Field(default=None, max_length=64)
    task_type: str = Field(min_length=1, max_length=120)
    dedupe_key: str | None = Field(default=None, min_length=8, max_length=160)
    run_after: datetime | None = None
    payload: dict | list | str | int | float | bool | None = None

    @field_validator("account_id", "task_type", "dedupe_key", mode="before")
    @classmethod
    def normalize_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ChatwootConfigPayload(BaseModel):
    config_id: str = "default"
    enabled: bool = False
    account_alerts_enabled: bool = True
    offline_alert_delay_seconds: int = 120
    base_url: str
    chatwoot_account_id: int | None = None
    api_access_token: str | None = None
    has_api_access_token: bool = False
    full_outbound_sync_enabled: bool = False
    account_grouping_enabled: bool = False
    managed_inbox_count: int = 0
    callback_path: str
    callback_url: str
    status: str = "disabled"
    last_error: str | None = None
    credential_status: str = "unconfigured"
    credential_error: str | None = None
    push_status: str = "unknown"
    push_error: str | None = None
    webhook_status: str = "unknown"
    webhook_error: str | None = None
    inbox_status: str = "unknown"
    inbox_error: str | None = None
    label_status: str = "unknown"
    label_error: str | None = None
    last_webhook_at: datetime | None = None
    last_push_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChatwootConfigUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    account_alerts_enabled: bool = True
    offline_alert_delay_seconds: int = Field(default=120, ge=30, le=3600)
    base_url: str = Field(min_length=8, max_length=1000)
    api_access_token: str | None = Field(default=None, min_length=12, max_length=1000)

    @field_validator(
        "base_url",
        "api_access_token",
        mode="before",
    )
    @classmethod
    def normalize_chatwoot_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_chatwoot_url(self) -> "ChatwootConfigUpdatePayload":
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Chatwoot 地址必须以 http:// 或 https:// 开头")
        self.base_url = self.base_url.rstrip("/")
        return self


class ChatwootTestResultPayload(BaseModel):
    success: bool
    message: str
    status_code: int | None = None


class WebNotificationConfigPayload(BaseModel):
    config_id: str = "default"
    enabled: bool = True
    has_custom_sound: bool = False
    sound_filename: str | None = None
    sound_mime_type: str | None = None
    sound_size_bytes: int | None = None
    sound_sha256: str | None = None
    sound_url: str | None = None
    created_at: datetime
    updated_at: datetime


class WebNotificationConfigUpdatePayload(BaseModel):
    enabled: bool = True


class ChatwootWebhookAcceptedPayload(BaseModel):
    accepted: bool = True
    duplicate: bool = False
    delivery_id: str


class OrderSyncSettingPayload(BaseModel):
    account_id: str
    scope: OrderSyncScope = "sold"
    sync_enabled: bool = True
    pending_interval_seconds: int = 90
    full_interval_minutes: int = 15
    jitter_seconds: int = 20
    last_sync_at: datetime | None = None
    last_pending_sync_at: datetime | None = None
    last_full_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    next_pending_sync_at: datetime | None = None
    next_full_sync_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OrderSyncSettingUpdatePayload(BaseModel):
    sync_enabled: bool = True
    pending_interval_seconds: int = Field(default=90, ge=60, le=3600)
    full_interval_minutes: int = Field(default=15, ge=10, le=1440)
    jitter_seconds: int = Field(default=20, ge=0, le=600)


class OrderSyncRunPayload(BaseModel):
    run_id: str
    account_id: str
    scope: OrderSyncScope = "sold"
    mode: OrderSyncMode
    trigger: str
    status: BackgroundTaskStatus
    total_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class OrderAccountSummaryPayload(BaseModel):
    account_id: str
    account_name: str
    scope: OrderSyncScope = "sold"
    enabled: bool
    runtime_state: RuntimeState
    total_count: int = 0
    active_count: int = 0
    pending_count: int = 0
    refunding_count: int = 0
    setting: OrderSyncSettingPayload


class OrderSyncRequestPayload(BaseModel):
    scope: OrderSyncScope = "sold"
    mode: OrderSyncMode = "full"

    @model_validator(mode="after")
    def validate_scope_mode(self) -> "OrderSyncRequestPayload":
        if self.scope == "bought" and self.mode != "full":
            raise ValueError("买入订单仅支持全量同步")
        return self


class OrderSyncEnqueuePayload(BaseModel):
    run: OrderSyncRunPayload
    background_task: BackgroundTaskPayload


class ProductPublishEnqueuePayload(BaseModel):
    publish_task: ProductPublishTaskPayload
    background_task: BackgroundTaskPayload


ProductPlatformStatus = Literal["selling", "offline", "deleted", "not_selling", "unknown"]
ProductOperationStatus = Literal[
    "pending", "running", "success", "partial_success", "failed", "verification_required"
]


class ProductItemPayload(BaseModel):
    account_id: str
    item_id: str
    title: str = ""
    price: str = ""
    category_id: str | None = None
    cover_url: str | None = None
    detail_url: str | None = None
    platform_item_status: str | None = None
    want_count: int | None = None
    want_text: str | None = None
    platform_status: ProductPlatformStatus = "unknown"
    sync_state: str = "current"
    missing_sync_count: int = 0
    last_seen_at: datetime | None = None
    last_synced_at: datetime | None = None
    last_polished_on: str | None = None
    last_polished_at: datetime | None = None
    published_at: datetime | None = None
    published_at_source: Literal["platform", "publish_task", "unknown"] = "unknown"
    created_at: datetime
    updated_at: datetime


class ProductLocalCleanupPayload(BaseModel):
    account_id: str
    item_id: str
    deleted: bool = True
    hidden_publish_task_count: int = 0


class ProductSyncSettingPayload(BaseModel):
    account_id: str
    sync_enabled: bool = True
    sync_interval_minutes: int = 20
    sync_jitter_minutes: int = 5
    full_sync_interval_hours: int = 6
    publish_verify_delay_seconds: int = 30
    auto_polish_enabled: bool = False
    polish_hour: int = 8
    polish_jitter_minutes: int = 10
    last_sync_at: datetime | None = None
    last_full_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    next_sync_at: datetime | None = None
    last_polish_at: datetime | None = None
    next_polish_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProductSyncSettingUpdatePayload(BaseModel):
    sync_enabled: bool | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    sync_jitter_minutes: int | None = Field(default=None, ge=0, le=120)
    full_sync_interval_hours: int | None = Field(default=None, ge=1, le=168)
    publish_verify_delay_seconds: int | None = Field(default=None, ge=10, le=300)
    auto_polish_enabled: bool | None = None
    polish_hour: int | None = Field(default=None, ge=0, le=23)
    polish_jitter_minutes: int | None = Field(default=None, ge=0, le=180)


class ProductAccountSummaryPayload(BaseModel):
    account_id: str
    account_name: str
    enabled: bool
    runtime_state: str = "stopped"
    selling_count: int = 0
    offline_count: int = 0
    unknown_count: int = 0
    setting: ProductSyncSettingPayload


class ProductOperationItemPayload(BaseModel):
    result_id: str
    run_id: str
    item_id: str
    status: str
    message: str | None = None
    platform_code: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductOperationRunPayload(BaseModel):
    run_id: str
    account_id: str
    operation: Literal["sync", "polish", "offline", "delete"]
    trigger: Literal["manual", "scheduled", "publish"]
    status: ProductOperationStatus
    full_sync: bool = False
    requested_item_ids: list[str] = Field(default_factory=list)
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    items: list[ProductOperationItemPayload] = Field(default_factory=list)


class ProductSyncRequestPayload(BaseModel):
    full: bool = True


class ProductItemOperationRequestPayload(BaseModel):
    item_ids: list[str] = Field(default_factory=list, min_length=1, max_length=200)

    @field_validator("item_ids")
    @classmethod
    def normalize_item_ids(cls, value: list[str]) -> list[str]:
        result = list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
        if not result:
            raise ValueError("至少选择一个商品")
        return result


class ProductOperationEnqueuePayload(BaseModel):
    run: ProductOperationRunPayload
    background_task: BackgroundTaskPayload


class AuditLogPayload(BaseModel):
    audit_id: str
    actor: str = "admin"
    action: str
    target: str
    success: bool = True
    status_code: int | None = None
    error: str | None = None
    client_ip: str | None = None
    created_at: datetime


CookieHealthState = Literal["missing", "unchecked", "valid", "renewing", "invalid"]


class CookieHealthPayload(BaseModel):
    state: CookieHealthState
    message: str | None = None
    checked_at: datetime | None = None
    last_renewed_at: datetime | None = None
    next_renewal_at: datetime | None = None
    last_failed_at: datetime | None = None
    verification_source: str | None = None
    failure_source: str | None = None
    error_kind: str | None = None
    manual_action_required: bool = False


class IMHealthPayload(BaseModel):
    state: RuntimeState
    available: bool = False
    message: str | None = None
    last_online_at: datetime | None = None


class AccountPayload(BaseModel):
    account_id: str
    remark: str | None = None
    display_name: str
    platform: str = "xianyu"
    platform_user_id: str | None = None
    platform_display_name: str | None = None
    platform_avatar_url: str | None = None
    platform_identity_source: str | None = None
    platform_identity_checked_at: datetime | None = None
    sort_order: int = 0
    enabled: bool
    conversation_visible: bool = True
    chat_enabled: bool = False
    order_management_visible: bool = True
    product_management_visible: bool = True
    auto_reply_enabled: bool = False
    automation_owner_user_id: str | None = None
    has_cookie: bool
    network_mode: AccountNetworkMode = "direct"
    proxy_id: str | None = None
    proxy_name: str | None = None
    proxy: ProxyConfigPayload
    browser_identity: AccountBrowserIdentityPayload = Field(
        default_factory=AccountBrowserIdentityPayload
    )
    runtime: RuntimeStatusPayload
    cookie_health: CookieHealthPayload
    im_health: IMHealthPayload
    cookie_updated_at: datetime | None = None
    cookie_update_source: str | None = None
    created_at: datetime
    updated_at: datetime


class ProxyTestPayload(BaseModel):
    ok: bool
    proxy_url: str | None = None
    message: str
    latency_ms: int | None = None
    exit_ip: str | None = None
    exit_ipv4: str | None = None
    exit_ipv6: str | None = None
    exit_country: str | None = None
    exit_region: str | None = None
    exit_city: str | None = None
    exit_isp: str | None = None
    exit_ipv6_country: str | None = None
    exit_ipv6_continent: str | None = None
    platform_status_code: int | None = None


class AccountConnectionHealthPayload(BaseModel):
    account_id: str
    account_name: str
    enabled: bool
    network_mode: AccountNetworkMode = "direct"
    proxy_id: str | None = None
    proxy_name: str | None = None
    running: bool
    online: bool
    connected_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    heartbeat_age_seconds: float | None = None
    last_server_frame_at: datetime | None = None
    server_frame_age_seconds: float | None = None
    last_rpc_success_at: datetime | None = None
    last_rpc_latency_ms: int | None = None
    last_rpc_error: str | None = None
    consecutive_rpc_failures: int = 0
    rpc_healthy: bool = False
    push_queue_depth: int = 0
    push_queue_dropped: int = 0
    push_inflight: int = 0
    active_pushes: list[str] = Field(default_factory=list)
    reconnect_count: int = 0
    last_disconnect_reason: str | None = None
    sync_queue_depth: int = 0
    side_effect_queue_depth: int = 0
    side_effect_queue_capacity: int = 200
    side_effect_queue_dropped: int = 0
    message_retry_pending: int = 0
    processing_errors_total: int = 0
    last_processing_error: str | None = None
    last_processing_error_at: datetime | None = None


class EventLoopHealthPayload(BaseModel):
    status: Literal["healthy", "warning", "critical"] = "healthy"
    current_lag_ms: float = 0
    max_lag_ms_60s: float = 0
    p95_lag_ms_60s: float = 0
    sample_count: int = 0
    consecutive_warnings: int = 0
    warning_count: int = 0
    last_sample_at: datetime | None = None


class ExecutorHealthPayload(BaseModel):
    name: str
    max_workers: int
    max_queue: int
    capacity: int
    active: int = 0
    queued: int = 0
    submitted: int = 0
    completed: int = 0
    failed: int = 0
    rejected: int = 0
    average_queue_wait_ms: float = 0
    average_duration_ms: float = 0
    last_duration_ms: float | None = None


class RealtimeHealthPayload(BaseModel):
    subscribers: int = 0
    queued: int = 0
    capacity_per_subscriber: int = 200
    published: int = 0
    resync_required: int = 0


class WorkerHealthPayload(BaseModel):
    online: bool = False
    worker_id: str | None = None
    process_id: int | None = None
    concurrency: int | None = None
    active_tasks: list[str] = Field(default_factory=list)
    queued_tasks: int = 0
    updated_at: float | None = None
    heartbeat_age_seconds: float | None = None
    error: str | None = None


class ProcessHealthPayload(BaseModel):
    process_id: int
    started_at: datetime
    uptime_seconds: float
    thread_count: int
    event_loop: EventLoopHealthPayload
    executors: list[ExecutorHealthPayload] = Field(default_factory=list)
    realtime: RealtimeHealthPayload
    worker: WorkerHealthPayload


class HealthPayload(BaseModel):
    ok: bool = True
    service: str = "xianyu-admin-api"
    runtime_ok: bool = True
    enabled_accounts: int = 0
    running_accounts: int = 0
    online_accounts: int = 0
