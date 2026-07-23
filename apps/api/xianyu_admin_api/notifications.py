"""Notification services for the admin backend."""

from __future__ import annotations

import asyncio
from urllib.parse import urljoin

import requests

from .executors import run_external_blocking

from integrations.xianyu_core.peer_names import normalize_peer_name

from .schemas import BarkConfigPayload, MessagePayload, NotificationResultPayload
from .store import AccountRecord, AccountStore


class BarkNotifier:
    """Bark push notification integration.

    This integration is intentionally independent from account SOCKS proxies.
    Account proxies are for Xianyu WS/MTOP traffic; Bark is an admin-side
    notification channel.
    """

    def __init__(self, store: AccountStore, timeout: float = 8.0) -> None:
        self._store = store
        self._timeout = timeout

    async def test(self, title: str, body: str) -> NotificationResultPayload:
        config = await self._store.get_bark_config()
        return await self._send(config, title=title, body=body)

    async def notify_inbound_message(
        self,
        account: AccountRecord,
        message: MessagePayload,
    ) -> None:
        if message.direction != "inbound" or message.message_type == "system":
            return

        config = await self._store.get_bark_config()
        if not config.enabled:
            return
        account_notification = await self._store.get_account_notification(account.account_id)
        if account_notification is None or not account_notification.enabled:
            return

        peer = (
            normalize_peer_name(message.peer_name, peer_user_id=message.peer_user_id)
            or message.peer_user_id
            or message.conversation_id
        )
        title = f"闲鱼新消息｜{account.display_name}"
        body = f"{peer}: {message.content or '[非文本消息]'}"
        result = await self._send(config, title=title, body=body)
        if not result.ok:
            await self._store.add_runtime_event(
                account.account_id,
                "error",
                f"Bark 通知发送失败：{result.message}",
            )

    async def _send(
        self,
        config: BarkConfigPayload,
        *,
        title: str,
        body: str,
    ) -> NotificationResultPayload:
        if not config.enabled:
            return NotificationResultPayload(ok=False, message="Bark 通知未启用")
        if not config.device_key:
            return NotificationResultPayload(ok=False, message="Bark device key 未配置")
        if not config.server_url.startswith(("http://", "https://")):
            return NotificationResultPayload(ok=False, message="Bark server_url 必须是 http(s) URL")

        return await run_external_blocking(self._send_sync, config, title, body)

    def _send_sync(
        self,
        config: BarkConfigPayload,
        title: str,
        body: str,
    ) -> NotificationResultPayload:
        endpoint = urljoin(config.server_url.rstrip("/") + "/", config.device_key.lstrip("/"))
        payload: dict[str, str] = {
            "title": title,
            "body": body,
        }
        if config.sound:
            payload["sound"] = config.sound
        if config.group:
            payload["group"] = config.group
        if config.icon:
            payload["icon"] = config.icon

        try:
            response = requests.post(endpoint, json=payload, timeout=self._timeout)
        except requests.RequestException as exc:
            return NotificationResultPayload(ok=False, message=str(exc))

        response_text = response.text[:1000] if response.text else None
        if 200 <= response.status_code < 300:
            return NotificationResultPayload(
                ok=True,
                message="Bark 通知已发送",
                status_code=response.status_code,
                response_text=response_text,
            )

        return NotificationResultPayload(
            ok=False,
            message=f"Bark HTTP {response.status_code}",
            status_code=response.status_code,
            response_text=response_text,
        )
