"""Database tables for the Xianyu admin API."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .account_labels import platform_account_display_name
from .database import Base, UTCDateTime


def utcnow() -> datetime:
    return datetime.now(UTC)


def epoch_milliseconds() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


class UserORM(Base):
    __tablename__ = "xianyu_users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_xianyu_users_username"),
        Index("ix_xianyu_users_username", "username"),
    )

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="operator")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    privacy_mask_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_login_source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    automation_accounts: Mapped[list["AccountORM"]] = relationship(
        back_populates="automation_owner"
    )
    auto_reply_setting: Mapped["UserAutoReplySettingORM"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    auto_reply_rules: Mapped[list["UserAutoReplyRuleORM"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    admin_sessions: Mapped[list["AdminSessionORM"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AdminSessionORM(Base):
    __tablename__ = "xianyu_admin_sessions"
    __table_args__ = (
        Index("ix_xianyu_admin_sessions_user", "user_id"),
        Index("ix_xianyu_admin_sessions_token", "refresh_token_hash", unique=True),
        Index("ix_xianyu_admin_sessions_expiry", "expires_at"),
    )

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )
    last_used_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    login_source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    user: Mapped["UserORM"] = relationship(back_populates="admin_sessions")


class QuickPhraseORM(Base):
    __tablename__ = "xianyu_quick_phrases"
    __table_args__ = (
        Index("ix_xianyu_quick_phrases_user_sort", "user_id", "sort_order"),
        Index("ix_xianyu_quick_phrases_user_recent", "user_id", "last_used_at"),
    )

    phrase_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_users.user_id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    group_name: Mapped[str] = mapped_column(String(80), nullable=False, default="默认")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class ProxyORM(Base):
    __tablename__ = "xianyu_proxies"
    __table_args__ = (UniqueConstraint("name", name="uq_xianyu_proxies_name"),)

    proxy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scheme: Mapped[str] = mapped_column(String(16), nullable=False, default="socks5h")
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    exit_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_ipv4: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_ipv6: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exit_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exit_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exit_isp: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exit_ipv6_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exit_ipv6_continent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exit_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_platform_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    account: Mapped["AccountORM | None"] = relationship(
        back_populates="bound_proxy",
        uselist=False,
    )


class AccountORM(Base):
    __tablename__ = "xianyu_accounts"
    __table_args__ = (
        Index("uq_xianyu_accounts_proxy_id", "proxy_id", unique=True),
        Index("ix_xianyu_accounts_sort", "sort_order", "created_at"),
    )

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    platform: Mapped[str] = mapped_column(
        String(32), nullable=False, default="xianyu", server_default="xianyu", index=True
    )
    platform_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform_avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    platform_identity_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    platform_identity_checked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    cookie: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conversation_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    chat_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    order_management_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    product_management_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    automation_owner_user_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("xianyu_users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    proxy_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("xianyu_proxies.proxy_id", ondelete="SET NULL"), nullable=True
    )

    proxy_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    proxy_scheme: Mapped[str] = mapped_column(String(16), nullable=False, default="socks5h")
    proxy_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proxy_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proxy_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proxy_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cookie_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cookie_update_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    im_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    im_token_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    @property
    def display_name(self) -> str:
        return platform_account_display_name(
            self.account_id,
            self.platform_display_name,
            self.platform,
        )

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    bound_proxy: Mapped[ProxyORM | None] = relationship(back_populates="account")
    automation_owner: Mapped[UserORM | None] = relationship(
        back_populates="automation_accounts"
    )
    browser_identity: Mapped["AccountBrowserIdentityORM"] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        uselist=False,
    )

    runtime: Mapped["RuntimeStatusORM"] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        uselist=False,
    )
    cookie_renewal: Mapped["CookieRenewalORM"] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        uselist=False,
    )
    cookie_renewal_attempts: Mapped[list["CookieRenewalAttemptORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["RuntimeEventORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    im_verifications: Mapped[list["IMVerificationORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["ConversationORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["MessageORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    message_cards: Mapped[list["MessageCardORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    orders: Mapped[list["OrderORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    order_events: Mapped[list["OrderEventORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    order_sync_setting: Mapped["OrderSyncSettingORM"] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        uselist=False,
    )
    order_sync_runs: Mapped[list["OrderSyncRunORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    auto_reply_setting: Mapped["AutoReplySettingORM"] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        uselist=False,
    )
    auto_reply_rules: Mapped[list["AutoReplyRuleORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    auto_reply_logs: Mapped[list["AutoReplyLogORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    delivery_templates: Mapped[list["DeliveryTemplateORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    delivery_records: Mapped[list["DeliveryRecordORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    delivery_automation_setting: Mapped["DeliveryAutomationSettingORM"] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        uselist=False,
    )
    product_drafts: Mapped[list["ProductDraftORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    product_images: Mapped[list["ProductImageAssetORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    product_location_caches: Mapped[list["ProductLocationCacheORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    product_platform_locations: Mapped[list["ProductPlatformLocationORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    product_publish_tasks: Mapped[list["ProductPublishTaskORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    product_items: Mapped[list["ProductItemORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    product_sync_setting: Mapped["ProductSyncSettingORM"] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        uselist=False,
    )
    product_operation_runs: Mapped[list["ProductOperationRunORM"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )


class AccountBrowserIdentityORM(Base):
    __tablename__ = "xianyu_account_browser_identities"
    __table_args__ = (
        Index(
            "uq_xianyu_account_browser_identities_seed",
            "fingerprint_seed",
            unique=True,
        ),
    )

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    browser_engine: Mapped[str] = mapped_column(
        String(32), nullable=False, default="system_chromium", server_default="system_chromium"
    )
    fingerprint_seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    browser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform: Mapped[str] = mapped_column(
        String(16), nullable=False, default="windows", server_default="windows"
    )
    platform_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="10.0.0", server_default="10.0.0"
    )
    brand: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Chrome", server_default="Chrome"
    )
    language: Mapped[str] = mapped_column(
        String(32), nullable=False, default="zh-CN", server_default="zh-CN"
    )
    accept_language: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="zh-CN,zh;q=0.9,en;q=0.8",
        server_default="zh-CN,zh;q=0.9,en;q=0.8",
    )
    timezone: Mapped[str] = mapped_column(
        String(80), nullable=False, default="Asia/Shanghai", server_default="Asia/Shanghai"
    )
    hardware_concurrency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spoof_canvas: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    spoof_webgl: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    spoof_audio: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    spoof_fonts: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    spoof_client_rects: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    webrtc_policy: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        default="proxy_only",
        server_default="proxy_only",
    )
    fingerprint_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    account: Mapped[AccountORM] = relationship(back_populates="browser_identity")


class RuntimeStatusORM(Base):
    __tablename__ = "xianyu_runtime_status"

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="stopped")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_state_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_online_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="runtime")


class IMVerificationORM(Base):
    __tablename__ = "xianyu_im_verifications"
    __table_args__ = (
        Index("ix_xianyu_im_verifications_account_created", "account_id", "created_at"),
        Index("ix_xianyu_im_verifications_status", "status"),
    )

    verification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="required")
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    verification_url_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    x5_cookie_names: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    triggered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    account: Mapped[AccountORM] = relationship(back_populates="im_verifications")


class CookieRenewalORM(Base):
    __tablename__ = "xianyu_cookie_renewals"

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trigger: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active_attempt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_cookie_names: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_succeeded_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_verified_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_failed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    runtime_applied: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="cookie_renewal")


class CookieRenewalAttemptORM(Base):
    __tablename__ = "xianyu_cookie_renewal_attempts"
    __table_args__ = (
        Index(
            "ix_xianyu_cookie_renewal_attempt_account_started",
            "account_id",
            "started_at",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="renewing")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_cookie_names: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    runtime_applied: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="cookie_renewal_attempts")


class RuntimeEventORM(Base):
    __tablename__ = "xianyu_runtime_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    account: Mapped[AccountORM] = relationship(back_populates="events")


class ConversationORM(Base):
    __tablename__ = "xianyu_conversations"
    __table_args__ = (
        UniqueConstraint("account_id", "conversation_id", name="uq_xianyu_conversation_account"),
        Index("ix_xianyu_conversations_account_updated", "account_id", "updated_at"),
        Index("ix_xianyu_conversations_last_message", "last_message_at", "updated_at"),
        Index(
            "ix_xianyu_conversations_account_activity",
            "account_id",
            "last_activity_at",
            "conversation_pk",
        ),
    )

    conversation_pk: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    peer_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    peer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    item_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    item_price: Mapped[str | None] = mapped_column(String(120), nullable=True)
    item_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    item_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    item_context_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    item_context_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(precision=3), nullable=True
    )
    last_message_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    last_message_direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(precision=3), nullable=True
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(precision=3), nullable=True
    )
    last_activity_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_activity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_activity_direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_reply: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", index=True
    )
    last_inbound_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(precision=3), nullable=True
    )
    last_outbound_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(precision=3), nullable=True
    )
    manual_takeover_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    manual_takeover_mode: Mapped[str | None] = mapped_column(
        String(16), nullable=True, default="auto", server_default="auto"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="conversations")


class PeerIdentityORM(Base):
    __tablename__ = "xianyu_peer_identities"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "account_id",
            "peer_user_id",
            name="uq_xianyu_peer_identity",
        ),
        Index("ix_xianyu_peer_identity_lookup", "account_id", "peer_user_id"),
    )

    identity_pk: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="xianyu")
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    peer_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="message")
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    avatar_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    profile_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


class ConversationReadStateORM(Base):
    __tablename__ = "xianyu_conversation_read_states"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "conversation_pk", name="uq_xianyu_conversation_read_state_user"
        ),
        Index("ix_xianyu_conversation_read_states_user", "user_id", "updated_at"),
    )

    state_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_users.user_id", ondelete="CASCADE"), nullable=False
    )
    conversation_pk: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_conversations.conversation_pk", ondelete="CASCADE"),
        nullable=False,
    )
    unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_read_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_read_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class MessageORM(Base):
    __tablename__ = "xianyu_messages"
    __table_args__ = (
        Index(
            "ix_xianyu_messages_conversation_created",
            "account_id",
            "conversation_id",
            "created_at_ms",
            "message_pk",
        ),
        Index(
            "ix_xianyu_messages_account_created",
            "account_id",
            "created_at_ms",
            "message_pk",
        ),
        Index("uq_xianyu_messages_platform_id", "account_id", "message_id", unique=True),
        Index("uq_xianyu_messages_dedupe_key", "account_id", "dedupe_key", unique=True),
        Index(
            "uq_xianyu_messages_client_request",
            "account_id",
            "client_request_id",
            unique=True,
        ),
    )

    message_pk: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    peer_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    peer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    send_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    send_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    recalled_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(precision=3), nullable=True
    )
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_ms: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=epoch_milliseconds
    )
    received_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(precision=3), nullable=False, default=utcnow
    )
    received_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(precision=3), nullable=True
    )

    account: Mapped[AccountORM] = relationship(back_populates="messages")
    attachments: Mapped[list["MessageAttachmentORM"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MessageAttachmentORM(Base):
    __tablename__ = "xianyu_message_attachments"
    __table_args__ = (Index("ix_xianyu_message_attachments_message", "message_pk"),)

    attachment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    message_pk: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_messages.message_pk", ondelete="CASCADE"),
        nullable=False,
    )
    attachment_type: Mapped[str] = mapped_column(String(32), nullable=False, default="image")
    remote_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploading")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    message: Mapped[MessageORM] = relationship(back_populates="attachments")


class MessageCardORM(Base):
    __tablename__ = "xianyu_message_cards"
    __table_args__ = (
        Index("ix_xianyu_message_cards_account_created", "account_id", "created_at"),
        Index("ix_xianyu_message_cards_conversation_created", "account_id", "conversation_id", "created_at"),
        Index("ix_xianyu_message_cards_item", "account_id", "item_id"),
        Index("ix_xianyu_message_cards_order", "account_id", "order_id"),
    )

    card_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    message_pk: Mapped[str] = mapped_column(String(64), nullable=False)
    card_type: Mapped[str] = mapped_column(String(24), nullable=False)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    raw_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    account: Mapped[AccountORM] = relationship(back_populates="message_cards")


class OrderORM(Base):
    __tablename__ = "xianyu_orders"
    __table_args__ = (
        Index("ix_xianyu_orders_account_updated", "account_id", "updated_at"),
        Index("ix_xianyu_orders_account_status", "account_id", "status"),
        Index("ix_xianyu_orders_conversation", "account_id", "conversation_id"),
        Index("ix_xianyu_orders_item", "account_id", "item_id"),
        Index(
            "uq_xianyu_orders_platform_id",
            "account_id",
            "platform_order_id",
            unique=True,
        ),
    )

    order_pk: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trade_role: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    data_source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    first_seen_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    platform_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    sync_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="provisional", server_default="provisional"
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    peer_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    peer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    buyer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receiver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receiver_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receiver_address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    status_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform_status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    platform_created_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    platform_paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    platform_completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    is_bargain: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    seller_rate_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    refund_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    refund_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform_refund_actions: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_refuse_options: Mapped[str | None] = mapped_column(Text, nullable=True)
    logistics_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    carrier_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tracking_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform_shipping_methods: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_shipping_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_message_pk: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_detail_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    headinfo_confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    platform_capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_action_links: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    account: Mapped[AccountORM] = relationship(back_populates="orders")
    events: Mapped[list["OrderEventORM"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    delivery_records: Mapped[list["DeliveryRecordORM"]] = relationship(back_populates="order")


class OrderOperationORM(Base):
    __tablename__ = "xianyu_order_operations"
    __table_args__ = (
        Index("ix_xianyu_order_operations_order_created", "order_pk", "created_at"),
        Index("ix_xianyu_order_operations_account_status", "account_id", "status"),
        Index(
            "uq_xianyu_order_operations_idempotency",
            "account_id",
            "idempotency_key",
            unique=True,
        ),
    )

    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_pk: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_orders.order_pk", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"), nullable=False
    )
    platform_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="processing")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pre_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    post_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    request_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class OrderEventORM(Base):
    __tablename__ = "xianyu_order_events"
    __table_args__ = (
        Index("ix_xianyu_order_events_order_created", "order_pk", "created_at"),
        Index("ix_xianyu_order_events_conversation", "account_id", "conversation_id"),
        Index("uq_xianyu_order_events_message", "account_id", "message_pk", unique=True),
    )

    event_pk: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_pk: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("xianyu_orders.order_pk", ondelete="CASCADE"), nullable=True
    )
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    message_pk: Mapped[str] = mapped_column(String(64), nullable=False)
    platform_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    status_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    account: Mapped[AccountORM] = relationship(back_populates="order_events")
    order: Mapped[OrderORM | None] = relationship(back_populates="events")


class OrderSyncSettingORM(Base):
    __tablename__ = "xianyu_order_sync_settings"

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pending_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    full_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    jitter_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_pending_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_full_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_pending_sync_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True, index=True
    )
    next_full_sync_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True, index=True
    )
    bought_sync_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    bought_full_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15, server_default="15"
    )
    bought_jitter_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20, server_default="20"
    )
    bought_last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    bought_last_full_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    bought_last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bought_last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    bought_next_full_sync_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    account: Mapped[AccountORM] = relationship(back_populates="order_sync_setting")


class OrderSyncRunORM(Base):
    __tablename__ = "xianyu_order_sync_runs"
    __table_args__ = (
        Index("ix_xianyu_order_sync_runs_account_created", "account_id", "created_at"),
        Index("ix_xianyu_order_sync_runs_active", "account_id", "scope", "status"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="sold", server_default="sold", index=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    account: Mapped[AccountORM] = relationship(back_populates="order_sync_runs")


class AutoReplySettingORM(Base):
    __tablename__ = "xianyu_auto_reply_settings"

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_reply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_reply_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    match_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="priority_first")
    allowlist_conversation_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocklist_conversation_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_api_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="auto_reply_setting")


class UserAutoReplySettingORM(Base):
    __tablename__ = "xianyu_user_auto_reply_settings"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_users.user_id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excluded_account_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_reply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_reply_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    match_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="priority_first")
    allowlist_conversation_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocklist_conversation_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_api_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    ai_include_images: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped[UserORM] = relationship(back_populates="auto_reply_setting")


class AIProviderSettingORM(Base):
    __tablename__ = "xianyu_ai_provider_settings"

    setting_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default="default", server_default="default"
    )
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class UserAutoReplyRuleORM(Base):
    __tablename__ = "xianyu_user_auto_reply_rules"
    __table_args__ = (
        Index("ix_xianyu_user_auto_reply_rules_user_priority", "user_id", "priority"),
    )

    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="keyword", server_default="keyword"
    )
    match_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="contains")
    case_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sender_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[str] = mapped_column(String(16), nullable=False, default="template")
    reply_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    continue_matching: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    context_message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default="10"
    )
    context_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_temperature: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.4, server_default="0.4"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped[UserORM] = relationship(back_populates="auto_reply_rules")


class AutoReplyRuleORM(Base):
    __tablename__ = "xianyu_auto_reply_rules"
    __table_args__ = (
        Index("ix_xianyu_auto_reply_rules_account_priority", "account_id", "priority"),
    )

    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="keyword", server_default="keyword"
    )
    match_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="contains")
    case_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="template", server_default="template"
    )
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    continue_matching: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    context_message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default="10"
    )
    context_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_temperature: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.4, server_default="0.4"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="auto_reply_rules")


class AutoReplyLogORM(Base):
    __tablename__ = "xianyu_auto_reply_logs"
    __table_args__ = (
        Index("ix_xianyu_auto_reply_logs_account_created", "account_id", "created_at"),
        Index("ix_xianyu_auto_reply_logs_conversation_created", "account_id", "conversation_id", "created_at"),
        Index(
            "uq_xianyu_auto_reply_logs_inbound",
            "account_id",
            "inbound_message_pk",
            unique=True,
        ),
    )

    log_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("xianyu_users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    inbound_message_pk: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outbound_message_pk: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    matched_keyword: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    account: Mapped[AccountORM] = relationship(back_populates="auto_reply_logs")


class DeliveryTemplateORM(Base):
    __tablename__ = "xianyu_delivery_templates"
    __table_args__ = (
        Index("ix_xianyu_delivery_templates_account_priority", "account_id", "priority"),
    )

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="delivery_templates")


class DeliveryRecordORM(Base):
    __tablename__ = "xianyu_delivery_records"
    __table_args__ = (
        Index("ix_xianyu_delivery_records_account_created", "account_id", "created_at"),
        Index("ix_xianyu_delivery_records_conversation_created", "account_id", "conversation_id", "created_at"),
        Index("ix_xianyu_delivery_records_card", "account_id", "card_id"),
        Index("ix_xianyu_delivery_records_order", "account_id", "order_id"),
    )

    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_pk: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("xianyu_orders.order_pk", ondelete="SET NULL"), nullable=True, index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    receiver_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    card_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_message_pk: Mapped[str | None] = mapped_column(String(64), nullable=True)
    send_message_pk: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    account: Mapped[AccountORM] = relationship(back_populates="delivery_records")
    order: Mapped[OrderORM | None] = relationship(back_populates="delivery_records")


class DeliveryAutomationSettingORM(Base):
    __tablename__ = "xianyu_delivery_automation_settings"

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_only")
    require_order_card: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    duplicate_guard_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_status_allowlist: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="delivery_automation_setting")


class ProductImageAssetORM(Base):
    __tablename__ = "xianyu_product_image_assets"
    __table_args__ = (
        Index("ix_xianyu_product_image_assets_account_created", "account_id", "created_at"),
        Index("ix_xianyu_product_image_assets_sha256", "account_id", "sha256"),
    )

    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(24), nullable=True, default="staged")
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    last_referenced_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    account: Mapped[AccountORM] = relationship(back_populates="product_images")


class ProductDraftORM(Base):
    __tablename__ = "xianyu_product_drafts"
    __table_args__ = (
        Index("ix_xianyu_product_drafts_account_updated", "account_id", "updated_at"),
        Index("ix_xianyu_product_drafts_status", "account_id", "status"),
    )

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[str] = mapped_column(String(64), nullable=False)
    original_price: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category_hint: Mapped[str | None] = mapped_column(String(120), nullable=True)
    images: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_choice: Mapped[str | None] = mapped_column(String(32), nullable=True, default="free_shipping")
    post_price: Mapped[str | None] = mapped_column(String(64), nullable=True)
    can_self_pickup: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    location_mode: Mapped[str | None] = mapped_column(String(32), nullable=True, default="account_default")
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="product_drafts")


class ProductLocationCacheORM(Base):
    __tablename__ = "xianyu_product_location_cache"
    __table_args__ = (
        Index("ix_xianyu_product_location_cache_fetched", "account_id", "fetched_at"),
    )

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    cache_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    options: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    account: Mapped[AccountORM] = relationship(back_populates="product_location_caches")


class ProductPlatformLocationORM(Base):
    __tablename__ = "xianyu_product_platform_locations"
    __table_args__ = (
        Index("ix_xianyu_platform_locations_account_seen", "account_id", "last_seen_at"),
    )

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    prov: Mapped[str] = mapped_column(String(80), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    area: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    division_id: Mapped[str] = mapped_column(String(64), nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    poi_id: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    poi_name: Mapped[str] = mapped_column(String(200), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    account: Mapped[AccountORM] = relationship(back_populates="product_platform_locations")


class PublishAddressGroupORM(Base):
    __tablename__ = "xianyu_publish_address_groups"
    __table_args__ = (UniqueConstraint("name", name="uq_xianyu_publish_address_groups_name"),)

    group_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    avoid_recent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    accounts: Mapped[list["PublishAddressGroupAccountORM"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    addresses: Mapped[list["PublishAddressORM"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class PublishAddressGroupAccountORM(Base):
    __tablename__ = "xianyu_publish_address_group_accounts"

    group_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_publish_address_groups.group_id", ondelete="CASCADE"), primary_key=True
    )
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"), primary_key=True
    )

    group: Mapped[PublishAddressGroupORM] = relationship(back_populates="accounts")


class PublishAddressORM(Base):
    __tablename__ = "xianyu_publish_addresses"
    __table_args__ = (
        UniqueConstraint("group_id", "fingerprint", name="uq_xianyu_publish_addresses_group_location"),
        Index("ix_xianyu_publish_addresses_group_enabled", "group_id", "enabled"),
    )

    address_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_publish_address_groups.group_id", ondelete="CASCADE"), nullable=False
    )
    source_account_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("xianyu_accounts.account_id", ondelete="SET NULL"), nullable=True
    )
    platform_location_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    prov: Mapped[str] = mapped_column(String(80), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    area: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    division_id: Mapped[str] = mapped_column(String(64), nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    poi_id: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    poi_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    group: Mapped[PublishAddressGroupORM] = relationship(back_populates="addresses")


class PublishAddressUsageORM(Base):
    __tablename__ = "xianyu_publish_address_usages"
    __table_args__ = (
        Index("ix_xianyu_publish_address_usages_recent", "group_id", "account_id", "selected_at"),
    )

    usage_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_publish_address_groups.group_id", ondelete="CASCADE"), nullable=False
    )
    address_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_publish_addresses.address_id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"), nullable=False
    )
    draft_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="selected")
    selected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class ProductPublishTaskORM(Base):
    __tablename__ = "xianyu_product_publish_tasks"
    __table_args__ = (
        Index("ix_xianyu_product_publish_tasks_account_created", "account_id", "created_at"),
        Index("ix_xianyu_product_publish_tasks_status", "account_id", "status"),
        Index(
            "uq_xianyu_product_publish_tasks_idempotency",
            "account_id",
            "idempotency_key",
            unique=True,
        ),
    )

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    draft_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_export")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True, default="pending")
    unique_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    item_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    failure_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    attempt_no: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_certainty: Mapped[str | None] = mapped_column(String(32), nullable=True)
    catalog_hidden_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    account: Mapped[AccountORM] = relationship(back_populates="product_publish_tasks")


class ProductPublishTaskAssetORM(Base):
    __tablename__ = "xianyu_product_publish_task_assets"
    __table_args__ = (
        Index("ix_xianyu_product_task_assets_asset", "asset_id", "retain_until"),
    )

    task_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_product_publish_tasks.task_id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_product_image_assets.asset_id", ondelete="CASCADE"),
        primary_key=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retain_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class ProductItemORM(Base):
    __tablename__ = "xianyu_product_items"
    __table_args__ = (
        Index("ix_xianyu_product_items_account_status", "account_id", "platform_status"),
        Index("ix_xianyu_product_items_account_seen", "account_id", "last_seen_at"),
        Index("ix_xianyu_product_items_account_published", "account_id", "published_at"),
    )

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    price: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    category_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    detail_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    platform_item_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    want_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    want_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform_status: Mapped[str] = mapped_column(String(32), nullable=False, default="selling")
    sync_state: Mapped[str] = mapped_column(String(32), nullable=False, default="current")
    missing_sync_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_polished_on: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_polished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    published_at_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="unknown"
    )
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    account: Mapped[AccountORM] = relationship(back_populates="product_items")


class ProductSyncSettingORM(Base):
    __tablename__ = "xianyu_product_sync_settings"

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    sync_jitter_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    full_sync_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    publish_verify_delay_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )
    auto_polish_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    polish_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    polish_jitter_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_full_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    last_polish_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    next_polish_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    account: Mapped[AccountORM] = relationship(back_populates="product_sync_setting")


class ProductOperationRunORM(Base):
    __tablename__ = "xianyu_product_operation_runs"
    __table_args__ = (
        Index("ix_xianyu_product_runs_account_created", "account_id", "created_at"),
        Index("ix_xianyu_product_runs_active", "account_id", "operation", "status"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    full_sync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requested_item_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    account: Mapped[AccountORM] = relationship(back_populates="product_operation_runs")
    items: Mapped[list["ProductOperationItemORM"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class ProductOperationItemORM(Base):
    __tablename__ = "xianyu_product_operation_items"
    __table_args__ = (Index("ix_xianyu_product_operation_items_run", "run_id"),)

    result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_product_operation_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    run: Mapped[ProductOperationRunORM] = relationship(back_populates="items")


class ChatwootConfigORM(Base):
    """Platform-wide Chatwoot managed-inbox configuration."""

    __tablename__ = "xianyu_chatwoot_config"

    config_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default="default", server_default="default"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    account_alerts_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    offline_alert_delay_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120, server_default="120"
    )
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    chatwoot_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    credential_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unconfigured", server_default="unconfigured"
    )
    credential_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    push_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="unknown"
    )
    push_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="unknown"
    )
    webhook_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    inbox_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="unknown"
    )
    inbox_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    label_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="unknown"
    )
    label_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="disabled", server_default="disabled"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_webhook_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_push_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class WebNotificationConfigORM(Base):
    """Platform-wide browser notification sound configuration."""

    __tablename__ = "xianyu_web_notification_config"

    config_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default="default", server_default="default"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    sound_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sound_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sound_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sound_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sound_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class ChatwootInboxBindingORM(Base):
    """Automatically managed Chatwoot API inbox for one Xianyu account."""

    __tablename__ = "xianyu_chatwoot_inbox_bindings"
    __table_args__ = (
        UniqueConstraint(
            "chatwoot_inbox_id",
            name="uq_xianyu_chatwoot_inbox_binding_remote",
        ),
        UniqueConstraint(
            "inbox_identifier",
            name="uq_xianyu_chatwoot_inbox_binding_identifier",
        ),
        Index("ix_xianyu_chatwoot_inbox_binding_status", "status", "updated_at"),
    )

    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        primary_key=True,
    )
    config_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_chatwoot_config.config_id", ondelete="CASCADE"),
        nullable=False,
        default="default",
        server_default="default",
    )
    chatwoot_inbox_id: Mapped[int] = mapped_column(Integer, nullable=False)
    inbox_identifier: Mapped[str] = mapped_column(String(160), nullable=False)
    webhook_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    label_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    alert_source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    alert_contact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    alert_conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_alert_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_alert_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ready", server_default="ready"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class ChatwootContactORM(Base):
    __tablename__ = "xianyu_chatwoot_contacts"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "peer_user_id",
            name="uq_xianyu_chatwoot_contact_peer",
        ),
        UniqueConstraint(
            "account_id",
            "source_id",
            name="uq_xianyu_chatwoot_contact_source",
        ),
    )

    contact_map_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    peer_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False)
    chatwoot_contact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class ChatwootConversationORM(Base):
    __tablename__ = "xianyu_chatwoot_conversations"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "conversation_id",
            name="uq_xianyu_chatwoot_conversation_local",
        ),
        UniqueConstraint(
            "chatwoot_conversation_id",
            name="uq_xianyu_chatwoot_conversation_remote",
        ),
    )

    conversation_map_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    peer_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False)
    chatwoot_conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chatwoot_inbox_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inbox_identifier: Mapped[str | None] = mapped_column(String(160), nullable=True)
    chatwoot_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    remote_agent_last_seen_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    read_synced_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class ChatwootMessageORM(Base):
    __tablename__ = "xianyu_chatwoot_messages"
    __table_args__ = (
        Index(
            "uq_xianyu_chatwoot_message_local",
            "account_id",
            "message_pk",
            unique=True,
        ),
        Index(
            "ix_xianyu_chatwoot_message_remote",
            "account_id",
            "chatwoot_message_id",
        ),
        Index("ix_xianyu_chatwoot_messages_state", "state", "updated_at"),
    )

    message_map_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    message_pk: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chatwoot_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chatwoot_conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    origin: Mapped[str] = mapped_column(String(24), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class ChatwootWebhookEventORM(Base):
    __tablename__ = "xianyu_chatwoot_webhook_events"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_xianyu_chatwoot_webhook_event"),
        Index("ix_xianyu_chatwoot_webhook_status", "status", "created_at"),
    )

    delivery_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    config_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("xianyu_chatwoot_config.config_id", ondelete="CASCADE"),
        nullable=False,
        default="default",
        server_default="default",
    )
    event_name: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class BackgroundTaskORM(Base):
    __tablename__ = "xianyu_background_tasks"
    __table_args__ = (
        Index("ix_xianyu_background_tasks_created", "created_at"),
        Index("ix_xianyu_background_tasks_status", "status", "created_at"),
        Index("ix_xianyu_background_tasks_lease", "status", "lease_expires_at"),
        Index("ix_xianyu_background_tasks_due", "status", "run_after", "created_at"),
        Index("ix_xianyu_background_tasks_account", "account_id", "created_at"),
        Index("uq_xianyu_background_tasks_dedupe", "dedupe_key", unique=True),
    )

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_type: Mapped[str] = mapped_column(String(120), nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    run_after: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
    queued_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AuditLogORM(Base):
    __tablename__ = "xianyu_audit_logs"
    __table_args__ = (
        Index("ix_xianyu_audit_logs_created", "created_at"),
        Index("ix_xianyu_audit_logs_success", "success", "created_at"),
    )

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="admin")
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target: Mapped[str] = mapped_column(String(500), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
