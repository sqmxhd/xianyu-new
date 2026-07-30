"""Durable Chatwoot API-inbox bridge.

The bridge deliberately keeps Chatwoot identifiers separate from Xianyu
identifiers.  Webhook handlers only authenticate, persist and enqueue work;
network and platform writes are performed by the background worker.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import mimetypes
import re
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from integrations.xianyu_core.images import MAX_IMAGE_INPUT_BYTES

from .executors import run_db_blocking, run_external_blocking
from .orm import (
    AccountORM,
    ChatwootConfigORM,
    ChatwootContactORM,
    ChatwootConversationORM,
    ChatwootInboxBindingORM,
    ChatwootMessageORM,
    ChatwootWebhookEventORM,
    ConversationORM,
    ConversationReadStateORM,
    MessageORM,
    PeerIdentityORM,
    UserORM,
    utcnow,
)
from .queue import enqueue_background_task
from .schemas import (
    BackgroundTaskCreatePayload,
    ChatwootConfigPayload,
    ChatwootConfigUpdatePayload,
    ChatwootTestResultPayload,
    ChatwootWebhookAcceptedPayload,
)
from .sensitive import decrypt_sensitive, encrypt_sensitive
from .settings import settings
from .store import AccountStore


logger = logging.getLogger(__name__)

CHATWOOT_LOCAL_MESSAGE_TASK = "chatwoot.sync_local_message"
CHATWOOT_WEBHOOK_TASK = "chatwoot.process_webhook"
CHATWOOT_ACCOUNT_STATUS_TASK = "chatwoot.sync_account_status"
CHATWOOT_ACCOUNT_METADATA_TASK = "chatwoot.sync_account_metadata"
CHATWOOT_ACCOUNT_ALERT_TASK = "chatwoot.send_account_alert"
CHATWOOT_ACCOUNT_ALERT_STATES = frozenset(
    {"offline", "auth_expired", "risk_blocked", "proxy_failed", "error"}
)
DEFAULT_PLATFORM = "xianyu"
PLATFORM_DISPLAY_NAMES = {
    "xianyu": "闲鱼",
}
MAX_WEBHOOK_BYTES = 2 * 1024 * 1024
WEBHOOK_MAX_AGE_SECONDS = 300
MAX_IMAGE_REDIRECTS = 3
MAX_AUDIO_INPUT_BYTES = 20 * 1024 * 1024
MAX_AUDIO_REDIRECTS = 3
XIANYU_AUDIO_HOST_SUFFIXES = (".aliyuncs.com",)
CHATWOOT_CONFIG_ID = "default"
CHATWOOT_CALLBACK_PATH = "/api/integrations/chatwoot/webhook"
CHATWOOT_INBOX_LOCK_TO_SINGLE_CONVERSATION = False
SHANGHAI_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
CHATWOOT_OUTBOUND_AUDIO_UNSUPPORTED_MESSAGE = (
    "当前闲鱼通道仅支持从 Chatwoot 发送文字和图片；"
    "语音仅支持接收和播放，本条未发送"
)
_AUDIO_FILE_EXTENSIONS = frozenset(
    {
        ".aac",
        ".amr",
        ".flac",
        ".m4a",
        ".mp3",
        ".oga",
        ".ogg",
        ".opus",
        ".wav",
        ".wave",
        ".webm",
    }
)
_ACCOUNT_LABEL_COLORS = (
    "#1f93ff",
    "#7c3aed",
    "#059669",
    "#dc2626",
    "#d97706",
    "#0891b2",
    "#db2777",
    "#4f46e5",
)
_CUSTOM_ATTRIBUTE_DEFINITIONS = (
    {
        "attribute_display_name": "来源平台",
        "attribute_display_type": 0,
        "attribute_description": "该客户或会话所属的平台",
        "attribute_key": "source_platform_name",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源平台标识",
        "attribute_display_type": 0,
        "attribute_description": "系统内部使用的平台唯一标识",
        "attribute_key": "source_platform",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源账户",
        "attribute_display_type": 0,
        "attribute_description": "该会话所属的平台账户名称",
        "attribute_key": "source_account_name",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源账户 ID",
        "attribute_display_type": 0,
        "attribute_description": "该会话所属的平台账户唯一标识",
        "attribute_key": "source_account_id",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源客户 ID",
        "attribute_display_type": 0,
        "attribute_description": "该会话客户在来源平台中的唯一标识",
        "attribute_key": "source_customer_id",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源客户名称",
        "attribute_display_type": 0,
        "attribute_description": "该会话客户在来源平台中的显示名称",
        "attribute_key": "source_customer_name",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源会话 ID",
        "attribute_display_type": 0,
        "attribute_description": "来源平台中的原始会话标识",
        "attribute_key": "source_conversation_id",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源账户状态",
        "attribute_display_type": 0,
        "attribute_description": "来源平台账户的当前运行状态",
        "attribute_key": "source_account_state",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源账户在线",
        "attribute_display_type": 5,
        "attribute_description": "来源平台账户当前是否在线",
        "attribute_key": "source_account_online",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "闲鱼账号名称",
        "attribute_display_type": 0,
        "attribute_description": "该客户或会话所属的闲鱼账号",
        "attribute_key": "xianyu_account_name",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "闲鱼账号 ID",
        "attribute_display_type": 0,
        "attribute_description": "本系统中的闲鱼账号唯一标识",
        "attribute_key": "xianyu_account_id",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "闲鱼会话 ID",
        "attribute_display_type": 0,
        "attribute_description": "闲鱼原始会话标识",
        "attribute_key": "xianyu_conversation_id",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "闲鱼账号状态",
        "attribute_display_type": 0,
        "attribute_description": "闲鱼账号的当前运行状态",
        "attribute_key": "xianyu_account_state",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "闲鱼账号在线",
        "attribute_display_type": 5,
        "attribute_description": "闲鱼账号当前是否在线",
        "attribute_key": "xianyu_account_online",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "闲鱼状态说明",
        "attribute_display_type": 0,
        "attribute_description": "闲鱼账号最近一次运行状态说明",
        "attribute_key": "xianyu_account_status_message",
        "attribute_model": 0,
    },
    {
        "attribute_display_name": "来源平台",
        "attribute_display_type": 0,
        "attribute_description": "该客户所属的平台",
        "attribute_key": "source_platform_name",
        "attribute_model": 1,
    },
    {
        "attribute_display_name": "来源平台标识",
        "attribute_display_type": 0,
        "attribute_description": "系统内部使用的平台唯一标识",
        "attribute_key": "source_platform",
        "attribute_model": 1,
    },
    {
        "attribute_display_name": "来源账户",
        "attribute_display_type": 0,
        "attribute_description": "该客户所属的平台账户名称",
        "attribute_key": "source_account_name",
        "attribute_model": 1,
    },
    {
        "attribute_display_name": "来源账户 ID",
        "attribute_display_type": 0,
        "attribute_description": "该客户所属的平台账户唯一标识",
        "attribute_key": "source_account_id",
        "attribute_model": 1,
    },
    {
        "attribute_display_name": "来源客户 ID",
        "attribute_display_type": 0,
        "attribute_description": "客户在来源平台中的唯一标识",
        "attribute_key": "source_customer_id",
        "attribute_model": 1,
    },
    {
        "attribute_display_name": "来源客户名称",
        "attribute_display_type": 0,
        "attribute_description": "客户在来源平台中的显示名称",
        "attribute_key": "source_customer_name",
        "attribute_model": 1,
    },
    {
        "attribute_display_name": "所属闲鱼账号",
        "attribute_display_type": 0,
        "attribute_description": "该客户所属的闲鱼账号名称",
        "attribute_key": "xianyu_account_name",
        "attribute_model": 1,
    },
    {
        "attribute_display_name": "闲鱼账号 ID",
        "attribute_display_type": 0,
        "attribute_description": "该客户所属的闲鱼账号唯一标识",
        "attribute_key": "xianyu_account_id",
        "attribute_model": 1,
    },
    {
        "attribute_display_name": "闲鱼客户 ID",
        "attribute_display_type": 0,
        "attribute_description": "闲鱼客户唯一标识",
        "attribute_key": "xianyu_peer_user_id",
        "attribute_model": 1,
    },
)


class ChatwootIntegrationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


def _chatwoot_callback_url() -> str:
    if not settings.public_base_url:
        return CHATWOOT_CALLBACK_PATH
    return f"{settings.public_base_url}{CHATWOOT_CALLBACK_PATH}"


def _chatwoot_tls_verify() -> bool | str:
    bundle = settings.chatwoot_ca_bundle
    if not bundle:
        return True
    path = Path(bundle)
    if not path.is_file():
        raise ChatwootIntegrationError(
            f"Chatwoot CA 证书文件不存在: {bundle}"
        )
    return str(path)


def _json_object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: object) -> str:
    return str(value or "").strip()


def _remote_id(value: object) -> str | None:
    normalized = _string(value)
    return normalized or None


def _message_is_outgoing(value: object) -> bool:
    normalized = _string(value).lower()
    return normalized in {"1", "outgoing"}


def _message_is_private(message: dict[str, Any]) -> bool:
    value = message.get("private")
    return value is True or _string(value).lower() == "true"


def _message_was_deleted(message: dict[str, Any]) -> bool:
    attributes = _json_object(message.get("content_attributes"))
    value = attributes.get("deleted")
    return value is True or _string(value).lower() == "true"


def _message_recall(message: dict[str, Any]) -> dict[str, Any]:
    attributes = _json_object(message.get("content_attributes"))
    recall = attributes.get("xianyu_recall") or attributes.get("xianyuRecall")
    return _json_object(recall)


def _message_recall_state(message: dict[str, Any]) -> str:
    return _string(_message_recall(message).get("state")).lower()


def _event_message(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("message")
    return _json_object(nested) if isinstance(nested, dict) else payload


def _event_conversation(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("conversation")
    if isinstance(nested, dict):
        return nested
    message = _event_message(payload)
    return _json_object(message.get("conversation"))


def _extract_chatwoot_conversation_id(payload: dict[str, Any]) -> str | None:
    conversation = _event_conversation(payload)
    return _remote_id(
        conversation.get("id")
        or conversation.get("display_id")
        or payload.get("conversation_id")
    )


def _extract_chatwoot_message_id(payload: dict[str, Any]) -> str | None:
    return _remote_id(_event_message(payload).get("id"))


def _extract_inbox_identifier(payload: dict[str, Any]) -> str | None:
    candidates = (
        payload.get("inbox"),
        _event_message(payload).get("inbox"),
        _event_conversation(payload).get("inbox"),
    )
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        identifier = _remote_id(
            candidate.get("identifier") or candidate.get("inbox_identifier")
        )
        if identifier:
            return identifier
    return None


def _extract_chatwoot_inbox_id(payload: dict[str, Any]) -> int | None:
    candidates: tuple[object, ...] = (
        payload.get("inbox_id"),
        _event_message(payload).get("inbox_id"),
        _event_conversation(payload).get("inbox_id"),
    )
    for container in (
        payload.get("inbox"),
        _event_message(payload).get("inbox"),
        _event_conversation(payload).get("inbox"),
    ):
        if isinstance(container, dict):
            candidates += (container.get("id"),)
    for candidate in candidates:
        try:
            inbox_id = int(candidate)
        except (TypeError, ValueError):
            continue
        if inbox_id > 0:
            return inbox_id
    return None


def _extract_chatwoot_account_id(payload: dict[str, Any]) -> int | None:
    conversation = _event_conversation(payload)
    candidates = (
        _json_object(payload.get("account")).get("id"),
        payload.get("account_id"),
        _json_object(conversation.get("account")).get("id"),
        conversation.get("account_id"),
    )
    for candidate in candidates:
        try:
            account_id = int(candidate)
        except (TypeError, ValueError):
            continue
        if account_id > 0:
            return account_id
    return None


def _chatwoot_epoch_seconds(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        timestamp = int(float(value))
    except (TypeError, ValueError):
        try:
            normalized = _string(value).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        timestamp = int(parsed.astimezone(UTC).timestamp())
    return timestamp if timestamp > 0 else None


def _chatwoot_read_snapshot(payload: dict[str, Any]) -> dict[str, Any] | None:
    conversation = _event_conversation(payload)
    if not conversation and (
        "unread_count" in payload
        or "agent_last_seen_at" in payload
        or "assignee_last_seen_at" in payload
    ):
        conversation = payload
    if "unread_count" not in conversation:
        return None
    try:
        unread_count = max(0, int(conversation["unread_count"]))
    except (TypeError, ValueError):
        return None
    seen_values = [
        value
        for value in (
            _chatwoot_epoch_seconds(conversation.get("agent_last_seen_at")),
            _chatwoot_epoch_seconds(conversation.get("assignee_last_seen_at")),
        )
        if value is not None
    ]
    if not seen_values:
        return None
    remote_conversation_id = _remote_id(
        conversation.get("id")
        or conversation.get("display_id")
        or payload.get("conversation_id")
    )
    if not remote_conversation_id:
        return None
    seen_at_epoch = max(seen_values)
    return {
        "chatwoot_conversation_id": remote_conversation_id,
        "unread_count": unread_count,
        "seen_at_epoch": seen_at_epoch,
        "seen_at": datetime.fromtimestamp(seen_at_epoch, UTC),
    }


def _platform_name(platform: object) -> str:
    key = _string(platform).lower() or DEFAULT_PLATFORM
    return PLATFORM_DISPLAY_NAMES.get(key, key)


def _account_state_indicator(state: object) -> str:
    normalized = _string(state).lower()
    if normalized == "online":
        return "🟢"
    if normalized in {"connecting", "reconnecting", "starting"}:
        return "🟡"
    return "🔴"


def _managed_inbox_name(
    *,
    platform: object,
    account_name: str,
    state: object,
) -> str:
    return (
        f"{_account_state_indicator(state)} "
        f"[{_platform_name(platform)}] {account_name}"
    )[:100]


def _account_label_title(
    account_name: str,
    account_id: str,
    platform: str = DEFAULT_PLATFORM,
) -> str:
    normalized = re.sub(r"[^\w-]+", "-", account_name, flags=re.UNICODE).strip("-_")
    normalized = normalized[:36] or "账号"
    return f"{_platform_name(platform)}-{normalized}-{account_id[:4].lower()}"


def _account_label_color(account_id: str) -> str:
    index = int(hashlib.sha256(account_id.encode()).hexdigest()[:8], 16)
    return _ACCOUNT_LABEL_COLORS[index % len(_ACCOUNT_LABEL_COLORS)]


def _visible_contact_name(
    peer_name: str,
    account_name: str,
    platform: str = DEFAULT_PLATFORM,
) -> str:
    del peer_name
    platform_name = _platform_name(platform)
    normalized_account_name = account_name.strip() or "未命名账号"
    return f"{platform_name}｜{normalized_account_name}"[:255]


def _visible_customer_name(value: object, fallback: object = None) -> str:
    normalized = re.sub(r"\s+", " ", _string(value)).strip()
    if not normalized:
        normalized = re.sub(r"\s+", " ", _string(fallback)).strip()
    return normalized or "未知客户"


def _chatwoot_inbound_content(
    context: dict[str, Any],
    content: str,
    *,
    has_images: bool,
    has_audio: bool,
) -> str:
    customer_name = _visible_customer_name(
        context.get("peer_name"),
        context.get("peer_user_id"),
    )
    rendered_content = content
    if not rendered_content:
        if has_images and has_audio:
            rendered_content = "[图片/语音]"
        elif has_images:
            rendered_content = "[图片]"
        elif has_audio:
            rendered_content = "[语音]"
        else:
            rendered_content = "[非文本消息]"
    return f"{customer_name}：{rendered_content}"


def _contact_identity_payload(
    *,
    account_id: str,
    account_name: str,
    platform: str = DEFAULT_PLATFORM,
    peer_user_id: str,
    peer_name: str,
    client_hmac_token: str | None,
) -> dict[str, Any]:
    platform_key = _string(platform).lower() or DEFAULT_PLATFORM
    platform_name = _platform_name(platform_key)
    identifier = f"{platform_key}:{account_id}:{peer_user_id}"
    payload: dict[str, Any] = {
        "identifier": identifier,
        "name": _visible_contact_name(peer_name, account_name, platform_key),
        "custom_attributes": {
            "source_platform": platform_key,
            "source_platform_name": platform_name,
            "source_account_id": account_id,
            "source_account_name": account_name,
            "source_customer_id": peer_user_id,
            "source_customer_name": _visible_customer_name(
                peer_name,
                peer_user_id,
            ),
            "xianyu_account_id": account_id,
            "xianyu_account_name": account_name,
            "xianyu_peer_user_id": peer_user_id,
        },
    }
    if client_hmac_token:
        payload["identifier_hash"] = hmac.new(
            client_hmac_token.encode(),
            identifier.encode(),
            hashlib.sha256,
        ).hexdigest()
    return payload


def _conversation_source_attributes(
    config: dict[str, Any],
    *,
    conversation_id: str,
    peer_user_id: str | None = None,
    state: str | None = None,
    status_message: str | None = None,
) -> dict[str, Any]:
    platform = _string(config.get("platform")).lower() or DEFAULT_PLATFORM
    platform_name = _platform_name(platform)
    account_id = _string(config.get("account_id"))
    account_name = _string(config.get("account_name")) or account_id[:8]
    attributes: dict[str, Any] = {
        "source_platform": platform,
        "source_platform_name": platform_name,
        "source_account_id": account_id,
        "source_account_name": account_name,
        "source_conversation_id": conversation_id,
        "xianyu_account_id": account_id,
        "xianyu_account_name": account_name,
        "xianyu_conversation_id": conversation_id,
    }
    if peer_user_id:
        attributes["source_customer_id"] = peer_user_id
    if state is not None:
        attributes.update(
            {
                "source_account_state": state,
                "source_account_online": state == "online",
                "xianyu_account_state": state,
                "xianyu_account_online": state == "online",
                "xianyu_account_status_message": (status_message or "")[:300],
            }
        )
    return attributes


def _extract_attachment_urls(message: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for attachment in message.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        file_type = _string(attachment.get("file_type")).lower()
        if file_type and file_type not in {"image", "file"}:
            continue
        url = _string(
            attachment.get("data_url")
            or attachment.get("file_url")
            or attachment.get("download_url")
        )
        if url and url not in urls:
            urls.append(url)
    return urls


def _attachment_is_audio(attachment: dict[str, Any]) -> bool:
    file_type = _string(attachment.get("file_type")).lower()
    mime_type = _string(
        attachment.get("content_type") or attachment.get("mime_type")
    ).lower()
    if file_type in {"audio", "voice"} or mime_type.startswith("audio/"):
        return True

    # Chatwoot normally labels audio attachments correctly, but API clients and
    # older payloads may only provide a filename or URL. Keep the bridge-side
    # guard effective even when the browser-side restriction is bypassed.
    for field in (
        "file_name",
        "filename",
        "data_url",
        "file_url",
        "download_url",
        "source_url",
    ):
        value = _string(attachment.get(field))
        if not value:
            continue
        suffix = PurePosixPath(urlsplit(value).path).suffix.lower()
        if suffix in _AUDIO_FILE_EXTENSIONS:
            return True
    return False


def _has_audio_attachment(message: dict[str, Any]) -> bool:
    for attachment in message.get("attachments") or []:
        if isinstance(attachment, dict) and _attachment_is_audio(attachment):
            return True
    return False


def _source_id(account_id: str, peer_user_id: str) -> str:
    digest = hashlib.sha256(f"{account_id}:{peer_user_id}".encode()).hexdigest()
    return f"xy_{digest[:40]}"


def _safe_filename(url: str, mime_type: str) -> str:
    suffix = PurePosixPath(urlsplit(url).path).suffix.lower()
    if not suffix or len(suffix) > 8:
        suffix = mimetypes.guess_extension(mime_type.split(";", 1)[0]) or ".jpg"
    return f"xianyu-{uuid.uuid4().hex[:12]}{suffix}"


def _host_is_private(hostname: str) -> bool:
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise ChatwootIntegrationError(f"图片地址无法解析: {hostname}") from exc
    if not addresses:
        raise ChatwootIntegrationError(f"图片地址无法解析: {hostname}")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    return False


def _url_origin(url: str) -> tuple[str, str, int]:
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise ChatwootIntegrationError("图片附件地址不合法") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ChatwootIntegrationError("图片附件地址不合法")
    effective_port = port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, hostname, effective_port


def _validate_image_url(
    url: str,
    *,
    allowed_private_origin: str | None,
) -> tuple[str, str, int]:
    origin = _url_origin(url)
    _, hostname, _ = origin
    if not _host_is_private(hostname):
        return origin
    if not allowed_private_origin or origin != _url_origin(allowed_private_origin):
        raise ChatwootIntegrationError("图片附件地址指向内网，已拒绝下载")
    return origin


def _download_image(
    url: str,
    *,
    allowed_private_origin: str | None = None,
) -> tuple[bytes, str, str]:
    source_url = url
    allowed_origin = (
        _url_origin(allowed_private_origin) if allowed_private_origin else None
    )
    current_url = url

    with requests.Session() as client:
        client.trust_env = False
        for redirect_count in range(MAX_IMAGE_REDIRECTS + 1):
            current_origin = _validate_image_url(
                current_url,
                allowed_private_origin=allowed_private_origin,
            )
            verify: bool | str = (
                _chatwoot_tls_verify()
                if allowed_origin is not None and current_origin == allowed_origin
                else True
            )
            response = client.get(
                current_url,
                timeout=(5, 20),
                stream=True,
                allow_redirects=False,
                verify=verify,
            )
            if 300 <= response.status_code < 400:
                location = _string(response.headers.get("location"))
                response.close()
                if not location:
                    raise ChatwootIntegrationError("图片附件重定向缺少目标地址")
                if redirect_count >= MAX_IMAGE_REDIRECTS:
                    raise ChatwootIntegrationError("图片附件重定向次数过多")
                next_url = urljoin(current_url, location)
                next_origin = _validate_image_url(
                    next_url,
                    allowed_private_origin=allowed_private_origin,
                )
                if current_origin[0] == "https" and next_origin[0] != "https":
                    raise ChatwootIntegrationError("图片附件重定向禁止降级到 HTTP")
                current_url = next_url
                continue
            try:
                if response.status_code >= 400:
                    raise ChatwootIntegrationError(
                        f"图片附件下载失败: HTTP {response.status_code}"
                    )
                mime_type = (
                    _string(response.headers.get("content-type"))
                    .split(";", 1)[0]
                    .lower()
                )
                if not mime_type.startswith("image/"):
                    raise ChatwootIntegrationError(
                        f"附件不是图片: {mime_type or '未知类型'}"
                    )
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_content(64 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_IMAGE_INPUT_BYTES:
                        raise ChatwootIntegrationError("图片附件超过 10 MB")
                    chunks.append(chunk)
            finally:
                response.close()
            break
        else:  # pragma: no cover - the bounded loop always exits or raises.
            raise ChatwootIntegrationError("图片附件重定向次数过多")
    data = b"".join(chunks)
    if not data:
        raise ChatwootIntegrationError("图片附件为空")
    return data, mime_type, _safe_filename(source_url, mime_type)


def _normalize_xianyu_audio_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise ChatwootIntegrationError("闲鱼语音地址不合法") from exc
    hostname = (parsed.hostname or "").lower()
    trusted = hostname == "aliyuncs.com" or any(
        hostname.endswith(suffix) for suffix in XIANYU_AUDIO_HOST_SUFFIXES
    )
    if (
        parsed.scheme not in {"http", "https"}
        or not trusted
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ChatwootIntegrationError("闲鱼语音地址不在受信任的媒体域名")
    if parsed.scheme == "http":
        parsed = parsed._replace(scheme="https")
    return urlunsplit(parsed)


def _download_xianyu_audio(url: str) -> tuple[bytes, str, str]:
    current_url = _normalize_xianyu_audio_url(url)
    with requests.Session() as client:
        client.trust_env = False
        for redirect_count in range(MAX_AUDIO_REDIRECTS + 1):
            current_url = _normalize_xianyu_audio_url(current_url)
            _, hostname, _ = _url_origin(current_url)
            if _host_is_private(hostname):
                raise ChatwootIntegrationError("闲鱼语音地址指向内网，已拒绝下载")
            response = client.get(
                current_url,
                timeout=(5, 20),
                stream=True,
                allow_redirects=False,
                verify=True,
            )
            if 300 <= response.status_code < 400:
                location = _string(response.headers.get("location"))
                response.close()
                if not location:
                    raise ChatwootIntegrationError("闲鱼语音重定向缺少目标地址")
                if redirect_count >= MAX_AUDIO_REDIRECTS:
                    raise ChatwootIntegrationError("闲鱼语音重定向次数过多")
                next_url = _normalize_xianyu_audio_url(
                    urljoin(current_url, location)
                )
                if urlsplit(next_url).scheme != "https":
                    raise ChatwootIntegrationError("闲鱼语音重定向禁止降级到 HTTP")
                current_url = next_url
                continue
            try:
                if response.status_code >= 400:
                    raise ChatwootIntegrationError(
                        f"闲鱼语音下载失败: HTTP {response.status_code}"
                    )
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_content(64 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_AUDIO_INPUT_BYTES:
                        raise ChatwootIntegrationError("闲鱼语音超过 20 MB")
                    chunks.append(chunk)
            finally:
                response.close()
            break
        else:  # pragma: no cover - the bounded loop always exits or raises.
            raise ChatwootIntegrationError("闲鱼语音重定向次数过多")
    data = b"".join(chunks)
    if not data:
        raise ChatwootIntegrationError("闲鱼语音附件为空")
    if data.startswith(b"#!AMR-WB\n"):
        mime_type = "audio/amr-wb"
    elif data.startswith(b"#!AMR\n"):
        mime_type = "audio/amr"
    else:
        raise ChatwootIntegrationError("闲鱼语音不是有效的 AMR 文件")
    return (
        data,
        mime_type,
        f"xianyu-voice-{uuid.uuid4().hex[:12]}.amr",
    )


def _extract_xianyu_audio_url(
    value: object,
    *,
    _depth: int = 0,
) -> str | None:
    """Recover an AMR URL from current and legacy raw message payloads."""
    if _depth > 12:
        return None
    if isinstance(value, dict):
        audio = value.get("audio")
        if isinstance(audio, dict):
            url = _string(audio.get("url"))
            if url:
                return url
        if _string(value.get("contentType")) == "3":
            url = _string(value.get("url"))
            if url:
                return url
        for nested in value.values():
            found = _extract_xianyu_audio_url(nested, _depth=_depth + 1)
            if found:
                return found
        return None
    if isinstance(value, list):
        for nested in value:
            found = _extract_xianyu_audio_url(nested, _depth=_depth + 1)
            if found:
                return found
        return None
    if not isinstance(value, str) or len(value) > MAX_WEBHOOK_BYTES:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    decoded: object | None = None
    if candidate.startswith(("{", "[")):
        try:
            decoded = json.loads(candidate)
        except (TypeError, ValueError):
            pass
    if decoded is None:
        try:
            padding = "=" * (-len(candidate) % 4)
            raw = base64.b64decode(candidate + padding, validate=True)
            if raw.startswith((b"{", b"[")):
                decoded = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            pass
    if decoded is value or decoded is None:
        return None
    return _extract_xianyu_audio_url(decoded, _depth=_depth + 1)


class ChatwootRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    async def get_config_payload(self) -> ChatwootConfigPayload | None:
        return await run_db_blocking(self._get_config_payload_sync)

    async def get_config_secret(self, inbox_id: int | None = None) -> str | None:
        return await run_db_blocking(self._get_config_secret_sync, inbox_id)

    async def remember_legacy_inbox_id(self, inbox_id: int) -> None:
        await run_db_blocking(self._remember_legacy_inbox_id_sync, inbox_id)

    async def remember_chatwoot_account_id(self, account_id: int) -> None:
        await run_db_blocking(
            self._remember_chatwoot_account_id_sync,
            account_id,
        )

    async def get_inbox_binding(
        self,
        account_id: str,
    ) -> dict[str, Any] | None:
        return await run_db_blocking(self._get_inbox_binding_sync, account_id)

    async def upsert_inbox_binding(
        self,
        *,
        account_id: str,
        chatwoot_inbox_id: int,
        inbox_identifier: str,
        webhook_secret: str,
        label_id: int | None,
        label_title: str | None,
    ) -> dict[str, Any]:
        return await run_db_blocking(
            self._upsert_inbox_binding_sync,
            account_id,
            chatwoot_inbox_id,
            inbox_identifier,
            webhook_secret,
            label_id,
            label_title,
        )

    async def update_inbox_binding_label(
        self,
        *,
        account_id: str,
        label_id: int,
        label_title: str,
    ) -> None:
        await run_db_blocking(
            self._update_inbox_binding_label_sync,
            account_id,
            label_id,
            label_title,
        )

    async def update_account_alert_channel(
        self,
        *,
        account_id: str,
        source_id: str,
        contact_id: str,
        conversation_id: str,
    ) -> None:
        await run_db_blocking(
            self._update_account_alert_channel_sync,
            account_id,
            source_id,
            contact_id,
            conversation_id,
        )

    async def record_account_alert_state(
        self,
        *,
        account_id: str,
        state: str,
    ) -> None:
        await run_db_blocking(
            self._record_account_alert_state_sync,
            account_id,
            state,
        )

    async def get_account_identity(
        self,
        account_id: str,
    ) -> dict[str, str] | None:
        return await run_db_blocking(self._get_account_identity_sync, account_id)

    async def get_config(
        self,
        *,
        account_id: str | None = None,
    ) -> dict[str, Any] | None:
        return await run_db_blocking(self._get_config_sync, account_id)

    async def upsert_config(
        self,
        payload: ChatwootConfigUpdatePayload,
    ) -> ChatwootConfigPayload:
        return await run_db_blocking(self._upsert_config_sync, payload)

    async def record_webhook(
        self,
        *,
        delivery_id: str,
        event_name: str,
        payload_sha256: str,
        raw_payload: bytes,
    ) -> bool:
        return await run_db_blocking(
            self._record_webhook_sync,
            delivery_id,
            event_name,
            payload_sha256,
            raw_payload,
        )

    async def get_webhook(self, delivery_id: str) -> dict[str, Any] | None:
        return await run_db_blocking(self._get_webhook_sync, delivery_id)

    async def finish_webhook(
        self,
        delivery_id: str,
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        await run_db_blocking(
            self._finish_webhook_sync,
            delivery_id,
            status,
            error,
        )

    async def get_local_message_context(
        self,
        account_id: str,
        message_pk: str,
    ) -> dict[str, Any] | None:
        return await run_db_blocking(
            self._get_local_message_context_sync,
            account_id,
            message_pk,
        )

    async def get_local_conversation_context(
        self,
        account_id: str,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        return await run_db_blocking(
            self._get_local_conversation_context_sync,
            account_id,
            conversation_id,
        )

    async def get_conversation_map_by_remote(
        self,
        account_id: str,
        chatwoot_conversation_id: str,
    ) -> dict[str, Any] | None:
        return await run_db_blocking(
            self._get_conversation_map_by_remote_sync,
            account_id,
            chatwoot_conversation_id,
        )

    async def get_conversation_map_by_remote_global(
        self,
        chatwoot_conversation_id: str,
    ) -> dict[str, Any] | None:
        return await run_db_blocking(
            self._get_conversation_map_by_remote_global_sync,
            chatwoot_conversation_id,
        )

    async def ensure_contact_map(
        self,
        *,
        account_id: str,
        peer_user_id: str,
        display_name: str | None,
        avatar_url: str | None,
        chatwoot_contact_id: str | None = None,
    ) -> dict[str, str | None]:
        return await run_db_blocking(
            self._ensure_contact_map_sync,
            account_id,
            peer_user_id,
            display_name,
            avatar_url,
            chatwoot_contact_id,
        )

    async def get_conversation_map(
        self,
        account_id: str,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        return await run_db_blocking(
            self._get_conversation_map_sync,
            account_id,
            conversation_id,
        )

    async def list_conversation_maps(self, account_id: str) -> list[dict[str, Any]]:
        return await run_db_blocking(self._list_conversation_maps_sync, account_id)

    async def list_read_sync_candidates(self) -> list[dict[str, Any]]:
        return await run_db_blocking(self._list_read_sync_candidates_sync)

    async def record_read_sync_observation(
        self,
        chatwoot_conversation_id: str,
        *,
        remote_seen_at: datetime,
        synced: bool,
    ) -> None:
        await run_db_blocking(
            self._record_read_sync_observation_sync,
            chatwoot_conversation_id,
            remote_seen_at,
            synced,
        )

    async def create_conversation_map(
        self,
        *,
        account_id: str,
        conversation_id: str,
        peer_user_id: str,
        source_id: str,
        chatwoot_conversation_id: str,
        chatwoot_inbox_id: int | None = None,
        inbox_identifier: str | None = None,
    ) -> dict[str, Any]:
        return await run_db_blocking(
            self._create_conversation_map_sync,
            account_id,
            conversation_id,
            peer_user_id,
            source_id,
            chatwoot_conversation_id,
            chatwoot_inbox_id,
            inbox_identifier,
        )

    async def record_message_map(
        self,
        *,
        account_id: str,
        message_pk: str | None,
        chatwoot_message_id: str | None,
        chatwoot_conversation_id: str | None,
        origin: str,
        state: str,
        error: str | None = None,
    ) -> None:
        await run_db_blocking(
            self._record_message_map_sync,
            account_id,
            message_pk,
            chatwoot_message_id,
            chatwoot_conversation_id,
            origin,
            state,
            error,
        )

    async def find_message_maps_by_remote(
        self,
        account_id: str,
        chatwoot_message_id: str,
    ) -> list[dict[str, str | None]]:
        return await run_db_blocking(
            self._find_message_maps_by_remote_sync,
            account_id,
            chatwoot_message_id,
        )

    async def find_message_maps_by_remote_global(
        self,
        chatwoot_message_id: str,
    ) -> list[dict[str, str | None]]:
        return await run_db_blocking(
            self._find_message_maps_by_remote_global_sync,
            chatwoot_message_id,
        )

    async def find_message_map_by_local(
        self,
        account_id: str,
        message_pk: str,
    ) -> dict[str, str | None] | None:
        return await run_db_blocking(
            self._find_message_map_by_local_sync,
            account_id,
            message_pk,
        )

    async def set_config_health(
        self,
        *,
        status: str,
        error: str | None = None,
        pushed: bool = False,
        webhook: bool = False,
    ) -> None:
        await run_db_blocking(
            self._set_config_health_sync,
            status,
            error,
            pushed,
            webhook,
        )

    async def update_conversation_status(
        self,
        account_id: str,
        chatwoot_conversation_id: str,
        status: str,
    ) -> None:
        await run_db_blocking(
            self._update_conversation_status_sync,
            account_id,
            chatwoot_conversation_id,
            status,
        )

    def _config_payload(
        self,
        row: ChatwootConfigORM,
        *,
        managed_inbox_count: int = 0,
    ) -> ChatwootConfigPayload:
        webhook_secret = decrypt_sensitive(row.webhook_secret_encrypted) or ""
        client_hmac_token = decrypt_sensitive(row.client_hmac_token_encrypted)
        api_access_token = decrypt_sensitive(row.api_access_token_encrypted)
        has_token = bool(api_access_token)
        return ChatwootConfigPayload(
            config_id=row.config_id,
            enabled=row.enabled,
            account_alerts_enabled=row.account_alerts_enabled,
            offline_alert_delay_seconds=row.offline_alert_delay_seconds,
            base_url=row.base_url,
            inbox_identifier=row.inbox_identifier,
            chatwoot_inbox_id=row.chatwoot_inbox_id,
            webhook_secret=webhook_secret,
            client_hmac_token=client_hmac_token,
            api_access_token=api_access_token,
            chatwoot_account_id=row.chatwoot_account_id,
            has_webhook_secret=bool(webhook_secret),
            has_client_hmac_token=bool(client_hmac_token),
            has_api_access_token=has_token,
            full_outbound_sync_enabled=bool(has_token and row.chatwoot_account_id),
            account_grouping_enabled=bool(
                has_token
                and row.chatwoot_account_id
                and managed_inbox_count > 0
            ),
            managed_inbox_count=managed_inbox_count,
            callback_path=CHATWOOT_CALLBACK_PATH,
            callback_url=row.callback_url or _chatwoot_callback_url(),
            status=row.status,
            last_error=row.last_error,
            last_webhook_at=row.last_webhook_at,
            last_push_at=row.last_push_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _get_config_payload_sync(self) -> ChatwootConfigPayload | None:
        with self._session_factory() as session:
            row = session.get(ChatwootConfigORM, CHATWOOT_CONFIG_ID)
            if row is None:
                return None
            managed_inbox_count = len(
                session.scalars(select(ChatwootInboxBindingORM.account_id)).all()
            )
            return self._config_payload(
                row,
                managed_inbox_count=managed_inbox_count,
            )

    def _get_config_secret_sync(self, inbox_id: int | None) -> str | None:
        with self._session_factory() as session:
            row = session.get(ChatwootConfigORM, CHATWOOT_CONFIG_ID)
            if row is None:
                return None
            if inbox_id is not None:
                binding = session.scalar(
                    select(ChatwootInboxBindingORM).where(
                        ChatwootInboxBindingORM.chatwoot_inbox_id == inbox_id
                    )
                )
                if binding is not None:
                    return decrypt_sensitive(binding.webhook_secret_encrypted)
                if row.chatwoot_inbox_id not in {None, inbox_id}:
                    return None
            return decrypt_sensitive(row.webhook_secret_encrypted)

    def _remember_legacy_inbox_id_sync(self, inbox_id: int) -> None:
        with self._session_factory() as session:
            row = session.get(ChatwootConfigORM, CHATWOOT_CONFIG_ID)
            if row is None or row.chatwoot_inbox_id is not None:
                return
            if session.scalar(
                select(ChatwootInboxBindingORM.account_id).where(
                    ChatwootInboxBindingORM.chatwoot_inbox_id == inbox_id
                )
            ):
                return
            row.chatwoot_inbox_id = inbox_id
            row.updated_at = utcnow()
            session.commit()

    def _remember_chatwoot_account_id_sync(self, account_id: int) -> None:
        with self._session_factory() as session:
            row = session.get(ChatwootConfigORM, CHATWOOT_CONFIG_ID)
            if row is None or row.chatwoot_account_id is not None:
                return
            row.chatwoot_account_id = account_id
            row.updated_at = utcnow()
            session.commit()

    @staticmethod
    def _inbox_binding_dict(row: ChatwootInboxBindingORM) -> dict[str, Any]:
        return {
            "account_id": row.account_id,
            "chatwoot_inbox_id": row.chatwoot_inbox_id,
            "inbox_identifier": row.inbox_identifier,
            "webhook_secret": decrypt_sensitive(row.webhook_secret_encrypted),
            "label_id": row.label_id,
            "label_title": row.label_title,
            "alert_source_id": row.alert_source_id,
            "alert_contact_id": row.alert_contact_id,
            "alert_conversation_id": row.alert_conversation_id,
            "last_alert_state": row.last_alert_state,
            "last_alert_at": row.last_alert_at,
            "status": row.status,
            "last_error": row.last_error,
        }

    def _get_inbox_binding_sync(
        self,
        account_id: str,
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(ChatwootInboxBindingORM, account_id)
            return self._inbox_binding_dict(row) if row else None

    def _upsert_inbox_binding_sync(
        self,
        account_id: str,
        chatwoot_inbox_id: int,
        inbox_identifier: str,
        webhook_secret: str,
        label_id: int | None,
        label_title: str | None,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(ChatwootInboxBindingORM, account_id)
            if row is None:
                row = ChatwootInboxBindingORM(
                    account_id=account_id,
                    config_id=CHATWOOT_CONFIG_ID,
                    chatwoot_inbox_id=chatwoot_inbox_id,
                    inbox_identifier=inbox_identifier,
                    webhook_secret_encrypted=encrypt_sensitive(webhook_secret) or "",
                    created_at=utcnow(),
                )
                session.add(row)
            row.chatwoot_inbox_id = chatwoot_inbox_id
            row.inbox_identifier = inbox_identifier
            row.webhook_secret_encrypted = encrypt_sensitive(webhook_secret) or ""
            row.label_id = label_id
            row.label_title = label_title
            row.status = "ready"
            row.last_error = None
            row.updated_at = utcnow()
            session.commit()
            return self._inbox_binding_dict(row)

    def _update_inbox_binding_label_sync(
        self,
        account_id: str,
        label_id: int,
        label_title: str,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(ChatwootInboxBindingORM, account_id)
            if row is None:
                return
            row.label_id = label_id
            row.label_title = label_title
            row.updated_at = utcnow()
            session.commit()

    def _update_account_alert_channel_sync(
        self,
        account_id: str,
        source_id: str,
        contact_id: str,
        conversation_id: str,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(ChatwootInboxBindingORM, account_id)
            if row is None:
                raise ChatwootIntegrationError("账号 Chatwoot Inbox 尚未创建")
            row.alert_source_id = source_id[:160]
            row.alert_contact_id = contact_id[:128]
            row.alert_conversation_id = conversation_id[:128]
            row.updated_at = utcnow()
            session.commit()

    def _record_account_alert_state_sync(
        self,
        account_id: str,
        state: str,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(ChatwootInboxBindingORM, account_id)
            if row is None:
                raise ChatwootIntegrationError("账号 Chatwoot Inbox 尚未创建")
            row.last_alert_state = state[:32]
            row.last_alert_at = utcnow()
            row.updated_at = row.last_alert_at
            session.commit()

    def _get_account_identity_sync(
        self,
        account_id: str,
    ) -> dict[str, str] | None:
        with self._session_factory() as session:
            row = session.get(AccountORM, account_id)
            if row is None:
                return None
            return {
                "account_id": row.account_id,
                "account_name": row.display_name,
                "platform": row.platform or DEFAULT_PLATFORM,
            }

    def _get_config_sync(self, account_id: str | None) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(ChatwootConfigORM, CHATWOOT_CONFIG_ID)
            if row is None:
                return None
            account = session.get(AccountORM, account_id) if account_id else None
            if account_id and account is None:
                return None
            binding = (
                session.get(ChatwootInboxBindingORM, account_id)
                if account_id
                else None
            )
            runtime = account.runtime if account is not None else None
            return {
                "config_id": row.config_id,
                "account_id": account_id,
                "enabled": bool(
                    row.enabled
                    and (
                        account is None
                        or (account.enabled and account.chat_enabled)
                    )
                ),
                "platform_enabled": bool(row.enabled),
                "account_alerts_enabled": bool(row.account_alerts_enabled),
                "offline_alert_delay_seconds": max(
                    30, min(int(row.offline_alert_delay_seconds or 120), 3600)
                ),
                "account_chat_enabled": bool(account.chat_enabled) if account else None,
                "account_name": account.display_name if account else None,
                "platform": (
                    account.platform if account and account.platform else DEFAULT_PLATFORM
                ),
                "platform_name": _platform_name(
                    account.platform if account else DEFAULT_PLATFORM
                ),
                "account_state": runtime.state if runtime else None,
                "account_status_message": runtime.message if runtime else None,
                "base_url": row.base_url.rstrip("/"),
                "inbox_identifier": (
                    binding.inbox_identifier if binding else row.inbox_identifier
                ),
                "chatwoot_inbox_id": (
                    binding.chatwoot_inbox_id if binding else row.chatwoot_inbox_id
                ),
                "legacy_inbox_identifier": row.inbox_identifier,
                "legacy_chatwoot_inbox_id": row.chatwoot_inbox_id,
                "chatwoot_account_id": row.chatwoot_account_id,
                "webhook_secret": decrypt_sensitive(
                    binding.webhook_secret_encrypted
                    if binding
                    else row.webhook_secret_encrypted
                ),
                "client_hmac_token": (
                    None
                    if binding
                    else decrypt_sensitive(row.client_hmac_token_encrypted)
                ),
                "legacy_client_hmac_token": decrypt_sensitive(
                    row.client_hmac_token_encrypted
                ),
                "api_access_token": decrypt_sensitive(row.api_access_token_encrypted),
                "callback_url": row.callback_url or _chatwoot_callback_url(),
                "managed_inbox": binding is not None,
                "label_id": binding.label_id if binding else None,
                "label_title": binding.label_title if binding else None,
                "alert_source_id": binding.alert_source_id if binding else None,
                "alert_contact_id": binding.alert_contact_id if binding else None,
                "alert_conversation_id": (
                    binding.alert_conversation_id if binding else None
                ),
                "last_alert_state": binding.last_alert_state if binding else None,
                "last_alert_at": binding.last_alert_at if binding else None,
            }

    def _upsert_config_sync(
        self,
        payload: ChatwootConfigUpdatePayload,
    ) -> ChatwootConfigPayload:
        with self._session_factory() as session:
            row = session.get(ChatwootConfigORM, CHATWOOT_CONFIG_ID)
            if row is None:
                if not payload.webhook_secret:
                    raise ValueError("首次配置必须填写 Webhook 秘密")
                row = ChatwootConfigORM(
                    config_id=CHATWOOT_CONFIG_ID,
                    webhook_secret_encrypted=encrypt_sensitive(payload.webhook_secret) or "",
                    base_url=payload.base_url,
                    inbox_identifier=payload.inbox_identifier,
                    created_at=utcnow(),
                )
                session.add(row)
            elif row.inbox_identifier != payload.inbox_identifier:
                session.execute(sql_delete(ChatwootMessageORM))
                session.execute(sql_delete(ChatwootConversationORM))
                session.execute(sql_delete(ChatwootContactORM))
                row.chatwoot_inbox_id = None
            row.enabled = payload.enabled
            row.account_alerts_enabled = payload.account_alerts_enabled
            row.offline_alert_delay_seconds = payload.offline_alert_delay_seconds
            row.base_url = payload.base_url
            row.inbox_identifier = payload.inbox_identifier
            row.callback_url = payload.callback_url or _chatwoot_callback_url()
            row.chatwoot_account_id = payload.chatwoot_account_id
            if payload.webhook_secret:
                row.webhook_secret_encrypted = encrypt_sensitive(payload.webhook_secret) or ""
            if payload.clear_client_hmac_token:
                row.client_hmac_token_encrypted = None
            elif payload.client_hmac_token:
                row.client_hmac_token_encrypted = encrypt_sensitive(
                    payload.client_hmac_token
                )
            if payload.clear_api_access_token:
                row.api_access_token_encrypted = None
            elif payload.api_access_token:
                row.api_access_token_encrypted = encrypt_sensitive(payload.api_access_token)
            row.status = "ready" if payload.enabled else "disabled"
            row.last_error = None
            row.updated_at = utcnow()
            session.commit()
            managed_inbox_count = len(
                session.scalars(select(ChatwootInboxBindingORM.account_id)).all()
            )
            return self._config_payload(
                row,
                managed_inbox_count=managed_inbox_count,
            )

    def _record_webhook_sync(
        self,
        delivery_id: str,
        event_name: str,
        payload_sha256: str,
        raw_payload: bytes,
    ) -> bool:
        with self._session_factory() as session:
            if session.get(ChatwootWebhookEventORM, delivery_id) is not None:
                return False
            row = ChatwootWebhookEventORM(
                delivery_id=delivery_id,
                config_id=CHATWOOT_CONFIG_ID,
                event_name=event_name[:80],
                payload_sha256=payload_sha256,
                payload=raw_payload.decode("utf-8"),
                status="pending",
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return False
            return True

    def _get_webhook_sync(self, delivery_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(ChatwootWebhookEventORM, delivery_id)
            if row is None:
                return None
            try:
                payload = json.loads(row.payload)
            except (TypeError, json.JSONDecodeError):
                payload = {}
            return {
                "delivery_id": row.delivery_id,
                "config_id": row.config_id,
                "event_name": row.event_name,
                "payload": payload if isinstance(payload, dict) else {},
                "status": row.status,
            }

    def _finish_webhook_sync(
        self,
        delivery_id: str,
        status: str,
        error: str | None,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(ChatwootWebhookEventORM, delivery_id)
            if row is None:
                return
            row.status = status
            row.error = error
            row.processed_at = utcnow()
            session.commit()

    def _get_local_message_context_sync(
        self,
        account_id: str,
        message_pk: str,
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            message = session.scalar(
                select(MessageORM)
                .options(selectinload(MessageORM.attachments))
                .where(
                    MessageORM.account_id == account_id,
                    MessageORM.message_pk == message_pk,
                )
            )
            if message is None:
                return None
            conversation = session.scalar(
                select(ConversationORM).where(
                    ConversationORM.account_id == account_id,
                    ConversationORM.conversation_id == message.conversation_id,
                )
            )
            if conversation is None or not conversation.peer_user_id:
                return None
            try:
                raw_payload = json.loads(message.raw_payload or "null")
            except (TypeError, json.JSONDecodeError):
                raw_payload = message.raw_payload
            identity = session.scalar(
                select(PeerIdentityORM).where(
                    PeerIdentityORM.account_id == account_id,
                    PeerIdentityORM.peer_user_id == conversation.peer_user_id,
                )
            )
            account = session.get(AccountORM, account_id)
            runtime = account.runtime if account is not None else None
            return {
                "message_pk": message.message_pk,
                "conversation_id": message.conversation_id,
                "peer_user_id": conversation.peer_user_id,
                "peer_name": conversation.peer_name or conversation.peer_user_id,
                "account_name": (
                    account.display_name if account else account_id[:8]
                ),
                "platform": (
                    account.platform if account and account.platform else DEFAULT_PLATFORM
                ),
                "platform_name": _platform_name(
                    account.platform if account else DEFAULT_PLATFORM
                ),
                "account_state": runtime.state if runtime else None,
                "account_status_message": runtime.message if runtime else None,
                "avatar_url": identity.avatar_url if identity else None,
                "direction": message.direction,
                "message_type": message.message_type,
                "content": message.content,
                "send_status": message.send_status,
                "recalled": message.recalled_at is not None,
                "created_at_ms": message.created_at_ms,
                "created_at": message.created_at.isoformat(),
                "raw_payload": raw_payload,
                "attachments": [
                    {
                        "attachment_type": item.attachment_type,
                        "remote_url": item.remote_url,
                        "mime_type": item.mime_type,
                        "status": item.status,
                    }
                    for item in message.attachments
                ],
            }

    def _get_local_conversation_context_sync(
        self,
        account_id: str,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            conversation = session.scalar(
                select(ConversationORM).where(
                    ConversationORM.account_id == account_id,
                    ConversationORM.conversation_id == conversation_id,
                )
            )
            if conversation is None or not conversation.peer_user_id:
                return None
            identity = session.scalar(
                select(PeerIdentityORM).where(
                    PeerIdentityORM.account_id == account_id,
                    PeerIdentityORM.peer_user_id == conversation.peer_user_id,
                )
            )
            account = session.get(AccountORM, account_id)
            runtime = account.runtime if account is not None else None
            return {
                "conversation_id": conversation.conversation_id,
                "peer_user_id": conversation.peer_user_id,
                "peer_name": conversation.peer_name or conversation.peer_user_id,
                "account_name": (
                    account.display_name if account else account_id[:8]
                ),
                "platform": (
                    account.platform if account and account.platform else DEFAULT_PLATFORM
                ),
                "platform_name": _platform_name(
                    account.platform if account else DEFAULT_PLATFORM
                ),
                "account_state": runtime.state if runtime else None,
                "account_status_message": runtime.message if runtime else None,
                "avatar_url": identity.avatar_url if identity else None,
                "last_inbound_at": conversation.last_inbound_at,
            }

    @staticmethod
    def _conversation_dict(row: ChatwootConversationORM) -> dict[str, Any]:
        return {
            "account_id": row.account_id,
            "conversation_id": row.conversation_id,
            "peer_user_id": row.peer_user_id,
            "source_id": row.source_id,
            "chatwoot_conversation_id": row.chatwoot_conversation_id,
            "chatwoot_inbox_id": row.chatwoot_inbox_id,
            "inbox_identifier": row.inbox_identifier,
        }

    def _get_conversation_map_by_remote_sync(
        self,
        account_id: str,
        chatwoot_conversation_id: str,
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.account_id == account_id,
                    ChatwootConversationORM.chatwoot_conversation_id
                    == chatwoot_conversation_id,
                )
            )
            return self._conversation_dict(row) if row else None

    def _get_conversation_map_by_remote_global_sync(
        self,
        chatwoot_conversation_id: str,
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.chatwoot_conversation_id
                    == chatwoot_conversation_id
                )
            )
            return self._conversation_dict(row) if row else None

    def _ensure_contact_map_sync(
        self,
        account_id: str,
        peer_user_id: str,
        display_name: str | None,
        avatar_url: str | None,
        chatwoot_contact_id: str | None,
    ) -> dict[str, str | None]:
        with self._session_factory() as session:
            row = session.scalar(
                select(ChatwootContactORM).where(
                    ChatwootContactORM.account_id == account_id,
                    ChatwootContactORM.peer_user_id == peer_user_id,
                )
            )
            if row is None:
                row = ChatwootContactORM(
                    contact_map_id=uuid.uuid4().hex,
                    account_id=account_id,
                    peer_user_id=peer_user_id,
                    source_id=_source_id(account_id, peer_user_id),
                )
                session.add(row)
            row.display_name = display_name or row.display_name
            row.avatar_url = avatar_url or row.avatar_url
            row.chatwoot_contact_id = chatwoot_contact_id or row.chatwoot_contact_id
            row.updated_at = utcnow()
            session.commit()
            return {
                "source_id": row.source_id,
                "chatwoot_contact_id": row.chatwoot_contact_id,
            }

    def _get_conversation_map_sync(
        self,
        account_id: str,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.account_id == account_id,
                    ChatwootConversationORM.conversation_id == conversation_id,
                )
            )
            return self._conversation_dict(row) if row else None

    def _list_conversation_maps_sync(self, account_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.account_id == account_id
                )
            ).all()
            contacts = {
                row.peer_user_id: row
                for row in session.scalars(
                    select(ChatwootContactORM).where(
                        ChatwootContactORM.account_id == account_id
                    )
                ).all()
            }
            result: list[dict[str, Any]] = []
            for row in rows:
                item = self._conversation_dict(row)
                contact = contacts.get(row.peer_user_id)
                item["peer_name"] = (
                    contact.display_name
                    if contact and contact.display_name
                    else row.peer_user_id
                )
                result.append(item)
            return result

    def _list_read_sync_candidates_sync(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            enabled_user_ids = tuple(
                session.scalars(
                    select(UserORM.user_id).where(UserORM.enabled.is_(True))
                ).all()
            )
            if not enabled_user_ids:
                return []
            rows = session.execute(
                select(ChatwootConversationORM, ConversationORM)
                .join(
                    ConversationORM,
                    (
                        ConversationORM.account_id
                        == ChatwootConversationORM.account_id
                    )
                    & (
                        ConversationORM.conversation_id
                        == ChatwootConversationORM.conversation_id
                    ),
                )
                .join(
                    AccountORM,
                    AccountORM.account_id == ChatwootConversationORM.account_id,
                )
                .where(
                    AccountORM.enabled.is_(True),
                    AccountORM.chat_enabled.is_(True),
                    ConversationORM.last_inbound_at.is_not(None),
                )
            ).all()
            conversation_pks = [conversation.conversation_pk for _, conversation in rows]
            read_states = (
                session.scalars(
                    select(ConversationReadStateORM).where(
                        ConversationReadStateORM.conversation_pk.in_(
                            conversation_pks
                        ),
                        ConversationReadStateORM.user_id.in_(enabled_user_ids),
                    )
                ).all()
                if conversation_pks
                else []
            )
            state_by_user_and_conversation = {
                (state.user_id, state.conversation_pk): state
                for state in read_states
            }
            candidates: list[dict[str, Any]] = []
            for mapping, conversation in rows:
                has_viewer_unread = any(
                    (
                        state_by_user_and_conversation[
                            (user_id, conversation.conversation_pk)
                        ].unread_count
                        if (user_id, conversation.conversation_pk)
                        in state_by_user_and_conversation
                        else conversation.unread_count
                    )
                    > 0
                    for user_id in enabled_user_ids
                )
                if not has_viewer_unread:
                    continue
                item = self._conversation_dict(mapping)
                item["last_inbound_at"] = conversation.last_inbound_at
                item["remote_agent_last_seen_at"] = (
                    mapping.remote_agent_last_seen_at
                )
                item["read_synced_at"] = mapping.read_synced_at
                candidates.append(item)
            return candidates

    def _record_read_sync_observation_sync(
        self,
        chatwoot_conversation_id: str,
        remote_seen_at: datetime,
        synced: bool,
    ) -> None:
        normalized_seen_at = (
            remote_seen_at.replace(tzinfo=UTC)
            if remote_seen_at.tzinfo is None
            else remote_seen_at.astimezone(UTC)
        )
        with self._session_factory() as session:
            row = session.scalar(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.chatwoot_conversation_id
                    == chatwoot_conversation_id
                )
            )
            if row is None:
                return
            if (
                row.remote_agent_last_seen_at is None
                or row.remote_agent_last_seen_at < normalized_seen_at
            ):
                row.remote_agent_last_seen_at = normalized_seen_at
            if synced:
                row.read_synced_at = utcnow()
            row.updated_at = utcnow()
            session.commit()

    def _create_conversation_map_sync(
        self,
        account_id: str,
        conversation_id: str,
        peer_user_id: str,
        source_id: str,
        chatwoot_conversation_id: str,
        chatwoot_inbox_id: int | None,
        inbox_identifier: str | None,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.scalar(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.account_id == account_id,
                    ChatwootConversationORM.conversation_id == conversation_id,
                )
            )
            remote_row = session.scalar(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.chatwoot_conversation_id
                    == chatwoot_conversation_id
                )
            )
            if remote_row is not None and (
                remote_row.account_id != account_id
                or remote_row.conversation_id != conversation_id
            ):
                raise ChatwootIntegrationError(
                    f"Chatwoot 会话 {chatwoot_conversation_id} 已绑定闲鱼会话 "
                    f"{remote_row.conversation_id}，不能重复绑定到 {conversation_id}"
                )
            if row is None:
                row = ChatwootConversationORM(
                    conversation_map_id=uuid.uuid4().hex,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    peer_user_id=peer_user_id,
                    source_id=source_id,
                    chatwoot_conversation_id=chatwoot_conversation_id,
                    chatwoot_inbox_id=chatwoot_inbox_id,
                    inbox_identifier=inbox_identifier,
                )
                session.add(row)
            else:
                row.chatwoot_conversation_id = chatwoot_conversation_id
                row.peer_user_id = peer_user_id
                row.source_id = source_id
                row.chatwoot_inbox_id = (
                    chatwoot_inbox_id or row.chatwoot_inbox_id
                )
                row.inbox_identifier = inbox_identifier or row.inbox_identifier
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                remote_row = session.scalar(
                    select(ChatwootConversationORM).where(
                        ChatwootConversationORM.chatwoot_conversation_id
                        == chatwoot_conversation_id
                    )
                )
                if remote_row is not None and (
                    remote_row.account_id != account_id
                    or remote_row.conversation_id != conversation_id
                ):
                    raise ChatwootIntegrationError(
                        f"Chatwoot 会话 {chatwoot_conversation_id} 已绑定闲鱼会话 "
                        f"{remote_row.conversation_id}，不能重复绑定到 {conversation_id}"
                    ) from exc
                raise
            return self._conversation_dict(row)

    def _record_message_map_sync(
        self,
        account_id: str,
        message_pk: str | None,
        chatwoot_message_id: str | None,
        chatwoot_conversation_id: str | None,
        origin: str,
        state: str,
        error: str | None,
    ) -> None:
        with self._session_factory() as session:
            row = (
                session.scalar(
                    select(ChatwootMessageORM).where(
                        ChatwootMessageORM.account_id == account_id,
                        ChatwootMessageORM.message_pk == message_pk,
                    )
                )
                if message_pk
                else None
            )
            if row is None:
                row = ChatwootMessageORM(
                    message_map_id=uuid.uuid4().hex,
                    account_id=account_id,
                    message_pk=message_pk,
                    chatwoot_message_id=chatwoot_message_id,
                    chatwoot_conversation_id=chatwoot_conversation_id,
                    origin=origin,
                    state=state,
                )
                session.add(row)
            else:
                row.chatwoot_message_id = chatwoot_message_id or row.chatwoot_message_id
                row.chatwoot_conversation_id = (
                    chatwoot_conversation_id or row.chatwoot_conversation_id
                )
                row.state = state
            row.error = error
            row.updated_at = utcnow()
            session.commit()

    @staticmethod
    def _message_map_dict(row: ChatwootMessageORM) -> dict[str, str | None]:
        return {
            "message_map_id": row.message_map_id,
            "account_id": row.account_id,
            "message_pk": row.message_pk,
            "chatwoot_message_id": row.chatwoot_message_id,
            "chatwoot_conversation_id": row.chatwoot_conversation_id,
            "origin": row.origin,
            "state": row.state,
            "error": row.error,
        }

    def _find_message_maps_by_remote_sync(
        self,
        account_id: str,
        chatwoot_message_id: str,
    ) -> list[dict[str, str | None]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ChatwootMessageORM).where(
                    ChatwootMessageORM.account_id == account_id,
                    ChatwootMessageORM.chatwoot_message_id == chatwoot_message_id,
                )
            ).all()
            return [self._message_map_dict(row) for row in rows]

    def _find_message_maps_by_remote_global_sync(
        self,
        chatwoot_message_id: str,
    ) -> list[dict[str, str | None]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ChatwootMessageORM).where(
                    ChatwootMessageORM.chatwoot_message_id == chatwoot_message_id
                )
            ).all()
            return [self._message_map_dict(row) for row in rows]

    def _find_message_map_by_local_sync(
        self,
        account_id: str,
        message_pk: str,
    ) -> dict[str, str | None] | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ChatwootMessageORM).where(
                    ChatwootMessageORM.account_id == account_id,
                    ChatwootMessageORM.message_pk == message_pk,
                )
            )
            return self._message_map_dict(row) if row else None

    def _set_config_health_sync(
        self,
        status: str,
        error: str | None,
        pushed: bool,
        webhook: bool,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(ChatwootConfigORM, CHATWOOT_CONFIG_ID)
            if row is None:
                return
            row.status = status
            row.last_error = error
            now = utcnow()
            if pushed:
                row.last_push_at = now
            if webhook:
                row.last_webhook_at = now
            row.updated_at = now
            session.commit()

    def _update_conversation_status_sync(
        self,
        account_id: str,
        chatwoot_conversation_id: str,
        status: str,
    ) -> None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.account_id == account_id,
                    ChatwootConversationORM.chatwoot_conversation_id
                    == chatwoot_conversation_id,
                )
            )
            if row:
                row.chatwoot_status = status
                row.updated_at = utcnow()
                session.commit()


def verify_chatwoot_signature(
    *,
    secret: str,
    raw_body: bytes,
    signature: str | None,
    timestamp: str | None,
    now: int | None = None,
) -> bool:
    normalized = _string(signature)
    if normalized.startswith("sha256="):
        normalized = normalized[7:]
    if not normalized or not timestamp or not timestamp.isdigit():
        return False
    current = int(time.time()) if now is None else now
    if abs(current - int(timestamp)) > WEBHOOK_MAX_AGE_SECONDS:
        return False
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(
        normalized,
        expected,
    )


async def accept_chatwoot_webhook(
    store: AccountStore,
    repository: ChatwootRepository,
    *,
    raw_body: bytes,
    signature: str | None,
    timestamp: str | None,
    delivery_header: str | None,
) -> ChatwootWebhookAcceptedPayload:
    if len(raw_body) > MAX_WEBHOOK_BYTES:
        raise ChatwootIntegrationError("Webhook 请求体超过 2 MB")
    try:
        parsed = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ChatwootIntegrationError("Webhook JSON 格式无效") from exc
    if not isinstance(parsed, dict):
        raise ChatwootIntegrationError("Webhook 数据必须是 JSON 对象")
    inbox_id = _extract_chatwoot_inbox_id(parsed)
    secret = await repository.get_config_secret(inbox_id)
    if not secret:
        raise PermissionError("Chatwoot inbox is not managed by this integration")
    if not verify_chatwoot_signature(
        secret=secret,
        raw_body=raw_body,
        signature=signature,
        timestamp=timestamp,
    ):
        raise PermissionError("invalid Chatwoot webhook signature")
    if inbox_id is not None:
        await repository.remember_legacy_inbox_id(inbox_id)
    payload_account_id = _extract_chatwoot_account_id(parsed)
    if payload_account_id is not None:
        await repository.remember_chatwoot_account_id(payload_account_id)
    config = await repository.get_config()
    if config is None:
        raise PermissionError("Chatwoot config not found")
    if (
        payload_account_id is not None
        and config.get("chatwoot_account_id") != payload_account_id
    ):
        raise PermissionError("Chatwoot account does not match config")
    payload_inbox_identifier = _extract_inbox_identifier(parsed)
    if (
        inbox_id is None
        and payload_inbox_identifier
        and payload_inbox_identifier != config["inbox_identifier"]
    ):
        raise PermissionError("Chatwoot inbox identifier does not match config")
    digest = hashlib.sha256(raw_body).hexdigest()
    delivery_id = _string(delivery_header) or f"fallback-{digest}"
    event_name = _string(parsed.get("event")) or "unknown"
    created = await repository.record_webhook(
        delivery_id=delivery_id[:160],
        event_name=event_name,
        payload_sha256=digest,
        raw_payload=raw_body,
    )
    if not created:
        return ChatwootWebhookAcceptedPayload(
            duplicate=True,
            delivery_id=delivery_id[:160],
        )
    if not config["enabled"]:
        await repository.finish_webhook(
            delivery_id[:160],
            status="ignored",
            error="platform config disabled",
        )
        return ChatwootWebhookAcceptedPayload(delivery_id=delivery_id[:160])
    remote_conversation_id = _extract_chatwoot_conversation_id(parsed)
    mapping = (
        await repository.get_conversation_map_by_remote_global(remote_conversation_id)
        if remote_conversation_id
        else None
    )
    task = await store.create_background_task(
        BackgroundTaskCreatePayload(
            account_id=mapping["account_id"] if mapping else None,
            task_type=CHATWOOT_WEBHOOK_TASK,
            dedupe_key=f"chatwoot-webhook:{delivery_id[:140]}",
            payload={"delivery_id": delivery_id[:160]},
        )
    )
    if task is None:
        raise ChatwootIntegrationError("无法创建 Chatwoot Webhook 后台任务")
    try:
        result = await enqueue_background_task(store, task)
        if result.queued:
            await store.mark_background_task_queued(task.task_id)
    except Exception:
        logger.warning("Chatwoot webhook task persisted but Redis enqueue failed", exc_info=True)
    return ChatwootWebhookAcceptedPayload(delivery_id=delivery_id[:160])


async def enqueue_local_message_sync(
    store: AccountStore,
    *,
    account_id: str,
    message_pk: str,
    send_status: str | None,
    recalled: bool,
) -> None:
    session_factory = getattr(store, "session_factory", None)
    if session_factory is None:
        return
    repository = ChatwootRepository(session_factory)
    try:
        config = await repository.get_config(account_id=account_id)
    except Exception:
        logger.debug(
            "Chatwoot local message sync skipped because integration storage is unavailable",
            exc_info=True,
        )
        return
    if config is None or not config["enabled"]:
        return
    revision = "recalled" if recalled else _string(send_status) or "received"
    task = await store.create_background_task(
        BackgroundTaskCreatePayload(
            account_id=account_id,
            task_type=CHATWOOT_LOCAL_MESSAGE_TASK,
            dedupe_key=f"chatwoot-local:{message_pk}:{revision}",
            payload={"message_pk": message_pk},
        )
    )
    if task is None or task.status != "pending":
        return
    try:
        result = await enqueue_background_task(store, task)
        if result.queued:
            await store.mark_background_task_queued(task.task_id)
    except Exception:
        logger.warning("Chatwoot local message task persisted but enqueue failed", exc_info=True)


async def enqueue_account_status_sync(
    store: AccountStore,
    *,
    account_id: str,
    state: str,
    message: str | None,
) -> None:
    session_factory = getattr(store, "session_factory", None)
    if session_factory is None:
        return
    repository = ChatwootRepository(session_factory)
    try:
        config = await repository.get_config(account_id=account_id)
    except Exception:
        logger.debug(
            "Chatwoot account state sync skipped because integration storage is unavailable",
            exc_info=True,
        )
        return
    if config is None or not config["enabled"]:
        return
    bucket = int(time.time() // 30)
    task = await store.create_background_task(
        BackgroundTaskCreatePayload(
            account_id=account_id,
            task_type=CHATWOOT_ACCOUNT_STATUS_TASK,
            dedupe_key=f"chatwoot-account-state:{account_id}:{state}:{bucket}",
            payload={"state": state, "message": message},
        )
    )
    if task is not None and task.status == "pending":
        try:
            result = await enqueue_background_task(store, task)
            if result.queued:
                await store.mark_background_task_queued(task.task_id)
        except Exception:
            logger.warning(
                "Chatwoot account state task persisted but enqueue failed",
                exc_info=True,
            )
    await enqueue_account_alert_sync(
        store,
        account_id=account_id,
        state=state,
        message=message,
    )


async def enqueue_account_alert_sync(
    store: AccountStore,
    *,
    account_id: str,
    state: str,
    message: str | None,
) -> None:
    if state not in CHATWOOT_ACCOUNT_ALERT_STATES and state != "online":
        return
    session_factory = getattr(store, "session_factory", None)
    if session_factory is None:
        return
    repository = ChatwootRepository(session_factory)
    try:
        config = await repository.get_config(account_id=account_id)
    except Exception:
        logger.debug(
            "Chatwoot account alert skipped because integration storage is unavailable",
            exc_info=True,
        )
        return
    if (
        config is None
        or not config["enabled"]
        or not config.get("account_alerts_enabled")
    ):
        return
    delay_seconds = (
        int(config.get("offline_alert_delay_seconds") or 120)
        if state == "offline"
        else 0
    )
    bucket = int(time.time() // 30)
    task = await store.create_background_task(
        BackgroundTaskCreatePayload(
            account_id=account_id,
            task_type=CHATWOOT_ACCOUNT_ALERT_TASK,
            dedupe_key=f"chatwoot-account-alert:{account_id}:{state}:{bucket}",
            run_after=(
                datetime.now(UTC) + timedelta(seconds=delay_seconds)
                if delay_seconds
                else None
            ),
            payload={
                "state": state,
                "message": message,
                "expected_state": state,
            },
        )
    )
    if task is None or task.status != "pending":
        return
    try:
        result = await enqueue_background_task(store, task)
        if result.queued:
            await store.mark_background_task_queued(task.task_id)
    except Exception:
        logger.warning(
            "Chatwoot account alert task persisted but enqueue failed",
            exc_info=True,
        )


async def enqueue_account_metadata_sync(
    store: AccountStore,
    *,
    account_id: str,
    reason: str,
) -> None:
    session_factory = getattr(store, "session_factory", None)
    if session_factory is None:
        return
    repository = ChatwootRepository(session_factory)
    try:
        config = await repository.get_config(account_id=account_id)
    except Exception:
        logger.debug(
            "Chatwoot account metadata sync skipped because integration storage is unavailable",
            exc_info=True,
        )
        return
    if config is None or not config["platform_enabled"]:
        return
    if not config["enabled"]:
        try:
            has_existing_mappings = bool(
                await repository.list_conversation_maps(account_id)
            )
        except Exception:
            logger.debug(
                "Chatwoot account metadata sync skipped because mapping storage is unavailable",
                exc_info=True,
            )
            return
        if not has_existing_mappings:
            return
    task = await store.create_background_task(
        BackgroundTaskCreatePayload(
            account_id=account_id,
            task_type=CHATWOOT_ACCOUNT_METADATA_TASK,
            dedupe_key=(
                f"chatwoot-account-metadata:{account_id}:{uuid.uuid4().hex}"
            ),
            payload={"reason": reason[:80]},
        )
    )
    if task is None or task.status != "pending":
        return
    try:
        result = await enqueue_background_task(store, task)
        if result.queued:
            await store.mark_background_task_queued(task.task_id)
    except Exception:
        logger.warning(
            "Chatwoot account metadata task persisted but enqueue failed",
            exc_info=True,
        )


def _chatwoot_request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    data: dict[str, str] | None = None,
    files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    timeout: int = 30,
    acceptable: set[int] | None = None,
) -> tuple[int, Any]:
    # Chatwoot documents `api_access_token`, but Nginx drops request headers
    # containing underscores unless `underscores_in_headers on` is configured.
    # Rack normalizes the hyphenated form to the same header and Chatwoot accepts
    # it, so this works with both direct Rails and default Nginx deployments.
    request_headers = {"api-access-token": token} if token else {}
    with requests.Session() as client:
        client.trust_env = False
        response = client.request(
            method,
            url,
            headers=request_headers,
            params=params,
            json=json_body if files is None else None,
            data=data,
            files=files,
            timeout=timeout,
            allow_redirects=False,
            verify=_chatwoot_tls_verify(),
        )
    try:
        body = response.json()
    except ValueError:
        body = {}
    accepted = acceptable or set()
    if response.status_code >= 400 and response.status_code not in accepted:
        detail = (
            body.get("message") or body.get("error") or response.text[:300]
            if isinstance(body, dict)
            else response.text[:300]
        )
        raise ChatwootIntegrationError(
            f"Chatwoot API HTTP {response.status_code}: {detail}",
            status_code=response.status_code,
        )
    return response.status_code, body


def _chatwoot_message_list(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    body = _json_object(payload)
    items = body.get("payload")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    messages = body.get("messages")
    if isinstance(messages, list):
        return [item for item in messages if isinstance(item, dict)]
    return []


async def _list_chatwoot_messages(
    config: dict[str, Any],
    *,
    chatwoot_conversation_id: str,
    before: str | None = None,
) -> list[dict[str, Any]]:
    token = _string(config.get("api_access_token"))
    chatwoot_account_id = config.get("chatwoot_account_id")
    if not token or not chatwoot_account_id:
        raise ChatwootIntegrationError(
            "读取 Chatwoot 消息需要服务账号令牌与平台账户 ID",
            status_code=503,
        )
    _, body = await run_external_blocking(
        _chatwoot_request,
        "GET",
        (
            f"{config['base_url']}/api/v1/accounts/{chatwoot_account_id}"
            f"/conversations/{chatwoot_conversation_id}/messages"
        ),
        token=token,
        params={"before": before} if before else None,
        timeout=10,
    )
    return _chatwoot_message_list(body)


async def test_chatwoot_config(
    repository: ChatwootRepository,
) -> ChatwootTestResultPayload:
    config = await repository.get_config()
    if config is None:
        return ChatwootTestResultPayload(success=False, message="配置不存在")
    try:
        status_code, _ = await run_external_blocking(
            _chatwoot_request,
            "GET",
            (
                f"{config['base_url']}/public/api/v1/inboxes/"
                f"{config['inbox_identifier']}"
            ),
            timeout=10,
        )
        if config["api_access_token"] and config["chatwoot_account_id"]:
            await run_external_blocking(
                _chatwoot_request,
                "GET",
                (
                    f"{config['base_url']}/api/v1/accounts/"
                    f"{config['chatwoot_account_id']}"
                ),
                token=config["api_access_token"],
                timeout=10,
            )
    except Exception as exc:
        await repository.set_config_health(
            status="error",
            error=str(exc)[:1000],
        )
        return ChatwootTestResultPayload(success=False, message=str(exc))
    await repository.set_config_health(status="ready", error=None)
    return ChatwootTestResultPayload(
        success=True,
        message=(
            "Chatwoot 连接正常"
            if config["api_access_token"] and config["chatwoot_account_id"]
            else "Chatwoot 基础连接正常；账号分组、标签和状态回写仍需平台账户 ID 与专用服务账号令牌"
        ),
        status_code=status_code,
    )


async def _ensure_custom_attribute_definitions(
    config: dict[str, Any],
) -> int:
    token = _string(config.get("api_access_token"))
    account_id = config.get("chatwoot_account_id")
    if not token or not account_id:
        return 0
    url = (
        f"{config['base_url']}/api/v1/accounts/{account_id}"
        "/custom_attribute_definitions"
    )
    _, body = await run_external_blocking(
        _chatwoot_request,
        "GET",
        url,
        token=token,
    )
    records = (
        body
        if isinstance(body, list)
        else _json_object(body).get("payload") or []
    )
    existing = {
        (
            _string(item.get("attribute_key")),
            _string(item.get("attribute_model")),
        )
        for item in records
        if isinstance(item, dict)
    }
    created = 0
    for definition in _CUSTOM_ATTRIBUTE_DEFINITIONS:
        model = definition["attribute_model"]
        model_aliases = {
            _string(model),
            "conversation_attribute" if model == 0 else "contact_attribute",
        }
        if any((definition["attribute_key"], alias) in existing for alias in model_aliases):
            continue
        await run_external_blocking(
            _chatwoot_request,
            "POST",
            url,
            token=token,
            json_body={"custom_attribute_definition": definition},
        )
        created += 1
    return created


async def _ensure_account_label(
    repository: ChatwootRepository,
    config: dict[str, Any],
) -> tuple[int, str]:
    token = _string(config.get("api_access_token"))
    chatwoot_account_id = config.get("chatwoot_account_id")
    account_id = _string(config.get("account_id"))
    account_name = _string(config.get("account_name")) or account_id[:8]
    platform = _string(config.get("platform")).lower() or DEFAULT_PLATFORM
    platform_name = _platform_name(platform)
    if not token or not chatwoot_account_id or not account_id:
        raise ChatwootIntegrationError(
            "账号标签需要 Chatwoot 平台账户 ID 与专用服务账号令牌"
        )
    desired_title = _account_label_title(account_name, account_id, platform)
    labels_url = (
        f"{config['base_url']}/api/v1/accounts/{chatwoot_account_id}/labels"
    )
    binding = await repository.get_inbox_binding(account_id)
    label_id = int(binding["label_id"]) if binding and binding.get("label_id") else None
    try:
        _, body = await run_external_blocking(
            _chatwoot_request,
            "GET",
            labels_url,
            token=token,
        )
        labels = _json_object(body).get("payload") or []
    except ChatwootIntegrationError as exc:
        # Some self-hosted Chatwoot versions return 500 from the collection
        # endpoint while create/update and conversation-label APIs still work.
        # A persisted label ID remains authoritative; for the initial creation
        # continue with an empty collection instead of blocking Inbox grouping.
        logger.warning("Chatwoot label listing failed; using local binding: %s", exc)
        labels = (
            [{"id": label_id, "title": binding.get("label_title")}]
            if binding and label_id is not None
            else []
        )
    matched: dict[str, Any] | None = None
    for item in labels:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        description = _string(item.get("description"))
        if (
            (label_id is not None and _string(item_id) == str(label_id))
            or description == f"{platform_name}账号:{account_id}"
            or _string(item.get("title")) == desired_title
        ):
            matched = item
            break
    label_payload = {
        "title": desired_title,
        "description": f"{platform_name}账号:{account_id}",
        "color": _account_label_color(account_id),
        "show_on_sidebar": True,
    }
    if matched is None:
        _, created_body = await run_external_blocking(
            _chatwoot_request,
            "POST",
            labels_url,
            token=token,
            json_body=label_payload,
        )
        matched = _json_object(created_body)
        if isinstance(matched.get("payload"), dict):
            matched = _json_object(matched["payload"])
    elif _string(matched.get("title")) != desired_title:
        await run_external_blocking(
            _chatwoot_request,
            "PATCH",
            f"{labels_url}/{matched['id']}",
            token=token,
            json_body=label_payload,
        )
    resolved_id = int(matched.get("id") or 0)
    if resolved_id <= 0:
        raise ChatwootIntegrationError("Chatwoot 创建账号标签后未返回标签 ID")
    if binding:
        await repository.update_inbox_binding_label(
            account_id=account_id,
            label_id=resolved_id,
            label_title=desired_title,
        )
    return resolved_id, desired_title


async def _ensure_inbox_membership(config: dict[str, Any]) -> bool:
    token = _string(config.get("api_access_token"))
    chatwoot_account_id = config.get("chatwoot_account_id")
    inbox_id = config.get("chatwoot_inbox_id")
    if not token or not chatwoot_account_id or not inbox_id:
        return False
    _, profile_body = await run_external_blocking(
        _chatwoot_request,
        "GET",
        f"{config['base_url']}/api/v1/profile",
        token=token,
    )
    profile_id = int(_json_object(profile_body).get("id") or 0)
    if profile_id <= 0:
        raise ChatwootIntegrationError(
            "Chatwoot 服务账号资料未返回用户 ID"
        )
    config["default_assignee_id"] = profile_id
    member_base = (
        f"{config['base_url']}/api/v1/accounts/{chatwoot_account_id}"
        "/inbox_members"
    )
    _, members_body = await run_external_blocking(
        _chatwoot_request,
        "GET",
        f"{member_base}/{inbox_id}",
        token=token,
    )
    member_ids = {
        int(item.get("id") or 0)
        for item in (_json_object(members_body).get("payload") or [])
        if isinstance(item, dict)
    }
    if profile_id in member_ids:
        return False
    await run_external_blocking(
        _chatwoot_request,
        "POST",
        member_base,
        token=token,
        json_body={
            "inbox_id": inbox_id,
            "user_ids": [profile_id],
        },
    )
    return True


async def _ensure_managed_account_inbox(
    repository: ChatwootRepository,
    config: dict[str, Any],
    *,
    refresh_display_name: bool = False,
    state_override: str | None = None,
) -> dict[str, Any]:
    token = _string(config.get("api_access_token"))
    chatwoot_account_id = config.get("chatwoot_account_id")
    account_id = _string(config.get("account_id"))
    account_name = _string(config.get("account_name")) or account_id[:8]
    platform = _string(config.get("platform")).lower() or DEFAULT_PLATFORM
    platform_name = _platform_name(platform)
    desired_name = _managed_inbox_name(
        platform=platform,
        account_name=account_name,
        state=state_override or config.get("account_state"),
    )
    if config.get("managed_inbox"):
        if refresh_display_name and token and chatwoot_account_id:
            await run_external_blocking(
                _chatwoot_request,
                "PATCH",
                (
                    f"{config['base_url']}/api/v1/accounts/"
                    f"{chatwoot_account_id}/inboxes/"
                    f"{config['chatwoot_inbox_id']}"
                ),
                token=token,
                json_body={
                    "name": desired_name,
                    "lock_to_single_conversation": (
                        CHATWOOT_INBOX_LOCK_TO_SINGLE_CONVERSATION
                    ),
                },
            )
        config = dict(config)
        config["member_added"] = await _ensure_inbox_membership(config)
        try:
            label_id, label_title = await _ensure_account_label(
                repository,
                config,
            )
        except ChatwootIntegrationError as exc:
            config = dict(config)
            config["label_error"] = str(exc)[:1000]
            logger.warning(
                "Chatwoot account label unavailable; Inbox grouping remains active: %s",
                exc,
            )
        else:
            if (
                config.get("label_id") != label_id
                or config.get("label_title") != label_title
            ):
                config = dict(config)
                config["label_id"] = label_id
                config["label_title"] = label_title
        return config
    if not token or not chatwoot_account_id:
        return config
    inboxes_url = (
        f"{config['base_url']}/api/v1/accounts/{chatwoot_account_id}/inboxes"
    )
    _, body = await run_external_blocking(
        _chatwoot_request,
        "GET",
        inboxes_url,
        token=token,
    )
    inboxes = _json_object(body).get("payload") or body
    remote: dict[str, Any] | None = None
    if isinstance(inboxes, list):
        for item in inboxes:
            if not isinstance(item, dict):
                continue
            attributes = _json_object(item.get("additional_attributes"))
            if (
                _string(item.get("channel_type")) == "Channel::Api"
                and _string(attributes.get("xianyu_account_id")) == account_id
            ):
                remote = item
                break
    if remote is None:
        _, created_body = await run_external_blocking(
            _chatwoot_request,
            "POST",
            inboxes_url,
            token=token,
            json_body={
                "name": desired_name,
                "enable_auto_assignment": False,
                "lock_to_single_conversation": (
                    CHATWOOT_INBOX_LOCK_TO_SINGLE_CONVERSATION
                ),
                "channel": {
                    "type": "api",
                    "webhook_url": config["callback_url"],
                    "hmac_mandatory": False,
                    "additional_attributes": {
                        "source_platform": platform,
                        "source_platform_name": platform_name,
                        "xianyu_account_id": account_id,
                        "xianyu_account_name": account_name,
                        "managed_by": "xianyu-admin",
                    },
                },
            },
        )
        remote = _json_object(created_body)
    remote_id = int(remote.get("id") or 0)
    if remote_id <= 0:
        raise ChatwootIntegrationError("Chatwoot 创建账号 Inbox 后未返回 Inbox ID")
    if (
        _string(remote.get("name")) != desired_name
        or "lock_to_single_conversation" not in remote
        or bool(remote.get("lock_to_single_conversation"))
        != CHATWOOT_INBOX_LOCK_TO_SINGLE_CONVERSATION
    ):
        await run_external_blocking(
            _chatwoot_request,
            "PATCH",
            f"{inboxes_url}/{remote_id}",
            token=token,
            json_body={
                "name": desired_name,
                "lock_to_single_conversation": (
                    CHATWOOT_INBOX_LOCK_TO_SINGLE_CONVERSATION
                ),
            },
        )
    if (
        not remote.get("inbox_identifier")
        or not remote.get("secret")
    ):
        _, detail_body = await run_external_blocking(
            _chatwoot_request,
            "GET",
            f"{inboxes_url}/{remote_id}",
            token=token,
        )
        remote = {**remote, **_json_object(detail_body)}
    inbox_identifier = _string(remote.get("inbox_identifier"))
    webhook_secret = _string(remote.get("secret"))
    if not inbox_identifier or not webhook_secret:
        raise ChatwootIntegrationError(
            "专用服务账号无法读取 API Inbox 标识符或签名秘密，请授予 Chatwoot 管理员权限"
        )
    await repository.upsert_inbox_binding(
        account_id=account_id,
        chatwoot_inbox_id=remote_id,
        inbox_identifier=inbox_identifier,
        webhook_secret=webhook_secret,
        label_id=None,
        label_title=None,
    )
    refreshed = await repository.get_config(account_id=account_id)
    if refreshed is None:
        raise ChatwootIntegrationError("账号 Inbox 创建后无法读取本地绑定")
    refreshed["member_added"] = await _ensure_inbox_membership(refreshed)
    try:
        label_id, label_title = await _ensure_account_label(
            repository,
            refreshed,
        )
    except ChatwootIntegrationError as exc:
        refreshed["label_error"] = str(exc)[:1000]
        logger.warning(
            "Chatwoot account label unavailable; Inbox grouping remains active: %s",
            exc,
        )
    else:
        refreshed["label_id"] = label_id
        refreshed["label_title"] = label_title
    return refreshed


async def _update_remote_contact_identity(
    config: dict[str, Any],
    *,
    inbox_identifier: str,
    source_id: str,
    peer_user_id: str,
    peer_name: str,
    legacy_inbox: bool,
) -> None:
    account_id = _string(config.get("account_id"))
    account_name = _string(config.get("account_name")) or account_id[:8]
    payload = _contact_identity_payload(
        account_id=account_id,
        account_name=account_name,
        platform=_string(config.get("platform")).lower() or DEFAULT_PLATFORM,
        peer_user_id=peer_user_id,
        peer_name=peer_name,
        client_hmac_token=(
            _string(config.get("legacy_client_hmac_token")) or None
            if legacy_inbox
            else None
        ),
    )
    await run_external_blocking(
        _chatwoot_request,
        "PATCH",
        (
            f"{config['base_url']}/public/api/v1/inboxes/{inbox_identifier}"
            f"/contacts/{source_id}"
        ),
        json_body=payload,
    )


async def _sync_remote_conversation_metadata(
    config: dict[str, Any],
    *,
    chatwoot_conversation_id: str,
    label_title: str | None,
    conversation_id: str,
    peer_user_id: str | None = None,
    state: str | None = None,
    status_message: str | None = None,
) -> None:
    token = _string(config.get("api_access_token"))
    chatwoot_account_id = config.get("chatwoot_account_id")
    if not token or not chatwoot_account_id:
        raise ChatwootIntegrationError(
            "会话账号标签需要 Chatwoot 平台账户 ID 与专用服务账号令牌"
        )
    base = (
        f"{config['base_url']}/api/v1/accounts/{chatwoot_account_id}"
        f"/conversations/{chatwoot_conversation_id}"
    )
    if label_title:
        _, labels_body = await run_external_blocking(
            _chatwoot_request,
            "GET",
            f"{base}/labels",
            token=token,
        )
        current_labels = [
            _string(item)
            for item in (_json_object(labels_body).get("payload") or [])
            if _string(item)
        ]
        labels = list(current_labels)
        if label_title not in labels:
            labels.append(label_title)
        if labels != current_labels:
            await run_external_blocking(
                _chatwoot_request,
                "POST",
                f"{base}/labels",
                token=token,
                json_body={"labels": labels},
            )
    attributes = _conversation_source_attributes(
        config,
        conversation_id=conversation_id,
        peer_user_id=peer_user_id,
        state=state,
        status_message=status_message,
    )
    await run_external_blocking(
        _chatwoot_request,
        "POST",
        f"{base}/custom_attributes",
        token=token,
        json_body={"custom_attributes": attributes},
    )


def _mapping_uses_managed_inbox(
    mapping: dict[str, Any],
    config: dict[str, Any],
) -> bool:
    managed_id = config.get("chatwoot_inbox_id")
    mapped_id = mapping.get("chatwoot_inbox_id")
    if managed_id and mapped_id:
        return int(managed_id) == int(mapped_id)
    return bool(
        config.get("managed_inbox")
        and _string(mapping.get("inbox_identifier"))
        == _string(config.get("inbox_identifier"))
    )


def _conversation_list(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    body = _json_object(payload)
    records = body.get("payload")
    if not isinstance(records, list):
        records = _json_object(body.get("data")).get("payload")
    return [item for item in (records or []) if isinstance(item, dict)]


async def _ensure_remote_conversation(
    repository: ChatwootRepository,
    config: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    existing = await repository.get_conversation_map(
        config["account_id"],
        context["conversation_id"],
    )
    migration_required = bool(
        existing
        and config.get("managed_inbox")
        and not _mapping_uses_managed_inbox(existing, config)
    )
    if existing and not migration_required:
        return existing
    contact_map = await repository.ensure_contact_map(
        account_id=config["account_id"],
        peer_user_id=context["peer_user_id"],
        display_name=context.get("peer_name"),
        avatar_url=context.get("avatar_url"),
    )
    source_id = _string(contact_map["source_id"])
    contact_url = (
        f"{config['base_url']}/public/api/v1/inboxes/"
        f"{config['inbox_identifier']}/contacts"
    )
    contact_payload = _contact_identity_payload(
        account_id=config["account_id"],
        account_name=context["account_name"],
        platform=_string(context.get("platform") or config.get("platform")).lower()
        or DEFAULT_PLATFORM,
        peer_user_id=context["peer_user_id"],
        peer_name=context.get("peer_name") or context["peer_user_id"],
        client_hmac_token=config.get("client_hmac_token"),
    )
    contact_payload.update({
        "source_id": source_id,
    })
    if context.get("avatar_url"):
        contact_payload["avatar_url"] = context["avatar_url"]
    remote_contact_id = _remote_id(contact_map.get("chatwoot_contact_id"))
    token = _string(config.get("api_access_token"))
    chatwoot_account_id = config.get("chatwoot_account_id")
    managed_inbox_id = config.get("chatwoot_inbox_id")
    if migration_required and remote_contact_id and token and chatwoot_account_id:
        await run_external_blocking(
            _chatwoot_request,
            "POST",
            (
                f"{config['base_url']}/api/v1/accounts/{chatwoot_account_id}"
                f"/contacts/{remote_contact_id}/contact_inboxes"
            ),
            token=token,
            json_body={
                "inbox_id": managed_inbox_id,
                "source_id": source_id,
            },
            acceptable={409, 422},
        )
    else:
        status_code, body = await run_external_blocking(
            _chatwoot_request,
            "POST",
            contact_url,
            json_body=contact_payload,
            acceptable={409, 422},
        )
        if status_code < 400:
            contact = _json_object(body.get("contact"))
            remote_contact_id = _remote_id(body.get("id") or contact.get("id"))
            await repository.ensure_contact_map(
                account_id=config["account_id"],
                peer_user_id=context["peer_user_id"],
                display_name=context.get("peer_name"),
                avatar_url=context.get("avatar_url"),
                chatwoot_contact_id=remote_contact_id,
            )
    await _update_remote_contact_identity(
        config,
        inbox_identifier=config["inbox_identifier"],
        source_id=source_id,
        peer_user_id=context["peer_user_id"],
        peer_name=context.get("peer_name") or context["peer_user_id"],
        legacy_inbox=not bool(config.get("managed_inbox")),
    )
    conversation_url = (
        f"{config['base_url']}/public/api/v1/inboxes/{config['inbox_identifier']}"
        f"/contacts/{source_id}/conversations"
    )
    _, listed_body = await run_external_blocking(
        _chatwoot_request,
        "GET",
        conversation_url,
        acceptable={404},
    )
    attributes = _conversation_source_attributes(
        config,
        conversation_id=context["conversation_id"],
        peer_user_id=context["peer_user_id"],
        state=_string(context.get("account_state")) or None,
        status_message=_string(context.get("account_status_message")) or None,
    )
    matching_remote = next(
        (
            item
            for item in _conversation_list(listed_body)
            if _string(
                _json_object(item.get("custom_attributes")).get(
                    "source_conversation_id"
                )
                or _json_object(item.get("custom_attributes")).get(
                    "xianyu_conversation_id"
                )
            )
            == _string(context["conversation_id"])
        ),
        None,
    )
    chatwoot_conversation_id = (
        _remote_id(
            matching_remote.get("id") or matching_remote.get("display_id")
        )
        if matching_remote
        else None
    )
    if chatwoot_conversation_id is None:
        if token and chatwoot_account_id and managed_inbox_id and remote_contact_id:
            _, conversation_body = await run_external_blocking(
                _chatwoot_request,
                "POST",
                (
                    f"{config['base_url']}/api/v1/accounts/"
                    f"{chatwoot_account_id}/conversations"
                ),
                token=token,
                json_body={
                    "source_id": source_id,
                    "inbox_id": managed_inbox_id,
                    "contact_id": int(remote_contact_id),
                    "status": "open",
                    "assignee_id": config.get("default_assignee_id"),
                    "custom_attributes": attributes,
                },
            )
        else:
            _, conversation_body = await run_external_blocking(
                _chatwoot_request,
                "POST",
                conversation_url,
                json_body={"custom_attributes": attributes},
            )
        chatwoot_conversation_id = _remote_id(
            conversation_body.get("id") or conversation_body.get("display_id")
        )
    if not chatwoot_conversation_id:
        raise ChatwootIntegrationError("Chatwoot 创建会话后未返回会话 ID")
    conversation_map = await repository.create_conversation_map(
        account_id=config["account_id"],
        conversation_id=context["conversation_id"],
        peer_user_id=context["peer_user_id"],
        source_id=source_id,
        chatwoot_conversation_id=chatwoot_conversation_id,
        chatwoot_inbox_id=config.get("chatwoot_inbox_id"),
        inbox_identifier=config.get("inbox_identifier"),
    )
    if (
        config.get("api_access_token")
        and config.get("chatwoot_account_id")
    ):
        await _sync_remote_conversation_metadata(
            config,
            chatwoot_conversation_id=chatwoot_conversation_id,
            label_title=config["label_title"],
            conversation_id=context["conversation_id"],
            peer_user_id=context["peer_user_id"],
            state=_string(context.get("account_state")) or None,
            status_message=_string(context.get("account_status_message")) or None,
        )
    if migration_required and existing is not None:
        previous_id = _string(existing.get("chatwoot_conversation_id"))
        try:
            await _create_private_delivery_note(
                config,
                chatwoot_conversation_id=chatwoot_conversation_id,
                content=(
                    f"系统已将该会话切换到 "
                    f"[{_platform_name(config.get('platform'))}] "
                    f"{config['account_name']} 专属收件箱；"
                    f"旧会话 #{previous_id} 仅保留历史记录。"
                ),
            )
            if previous_id and previous_id != chatwoot_conversation_id:
                await run_external_blocking(
                    _chatwoot_request,
                    "POST",
                    (
                        f"{config['base_url']}/api/v1/accounts/"
                        f"{chatwoot_account_id}/conversations/"
                        f"{previous_id}/toggle_status"
                    ),
                    token=token,
                    json_body={"status": "resolved"},
                    acceptable={404},
                )
        except Exception:
            logger.warning(
                "Chatwoot legacy conversation was remapped but cleanup failed "
                "account=%s old=%s new=%s",
                config["account_id"],
                previous_id,
                chatwoot_conversation_id,
                exc_info=True,
            )
        conversation_map["migrated"] = True
        conversation_map["previous_chatwoot_conversation_id"] = previous_id
    return conversation_map


def _context_image_urls(context: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for attachment in context.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        if _string(attachment.get("attachment_type")).lower() != "image":
            continue
        url = _string(attachment.get("remote_url"))
        if url and url not in urls:
            urls.append(url)
    if context.get("message_type") == "image":
        for line in _string(context.get("content")).splitlines():
            url = line.strip()
            if url.startswith(("http://", "https://")) and url not in urls:
                urls.append(url)
    return urls


def _context_audio_urls(context: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for attachment in context.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        if _string(attachment.get("attachment_type")).lower() != "audio":
            continue
        url = _string(attachment.get("remote_url"))
        if url and url not in urls:
            urls.append(url)
    if context.get("message_type") == "audio" and not urls:
        url = _extract_xianyu_audio_url(context.get("raw_payload"))
        if url:
            urls.append(url)
    return urls


async def _create_private_delivery_note(
    config: dict[str, Any],
    *,
    chatwoot_conversation_id: str,
    content: str,
    content_attributes: dict[str, Any] | None = None,
) -> bool:
    if not config.get("api_access_token") or not config.get("chatwoot_account_id"):
        return False
    message_url = (
        f"{config['base_url']}/api/v1/accounts/{config['chatwoot_account_id']}"
        f"/conversations/{chatwoot_conversation_id}/messages"
    )
    body: dict[str, Any] = {
        "content": content,
        "message_type": "outgoing",
        "private": True,
    }
    if content_attributes:
        body["content_attributes"] = content_attributes
    await run_external_blocking(
        _chatwoot_request,
        "POST",
        message_url,
        token=config["api_access_token"],
        json_body=body,
    )
    return True


def _recall_snapshot_payload(
    contexts: list[dict[str, Any]],
    *,
    succeeded: bool,
    error: str | None,
) -> tuple[str, list[str]]:
    ordered = sorted(
        contexts,
        key=lambda item: (
            int(item.get("created_at_ms") or 0),
            _string(item.get("message_pk")),
        ),
    )
    image_urls: list[str] = []
    contents: list[str] = []
    for context in ordered:
        context_images = _context_image_urls(context)
        for image_url in context_images:
            if image_url not in image_urls:
                image_urls.append(image_url)
        raw_content = _string(context.get("content")).strip()
        if raw_content:
            visible_lines = [
                line
                for line in raw_content.splitlines()
                if line.strip() and line.strip() not in context_images
            ]
            visible_content = "\n".join(visible_lines).strip()
            if visible_content and visible_content not in contents:
                contents.append(visible_content)

    created_at = next(
        (
            _string(context.get("created_at"))
            for context in ordered
            if _string(context.get("created_at"))
        ),
        "",
    )
    header = "原消息"
    if created_at:
        try:
            original_time = datetime.fromisoformat(created_at)
            if original_time.tzinfo is None:
                original_time = original_time.replace(tzinfo=UTC)
            header = (
                "原消息（"
                f"{original_time.astimezone(SHANGHAI_TIMEZONE):%Y-%m-%d %H:%M:%S}"
                " 上海时间）"
            )
        except ValueError:
            pass

    if contents:
        original_content = "\n".join(contents)
    elif image_urls:
        original_content = "[图片]"
    else:
        original_content = "[原消息内容未能从本地记录恢复]"
    status = (
        "↩ 闲鱼消息已撤回"
        if succeeded
        else f"⚠️ 闲鱼消息撤回失败：{error or '闲鱼平台未确认撤回'}"
    )
    return f"{header}：\n{original_content}\n\n{status}", image_urls


async def _chatwoot_recall_snapshot_exists(
    config: dict[str, Any],
    *,
    chatwoot_conversation_id: str,
    chatwoot_message_id: str,
) -> bool:
    messages = await _list_chatwoot_messages(
        config,
        chatwoot_conversation_id=chatwoot_conversation_id,
    )
    return any(
        _message_is_private(message)
        and _remote_id(
            _json_object(message.get("content_attributes")).get(
                "xianyu_deleted_source_message_id"
            )
        )
        == chatwoot_message_id
        for message in messages
    )


async def _create_private_recall_snapshot(
    config: dict[str, Any],
    *,
    chatwoot_conversation_id: str,
    chatwoot_message_id: str,
    contexts: list[dict[str, Any]],
    succeeded: bool,
    error: str | None,
) -> bool:
    if not config.get("api_access_token") or not config.get("chatwoot_account_id"):
        raise ChatwootIntegrationError(
            "恢复已删除原消息需要 Chatwoot 服务账号令牌与平台账户 ID"
        )
    content, image_urls = _recall_snapshot_payload(
        contexts,
        succeeded=succeeded,
        error=error,
    )
    attributes = {
        "xianyu_deleted_source_message_id": chatwoot_message_id,
        "xianyu_recall_snapshot": True,
        "xianyu_recall_state": "recalled" if succeeded else "failed",
    }
    if not image_urls:
        return await _create_private_delivery_note(
            config,
            chatwoot_conversation_id=chatwoot_conversation_id,
            content=content,
            content_attributes=attributes,
        )

    files: list[tuple[str, tuple[str, bytes, str]]] = []
    for image_url in image_urls:
        data, mime_type, filename = await run_external_blocking(
            _download_image,
            image_url,
        )
        files.append(("attachments[]", (filename, data, mime_type)))
    message_url = (
        f"{config['base_url']}/api/v1/accounts/{config['chatwoot_account_id']}"
        f"/conversations/{chatwoot_conversation_id}/messages"
    )
    form_data = {
        "content": content,
        "message_type": "outgoing",
        "private": "true",
        "content_attributes[xianyu_deleted_source_message_id]": (
            chatwoot_message_id
        ),
        "content_attributes[xianyu_recall_snapshot]": "true",
        "content_attributes[xianyu_recall_state]": (
            "recalled" if succeeded else "failed"
        ),
    }
    await run_external_blocking(
        _chatwoot_request,
        "POST",
        message_url,
        token=config["api_access_token"],
        data=form_data,
        files=files,
    )
    return True


async def _update_chatwoot_recall_state(
    config: dict[str, Any],
    *,
    chatwoot_conversation_id: str,
    chatwoot_message_id: str,
    state: str,
    error: str | None = None,
) -> dict[str, Any]:
    token = _string(config.get("api_access_token"))
    chatwoot_account_id = config.get("chatwoot_account_id")
    if not token or not chatwoot_account_id:
        raise ChatwootIntegrationError(
            "撤回状态回写需要 Chatwoot 服务账号令牌与平台账户 ID"
        )
    _, body = await run_external_blocking(
        _chatwoot_request,
        "POST",
        (
            f"{config['base_url']}/api/v1/accounts/{chatwoot_account_id}"
            f"/conversations/{chatwoot_conversation_id}/messages/"
            f"{chatwoot_message_id}/xianyu_recall"
        ),
        token=token,
        json_body={
            "recall_state": state,
            "recall_error": error,
        },
    )
    return _json_object(body)


async def execute_local_message_task(
    store: AccountStore,
    *,
    account_id: str,
    message_pk: str,
) -> dict[str, Any]:
    repository = ChatwootRepository(store.session_factory)
    config = await repository.get_config(account_id=account_id)
    if config is None or not config["enabled"]:
        return {"ok": True, "skipped": True, "reason": "Chat disabled"}
    context = await repository.get_local_message_context(account_id, message_pk)
    if context is None:
        return {"ok": True, "skipped": True, "reason": "message context unavailable"}
    mapped = await repository.find_message_map_by_local(account_id, message_pk)
    if context["recalled"]:
        if not mapped or not mapped.get("chatwoot_message_id"):
            return {"ok": True, "skipped": True, "reason": "message not mirrored"}
        if mapped.get("state") == "recalled":
            return {"ok": True, "skipped": True, "reason": "recall already mirrored"}
        if not config["api_access_token"] or not config["chatwoot_account_id"]:
            error = "反向撤回需要 Chatwoot 服务账号令牌与平台账户 ID"
            await repository.record_message_map(
                account_id=account_id,
                message_pk=message_pk,
                chatwoot_message_id=mapped["chatwoot_message_id"],
                chatwoot_conversation_id=mapped["chatwoot_conversation_id"],
                origin=mapped["origin"] or "xianyu",
                state="recall_unsupported",
                error=error,
            )
            return {"ok": True, "skipped": True, "reason": error}
        await _update_chatwoot_recall_state(
            config,
            chatwoot_conversation_id=_string(
                mapped["chatwoot_conversation_id"]
            ),
            chatwoot_message_id=_string(mapped["chatwoot_message_id"]),
            state="recalled",
        )
        await repository.record_message_map(
            account_id=account_id,
            message_pk=message_pk,
            chatwoot_message_id=mapped["chatwoot_message_id"],
            chatwoot_conversation_id=mapped["chatwoot_conversation_id"],
            origin=mapped["origin"] or "xianyu",
            state="recalled",
        )
        return {
            "ok": True,
            "action": "recalled",
            "representation": "original_message_state",
        }
    if mapped:
        return {"ok": True, "skipped": True, "reason": "already mirrored"}
    if context["direction"] == "outbound" and context["send_status"] != "sent":
        return {"ok": True, "skipped": True, "reason": "outbound message not acknowledged"}
    if config.get("api_access_token") and config.get("chatwoot_account_id"):
        config = await _ensure_managed_account_inbox(repository, config)
    conversation_map = await _ensure_remote_conversation(repository, config, context)
    conversation_inbox_identifier = (
        _string(conversation_map.get("inbox_identifier"))
        or config["inbox_identifier"]
    )
    image_urls = _context_image_urls(context)
    files: list[tuple[str, tuple[str, bytes, str]]] = []
    for image_url in image_urls:
        data, mime_type, filename = await run_external_blocking(
            _download_image,
            image_url,
        )
        files.append(("attachments[]", (filename, data, mime_type)))
    audio_urls = _context_audio_urls(context)
    for audio_url in audio_urls:
        data, mime_type, filename = await run_external_blocking(
            _download_xianyu_audio,
            audio_url,
        )
        files.append(("attachments[]", (filename, data, mime_type)))
    content = _string(context.get("content"))
    if image_urls and content in image_urls:
        content = ""
    if context["direction"] == "inbound":
        content = _chatwoot_inbound_content(
            context,
            content,
            has_images=bool(image_urls),
            has_audio=bool(audio_urls),
        )
        message_url = (
            f"{config['base_url']}/public/api/v1/inboxes/{conversation_inbox_identifier}"
            f"/contacts/{conversation_map['source_id']}/conversations/"
            f"{conversation_map['chatwoot_conversation_id']}/messages"
        )
        data = {"content": content, "echo_id": message_pk}
        _, body = await run_external_blocking(
            _chatwoot_request,
            "POST",
            message_url,
            data=data if files else None,
            files=files or None,
            json_body=data if not files else None,
        )
    else:
        if not config["api_access_token"] or not config["chatwoot_account_id"]:
            error = "本地发出的消息要同步到 Chatwoot，需要服务账号令牌与平台账户 ID"
            await repository.record_message_map(
                account_id=account_id,
                message_pk=message_pk,
                chatwoot_message_id=None,
                chatwoot_conversation_id=conversation_map["chatwoot_conversation_id"],
                origin="xianyu",
                state="outbound_sync_unsupported",
                error=error,
            )
            return {"ok": True, "skipped": True, "reason": error}
        message_url = (
            f"{config['base_url']}/api/v1/accounts/{config['chatwoot_account_id']}"
            f"/conversations/{conversation_map['chatwoot_conversation_id']}/messages"
        )
        data = {"content": content, "message_type": "outgoing"}
        _, body = await run_external_blocking(
            _chatwoot_request,
            "POST",
            message_url,
            token=config["api_access_token"],
            data=data if files else None,
            files=files or None,
            json_body=data if not files else None,
        )
    chatwoot_message_id = _remote_id(body.get("id"))
    if not chatwoot_message_id:
        raise ChatwootIntegrationError("Chatwoot 创建消息后未返回消息 ID")
    await repository.record_message_map(
        account_id=account_id,
        message_pk=message_pk,
        chatwoot_message_id=chatwoot_message_id,
        chatwoot_conversation_id=conversation_map["chatwoot_conversation_id"],
        origin="xianyu",
        state="synced",
    )
    await repository.set_config_health(
        status="ready",
        error=None,
        pushed=True,
    )
    return {
        "ok": True,
        "chatwoot_message_id": chatwoot_message_id,
        "attachments": len(files),
    }


def _chatwoot_conversation_response(payload: object) -> dict[str, Any]:
    body = _json_object(payload)
    if "id" in body:
        return body
    nested = body.get("payload")
    if isinstance(nested, dict):
        return nested
    data = _json_object(body.get("data"))
    nested = data.get("payload")
    if isinstance(nested, dict):
        return nested
    return data if "id" in data else {}


async def _sync_chatwoot_read_snapshot(
    store: AccountStore,
    repository: ChatwootRepository,
    payload: dict[str, Any],
    *,
    mapping: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    snapshot = _chatwoot_read_snapshot(payload)
    if snapshot is None:
        return []
    remote_conversation_id = snapshot["chatwoot_conversation_id"]
    if mapping is None:
        mapping = await repository.get_conversation_map_by_remote_global(
            remote_conversation_id
        )
    if mapping is None:
        return []
    config = await repository.get_config(account_id=mapping["account_id"])
    if config is None or not config["enabled"]:
        return []

    remote_seen_at = snapshot["seen_at"]
    await repository.record_read_sync_observation(
        remote_conversation_id,
        remote_seen_at=remote_seen_at,
        synced=False,
    )
    if snapshot["unread_count"] != 0:
        return []

    last_inbound_at = mapping.get("last_inbound_at")
    if not isinstance(last_inbound_at, datetime):
        context = await repository.get_local_conversation_context(
            mapping["account_id"],
            mapping["conversation_id"],
        )
        last_inbound_at = context.get("last_inbound_at") if context else None
    if not isinstance(last_inbound_at, datetime):
        return []
    normalized_last_inbound = (
        last_inbound_at.replace(tzinfo=UTC)
        if last_inbound_at.tzinfo is None
        else last_inbound_at.astimezone(UTC)
    )
    if int(normalized_last_inbound.timestamp()) > snapshot["seen_at_epoch"]:
        return []

    # Chatwoot serializes these timestamps to whole seconds. Treat the whole
    # reported second as covered while the store re-checks for a newer inbound
    # message under the account write lock.
    read_through_at = remote_seen_at.replace(microsecond=999_999)
    covered, updates = await store.mark_conversation_read_shared(
        mapping["account_id"],
        mapping["conversation_id"],
        read_through_at=read_through_at,
    )
    await repository.record_read_sync_observation(
        remote_conversation_id,
        remote_seen_at=remote_seen_at,
        synced=covered,
    )
    if not covered:
        return []
    return [
        {
            "event": "conversation_read",
            "user_id": user_id,
            "data": conversation.model_dump(mode="json"),
        }
        for user_id, conversation in updates
    ]


async def reconcile_chatwoot_read_states(
    store: AccountStore,
) -> dict[str, Any]:
    """Reconcile Chatwoot agent views into local per-user unread state."""

    repository = ChatwootRepository(store.session_factory)
    config = await repository.get_config()
    if config is None or not config["platform_enabled"]:
        return {"ok": True, "skipped": True, "reason": "Chatwoot disabled"}
    token = _string(config.get("api_access_token"))
    chatwoot_account_id = config.get("chatwoot_account_id")
    if not token or not chatwoot_account_id:
        return {
            "ok": True,
            "skipped": True,
            "reason": "Chatwoot service credentials missing",
        }
    candidates = await repository.list_read_sync_candidates()
    if not candidates:
        return {
            "ok": True,
            "checked": 0,
            "read_synced_users": 0,
            "events": [],
            "errors": [],
        }

    semaphore = asyncio.Semaphore(4)

    async def fetch_and_sync(
        mapping: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], str | None]:
        remote_conversation_id = mapping["chatwoot_conversation_id"]
        try:
            async with semaphore:
                _, body = await run_external_blocking(
                    _chatwoot_request,
                    "GET",
                    (
                        f"{config['base_url']}/api/v1/accounts/"
                        f"{chatwoot_account_id}/conversations/"
                        f"{remote_conversation_id}"
                    ),
                    token=token,
                    timeout=10,
                )
            remote_conversation = _chatwoot_conversation_response(body)
            if not remote_conversation:
                raise ChatwootIntegrationError(
                    f"Chatwoot 会话 {remote_conversation_id} 响应缺少会话数据"
                )
            events = await _sync_chatwoot_read_snapshot(
                store,
                repository,
                remote_conversation,
                mapping=mapping,
            )
            return events, None
        except Exception as exc:
            return [], (
                f"Chatwoot 会话 {remote_conversation_id} 已读同步失败: "
                f"{str(exc)[:300]}"
            )

    results = await asyncio.gather(
        *(fetch_and_sync(mapping) for mapping in candidates)
    )
    events = [event for result, _ in results for event in result]
    errors = [error for _, error in results if error]
    return {
        "ok": not errors,
        "checked": len(candidates),
        "read_synced_users": len(events),
        "events": events,
        "errors": errors,
    }


async def _handle_conversation_status(
    store: AccountStore,
    repository: ChatwootRepository,
    payload: dict[str, Any],
) -> dict[str, Any]:
    remote_conversation_id = _extract_chatwoot_conversation_id(payload)
    conversation = _event_conversation(payload)
    status = _string(conversation.get("status") or payload.get("status")).lower()
    if not remote_conversation_id or not status:
        return {"ok": True, "skipped": True}
    mapping = await repository.get_conversation_map_by_remote_global(
        remote_conversation_id
    )
    if mapping is None:
        return {"ok": True, "status": status, "mapped": False}
    account_id = mapping["account_id"]
    config = await repository.get_config(account_id=account_id)
    if config is None or not config["enabled"]:
        return {"ok": True, "skipped": True, "reason": "account Chat disabled"}
    await repository.update_conversation_status(
        account_id,
        remote_conversation_id,
        status,
    )
    if status == "resolved":
        await store.set_manual_takeover(
            account_id,
            mapping["conversation_id"],
            mode="auto",
        )
    return {"ok": True, "status": status, "mapped": True}


async def execute_webhook_task(
    store: AccountStore,
    *,
    delivery_id: str,
    runtime_command: Any,
    read_notifier: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    repository = ChatwootRepository(store.session_factory)
    delivery = await repository.get_webhook(delivery_id)
    if delivery is None:
        raise ChatwootIntegrationError("Webhook 投递记录不存在")
    platform_config = await repository.get_config()
    if platform_config is None or not platform_config["enabled"]:
        await repository.finish_webhook(
            delivery_id,
            status="ignored",
            error="platform config disabled",
        )
        return {"ok": True, "skipped": True, "reason": "platform config disabled"}
    payload = delivery["payload"]
    event_name = delivery["event_name"]
    try:
        read_events: list[dict[str, Any]] = []
        try:
            read_events = await _sync_chatwoot_read_snapshot(
                store,
                repository,
                payload,
            )
            if read_notifier is not None:
                for event in read_events:
                    await read_notifier(event)
        except Exception:
            # Read reconciliation must never block message delivery or status
            # processing. The polling loop will retry it independently.
            logger.warning(
                "Chatwoot webhook read reconciliation failed",
                exc_info=True,
            )
        if event_name in {
            "conversation_status_changed",
            "conversation_updated",
            "conversation_created",
        }:
            result = await _handle_conversation_status(store, repository, payload)
        elif event_name == "message_updated":
            message = _event_message(payload)
            remote_message_id = _extract_chatwoot_message_id(payload)
            remote_conversation_id = _extract_chatwoot_conversation_id(payload)
            recall_state = _message_recall_state(message)
            if not remote_message_id:
                result = {"ok": True, "skipped": True}
            elif _message_was_deleted(message):
                maps = await repository.find_message_maps_by_remote_global(
                    remote_message_id
                )
                mapped_messages = [
                    item
                    for item in maps
                    if item.get("message_pk")
                    and item.get("chatwoot_conversation_id")
                ]
                should_recall = (
                    _message_is_outgoing(message.get("message_type"))
                    and not _message_is_private(message)
                    and bool(mapped_messages)
                )
                if not should_recall:
                    deleted_maps = 0
                    for item in mapped_messages:
                        account_id = _string(item.get("account_id"))
                        config = await repository.get_config(account_id=account_id)
                        if config is None or not config["enabled"]:
                            continue
                        await repository.record_message_map(
                            account_id=account_id,
                            message_pk=_remote_id(item.get("message_pk")),
                            chatwoot_message_id=remote_message_id,
                            chatwoot_conversation_id=_remote_id(
                                item.get("chatwoot_conversation_id")
                            ),
                            origin=_string(item.get("origin")) or "chatwoot",
                            state="remote_deleted",
                        )
                        deleted_maps += 1
                    result = {
                        "ok": True,
                        "remote_deleted": deleted_maps,
                        "platform_recall": False,
                    }
                else:
                    recall_results: list[dict[str, Any]] = []
                    status_config: dict[str, Any] | None = None
                    snapshot_contexts: list[dict[str, Any]] = []
                    snapshot_required = False
                    for item in mapped_messages:
                        account_id = _string(item.get("account_id"))
                        message_pk = _string(item.get("message_pk"))
                        item_state = _string(item.get("state"))
                        context = await repository.get_local_message_context(
                            account_id,
                            message_pk,
                        )
                        if context is not None:
                            snapshot_contexts.append(context)
                        config = await repository.get_config(account_id=account_id)
                        if status_config is None and config is not None:
                            status_config = config
                        if item_state == "recalled":
                            recall_results.append(
                                {
                                    "success": True,
                                    "message_pk": message_pk,
                                    "already_recalled": True,
                                }
                            )
                            continue
                        if item_state == "recall_failed":
                            recall_results.append(
                                {
                                    "success": False,
                                    "message_pk": message_pk,
                                    "already_processed": True,
                                    "error": _string(item.get("error"))
                                    or "闲鱼平台未确认撤回",
                                }
                            )
                            continue
                        if item_state in {
                            "recall_snapshot_pending",
                            "gateway_recalled_note_pending",
                        }:
                            snapshot_required = True
                            recall_results.append(
                                {
                                    "success": True,
                                    "message_pk": message_pk,
                                    "snapshot_pending": True,
                                }
                            )
                            continue
                        if item_state == "recall_failed_snapshot_pending":
                            snapshot_required = True
                            recall_results.append(
                                {
                                    "success": False,
                                    "message_pk": message_pk,
                                    "snapshot_pending": True,
                                    "error": _string(item.get("error"))
                                    or "闲鱼平台未确认撤回",
                                }
                            )
                            continue
                        snapshot_required = True
                        if config is None or not config["enabled"]:
                            recall_result = {
                                "success": False,
                                "error": "该闲鱼账户的 Chat 同步已关闭",
                            }
                        else:
                            conversation_map = (
                                await repository.get_conversation_map_by_remote(
                                    account_id,
                                    _string(item.get("chatwoot_conversation_id")),
                                )
                            )
                            conversation_id = _string(
                                (conversation_map or {}).get("conversation_id")
                            )
                            if not conversation_id:
                                recall_result = {
                                    "success": False,
                                    "error": "没有找到对应的闲鱼会话映射",
                                }
                            else:
                                try:
                                    recall_result = await runtime_command(
                                        "recall",
                                        account_id,
                                        {
                                            "conversation_id": conversation_id,
                                            "message_pk": message_pk,
                                        },
                                    )
                                except Exception as exc:
                                    recall_result = {
                                        "success": False,
                                        "error": str(exc)[:1000],
                                    }
                        recall_result = _json_object(recall_result)
                        recall_result["message_pk"] = message_pk
                        recall_result["snapshot_pending"] = True
                        recall_results.append(recall_result)
                        success = bool(recall_result.get("success"))
                        await repository.record_message_map(
                            account_id=account_id,
                            message_pk=_remote_id(message_pk),
                            chatwoot_message_id=remote_message_id,
                            chatwoot_conversation_id=_remote_id(
                                item.get("chatwoot_conversation_id")
                            ),
                            origin=_string(item.get("origin")) or "chatwoot",
                            state=(
                                "recall_snapshot_pending"
                                if success
                                else "recall_failed_snapshot_pending"
                            ),
                            error=(
                                None
                                if success
                                else _string(recall_result.get("error"))
                                or "闲鱼平台未确认撤回"
                            ),
                        )
                    succeeded = bool(recall_results) and all(
                        item.get("success") for item in recall_results
                    )
                    error = None
                    if not succeeded:
                        error = "; ".join(
                            _string(item.get("error")) or "闲鱼平台未确认撤回"
                            for item in recall_results
                            if not item.get("success")
                        )[:1000]
                    snapshot_created = False
                    if snapshot_required:
                        if status_config is None:
                            status_config = platform_config
                        if not remote_conversation_id:
                            raise ChatwootIntegrationError(
                                "Chatwoot 删除事件缺少会话 ID，无法恢复原消息快照"
                            )
                        snapshot_exists = (
                            await _chatwoot_recall_snapshot_exists(
                                status_config,
                                chatwoot_conversation_id=remote_conversation_id,
                                chatwoot_message_id=remote_message_id,
                            )
                        )
                        if not snapshot_exists:
                            await _create_private_recall_snapshot(
                                status_config,
                                chatwoot_conversation_id=remote_conversation_id,
                                chatwoot_message_id=remote_message_id,
                                contexts=snapshot_contexts,
                                succeeded=succeeded,
                                error=error,
                            )
                            snapshot_created = True
                        outcomes = {
                            _string(item.get("message_pk")): item
                            for item in recall_results
                        }
                        for item in mapped_messages:
                            outcome = outcomes.get(
                                _string(item.get("message_pk"))
                            )
                            if not outcome or not outcome.get("snapshot_pending"):
                                continue
                            item_success = bool(outcome.get("success"))
                            await repository.record_message_map(
                                account_id=_string(item.get("account_id")),
                                message_pk=_remote_id(item.get("message_pk")),
                                chatwoot_message_id=remote_message_id,
                                chatwoot_conversation_id=_remote_id(
                                    item.get("chatwoot_conversation_id")
                                ),
                                origin=_string(item.get("origin")) or "chatwoot",
                                state=(
                                    "recalled"
                                    if item_success
                                    else "recall_failed"
                                ),
                                error=(
                                    None
                                    if item_success
                                    else _string(outcome.get("error"))
                                    or "闲鱼平台未确认撤回"
                                ),
                            )
                    result = {
                        "ok": succeeded,
                        "remote_deleted": len(mapped_messages),
                        "platform_recall": True,
                        "private_snapshot_created": snapshot_created,
                        "recalled_messages": sum(
                            1 for item in recall_results if item.get("success")
                        ),
                        "failed_messages": sum(
                            1 for item in recall_results if not item.get("success")
                        ),
                    }
                    if error:
                        result["error"] = error
            elif recall_state == "requested":
                maps = await repository.find_message_maps_by_remote_global(
                    remote_message_id
                )
                mapped_messages = [
                    item
                    for item in maps
                    if item.get("message_pk")
                    and item.get("chatwoot_conversation_id")
                ]
                recall_results: list[dict[str, Any]] = []
                if not mapped_messages:
                    recall_results.append(
                        {
                            "success": False,
                            "error": "消息仍在同步或没有闲鱼消息映射，请稍后重试",
                        }
                    )
                for item in mapped_messages:
                    account_id = _string(item.get("account_id"))
                    if item.get("state") == "recalled":
                        recall_results.append(
                            {
                                "success": True,
                                "message_pk": item.get("message_pk"),
                                "already_recalled": True,
                            }
                        )
                        continue
                    config = await repository.get_config(account_id=account_id)
                    if config is None or not config["enabled"]:
                        recall_results.append(
                            {
                                "success": False,
                                "message_pk": item.get("message_pk"),
                                "error": "该闲鱼账户的 Chat 同步已关闭",
                            }
                        )
                        continue
                    try:
                        recall_result = await runtime_command(
                            "recall",
                            account_id,
                            {
                                "conversation_id": _string(
                                    item.get("conversation_id")
                                )
                                or _string(
                                    (
                                        await repository.get_conversation_map_by_remote(
                                            account_id,
                                            _string(
                                                item.get(
                                                    "chatwoot_conversation_id"
                                                )
                                            ),
                                        )
                                        or {}
                                    ).get("conversation_id")
                                ),
                                "message_pk": _string(item.get("message_pk")),
                            },
                        )
                    except Exception as exc:
                        recall_result = {
                            "success": False,
                            "error": str(exc)[:1000],
                        }
                    recall_result = _json_object(recall_result)
                    recall_results.append(recall_result)
                    if not recall_result.get("success"):
                        await repository.record_message_map(
                            account_id=account_id,
                            message_pk=_remote_id(item.get("message_pk")),
                            chatwoot_message_id=remote_message_id,
                            chatwoot_conversation_id=_remote_id(
                                item.get("chatwoot_conversation_id")
                            ),
                            origin=_string(item.get("origin")) or "chatwoot",
                            state="recall_failed",
                            error=_string(recall_result.get("error"))
                            or "闲鱼平台未确认撤回",
                        )
                succeeded = bool(recall_results) and all(
                    item.get("success") for item in recall_results
                )
                error = None
                if not succeeded:
                    error = "; ".join(
                        _string(item.get("error")) or "闲鱼平台未确认撤回"
                        for item in recall_results
                        if not item.get("success")
                    )[:1000]
                status_config = platform_config
                if mapped_messages:
                    mapped_config = await repository.get_config(
                        account_id=_string(mapped_messages[0].get("account_id"))
                    )
                    if mapped_config is not None:
                        status_config = mapped_config
                if remote_conversation_id:
                    await _update_chatwoot_recall_state(
                        status_config,
                        chatwoot_conversation_id=remote_conversation_id,
                        chatwoot_message_id=remote_message_id,
                        state="recalled" if succeeded else "failed",
                        error=error,
                    )
                if succeeded:
                    for item in mapped_messages:
                        await repository.record_message_map(
                            account_id=_string(item.get("account_id")),
                            message_pk=_remote_id(item.get("message_pk")),
                            chatwoot_message_id=remote_message_id,
                            chatwoot_conversation_id=_remote_id(
                                item.get("chatwoot_conversation_id")
                            ),
                            origin=_string(item.get("origin")) or "chatwoot",
                            state="recalled",
                        )
                result = {
                    "ok": succeeded,
                    "platform_recall": True,
                    "recalled_messages": sum(
                        1 for item in recall_results if item.get("success")
                    ),
                    "failed_messages": sum(
                        1 for item in recall_results if not item.get("success")
                    ),
                }
                if error:
                    result["error"] = error
            else:
                result = {
                    "ok": True,
                    "skipped": True,
                    "reason": "message update is not a delete or recall request",
                }
        elif event_name == "message_created":
            message = _event_message(payload)
            if not _message_is_outgoing(message.get("message_type")) or _message_is_private(message):
                result = {"ok": True, "skipped": True, "reason": "not a public agent message"}
            else:
                remote_conversation_id = _extract_chatwoot_conversation_id(payload)
                remote_message_id = _extract_chatwoot_message_id(payload)
                if not remote_conversation_id or not remote_message_id:
                    raise ChatwootIntegrationError("Chatwoot 消息缺少会话或消息 ID")
                existing = await repository.find_message_maps_by_remote_global(
                    remote_message_id
                )
                if existing:
                    result = {"ok": True, "skipped": True, "reason": "already forwarded"}
                else:
                    mapping = await repository.get_conversation_map_by_remote_global(
                        remote_conversation_id,
                    )
                    if mapping is None:
                        raise ChatwootIntegrationError("Chatwoot 会话尚未映射到闲鱼会话")
                    account_id = mapping["account_id"]
                    config = await repository.get_config(account_id=account_id)
                    if config is None or not config["enabled"]:
                        result = {
                            "ok": True,
                            "skipped": True,
                            "reason": "account Chat disabled",
                        }
                        await repository.finish_webhook(delivery_id, status="ignored")
                        return result
                    if _has_audio_attachment(message):
                        error = CHATWOOT_OUTBOUND_AUDIO_UNSUPPORTED_MESSAGE
                        await repository.record_message_map(
                            account_id=account_id,
                            message_pk=None,
                            chatwoot_message_id=remote_message_id,
                            chatwoot_conversation_id=remote_conversation_id,
                            origin="chatwoot",
                            state="audio_unsupported",
                            error=error,
                        )
                        note_created = False
                        note_error: str | None = None
                        try:
                            note_created = await _create_private_delivery_note(
                                config,
                                chatwoot_conversation_id=remote_conversation_id,
                                content=error,
                            )
                        except Exception as exc:
                            note_error = str(exc)[:1000]
                            logger.warning(
                                "Failed to add Chatwoot audio delivery note: %s",
                                exc,
                            )
                        result = {
                            "ok": True,
                            "skipped": True,
                            "reason": error,
                            "private_note_created": note_created,
                        }
                        if note_error:
                            result["private_note_error"] = note_error
                        await repository.finish_webhook(
                            delivery_id,
                            status="ignored",
                        )
                        return result
                    pieces: list[dict[str, Any]] = []
                    content = _string(message.get("content"))
                    if content:
                        pieces.append(
                            await runtime_command(
                                "text",
                                account_id,
                                {
                                    "conversation_id": mapping["conversation_id"],
                                    "receiver_user_id": mapping["peer_user_id"],
                                    "text": content,
                                    "client_request_id": f"cw-{remote_message_id}-text"[:64],
                                },
                            )
                        )
                    for index, url in enumerate(_extract_attachment_urls(message)):
                        image_data, mime_type, filename = await run_external_blocking(
                            _download_image,
                            url,
                            allowed_private_origin=config["base_url"],
                        )
                        pieces.append(
                            await runtime_command(
                                "image",
                                account_id,
                                {
                                    "conversation_id": mapping["conversation_id"],
                                    "client_request_id": (
                                        f"cw-{remote_message_id}-image-{index}"[:64]
                                    ),
                                    "image_data": image_data,
                                    "mime_type": mime_type,
                                    "filename": filename,
                                },
                            )
                        )
                    if not pieces:
                        result = {"ok": True, "skipped": True, "reason": "empty message"}
                    else:
                        for piece in pieces:
                            local_message = _json_object(piece.get("message"))
                            local_message_pk = _remote_id(local_message.get("message_pk"))
                            if local_message_pk:
                                await repository.record_message_map(
                                    account_id=account_id,
                                    message_pk=local_message_pk,
                                    chatwoot_message_id=remote_message_id,
                                    chatwoot_conversation_id=remote_conversation_id,
                                    origin="chatwoot",
                                    state="synced" if piece.get("success") else "failed",
                                    error=_string(piece.get("error")) or None,
                                )
                        if any(not piece.get("success") for piece in pieces):
                            raise ChatwootIntegrationError(
                                "; ".join(
                                    _string(piece.get("error")) or "闲鱼发送失败"
                                    for piece in pieces
                                    if not piece.get("success")
                                )
                            )
                        await store.set_manual_takeover(
                            account_id,
                            mapping["conversation_id"],
                            mode="permanent",
                        )
                        result = {"ok": True, "pieces": len(pieces)}
        else:
            result = {"ok": True, "skipped": True, "reason": "unsupported event"}
        if read_events:
            result["read_synced_users"] = len(read_events)
    except Exception as exc:
        await repository.finish_webhook(delivery_id, status="failed", error=str(exc)[:1000])
        await repository.set_config_health(
            status="error",
            error=str(exc)[:1000],
            webhook=True,
        )
        raise
    await repository.finish_webhook(delivery_id, status="success")
    await repository.set_config_health(
        status="ready",
        error=None,
        webhook=True,
    )
    return result


async def execute_account_status_task(
    store: AccountStore,
    *,
    account_id: str,
    state: str,
    message: str | None,
) -> dict[str, Any]:
    repository = ChatwootRepository(store.session_factory)
    config = await repository.get_config(account_id=account_id)
    if config is None or not config["enabled"]:
        return {"ok": True, "skipped": True}
    status = "online" if state == "online" else "offline" if state in {
        "disabled",
        "stopped",
        "offline",
        "auth_expired",
        "risk_blocked",
        "proxy_failed",
        "error",
    } else "connecting"
    updated_conversations = 0
    if not config["api_access_token"] or not config["chatwoot_account_id"]:
        await repository.set_config_health(
            status="degraded",
            error=(
                "账号状态回写需要配置 Chatwoot 平台账户 ID "
                "与专用服务账号令牌"
            ),
        )
        return {
            "ok": True,
            "skipped": True,
            "reason": "Chatwoot service credentials missing",
            "state": state,
            "chatwoot_status": status,
            "updated_conversations": 0,
        }
    await _ensure_custom_attribute_definitions(config)
    config = await _ensure_managed_account_inbox(
        repository,
        config,
        refresh_display_name=True,
        state_override=state,
    )
    stale_conversations = 0
    migrated_conversations = 0
    for conversation in await repository.list_conversation_maps(account_id):
        try:
            if not _mapping_uses_managed_inbox(conversation, config):
                context = await repository.get_local_conversation_context(
                    account_id,
                    conversation["conversation_id"],
                )
                if context is not None:
                    conversation = await _ensure_remote_conversation(
                        repository,
                        config,
                        context,
                    )
                    if conversation.get("migrated"):
                        migrated_conversations += 1
            await _sync_remote_conversation_metadata(
                config,
                chatwoot_conversation_id=conversation[
                    "chatwoot_conversation_id"
                ],
                label_title=config["label_title"],
                conversation_id=conversation["conversation_id"],
                peer_user_id=conversation["peer_user_id"],
                state=state,
                status_message=message,
            )
            updated_conversations += 1
        except ChatwootIntegrationError as exc:
            if exc.status_code == 404:
                stale_conversations += 1
                continue
            raise
    await repository.set_config_health(
        status="degraded" if config.get("label_error") else "ready",
        error=(
            "账号 Inbox 与状态属性已同步；Chatwoot 标签接口异常，标签暂未同步"
            if config.get("label_error")
            else None
        ),
        pushed=updated_conversations > 0,
    )
    return {
        "ok": True,
        "state": state,
        "chatwoot_status": status,
        "updated_conversations": updated_conversations,
        "migrated_conversations": migrated_conversations,
        "stale_conversations": stale_conversations,
    }


def _account_alert_source_id(account_id: str) -> str:
    digest = hashlib.sha256(f"account-alert:{account_id}".encode("utf-8")).hexdigest()
    return f"xy_account_alert_{digest[:32]}"


def _account_alert_content(
    config: dict[str, Any],
    *,
    state: str,
    message: str | None,
) -> str:
    event_labels = {
        "offline": "IM 连接持续掉线",
        "auth_expired": "Web Cookie 已确认失效",
        "risk_blocked": "账户触发风险控制",
        "proxy_failed": "账户代理连接异常",
        "error": "账户运行异常",
        "online": "账户已恢复在线",
        "test": "账户状态提醒测试",
    }
    icon = "✅" if state == "online" else "🧪" if state == "test" else "⚠️"
    detail = _string(message) or (
        "Chatwoot 账户状态提醒链路工作正常"
        if state == "test"
        else "请在平台账户页面检查当前连接状态"
    )
    occurred_at = datetime.now(SHANGHAI_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    return "\n".join(
        [
            f"{icon} {event_labels.get(state, '账户状态变化')}",
            f"平台：{config.get('platform_name') or _platform_name(config.get('platform'))}",
            f"账户：{config.get('account_name') or config.get('account_id')}",
            f"说明：{detail}",
            f"时间：{occurred_at} 上海时间",
        ]
    )


async def _ensure_account_alert_conversation(
    repository: ChatwootRepository,
    config: dict[str, Any],
) -> tuple[str, str]:
    config = await _ensure_managed_account_inbox(
        repository,
        config,
        refresh_display_name=True,
    )
    source_id = _string(config.get("alert_source_id")) or _account_alert_source_id(
        config["account_id"]
    )
    contact_name = (
        f"账户状态｜{config.get('platform_name') or _platform_name(config.get('platform'))}"
        f"｜{config.get('account_name') or config['account_id'][:8]}"
    )
    contact_url = (
        f"{config['base_url']}/public/api/v1/inboxes/"
        f"{config['inbox_identifier']}/contacts"
    )
    status_code, created_body = await run_external_blocking(
        _chatwoot_request,
        "POST",
        contact_url,
        json_body={
            "source_id": source_id,
            "name": contact_name,
            "custom_attributes": {
                "source_platform": config.get("platform") or DEFAULT_PLATFORM,
                "source_account_id": config["account_id"],
                "source_account_name": config.get("account_name"),
                "xianyu_event_channel": "account_status",
            },
        },
        acceptable={409, 422},
    )
    created = _json_object(created_body)
    created_contact = _json_object(created.get("contact"))
    contact_id = _remote_id(created.get("id") or created_contact.get("id"))
    await run_external_blocking(
        _chatwoot_request,
        "PATCH",
        f"{contact_url}/{source_id}",
        json_body={
            "name": contact_name,
            "custom_attributes": {
                "source_platform": config.get("platform") or DEFAULT_PLATFORM,
                "source_account_id": config["account_id"],
                "source_account_name": config.get("account_name"),
                "xianyu_event_channel": "account_status",
            },
        },
    )
    if contact_id is None or status_code >= 400:
        _, contact_body = await run_external_blocking(
            _chatwoot_request,
            "GET",
            f"{contact_url}/{source_id}",
        )
        contact_payload = _json_object(contact_body)
        nested_contact = _json_object(contact_payload.get("contact"))
        contact_id = _remote_id(
            contact_payload.get("id") or nested_contact.get("id")
        )
    if contact_id is None:
        raise ChatwootIntegrationError("Chatwoot 账户提醒联系人未返回联系人 ID")

    conversation_id = _remote_id(config.get("alert_conversation_id"))
    if conversation_id:
        status_code, _ = await run_external_blocking(
            _chatwoot_request,
            "GET",
            (
                f"{config['base_url']}/api/v1/accounts/"
                f"{config['chatwoot_account_id']}/conversations/{conversation_id}"
            ),
            token=config["api_access_token"],
            acceptable={404},
        )
        if status_code == 404:
            conversation_id = None
    attributes = _conversation_source_attributes(
        config,
        conversation_id=f"account-alert:{config['account_id']}",
        peer_user_id="system:account-status",
        state=_string(config.get("account_state")) or None,
        status_message=_string(config.get("account_status_message")) or None,
    )
    attributes["xianyu_event_channel"] = "account_status"
    if conversation_id is None:
        _, conversation_body = await run_external_blocking(
            _chatwoot_request,
            "POST",
            (
                f"{config['base_url']}/api/v1/accounts/"
                f"{config['chatwoot_account_id']}/conversations"
            ),
            token=config["api_access_token"],
            json_body={
                "source_id": source_id,
                "inbox_id": config["chatwoot_inbox_id"],
                "contact_id": int(contact_id),
                "status": "open",
                "assignee_id": config.get("default_assignee_id"),
                "custom_attributes": attributes,
            },
        )
        conversation_id = _remote_id(
            conversation_body.get("id") or conversation_body.get("display_id")
        )
    if conversation_id is None:
        raise ChatwootIntegrationError("Chatwoot 账户提醒会话未返回会话 ID")
    await repository.update_account_alert_channel(
        account_id=config["account_id"],
        source_id=source_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
    )
    return source_id, conversation_id


async def execute_account_alert_task(
    store: AccountStore,
    *,
    account_id: str,
    state: str,
    message: str | None,
    expected_state: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    repository = ChatwootRepository(store.session_factory)
    config = await repository.get_config(account_id=account_id)
    if (
        config is None
        or not config["enabled"]
        or not config.get("account_alerts_enabled")
    ):
        return {"ok": True, "skipped": True, "reason": "account alerts disabled"}
    current_state = _string(config.get("account_state"))
    if not force and expected_state and current_state != expected_state:
        return {
            "ok": True,
            "skipped": True,
            "reason": "account state changed before alert delay elapsed",
            "current_state": current_state,
        }
    previous_state = _string(config.get("last_alert_state"))
    if not force:
        if state == "online" and previous_state not in CHATWOOT_ACCOUNT_ALERT_STATES:
            return {
                "ok": True,
                "skipped": True,
                "reason": "no prior failure alert requires recovery",
            }
        if state in CHATWOOT_ACCOUNT_ALERT_STATES and previous_state == state:
            return {
                "ok": True,
                "skipped": True,
                "reason": "alert state already delivered",
            }
    if not config.get("api_access_token") or not config.get("chatwoot_account_id"):
        raise ChatwootIntegrationError(
            "账户状态提醒需要 Chatwoot 平台账户 ID 与专用服务账号令牌"
        )
    source_id, conversation_id = await _ensure_account_alert_conversation(
        repository,
        config,
    )
    content = _account_alert_content(config, state=state, message=message)
    await run_external_blocking(
        _chatwoot_request,
        "POST",
        (
            f"{config['base_url']}/api/v1/accounts/"
            f"{config['chatwoot_account_id']}/conversations/"
            f"{conversation_id}/toggle_status"
        ),
        token=config["api_access_token"],
        json_body={"status": "open"},
        acceptable={404},
    )
    _, body = await run_external_blocking(
        _chatwoot_request,
        "POST",
        (
            f"{config['base_url']}/public/api/v1/inboxes/"
            f"{config['inbox_identifier']}/contacts/{source_id}/conversations/"
            f"{conversation_id}/messages"
        ),
        json_body={
            "content": content,
            "echo_id": (
                f"account-alert-{account_id}-{state}-"
                f"{int(time.time() * 1000)}"
            ),
        },
    )
    if not force:
        await repository.record_account_alert_state(
            account_id=account_id,
            state=state,
        )
    await repository.set_config_health(status="ready", error=None, pushed=True)
    message_body = _json_object(body)
    return {
        "ok": True,
        "state": state,
        "previous_state": previous_state or None,
        "chatwoot_conversation_id": conversation_id,
        "chatwoot_message_id": _remote_id(
            message_body.get("id")
            or _json_object(message_body.get("message")).get("id")
        ),
    }


async def execute_account_metadata_task(
    store: AccountStore,
    *,
    account_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    repository = ChatwootRepository(store.session_factory)
    config = await repository.get_config(account_id=account_id)
    if config is None or not config["platform_enabled"]:
        return {"ok": True, "skipped": True, "reason": "Chatwoot disabled"}
    account_chat_enabled = bool(config["enabled"])
    token_ready = bool(
        config.get("api_access_token") and config.get("chatwoot_account_id")
    )
    definitions_created = 0
    if token_ready:
        definitions_created = await _ensure_custom_attribute_definitions(config)
        if account_chat_enabled or config.get("managed_inbox"):
            config = await _ensure_managed_account_inbox(
                repository,
                config,
                refresh_display_name=True,
            )
    mappings = await repository.list_conversation_maps(account_id)
    contact_updates = 0
    conversation_updates = 0
    migrated_conversations = 0
    stale_conversations = 0
    errors: list[str] = []
    for mapping in mappings:
        if (
            account_chat_enabled
            and config.get("managed_inbox")
            and not _mapping_uses_managed_inbox(mapping, config)
        ):
            context = await repository.get_local_conversation_context(
                account_id,
                mapping["conversation_id"],
            )
            if context is None:
                context = {
                    "conversation_id": mapping["conversation_id"],
                    "peer_user_id": mapping["peer_user_id"],
                    "peer_name": _string(mapping.get("peer_name"))
                    or mapping["peer_user_id"],
                    "account_name": config["account_name"],
                    "platform": config["platform"],
                    "account_state": config.get("account_state"),
                    "account_status_message": config.get(
                        "account_status_message"
                    ),
                    "avatar_url": None,
                }
            try:
                mapping = await _ensure_remote_conversation(
                    repository,
                    config,
                    context,
                )
                if mapping.get("migrated"):
                    migrated_conversations += 1
            except Exception as exc:
                errors.append(
                    f"会话 {mapping['chatwoot_conversation_id']} 迁移失败: "
                    f"{str(exc)[:300]}"
                )
                continue
        inbox_identifier = _string(mapping.get("inbox_identifier")) or _string(
            config.get("legacy_inbox_identifier")
        )
        if not inbox_identifier:
            errors.append(
                f"会话 {mapping['chatwoot_conversation_id']} 缺少 Inbox 标识符"
            )
            continue
        legacy_inbox = (
            inbox_identifier == _string(config.get("legacy_inbox_identifier"))
        )
        try:
            await _update_remote_contact_identity(
                config,
                inbox_identifier=inbox_identifier,
                source_id=mapping["source_id"],
                peer_user_id=mapping["peer_user_id"],
                peer_name=_string(mapping.get("peer_name"))
                or mapping["peer_user_id"],
                legacy_inbox=legacy_inbox,
            )
            contact_updates += 1
            if token_ready and config.get("managed_inbox"):
                await _sync_remote_conversation_metadata(
                    config,
                    chatwoot_conversation_id=mapping[
                        "chatwoot_conversation_id"
                    ],
                    label_title=config["label_title"],
                    conversation_id=mapping["conversation_id"],
                    peer_user_id=mapping["peer_user_id"],
                    state=_string(config.get("account_state")) or None,
                    status_message=_string(
                        config.get("account_status_message")
                    )
                    or None,
                )
                conversation_updates += 1
        except Exception as exc:
            if (
                isinstance(exc, ChatwootIntegrationError)
                and exc.status_code == 404
            ):
                stale_conversations += 1
                continue
            errors.append(
                f"会话 {mapping['chatwoot_conversation_id']}: {str(exc)[:300]}"
            )
    if errors:
        error = "; ".join(errors[:5])
        await repository.set_config_health(status="error", error=error)
        raise ChatwootIntegrationError(error)
    if token_ready:
        await repository.set_config_health(
            status="degraded" if config.get("label_error") else "ready",
            error=(
                "账号 Inbox 与自定义属性已同步；Chatwoot 标签接口异常，标签暂未同步"
                if config.get("label_error")
                else None
            ),
            pushed=True,
        )
    else:
        await repository.set_config_health(
            status="degraded",
            error=(
                "账号名称已同步；会话标签、账号分组和状态回写需要配置 "
                "Chatwoot 平台账户 ID 与专用服务账号令牌"
            ),
            pushed=contact_updates > 0,
        )
    return {
        "ok": True,
        "reason": reason,
        "account_chat_enabled": account_chat_enabled,
        "token_ready": token_ready,
        "managed_inbox": bool(config.get("managed_inbox")),
        "label_synced": bool(config.get("label_title")),
        "label_error": config.get("label_error"),
        "definitions_created": definitions_created,
        "contact_updates": contact_updates,
        "conversation_updates": conversation_updates,
        "migrated_conversations": migrated_conversations,
        "conversation_count": len(mappings),
        "stale_conversations": stale_conversations,
    }
