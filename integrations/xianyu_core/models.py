"""Stable internal models for Xianyu account sessions and messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .identity import ClientIdentity


class ConnectionState(StrEnum):
    """Runtime state for one Xianyu account connection."""

    DISABLED = "disabled"
    STOPPED = "stopped"
    CONNECTING = "connecting"
    ONLINE = "online"
    RECONNECTING = "reconnecting"
    OFFLINE = "offline"
    AUTH_EXPIRED = "auth_expired"
    RISK_BLOCKED = "risk_blocked"
    PROXY_FAILED = "proxy_failed"
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class InteractiveVerification:
    """Interactive platform verification requested while obtaining an IM token."""

    account_id: str
    reason_code: str
    verification_url: str | None = None
    detected_at_ms: int | None = None


class Direction(StrEnum):
    """Message direction relative to the managed account."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(StrEnum):
    """Normalized message types consumed by business modules."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    CARD = "card"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class ChatMediaAttachment:
    """Normalized remote media attached to a chat event."""

    attachment_type: str
    remote_url: str
    mime_type: str | None = None
    size_bytes: int | None = None
    duration_seconds: int | None = None


@dataclass(slots=True)
class ProxyConfig:
    """Per-account SOCKS proxy configuration.

    Only SOCKS5/SOCKS5h is supported by design. HTTP proxy support is excluded
    to avoid mixed outbound behavior between WS and MTOP requests.
    """

    enabled: bool = False
    required: bool = False
    scheme: str = "socks5h"
    host: str = ""
    port: int | None = None
    username: str | None = None
    password: str | None = None


@dataclass(slots=True)
class AccountConfig:
    """Runtime configuration for one account session."""

    account_id: str
    cookie: str
    nickname: str | None = None
    enabled: bool = True
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    client_identity: ClientIdentity = field(default_factory=ClientIdentity)
    im_token: str | None = None
    im_token_expires_at_ms: int | None = None


@dataclass(slots=True)
class ChatMessageEvent:
    """Normalized chat event emitted by the protocol adapter."""

    account_id: str
    conversation_id: str
    message_id: str | None
    peer_user_id: str | None
    peer_name: str | None
    direction: Direction
    message_type: MessageType
    content: str
    raw_payload: Mapping[str, Any] = field(default_factory=dict)
    item_id: str | None = None
    created_at_ms: int | None = None
    attachments: list[ChatMediaAttachment] = field(default_factory=list)


@dataclass(slots=True)
class ConversationSummary:
    """One normalized conversation returned by the Xianyu IM history RPC."""

    account_id: str
    conversation_id: str
    peer_user_id: str | None = None
    peer_name: str | None = None
    item_id: str | None = None
    item_title: str | None = None
    item_price: str | None = None
    item_image_url: str | None = None
    item_url: str | None = None
    last_message_content: str = ""
    last_message_type: MessageType = MessageType.UNKNOWN
    last_message_direction: Direction | None = None
    last_message_at_ms: int | None = None
    unread_count: int = 0
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConversationPage:
    """Cursor page returned by the Xianyu conversation RPC."""

    items: list[ConversationSummary] = field(default_factory=list)
    has_more: bool = False
    next_cursor: int | None = None


@dataclass(slots=True)
class MessagePage:
    """Cursor page returned by the Xianyu message history RPC."""

    items: list[ChatMessageEvent] = field(default_factory=list)
    has_more: bool = False
    next_cursor: int | None = None


@dataclass(slots=True)
class SendMessageResult:
    """Result returned by outbound message operations."""

    success: bool
    account_id: str
    conversation_id: str
    message_id: str | None = None
    error: str | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlatformBlacklistResult:
    """Authoritative platform blacklist state for one conversation."""

    success: bool
    account_id: str
    conversation_id: str
    blocked: bool | None = None
    error: str | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)
