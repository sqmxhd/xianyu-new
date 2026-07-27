"""Concrete phase-1 Xianyu WebSocket client.

This implementation is intentionally minimal:

- one runtime process can hold multiple account sessions;
- every enabled proxy is SOCKS-only and is applied to WS and requests.Session;
- inbound chat messages are normalized into ``ChatMessageEvent``;
- outbound text messages are sent through the active account WebSocket.

It doesn't persist to a database, implement auto-reply, or implement delivery.
Those belong to later phases.
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, urlparse

import requests

from .images import ImageUploadError, PreparedImage, UploadedImage, prepare_image
from .message_content import parse_text_card_content
from .models import (
    AccountConfig,
    ChatMediaAttachment,
    ChatMessageEvent,
    ConnectionState,
    ConversationPage,
    ConversationSummary,
    Direction,
    MessagePage,
    MessageType,
    PlatformBlacklistResult,
    SendMessageResult,
    InteractiveVerification,
)
from .identity import DEFAULT_CLIENT_IDENTITY
from .peer_names import extract_peer_name
from .ports import (
    CookieHandler,
    MessageHandler,
    StateHandler,
    TokenHandler,
    VerificationHandler,
)
from .proxy import build_socks_proxy_url
from .upstream import UpstreamModules, load_upstream_modules


DEFAULT_WS_URL = "wss://wss-goofish.dingtalk.com/"
IMAGE_UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
DEFAULT_USER_AGENT = DEFAULT_CLIENT_IDENTITY.user_agent
DEFAULT_DINGTALK_UA = DEFAULT_CLIENT_IDENTITY.dingtalk_user_agent
PLATFORM_BLACKLIST_APIS = {
    "query": ("mtop.taobao.idlemessage.pc.blacklist.query", "1.0"),
    "add": ("mtop.taobao.idlemessage.pc.blacklist.add", "2.0"),
    "remove": ("mtop.taobao.idlemessage.pc.blacklist.remove", "1.0"),
}
MAX_CURSOR = 9_007_199_254_740_991
logger = logging.getLogger(__name__)
_PROTOCOL_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="xianyu-protocol",
)
PUSH_QUEUE_MAX_SIZE = 1000
PUSH_WORKER_COUNT = 4
BlockingRunner = Callable[..., Awaitable[Any]]


async def _default_blocking_runner(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(func, *args, **kwargs)


def _apply_identity_headers(session: Any, identity: Any) -> None:
    """Apply account identity to requests-compatible and lightweight test adapters."""

    headers = getattr(session, "headers", None)
    if headers is None:
        headers = {}
        try:
            session.headers = headers
        except (AttributeError, TypeError):
            return
    update = getattr(headers, "update", None)
    if callable(update):
        update(
            {
                "User-Agent": identity.user_agent,
                "Accept-Language": identity.accept_language,
            }
        )


class RiskControlError(RuntimeError):
    """The platform asked the account to complete an interactive validation."""

    def __init__(self, verification: InteractiveVerification) -> None:
        super().__init__("闲鱼 IM 需要完成安全验证，连接已停止等待人工处理")
        self.verification = verification


class AuthenticationExpiredError(RuntimeError):
    """The platform rejected the account session and requires fresh credentials."""


class XianyuCoreRuntime:
    """In-memory runtime implementing the phase-1 XianyuCoreClient port."""

    def __init__(
        self,
        upstream: UpstreamModules | None = None,
        *,
        platform_runner: BlockingRunner | None = None,
        media_runner: BlockingRunner | None = None,
    ) -> None:
        self._upstream = upstream
        self._sessions: dict[str, XianyuAccountSession] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._platform_runner = platform_runner or _default_blocking_runner
        self._media_runner = media_runner or _default_blocking_runner

    def _session_lock(self, account_id: str) -> asyncio.Lock:
        return self._session_locks.setdefault(account_id, asyncio.Lock())

    @property
    def upstream(self) -> UpstreamModules:
        if self._upstream is None:
            self._upstream = load_upstream_modules()
        return self._upstream

    async def start_account(
        self,
        account: AccountConfig,
        on_message: MessageHandler,
        on_state: StateHandler | None = None,
        on_cookie: CookieHandler | None = None,
        on_im_token: TokenHandler | None = None,
        on_verification: VerificationHandler | None = None,
        wait_until_online: float = 15.0,
        force_restart: bool = False,
    ) -> bool:
        async with self._session_lock(account.account_id):
            if not account.enabled:
                if on_state:
                    await on_state(
                        account.account_id, ConnectionState.DISABLED, "account disabled"
                    )
                return False

            existing = self._sessions.get(account.account_id)
            if existing is not None and existing.is_running() and not force_restart:
                return await existing.wait_online(timeout=wait_until_online)

            await self._stop_account_locked(account.account_id)
            session = XianyuAccountSession(
                account=account,
                upstream=self.upstream,
                platform_runner=self._platform_runner,
                media_runner=self._media_runner,
            )
            self._sessions[account.account_id] = session
            session.start(
                on_message=on_message,
                on_state=on_state,
                on_cookie=on_cookie,
                on_im_token=on_im_token,
                on_verification=on_verification,
            )
            return await session.wait_online(timeout=wait_until_online)

    async def stop_account(self, account_id: str) -> None:
        async with self._session_lock(account_id):
            await self._stop_account_locked(account_id)

    async def _stop_account_locked(self, account_id: str) -> None:
        session = self._sessions.pop(account_id, None)
        if session:
            await session.stop()

    async def stop_all(self) -> None:
        account_ids = list(self._sessions)
        if account_ids:
            await asyncio.gather(*(self.stop_account(account_id) for account_id in account_ids))

    async def wait_account(self, account_id: str) -> None:
        session = self._sessions[account_id]
        await session.wait()

    async def send_text(
        self,
        account_id: str,
        conversation_id: str,
        receiver_user_id: str,
        text: str,
    ) -> SendMessageResult:
        session = self._sessions.get(account_id)
        if session is None:
            return SendMessageResult(
                success=False,
                account_id=account_id,
                conversation_id=conversation_id,
                error="account session is not running",
            )
        return await session.send_text(conversation_id, receiver_user_id, text)

    async def send_image(
        self,
        account_id: str,
        conversation_id: str,
        receiver_user_id: str,
        image_data: bytes,
    ) -> SendMessageResult:
        session = self._sessions.get(account_id)
        if session is None:
            return SendMessageResult(
                success=False,
                account_id=account_id,
                conversation_id=conversation_id,
                error="account session is not running",
            )
        return await session.send_image(conversation_id, receiver_user_id, image_data)

    async def recall_message(
        self,
        account_id: str,
        conversation_id: str,
        message_id: str,
    ) -> SendMessageResult:
        session = self._sessions.get(account_id)
        if session is None:
            return SendMessageResult(
                success=False,
                account_id=account_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error="account session is not running",
            )
        return await session.recall_message(conversation_id, message_id)

    async def get_platform_blacklist(
        self,
        account_id: str,
        conversation_id: str,
    ) -> PlatformBlacklistResult:
        session = self._sessions.get(account_id)
        if session is None:
            return PlatformBlacklistResult(
                success=False,
                account_id=account_id,
                conversation_id=conversation_id,
                error="account session is not running",
            )
        return await session.platform_blacklist(conversation_id, "query")

    async def set_platform_blacklist(
        self,
        account_id: str,
        conversation_id: str,
        blocked: bool,
    ) -> PlatformBlacklistResult:
        session = self._sessions.get(account_id)
        if session is None:
            return PlatformBlacklistResult(
                success=False,
                account_id=account_id,
                conversation_id=conversation_id,
                error="account session is not running",
            )
        return await session.platform_blacklist(
            conversation_id,
            "add" if blocked else "remove",
        )

    async def refresh_token(self, account_id: str) -> None:
        session = self._sessions.get(account_id)
        if session is None:
            raise RuntimeError(f"account session is not running: {account_id}")
        await session.refresh_token()

    async def list_conversations(
        self, account_id: str, cursor: int | None = None, limit: int = 20
    ) -> ConversationPage:
        session = self._sessions.get(account_id)
        if session is None:
            raise RuntimeError(f"account session is not running: {account_id}")
        return await session.list_conversations(cursor=cursor, limit=limit)

    async def list_messages(
        self,
        account_id: str,
        conversation_id: str,
        cursor: int | None = None,
        limit: int = 20,
    ) -> MessagePage:
        session = self._sessions.get(account_id)
        if session is None:
            raise RuntimeError(f"account session is not running: {account_id}")
        return await session.list_messages(conversation_id, cursor=cursor, limit=limit)

    async def get_order_headinfo(
        self,
        account_id: str,
        item_id: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        session = self._sessions.get(account_id)
        if session is None:
            raise RuntimeError(f"account session is not running: {account_id}")
        return await session.get_order_headinfo(item_id, conversation_id)

    async def get_account_identity(self, account_id: str) -> dict[str, str | None]:
        session = self._sessions.get(account_id)
        if session is None:
            raise RuntimeError(f"account session is not running: {account_id}")
        return await session.get_account_identity()

    async def get_user_profile(
        self,
        account_id: str,
        conversation_id: str,
        *,
        is_owner: bool = False,
    ) -> dict[str, str | None]:
        session = self._sessions.get(account_id)
        if session is None:
            raise RuntimeError(f"account session is not running: {account_id}")
        return await session.get_user_profile(conversation_id, is_owner=is_owner)

    async def replace_cookie(self, account_id: str, cookie: str) -> bool:
        async with self._session_lock(account_id):
            session = self._sessions.get(account_id)
            if session is None or not session.is_running():
                return False
            await session.replace_cookie(cookie)
            return True

    def is_account_online(self, account_id: str) -> bool:
        session = self._sessions.get(account_id)
        return bool(session and session._online_event.is_set())

    def is_account_running(self, account_id: str) -> bool:
        session = self._sessions.get(account_id)
        return bool(session and session.is_running())

    def account_connection_health(self, account_id: str) -> dict[str, Any]:
        session = self._sessions.get(account_id)
        if session is None:
            return {
                "running": False,
                "online": False,
                "connected_at_ms": None,
                "last_heartbeat_at_ms": None,
                "reconnect_count": 0,
                "last_disconnect_reason": None,
            }
        return session.connection_health()


class XianyuAccountSession:
    """One account-scoped WebSocket session."""

    def __init__(
        self,
        account: AccountConfig,
        upstream: UpstreamModules,
        ws_url: str = DEFAULT_WS_URL,
        heartbeat_interval: int = 15,
        token_refresh_interval: int = 0,
        platform_runner: BlockingRunner | None = None,
        media_runner: BlockingRunner | None = None,
    ) -> None:
        self.account = account
        self.client_identity = account.client_identity
        self.upstream = upstream
        self.ws_url = ws_url
        self.heartbeat_interval = heartbeat_interval
        self.token_refresh_interval = token_refresh_interval
        self._platform_runner = platform_runner or _default_blocking_runner
        self._media_runner = media_runner or _default_blocking_runner

        self.cookies = upstream.trans_cookies(account.cookie)
        if "unb" not in self.cookies:
            raise ValueError("cookie is missing required field: unb")

        self.myid = self.cookies["unb"]
        stable_device_uuid = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"xianyu-im:{account.account_id}:{self.myid}",
        )
        self.device_id = f"{str(stable_device_uuid).upper()}-{self.myid}"
        self.proxy_url = build_socks_proxy_url(account.proxy)

        self.xianyu = upstream.XianyuApis(self.cookies, self.device_id)
        self.xianyu.session.trust_env = False
        _apply_identity_headers(self.xianyu.session, self.client_identity)
        if self.proxy_url:
            self.xianyu.session.proxies.update({"http": self.proxy_url, "https": self.proxy_url})

        self.websocket: Any | None = None
        self._task: asyncio.Task[None] | None = None
        self._receiver_task: asyncio.Task[None] | None = None
        self._push_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._token_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._online_event = asyncio.Event()
        self._on_message: MessageHandler | None = None
        self._on_state: StateHandler | None = None
        self._on_cookie: CookieHandler | None = None
        self._on_im_token: TokenHandler | None = None
        self._on_verification: VerificationHandler | None = None
        self._pending_requests: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._push_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=PUSH_QUEUE_MAX_SIZE
        )
        self._credential_lock = asyncio.Lock()
        self._credential_changed_event = asyncio.Event()
        self._rpc_lock = asyncio.Lock()
        self._last_rpc_at = 0.0
        self._token_refresh_failed = False
        self._im_token_expires_at_ms: int | None = account.im_token_expires_at_ms
        self._im_token: str | None = (
            account.im_token
            if account.im_token
            and (account.im_token_expires_at_ms or 0) > int(time.time() * 1000) + 60_000
            else None
        )
        self._started_at_ms = int(time.time() * 1000)
        self._connected_at_ms: int | None = None
        self._last_heartbeat_at_ms: int | None = None
        self._last_server_frame_at_ms: int | None = None
        self._last_rpc_success_at_ms: int | None = None
        self._last_rpc_latency_ms: int | None = None
        self._last_rpc_error: str | None = None
        self._consecutive_rpc_failures = 0
        self._push_queue_dropped = 0
        self._push_inflight = 0
        self._active_pushes: dict[str, str] = {}
        self._reconnect_count = 0
        self._connection_count = 0
        self._last_disconnect_reason: str | None = None

    def start(
        self,
        on_message: MessageHandler,
        on_state: StateHandler | None,
        on_cookie: CookieHandler | None = None,
        on_im_token: TokenHandler | None = None,
        on_verification: VerificationHandler | None = None,
    ) -> None:
        self._on_message = on_message
        self._on_state = on_state
        self._on_cookie = on_cookie
        self._on_im_token = on_im_token
        self._on_verification = on_verification
        self._task = asyncio.create_task(self._run(), name=f"xianyu:{self.account.account_id}")

    async def wait(self) -> None:
        if self._task:
            await self._task

    def is_running(self) -> bool:
        return bool(
            self._task
            and not self._task.done()
            and not self._stop_event.is_set()
        )

    def connection_health(self) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        server_frame_recent = bool(
            self._last_server_frame_at_ms
            and now_ms - self._last_server_frame_at_ms <= max(60_000, self.heartbeat_interval * 4_000)
        )
        return {
            "running": self.is_running(),
            "online": self._online_event.is_set(),
            "connected_at_ms": self._connected_at_ms,
            "last_heartbeat_at_ms": self._last_heartbeat_at_ms,
            "last_server_frame_at_ms": self._last_server_frame_at_ms,
            "last_rpc_success_at_ms": self._last_rpc_success_at_ms,
            "last_rpc_latency_ms": self._last_rpc_latency_ms,
            "last_rpc_error": self._last_rpc_error,
            "consecutive_rpc_failures": self._consecutive_rpc_failures,
            "rpc_healthy": (
                self._online_event.is_set()
                and server_frame_recent
                and self._consecutive_rpc_failures == 0
            ),
            "push_queue_depth": self._push_queue.qsize(),
            "push_queue_dropped": self._push_queue_dropped,
            "push_inflight": self._push_inflight,
            "active_pushes": list(self._active_pushes.values()),
            "reconnect_count": self._reconnect_count,
            "last_disconnect_reason": self._last_disconnect_reason,
        }

    async def wait_online(self, timeout: float = 15.0) -> bool:
        try:
            await asyncio.wait_for(self._online_event.wait(), timeout=timeout)
        except TimeoutError:
            return False
        return True

    async def stop(self) -> None:
        self._stop_event.set()
        for task in (
            self._heartbeat_task,
            self._token_task,
            self._receiver_task,
            self._push_task,
            self._task,
        ):
            if task and not task.done():
                task.cancel()
        if self.websocket is not None:
            with suppress(Exception):
                await self.websocket.close()
        for task in (
            self._heartbeat_task,
            self._token_task,
            self._receiver_task,
            self._push_task,
            self._task,
        ):
            if task:
                with suppress(asyncio.CancelledError, Exception):
                    await task
        await self._emit_state(ConnectionState.STOPPED, None)

    async def send_text(
        self,
        conversation_id: str,
        receiver_user_id: str,
        text: str,
    ) -> SendMessageResult:
        payload = {
            "contentType": 1,
            "text": {
                "text": text,
            },
        }
        return await self._send_custom_message(
            conversation_id,
            receiver_user_id,
            payload,
        )

    async def send_image(
        self,
        conversation_id: str,
        receiver_user_id: str,
        image_data: bytes,
    ) -> SendMessageResult:
        if self.websocket is None or not self._online_event.is_set():
            return SendMessageResult(
                success=False,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                error="websocket is not online",
            )
        try:
            prepared = await self._media_runner(prepare_image, image_data)
            uploaded = await self._upload_image(prepared)
        except Exception as exc:
            return SendMessageResult(
                success=False,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                error=str(exc),
            )

        payload = {
            "contentType": 2,
            "image": {
                "pics": [
                    {
                        "type": 0,
                        "url": uploaded.url,
                        "width": uploaded.width,
                        "height": uploaded.height,
                    }
                ]
            },
        }
        result = await self._send_custom_message(
            conversation_id,
            receiver_user_id,
            payload,
        )
        result.raw_payload = {
            **dict(result.raw_payload),
            "media": {
                "url": uploaded.url,
                "width": uploaded.width,
                "height": uploaded.height,
                "mime_type": uploaded.mime_type,
                "size_bytes": uploaded.size_bytes,
                "sha256": uploaded.sha256,
            },
        }
        return result

    async def recall_message(
        self,
        conversation_id: str,
        message_id: str,
    ) -> SendMessageResult:
        if self.websocket is None or not self._online_event.is_set():
            return SendMessageResult(
                success=False,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error="websocket is not online",
            )
        frame = {
            "lwp": "/r/MessageManager/recallMessage",
            "headers": {"mid": self.upstream.generate_mid()},
            "body": [message_id],
        }
        try:
            response = await self._send_and_wait(frame, timeout=10)
            code = response.get("code", 200 if "body" in response else None)
            success = str(code) == "200"
            return SendMessageResult(
                success=success,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error=None if success else self._response_error(response),
                raw_payload={"request": frame, "response": response},
            )
        except Exception as exc:
            return SendMessageResult(
                success=False,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error=str(exc),
                raw_payload={"request": frame},
            )

    async def platform_blacklist(
        self,
        conversation_id: str,
        action: str,
    ) -> PlatformBlacklistResult:
        expected_cookie = self.account.cookie
        updated_cookie: str | None = None
        cookie_applied = False
        try:
            async with self._credential_lock:
                try:
                    result = await self._platform_runner(
                        self._platform_blacklist_sync,
                        conversation_id,
                        action,
                    )
                finally:
                    updated_cookie = self.upstream.get_session_cookies_str(self.xianyu.session)
                if updated_cookie and updated_cookie != expected_cookie:
                    updated_cookies = self.upstream.trans_cookies(updated_cookie)
                    if updated_cookies.get("unb") == self.myid:
                        self.cookies = updated_cookies
                        self.account.cookie = updated_cookie
                        cookie_applied = True
            if self._on_cookie and cookie_applied and updated_cookie:
                await self._on_cookie(self.account.account_id, expected_cookie, updated_cookie)
            blocked = bool(result.get("isInBlack")) if action == "query" else action == "add"
            return PlatformBlacklistResult(
                success=True,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                blocked=blocked,
                raw_payload=result,
            )
        except Exception as exc:
            if self._on_cookie and cookie_applied and updated_cookie:
                await self._on_cookie(self.account.account_id, expected_cookie, updated_cookie)
            return PlatformBlacklistResult(
                success=False,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                error=str(exc),
            )

    def _platform_blacklist_sync(
        self,
        conversation_id: str,
        action: str,
    ) -> dict[str, Any]:
        if action not in PLATFORM_BLACKLIST_APIS:
            raise ValueError("unsupported platform blacklist action")
        api, version = PLATFORM_BLACKLIST_APIS[action]
        data = json.dumps(
            {"sessionId": self._strip_goofish(conversation_id)},
            separators=(",", ":"),
        )
        last_error = "platform blacklist request failed"
        for attempt in range(2):
            timestamp = str(int(time.time() * 1000))
            cookies = self.upstream.trans_cookies(
                self.upstream.get_session_cookies_str(self.xianyu.session)
            )
            token = cookies.get("_m_h5_tk", "").split("_", 1)[0]
            if not token:
                raise RuntimeError("cookie is missing _m_h5_tk for platform blacklist request")
            params = {
                "jsv": "2.7.2",
                "appKey": "34839810",
                "t": timestamp,
                "sign": self.upstream.generate_sign(timestamp, token, data),
                "v": version,
                "type": "originaljson",
                "accountSite": "xianyu",
                "dataType": "json",
                "timeout": "20000",
                "api": api,
                "sessionOption": "AutoLoginOnly",
            }
            response = self.xianyu.session.post(
                f"https://h5api.m.goofish.com/h5/{api}/{version}/",
                params=params,
                data={"data": data},
                headers={
                    "Accept": "application/json",
                    "Origin": "https://www.goofish.com",
                    "Referer": "https://www.goofish.com/",
                    "User-Agent": self.client_identity.user_agent,
                },
                timeout=20,
            )
            response.raise_for_status()
            response_cookie_values = response.cookies.get_dict()
            if isinstance(response_cookie_values, dict):
                response_cookie_names = set(response_cookie_values)
                for cookie in tuple(self.xianyu.session.cookies):
                    if (
                        cookie.name in response_cookie_names
                        and cookie.domain == ""
                        and cookie.path == "/"
                    ):
                        self.xianyu.session.cookies.clear(
                            domain=cookie.domain,
                            path=cookie.path,
                            name=cookie.name,
                        )
            payload = response.json()
            entries = payload.get("ret") if isinstance(payload, dict) else None
            entries = entries if isinstance(entries, list) else [entries] if entries else []
            if any("SUCCESS" in str(entry).upper() for entry in entries):
                result = payload.get("data") if isinstance(payload, dict) else None
                return result if isinstance(result, dict) else {}
            last_error = str(entries[0] if entries else last_error)
            token_expired = any(
                "TOKEN_EX" in str(entry).upper() or "TOKEN_EXO" in str(entry).upper()
                for entry in entries
            )
            if not token_expired or attempt > 0:
                break
        if "FAIL_SYS_SESSION_EXPIRED" in last_error.upper() or "Session过期" in last_error:
            raise AuthenticationExpiredError(last_error)
        raise RuntimeError(last_error)

    async def _send_custom_message(
        self,
        conversation_id: str,
        receiver_user_id: str,
        payload: dict[str, Any],
    ) -> SendMessageResult:
        if self.websocket is None or not self._online_event.is_set():
            return SendMessageResult(
                success=False,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                error="websocket is not online",
            )

        message_id = self.upstream.generate_mid()
        encoded_payload = base64.b64encode(
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")
        frame = {
            "lwp": "/r/MessageSend/sendByReceiverScope",
            "headers": {
                "mid": message_id,
            },
            "body": [
                {
                    "uuid": self.upstream.generate_uuid(),
                    "cid": f"{conversation_id}@goofish",
                    "conversationType": 1,
                    "content": {
                        "contentType": 101,
                        "custom": {
                            "type": 1,
                            "data": encoded_payload,
                        },
                    },
                    "redPointPolicy": 0,
                    "extension": {
                        "extJson": "{}",
                    },
                    "ctx": {
                        "appVersion": "1.0",
                        "platform": "web",
                    },
                    "mtags": {},
                    "msgReadStatusSetting": 1,
                },
                {
                    "actualReceivers": [
                        f"{receiver_user_id}@goofish",
                        f"{self.myid}@goofish",
                    ],
                },
            ],
        }

        try:
            response = await self._send_and_wait(frame, timeout=10)
            code = response.get("code", 200 if "body" in response else None)
            success = str(code) == "200"
            platform_message_id = self._extract_response_message_id(response) or message_id
            return SendMessageResult(
                success=success,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                message_id=platform_message_id,
                error=None if success else self._response_error(response),
                raw_payload={"request": frame, "response": response},
            )
        except TimeoutError:
            return SendMessageResult(
                success=False,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error="timed out waiting for platform acknowledgement",
                raw_payload={"request": frame},
            )
        except Exception as exc:
            return SendMessageResult(
                success=False,
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                message_id=message_id,
                error=str(exc),
                raw_payload={"request": frame},
            )

    async def _upload_image(self, prepared: PreparedImage) -> UploadedImage:
        async with self._credential_lock:
            expected_cookie = self.account.cookie
            image_url = await self._media_runner(self._upload_image_sync, prepared)
            updated_cookie = self.upstream.get_session_cookies_str(self.xianyu.session)
            if updated_cookie and updated_cookie != expected_cookie:
                updated_cookies = self.upstream.trans_cookies(updated_cookie)
                if updated_cookies.get("unb") == self.myid:
                    self.cookies = updated_cookies
                    self.account.cookie = updated_cookie

        if self._on_cookie and updated_cookie and updated_cookie != expected_cookie:
            await self._on_cookie(self.account.account_id, expected_cookie, updated_cookie)
        return UploadedImage(
            url=image_url,
            width=prepared.width,
            height=prepared.height,
            mime_type=prepared.mime_type,
            size_bytes=prepared.size_bytes,
            sha256=prepared.sha256,
        )

    def _upload_image_sync(self, prepared: PreparedImage) -> str:
        response: requests.Response | None = None
        for attempt in range(3):
            try:
                response = self.xianyu.session.post(
                    IMAGE_UPLOAD_URL,
                    params={
                        "floderId": "0",
                        "appkey": "xy_chat",
                        "_input_charset": "utf-8",
                    },
                    files={
                        "file": (
                            prepared.filename,
                            prepared.data,
                            prepared.mime_type,
                        )
                    },
                    headers={
                        "accept": "application/json, text/javascript, */*; q=0.01",
                        "origin": "https://www.goofish.com",
                        "referer": "https://www.goofish.com/",
                        "user-agent": self.client_identity.user_agent,
                        "x-requested-with": "XMLHttpRequest",
                    },
                    timeout=30,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                break
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
                if attempt == 2:
                    raise ImageUploadError("图片上传网络连接失败，请稍后重试") from exc
                time.sleep(0.5 * (2**attempt))
        if response is None:
            raise ImageUploadError("图片上传网络连接失败，请稍后重试")
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise ImageUploadError(
                f"图片上传被平台拒绝 (HTTP {response.status_code})"
            ) from exc
        response_text = response.text
        if "<html" in response_text.lower() or "<!doctype" in response_text.lower():
            raise ImageUploadError("图片上传认证失败，请先续期或重新登录")
        try:
            payload = response.json()
        except Exception as exc:
            raise ImageUploadError("图片上传返回了无法识别的数据") from exc
        image_url = self._extract_image_url(payload)
        if not image_url:
            raise ImageUploadError("图片上传响应中没有媒体地址")
        return image_url

    @classmethod
    def _extract_image_url(cls, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        candidates: list[Any] = [payload]
        for key in ("data", "object", "result"):
            value = payload.get(key)
            if isinstance(value, dict):
                candidates.append(value)
        for candidate in candidates:
            for key in ("url", "fileUrl", "file_url"):
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    url = value.strip()
                    if url.startswith("//"):
                        url = f"https:{url}"
                    if url.startswith(("https://", "http://")):
                        return url
        return None

    async def list_conversations(
        self, cursor: int | None = None, limit: int = 20
    ) -> ConversationPage:
        bounded_limit = max(1, min(limit, 100))
        start_cursor = cursor if cursor is not None else MAX_CURSOR
        last_body: dict[str, Any] = {}
        for attempt in range(3):
            mid = self.upstream.generate_mid()
            response = await self._send_and_wait(
                {
                    "lwp": "/r/Conversation/listNewestPagination",
                    "headers": {"mid": mid},
                    "body": [start_cursor, bounded_limit],
                }
            )
            last_body = response.get("body") if isinstance(response.get("body"), dict) else {}
            if str(last_body.get("code") or "") != "400600001":
                break
            await asyncio.sleep((attempt + 1) * 2)
        if "reason" in last_body:
            raise RuntimeError(str(last_body.get("reason") or last_body.get("code") or "IM error"))
        items = [
            parsed
            for raw in last_body.get("userConvs", [])
            if isinstance(raw, dict)
            and (parsed := self._parse_conversation_summary(raw)) is not None
        ]
        return ConversationPage(
            items=items,
            has_more=self._as_bool(last_body.get("hasMore")),
            next_cursor=self._as_int(last_body.get("nextCursor")),
        )

    async def list_messages(
        self,
        conversation_id: str,
        cursor: int | None = None,
        limit: int = 20,
    ) -> MessagePage:
        bounded_limit = max(1, min(limit, 100))
        body: dict[str, Any] = {}
        for attempt in range(3):
            mid = self.upstream.generate_mid()
            response = await self._send_and_wait(
                {
                    "lwp": "/r/MessageManager/listUserMessages",
                    "headers": {"mid": mid},
                    "body": [
                        self._with_goofish_suffix(conversation_id),
                        False,
                        cursor if cursor is not None else MAX_CURSOR,
                        bounded_limit,
                        False,
                    ],
                }
            )
            body = response.get("body") if isinstance(response.get("body"), dict) else {}
            if str(body.get("code") or "") != "400600001":
                break
            await asyncio.sleep((attempt + 1) * 2)
        if "reason" in body:
            raise RuntimeError(str(body.get("reason") or body.get("code") or "IM error"))
        items = [
            parsed
            for raw in body.get("userMessageModels", [])
            if isinstance(raw, dict)
            and (parsed := self._parse_history_message(raw, conversation_id)) is not None
        ]
        items.reverse()
        return MessagePage(
            items=items,
            has_more=self._as_bool(body.get("hasMore")),
            next_cursor=self._as_int(body.get("nextCursor")),
        )

    async def get_order_headinfo(
        self,
        item_id: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        async with self._credential_lock:
            expected_cookie = self.account.cookie
            result = await self._platform_runner(
                self._get_order_headinfo_sync,
                item_id,
                conversation_id,
            )
            updated_cookie = self.upstream.get_session_cookies_str(self.xianyu.session)
            if updated_cookie and updated_cookie != expected_cookie:
                updated_cookies = self.upstream.trans_cookies(updated_cookie)
                if updated_cookies.get("unb") == self.myid:
                    self.cookies = updated_cookies
                    self.account.cookie = updated_cookie
        if self._on_cookie and updated_cookie and updated_cookie != expected_cookie:
            await self._on_cookie(self.account.account_id, expected_cookie, updated_cookie)
        return result

    async def get_account_identity(self) -> dict[str, str | None]:
        result = await self._run_identity_query(self._get_account_identity_sync)
        return {
            "platform_user_id": self.myid,
            "display_name": self._first_string(
                result.get("displayName"),
                result.get("fishNick"),
                result.get("nick"),
            ),
            "avatar_url": self._normalize_media_url(
                self._first_string(
                    result.get("avatar"),
                    result.get("logo"),
                    result.get("avatarUrl"),
                )
            ),
        }

    async def get_user_profile(
        self,
        conversation_id: str,
        *,
        is_owner: bool = False,
    ) -> dict[str, str | None]:
        result = await self._run_identity_query(
            self._get_user_profile_sync,
            conversation_id,
            is_owner,
        )
        return {
            "display_name": self._first_string(
                result.get("fishNick"),
                result.get("displayName"),
                result.get("nick"),
            ),
            "avatar_url": self._normalize_media_url(
                self._first_string(
                    result.get("logo"),
                    result.get("avatar"),
                    result.get("avatarUrl"),
                )
            ),
        }

    async def _run_identity_query(
        self,
        query: Callable[..., dict[str, Any]],
        *args: Any,
    ) -> dict[str, Any]:
        expected_cookie = self.account.cookie
        updated_cookie: str | None = None
        cookie_applied = False
        async with self._credential_lock:
            try:
                result = await self._platform_runner(query, *args)
            finally:
                updated_cookie = self.upstream.get_session_cookies_str(self.xianyu.session)
            if updated_cookie and updated_cookie != expected_cookie:
                updated_cookies = self.upstream.trans_cookies(updated_cookie)
                if updated_cookies.get("unb") == self.myid:
                    self.cookies = updated_cookies
                    self.account.cookie = updated_cookie
                    cookie_applied = True
        if self._on_cookie and cookie_applied and updated_cookie:
            await self._on_cookie(self.account.account_id, expected_cookie, updated_cookie)
        return result

    def _get_account_identity_sync(self) -> dict[str, Any]:
        data = self._signed_mtop_query_sync(
            "mtop.idle.web.user.page.nav",
            "1.0",
            {},
        )
        module = data.get("module") if isinstance(data.get("module"), dict) else {}
        base = module.get("base") if isinstance(module.get("base"), dict) else {}
        return base

    def _get_user_profile_sync(
        self,
        conversation_id: str,
        is_owner: bool,
    ) -> dict[str, Any]:
        data = self._signed_mtop_query_sync(
            "mtop.taobao.idlemessage.pc.user.query",
            "4.0",
            {
                "type": 0,
                "sessionType": 1,
                "sessionId": self._strip_goofish(conversation_id),
                "isOwner": bool(is_owner),
            },
        )
        user_info = data.get("userInfo") if isinstance(data.get("userInfo"), dict) else {}
        return user_info

    def _signed_mtop_query_sync(
        self,
        api: str,
        version: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        last_error = f"{api} request failed"
        for attempt in range(2):
            timestamp = str(int(time.time() * 1000))
            cookies = self.upstream.trans_cookies(
                self.upstream.get_session_cookies_str(self.xianyu.session)
            )
            token = cookies.get("_m_h5_tk", "").split("_", 1)[0]
            if not token:
                raise RuntimeError(f"cookie is missing _m_h5_tk for {api}")
            response = self.xianyu.session.post(
                f"https://h5api.m.goofish.com/h5/{api}/{version}/",
                params={
                    "jsv": "2.7.2",
                    "appKey": "34839810",
                    "t": timestamp,
                    "sign": self.upstream.generate_sign(timestamp, token, data),
                    "v": version,
                    "type": "originaljson",
                    "accountSite": "xianyu",
                    "dataType": "json",
                    "timeout": "20000",
                    "api": api,
                    "sessionOption": "AutoLoginOnly",
                },
                data={"data": data},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://www.goofish.com",
                    "Referer": "https://www.goofish.com/",
                    "User-Agent": self.client_identity.user_agent,
                },
                timeout=20,
            )
            response.raise_for_status()
            response_cookie_values = response.cookies.get_dict()
            if isinstance(response_cookie_values, dict):
                response_cookie_names = set(response_cookie_values)
                for cookie in tuple(self.xianyu.session.cookies):
                    if (
                        cookie.name in response_cookie_names
                        and cookie.domain == ""
                        and cookie.path == "/"
                    ):
                        self.xianyu.session.cookies.clear(
                            domain=cookie.domain,
                            path=cookie.path,
                            name=cookie.name,
                        )
            response_payload = response.json()
            entries = (
                response_payload.get("ret")
                if isinstance(response_payload, dict)
                else None
            )
            entries = entries if isinstance(entries, list) else [entries] if entries else []
            if any("SUCCESS" in str(entry).upper() for entry in entries):
                result = response_payload.get("data")
                return result if isinstance(result, dict) else {}
            last_error = str(entries[0] if entries else last_error)
            token_expired = any(
                "TOKEN_EX" in str(entry).upper() or "TOKEN_EXO" in str(entry).upper()
                for entry in entries
            )
            if not token_expired or attempt > 0:
                break
        if "FAIL_SYS_SESSION_EXPIRED" in last_error.upper() or "Session过期" in last_error:
            raise AuthenticationExpiredError(last_error)
        raise RuntimeError(last_error)

    @staticmethod
    def _first_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _normalize_media_url(value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("//"):
            return f"https:{value}"
        if value.startswith("http://"):
            return f"https://{value[7:]}"
        return value

    def _get_order_headinfo_sync(
        self,
        item_id: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        api = "mtop.idle.trade.pc.message.headinfo"
        timestamp = str(int(time.time() * 1000))
        data_value = json.dumps(
            {"itemId": str(item_id), "sessionId": int(conversation_id)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        token_cookie = self.xianyu.session.cookies.get("_m_h5_tk")
        if not token_cookie:
            raise RuntimeError("order query requires _m_h5_tk cookie")
        params = {
            "jsv": "2.7.2",
            "appKey": "34839810",
            "t": timestamp,
            "sign": self.upstream.generate_sign(
                timestamp, str(token_cookie).split("_")[0], data_value
            ),
            "v": "1.0",
            "type": "originaljson",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": api,
            "sessionOption": "AutoLoginOnly",
        }
        response = self.xianyu.session.post(
            f"https://h5api.m.goofish.com/h5/{api}/1.0/",
            params=params,
            data={"data": data_value},
            headers={
                "accept": "application/json",
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://www.goofish.com",
                "referer": "https://www.goofish.com/",
                "user-agent": self.client_identity.user_agent,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        ret = payload.get("ret") if isinstance(payload, dict) else None
        if not isinstance(payload, dict) or not ret or not str(ret[0]).startswith("SUCCESS"):
            error_text = str(ret or "invalid response")
            if "FAIL_SYS_SESSION_EXPIRED" in error_text.upper() or "Session过期" in error_text:
                raise AuthenticationExpiredError(error_text)
            raise RuntimeError(f"order query rejected: {ret or 'invalid response'}")
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    async def refresh_token(self) -> None:
        async with self._credential_lock:
            expected_cookie = self.account.cookie
            response = await self._platform_runner(self.xianyu.refresh_token)
            self._validate_refresh_response(response)
            new_cookie = self.upstream.get_session_cookies_str(self.xianyu.session)
            if not new_cookie:
                raise RuntimeError("token refresh returned an empty cookie jar")
            new_cookies = self.upstream.trans_cookies(new_cookie)
            if new_cookies.get("unb") != self.myid:
                raise RuntimeError("token refresh returned a different account")
            self.cookies = new_cookies
            self.account.cookie = new_cookie

        if self._on_cookie and new_cookie != expected_cookie:
            await self._on_cookie(self.account.account_id, expected_cookie, new_cookie)

    async def replace_cookie(self, cookie: str) -> None:
        new_cookies = self.upstream.trans_cookies(cookie)
        if new_cookies.get("unb") != self.myid:
            raise ValueError("replacement cookie belongs to a different account")
        if not new_cookies.get("_m_h5_tk"):
            raise ValueError("replacement cookie is missing _m_h5_tk")

        async with self._credential_lock:
            replacement = self.upstream.XianyuApis(new_cookies, self.device_id)
            replacement.session.trust_env = False
            _apply_identity_headers(replacement.session, self.client_identity)
            if self.proxy_url:
                replacement.session.proxies.update(
                    {"http": self.proxy_url, "https": self.proxy_url}
                )
            previous = self.xianyu
            self.xianyu = replacement
            self.cookies = new_cookies
            self.account.cookie = cookie
            self._credential_changed_event.set()
            with suppress(Exception):
                previous.session.close()

    async def _run(self) -> None:
        attempt = 0
        retry_delay = 1.0
        while not self._stop_event.is_set():
            next_delay = retry_delay
            terminal_error = False
            try:
                state = ConnectionState.CONNECTING if attempt == 0 else ConnectionState.RECONNECTING
                await self._emit_state(state, None if attempt == 0 else f"retry attempt {attempt}")
                headers = self._build_ws_headers()
                async with self._connect(headers) as websocket:
                    self.websocket = websocket
                    self._push_task = asyncio.create_task(
                        self._push_loop(),
                        name=f"xianyu-push:{self.account.account_id}",
                    )
                    self._receiver_task = asyncio.create_task(
                        self._receiver_loop(websocket),
                        name=f"xianyu-recv:{self.account.account_id}",
                    )
                    await self._init_session()
                    self._heartbeat_task = asyncio.create_task(
                        self._heartbeat_loop(),
                        name=f"xianyu-heartbeat:{self.account.account_id}",
                    )
                    if self.token_refresh_interval > 0:
                        self._token_task = asyncio.create_task(
                            self._token_refresh_loop(),
                            name=f"xianyu-token:{self.account.account_id}",
                        )
                    self._connection_count += 1
                    if self._connection_count > 1:
                        self._reconnect_count += 1
                    self._connected_at_ms = int(time.time() * 1000)
                    self._last_heartbeat_at_ms = self._connected_at_ms
                    self._last_disconnect_reason = None
                    self._online_event.set()
                    await self._emit_state(ConnectionState.ONLINE, None)
                    attempt = 0
                    retry_delay = 1.0

                    monitored = {self._receiver_task, self._heartbeat_task, self._push_task}
                    if self._token_task is not None:
                        monitored.add(self._token_task)
                    done, _ = await asyncio.wait(
                        monitored,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not self._stop_event.is_set():
                        for completed in done:
                            exception = completed.exception()
                            if exception is not None:
                                raise exception
                        names = ", ".join(task.get_name() for task in done)
                        raise ConnectionError(f"connection task stopped unexpectedly: {names}")
            except asyncio.CancelledError:
                raise
            except RiskControlError as exc:
                self._last_disconnect_reason = str(exc)
                if self._on_verification is not None:
                    await self._on_verification(exc.verification)
                await self._emit_state(ConnectionState.RISK_BLOCKED, str(exc))
                terminal_error = True
            except AuthenticationExpiredError as exc:
                self._last_disconnect_reason = str(exc)
                await self._emit_state(ConnectionState.AUTH_EXPIRED, str(exc))
                terminal_error = True
            except Exception as exc:
                self._last_disconnect_reason = str(exc)
                await self._emit_state(self._classify_connection_error(exc), str(exc))
            finally:
                await self._cleanup_connection("websocket connection lost")

            if self._stop_event.is_set() or terminal_error:
                break
            attempt += 1
            if next_delay < 900:
                await self._emit_state(ConnectionState.RECONNECTING, f"retrying in {next_delay:g}s")
            credentials_changed = False
            try:
                await asyncio.wait_for(self._credential_changed_event.wait(), timeout=next_delay)
                self._credential_changed_event.clear()
                credentials_changed = True
            except TimeoutError:
                pass
            retry_delay = (
                1.0
                if credentials_changed
                else min(retry_delay * 2, 60.0) if next_delay < 900 else 60.0
            )

    async def _receiver_loop(self, websocket: Any) -> None:
        async for raw_message in websocket:
            if self._stop_event.is_set():
                break
            await self._handle_raw_message(raw_message)

    async def _push_loop(self) -> None:
        workers = [
            asyncio.create_task(
                self._push_worker_loop(),
                name=f"xianyu-push-worker:{self.account.account_id}:{index}",
            )
            for index in range(PUSH_WORKER_COUNT)
        ]
        try:
            await asyncio.gather(*workers)
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    async def _push_worker_loop(self) -> None:
        while not self._stop_event.is_set():
            frame = await self._push_queue.get()
            self._push_inflight += 1
            try:
                await self._process_push_frame(frame)
            finally:
                self._push_inflight = max(0, self._push_inflight - 1)
                self._push_queue.task_done()

    def _connect(self, headers: dict[str, str]):
        try:
            import websockets
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "missing dependency: websockets. Install integrations/xianyu_core/requirements.txt"
            ) from exc

        connect = websockets.connect
        signature = inspect.signature(connect)
        kwargs: dict[str, Any] = {}
        kwargs.update(
            {
                "ping_interval": 20,
                "ping_timeout": 15,
                "open_timeout": 30,
                "close_timeout": 5,
            }
        )
        if "additional_headers" in signature.parameters:
            kwargs["additional_headers"] = headers
        elif "extra_headers" in signature.parameters:
            kwargs["extra_headers"] = headers
        else:
            raise RuntimeError("unsupported websockets.connect signature: no headers parameter")

        if self.proxy_url:
            if "proxy" not in signature.parameters:
                raise RuntimeError(
                    "installed websockets version doesn't support explicit proxy=. "
                    "Use websockets>=16 or implement python-socks socket injection."
                )
            kwargs["proxy"] = self.proxy_url
        elif "proxy" in signature.parameters:
            kwargs["proxy"] = None

        return connect(self.ws_url, **kwargs)

    def _build_ws_headers(self) -> dict[str, str]:
        return {
            "Cookie": self.upstream.get_session_cookies_str(self.xianyu.session),
            "Host": "wss-goofish.dingtalk.com",
            "Connection": "Upgrade",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": self.client_identity.user_agent,
            "Origin": "https://www.goofish.com",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": self.client_identity.accept_language,
        }

    async def _init_session(self) -> None:
        token = await self._get_im_token()

        reg_frame = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": "444e9908a51d1cb236a27862abc769c9",
                "token": token,
                "ua": self.client_identity.dingtalk_user_agent,
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": self.device_id,
                "mid": self.upstream.generate_mid(),
            },
        }
        reg_response = await self._send_and_wait(reg_frame, timeout=8)
        reg_code = reg_response.get("code", 200 if "body" in reg_response else None)
        if str(reg_code) != "200":
            await self._invalidate_im_token()
            raise RuntimeError(f"IM registration rejected: {self._response_error(reg_response)}")

        now_ms = int(time.time() * 1000)
        ack_diff_frame = {
            "lwp": "/r/SyncStatus/ackDiff",
            "headers": {
                "mid": self.upstream.generate_mid(),
            },
            "body": [
                {
                    "pipeline": "sync",
                    "tooLong2Tag": "PNM,1",
                    "channel": "sync",
                    "topic": "sync",
                    "highPts": 0,
                    "pts": now_ms * 1000,
                    "seq": 0,
                    "timestamp": now_ms,
                }
            ],
        }
        await self._send_frame(ack_diff_frame)
        await asyncio.sleep(3)

    async def _get_im_token(self) -> str:
        async with self._credential_lock:
            return await self._get_im_token_locked()

    async def _get_im_token_locked(self) -> str:
        now_ms = int(time.time() * 1000)
        if self._im_token and (self._im_token_expires_at_ms or 0) > now_ms + 60_000:
            return self._im_token
        if self._im_token:
            await self._invalidate_im_token()
        token_response = await self._platform_runner(self.xianyu.get_token)
        expected_cookie = self.account.cookie
        updated_cookie = self.upstream.get_session_cookies_str(self.xianyu.session)
        if updated_cookie and updated_cookie != expected_cookie:
            updated_cookies = self.upstream.trans_cookies(updated_cookie)
            if updated_cookies.get("unb") == self.myid:
                self.cookies = updated_cookies
                self.account.cookie = updated_cookie
                if self._on_cookie:
                    await self._on_cookie(
                        self.account.account_id,
                        expected_cookie,
                        updated_cookie,
                    )
        token = (
            token_response.get("data", {}).get("accessToken")
            if isinstance(token_response, dict)
            else None
        )
        if token:
            self._im_token = str(token)
            self._im_token_expires_at_ms = int(time.time() * 1000) + 4 * 60 * 60 * 1000
            if self._on_im_token:
                await self._on_im_token(
                    self.account.account_id,
                    self._im_token,
                    self._im_token_expires_at_ms,
                )
            return self._im_token
        response_text = json.dumps(token_response, ensure_ascii=False)
        response_lower = response_text.lower()
        response_data = token_response.get("data") if isinstance(token_response, dict) else None
        verification_url = (
            str(response_data.get("url") or "").strip()
            if isinstance(response_data, dict)
            else ""
        )
        ret_values = token_response.get("ret") if isinstance(token_response, dict) else None
        if isinstance(ret_values, list):
            ret_text = " ".join(str(value) for value in ret_values)
        elif ret_values is None:
            ret_text = ""
        else:
            ret_text = str(ret_values)
        if any(
            marker in response_lower
            for marker in ("fail_sys_user_validate", "rgv587_error", "punish", "captcha")
        ):
            reason_code = next(
                (
                    marker
                    for marker in ("FAIL_SYS_USER_VALIDATE", "RGV587_ERROR")
                    if marker in ret_text
                ),
                "INTERACTIVE_VERIFICATION_REQUIRED",
            )
            raise RiskControlError(
                InteractiveVerification(
                    account_id=self.account.account_id,
                    reason_code=reason_code,
                    verification_url=verification_url or None,
                    detected_at_ms=int(time.time() * 1000),
                )
            )
        if "FAIL_SYS_SESSION_EXPIRED" in response_text or "Session过期" in response_text:
            raise AuthenticationExpiredError("闲鱼登录会话已过期，请重新扫码登录")
        raise RuntimeError(f"failed to get IM access token: {response_text[:500]}")

    async def _invalidate_im_token(self) -> None:
        self._im_token = None
        self._im_token_expires_at_ms = None
        if self._on_im_token:
            await self._on_im_token(self.account.account_id, "", 0)

    async def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set() and self.websocket is not None:
            await asyncio.wait_for(
                self._send_frame(
                    {"lwp": "/!", "headers": {"mid": self.upstream.generate_mid()}}
                ),
                timeout=2,
            )
            self._last_heartbeat_at_ms = int(time.time() * 1000)
            await asyncio.sleep(self.heartbeat_interval)

    async def _token_refresh_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self.token_refresh_interval)
            if self._stop_event.is_set():
                break
            try:
                await self.refresh_token()
                if self._token_refresh_failed:
                    self._token_refresh_failed = False
                    await self._emit_state(ConnectionState.ONLINE, "令牌刷新已恢复")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._token_refresh_failed = True
                await self._emit_state(self._classify_connection_error(exc), str(exc))

    @staticmethod
    def _validate_refresh_response(response: Any) -> None:
        if not isinstance(response, dict):
            raise RuntimeError("token refresh returned an invalid response")
        ret = response.get("ret")
        entries = ret if isinstance(ret, list) else [ret] if ret else []
        if entries and not any(str(entry).upper().startswith("SUCCESS") for entry in entries):
            detail = str(entries[0])[:200]
            raise RuntimeError(f"token refresh rejected: {detail}")

    async def _send_frame(self, frame: dict[str, Any]) -> None:
        if self.websocket is None:
            raise RuntimeError("websocket is not connected")
        await self.websocket.send(json.dumps(frame, ensure_ascii=False))

    async def _send_and_wait(
        self, frame: dict[str, Any], timeout: float = 15
    ) -> dict[str, Any]:
        headers = frame.setdefault("headers", {})
        mid = str(headers.get("mid") or self.upstream.generate_mid())
        headers["mid"] = mid
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        async with self._rpc_lock:
            throttle_delay = 0.35 - (time.monotonic() - self._last_rpc_at)
            if throttle_delay > 0:
                await asyncio.sleep(throttle_delay)
            self._pending_requests[mid] = future
            started = time.monotonic()
            try:
                await self._send_frame(frame)
                response = await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
                self._last_rpc_success_at_ms = int(time.time() * 1000)
                self._last_rpc_latency_ms = max(0, int((time.monotonic() - started) * 1000))
                self._last_rpc_error = None
                self._consecutive_rpc_failures = 0
                return response
            except TimeoutError as exc:
                error = f"IM request timed out: {frame.get('lwp', 'unknown')}"
                self._last_rpc_error = error
                self._consecutive_rpc_failures += 1
                raise TimeoutError(error) from exc
            except Exception as exc:
                self._last_rpc_error = str(exc)[:300]
                self._consecutive_rpc_failures += 1
                raise
            finally:
                self._pending_requests.pop(mid, None)
                self._last_rpc_at = time.monotonic()

    async def _handle_raw_message(self, raw_message: Any) -> None:
        try:
            frame = json.loads(raw_message)
        except Exception:
            return

        self._last_server_frame_at_ms = int(time.time() * 1000)
        await self._send_ack(frame)
        if self._resolve_pending_response(frame):
            return
        if not self._on_message:
            return
        if self._push_task is None or self._push_task.done():
            await self._process_push_frame(frame)
            return
        if self._push_queue.full():
            try:
                self._push_queue.get_nowait()
                self._push_queue.task_done()
                self._push_queue_dropped += 1
            except asyncio.QueueEmpty:
                pass
            logger.warning(
                "Xianyu push queue overflow for account=%s dropped=%s",
                self.account.account_id,
                self._push_queue_dropped,
            )
        self._push_queue.put_nowait(frame)

    async def _process_push_frame(self, frame: dict[str, Any]) -> None:
        if not self._on_message:
            return
        task = asyncio.current_task()
        task_key = task.get_name() if task else str(id(frame))
        self._active_pushes[task_key] = self._push_frame_summary(frame)
        loop = asyncio.get_running_loop()
        try:
            events = await loop.run_in_executor(
                _PROTOCOL_EXECUTOR,
                self._parse_chat_events,
                frame,
            )
            for event in events:
                try:
                    await self._on_message(event)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Xianyu message callback failed for account=%s conversation=%s",
                        event.account_id,
                        event.conversation_id,
                    )
        finally:
            self._active_pushes.pop(task_key, None)

    @staticmethod
    def _push_frame_summary(frame: dict[str, Any]) -> str:
        body = frame.get("body")
        package = body.get("syncPushPackage") if isinstance(body, dict) else None
        entries = package.get("data", []) if isinstance(package, dict) else []
        parts: list[str] = []
        for entry in entries[:8]:
            data = entry.get("data") if isinstance(entry, dict) else None
            if isinstance(data, str):
                parts.append(f"{data[:8]}:{len(data)}")
            elif isinstance(data, dict):
                parts.append("json")
            else:
                parts.append(type(data).__name__)
        return f"entries={len(entries)}[{','.join(parts)}]"

    def _resolve_pending_response(self, frame: dict[str, Any]) -> bool:
        headers = frame.get("headers")
        message_id = headers.get("mid") if isinstance(headers, dict) else None
        future = self._pending_requests.get(str(message_id)) if message_id else None
        if future is None:
            return False
        if not future.done():
            future.set_result(frame)
        return True

    @staticmethod
    def _response_error(frame: dict[str, Any]) -> str:
        for key in ("message", "msg", "error"):
            value = frame.get(key)
            if value:
                return str(value)
        body = frame.get("body")
        if isinstance(body, dict):
            for key in ("reason", "developerMessage", "message", "code"):
                value = body.get(key)
                if value:
                    return str(value)
        return f"platform rejected message with code {frame.get('code')!r}"

    async def _cleanup_connection(self, error: str) -> None:
        self._online_event.clear()
        self._connected_at_ms = None
        for task in (
            self._heartbeat_task,
            self._token_task,
            self._receiver_task,
            self._push_task,
        ):
            if task is asyncio.current_task():
                continue
            if task and not task.done():
                task.cancel()
        for task in (
            self._heartbeat_task,
            self._token_task,
            self._receiver_task,
            self._push_task,
        ):
            if task is asyncio.current_task():
                continue
            if task:
                with suppress(asyncio.CancelledError, Exception):
                    await task
        self._heartbeat_task = None
        self._token_task = None
        self._receiver_task = None
        self._push_task = None
        while not self._push_queue.empty():
            try:
                self._push_queue.get_nowait()
                self._push_queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.websocket = None
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(ConnectionError(error))
        self._pending_requests.clear()

    def _classify_connection_error(self, exc: Exception) -> ConnectionState:
        message = str(exc).lower()
        if self.proxy_url and any(
            marker in message for marker in ("proxy", "socks", "tunnel", "connection refused")
        ):
            return ConnectionState.PROXY_FAILED
        if isinstance(exc, AuthenticationExpiredError) or any(
            marker in message
            for marker in (
                "fail_sys_session_expired",
                "session过期",
                "cookie is missing required field",
                "different account",
            )
        ):
            return ConnectionState.AUTH_EXPIRED
        return ConnectionState.OFFLINE if self._online_event.is_set() else ConnectionState.ERROR

    async def _send_ack(self, frame: dict[str, Any]) -> None:
        headers = frame.get("headers") or {}
        ack_headers = {
            "mid": headers.get("mid") or self.upstream.generate_mid(),
            "sid": headers.get("sid") or "",
        }
        for key in ("app-key", "ua", "dt"):
            if key in headers:
                ack_headers[key] = headers[key]
        await self._send_frame({"code": 200, "headers": ack_headers})

    def _parse_chat_events(self, frame: dict[str, Any]) -> list[ChatMessageEvent]:
        events: list[ChatMessageEvent] = []
        for payload in self._extract_sync_payloads(frame):
            event = self._parse_push_payload(payload)
            if event is not None:
                events.append(event)
        return events

    def _parse_chat_event(self, frame: dict[str, Any]) -> ChatMessageEvent | None:
        """Compatibility helper for callers that expect one push event."""

        events = self._parse_chat_events(frame)
        return events[0] if events else None

    def _parse_push_payload(self, payload: dict[str, Any]) -> ChatMessageEvent | None:
        message_node = payload.get("1")
        if isinstance(message_node, dict):
            conversation_id = self._strip_goofish(message_node.get("2"))
            if not conversation_id:
                return None
            meta = message_node.get("10")
            meta = meta if isinstance(meta, dict) else {}
            sender_id = self._strip_goofish(meta.get("senderUserId"))
            direction = Direction.OUTBOUND if sender_id == self.myid else Direction.INBOUND
            content_type, content = self._parse_push_content(message_node, meta)
            peer_id = sender_id if direction == Direction.INBOUND else self._strip_goofish(
                meta.get("receiverUserId") or meta.get("receiverId")
            )
            peer_name = (
                extract_peer_name(meta, peer_user_id=peer_id)
                if direction == Direction.INBOUND
                else None
            )
            return ChatMessageEvent(
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                message_id=self._extract_push_message_id(message_node, meta),
                peer_user_id=peer_id or None,
                peer_name=peer_name,
                direction=direction,
                message_type=content_type,
                content=content,
                raw_payload=payload,
                item_id=self._extract_item_id(payload),
                created_at_ms=self._extract_created_at_ms(message_node),
                attachments=self._parse_push_attachments(message_node),
            )

        meta = payload.get("4")
        if isinstance(message_node, str) and isinstance(meta, dict):
            conversation_id = self._strip_goofish(payload.get("2"))
            if not conversation_id:
                return None
            sender_id = self._strip_goofish(meta.get("senderUserId"))
            direction = Direction.OUTBOUND if sender_id == self.myid else Direction.INBOUND
            content = str(meta.get("reminderContent") or "[系统消息]")
            return ChatMessageEvent(
                account_id=self.account.account_id,
                conversation_id=conversation_id,
                message_id=str(payload.get("3") or self._message_id_from_meta(meta) or "") or None,
                peer_user_id=sender_id if direction == Direction.INBOUND else None,
                peer_name=(
                    extract_peer_name(meta, peer_user_id=sender_id)
                    if direction == Direction.INBOUND
                    else None
                ),
                direction=direction,
                message_type=MessageType.SYSTEM,
                content=content,
                raw_payload=payload,
                item_id=self._extract_item_id(payload),
                created_at_ms=self._extract_created_at_ms(payload),
            )
        return None

    def _parse_conversation_summary(
        self, raw: dict[str, Any]
    ) -> ConversationSummary | None:
        conv = raw.get("singleChatUserConversation", raw)
        if not isinstance(conv, dict):
            return None
        details = conv.get("singleChatConversation")
        if not isinstance(details, dict):
            return None
        conversation_id = self._strip_goofish(details.get("cid"))
        if not conversation_id:
            return None
        first = self._strip_goofish(details.get("pairFirst"))
        second = self._strip_goofish(details.get("pairSecond"))
        peer_id = second if first == self.myid else first
        if not peer_id or peer_id == "0":
            return None

        last_wrapper = conv.get("lastMessage")
        last_message = last_wrapper.get("message", {}) if isinstance(last_wrapper, dict) else {}
        last_message = last_message if isinstance(last_message, dict) else {}
        last_message_at_ms = self._extract_created_at_ms(last_message)
        if last_message_at_ms is None and isinstance(last_wrapper, dict):
            last_message_at_ms = self._extract_created_at_ms(last_wrapper)
        if last_message_at_ms is None:
            last_message_at_ms = self._as_int(
                conv.get("modifyTime")
                or details.get("modifyTime")
                or conv.get("lastMessageTime")
                or details.get("lastMessageTime")
            )
        extension = self._as_dict(last_message.get("extension"))
        sender_id = self._strip_goofish(extension.get("senderUserId"))
        direction = Direction.OUTBOUND if sender_id == self.myid else Direction.INBOUND
        message_type, content = self._parse_history_content(last_message)
        peer_name = None
        if sender_id == peer_id:
            peer_name = extract_peer_name(extension, peer_user_id=peer_id)
        detail_extension = self._as_dict(details.get("extension"))
        return ConversationSummary(
            account_id=self.account.account_id,
            conversation_id=conversation_id,
            peer_user_id=peer_id,
            peer_name=peer_name,
            item_id=str(
                detail_extension.get("itemId") or detail_extension.get("item_id") or ""
            )
            or self._extract_item_id(raw),
            item_title=self._first_scalar(
                detail_extension, "itemTitle", "title", "subject"
            ),
            item_price=self._first_scalar(
                detail_extension, "itemPrice", "price", "salePrice"
            ),
            item_image_url=self._first_scalar(
                detail_extension, "itemPic", "mainPic", "picUrl", "imageUrl"
            ),
            item_url=self._first_scalar(
                detail_extension, "itemUrl", "jumpUrl", "targetUrl", "url"
            ),
            last_message_content=content,
            last_message_type=message_type,
            last_message_direction=direction,
            last_message_at_ms=last_message_at_ms,
            unread_count=self._as_int(conv.get("redPoint")) or 0,
            raw_payload=raw,
        )

    def _parse_history_message(
        self, model: dict[str, Any], conversation_id: str
    ) -> ChatMessageEvent | None:
        message = model.get("message")
        if not isinstance(message, dict):
            return None
        extension = self._as_dict(message.get("extension"))
        sender_id = self._strip_goofish(extension.get("senderUserId"))
        direction = Direction.OUTBOUND if sender_id == self.myid else Direction.INBOUND
        message_type, content = self._parse_history_content(message)
        peer_id = sender_id if direction == Direction.INBOUND else self._strip_goofish(
            extension.get("receiverUserId") or extension.get("receiverId")
        )
        return ChatMessageEvent(
            account_id=self.account.account_id,
            conversation_id=self._strip_goofish(conversation_id),
            message_id=str(message.get("messageId") or model.get("messageId") or "") or None,
            peer_user_id=peer_id or None,
            peer_name=(
                extract_peer_name(extension, peer_user_id=peer_id)
                if direction == Direction.INBOUND
                else None
            ),
            direction=direction,
            message_type=message_type,
            content=content,
            raw_payload=model,
            item_id=self._extract_item_id(model),
            created_at_ms=self._as_int(message.get("createAt") or message.get("time")),
            attachments=self._parse_history_attachments(message),
        )

    def _parse_push_content(
        self, message_node: dict[str, Any], meta: dict[str, Any]
    ) -> tuple[MessageType, str]:
        message_content = message_node.get("6")
        nested = message_content.get("3", {}) if isinstance(message_content, dict) else {}
        if isinstance(nested, dict):
            decoded = self._decode_json_value(nested.get("5"))
            if decoded:
                interpreted = self._interpret_content(decoded, nested)
                if interpreted[0] != MessageType.UNKNOWN:
                    return interpreted
                fallback = str(nested.get("2") or meta.get("reminderContent") or "")
                return interpreted[0], fallback or interpreted[1]
            if nested.get("2"):
                return MessageType.CARD, str(nested["2"])
            decoded = self._decode_json_value(nested.get("1"))
            if decoded:
                interpreted = self._interpret_content(decoded, nested)
                if interpreted[0] != MessageType.UNKNOWN:
                    return interpreted
                fallback = str(nested.get("2") or meta.get("reminderContent") or "")
                return interpreted[0], fallback or interpreted[1]
        reminder = str(meta.get("reminderContent") or "")
        if reminder in {"[图片]", "[语音]"}:
            return MessageType.IMAGE if reminder == "[图片]" else MessageType.AUDIO, reminder
        return (MessageType.TEXT if reminder else MessageType.UNKNOWN, reminder)

    def _parse_history_content(self, message: dict[str, Any]) -> tuple[MessageType, str]:
        content = message.get("content")
        custom = content.get("custom", {}) if isinstance(content, dict) else {}
        custom = custom if isinstance(custom, dict) else {}
        decoded = self._decode_json_value(custom.get("data"))
        if decoded:
            return self._interpret_content(decoded, custom)
        summary = str(custom.get("summary") or custom.get("degrade") or "")
        return (MessageType.TEXT if summary else MessageType.SYSTEM, summary or "[系统消息]")

    @staticmethod
    def _interpret_content(
        decoded: dict[str, Any], fallback: dict[str, Any]
    ) -> tuple[MessageType, str]:
        text_card = parse_text_card_content(decoded)
        if text_card is not None:
            return MessageType.SYSTEM, text_card
        text = decoded.get("text")
        if isinstance(text, dict) and text.get("text") is not None:
            return MessageType.TEXT, str(text.get("text") or "")
        if isinstance(text, str):
            return MessageType.TEXT, text
        image = decoded.get("image")
        pics = image.get("pics", []) if isinstance(image, dict) else []
        urls = [
            str(pic.get("url"))
            for pic in pics
            if isinstance(pic, dict) and pic.get("url")
        ]
        if decoded.get("picUrl"):
            urls.append(str(decoded["picUrl"]))
        if urls or decoded.get("contentType") == 2:
            return MessageType.IMAGE, "\n".join(dict.fromkeys(urls)) or "[图片]"
        audio = decoded.get("audio")
        if isinstance(audio, dict) or decoded.get("contentType") == 3:
            duration = XianyuAccountSession._as_int(
                audio.get("duration") if isinstance(audio, dict) else None
            )
            return (
                MessageType.AUDIO,
                f"[语音 {duration}秒]" if duration is not None else "[语音]",
            )
        title = decoded.get("title") or decoded.get("template")
        if title:
            return MessageType.CARD, str(title)
        summary = fallback.get("summary") or fallback.get("degrade")
        if summary:
            return MessageType.TEXT, str(summary)
        return MessageType.UNKNOWN, f"[未知消息类型:{decoded.get('contentType', '')}]"

    @staticmethod
    def _audio_attachment(
        decoded: dict[str, Any] | None,
    ) -> ChatMediaAttachment | None:
        audio = decoded.get("audio") if isinstance(decoded, dict) else None
        if not isinstance(audio, dict):
            return None
        url = str(audio.get("url") or "").strip()
        if not url:
            return None
        return ChatMediaAttachment(
            attachment_type="audio",
            remote_url=url,
            mime_type="audio/amr",
            size_bytes=XianyuAccountSession._as_int(
                audio.get("sizeBytes") or audio.get("size")
            ),
            duration_seconds=XianyuAccountSession._as_int(audio.get("duration")),
        )

    def _parse_push_attachments(
        self,
        message_node: dict[str, Any],
    ) -> list[ChatMediaAttachment]:
        message_content = message_node.get("6")
        nested = message_content.get("3", {}) if isinstance(message_content, dict) else {}
        if not isinstance(nested, dict):
            return []
        for key in ("5", "1"):
            attachment = self._audio_attachment(
                self._decode_json_value(nested.get(key))
            )
            if attachment is not None:
                return [attachment]
        return []

    def _parse_history_attachments(
        self,
        message: dict[str, Any],
    ) -> list[ChatMediaAttachment]:
        content = message.get("content")
        custom = content.get("custom", {}) if isinstance(content, dict) else {}
        custom = custom if isinstance(custom, dict) else {}
        attachment = self._audio_attachment(
            self._decode_json_value(custom.get("data"))
        )
        return [attachment] if attachment is not None else []

    def _extract_sync_payloads(self, frame: dict[str, Any]) -> list[dict[str, Any]]:
        body = frame.get("body")
        sync_package = body.get("syncPushPackage") if isinstance(body, dict) else None
        entries = sync_package.get("data", []) if isinstance(sync_package, dict) else []
        payloads: list[dict[str, Any]] = []
        for entry in entries:
            data = entry.get("data") if isinstance(entry, dict) else None
            decoded = self._decode_sync_data(data)
            if decoded is not None:
                payloads.append(decoded)
        return payloads

    def _extract_sync_payload(self, frame: dict[str, Any]) -> dict[str, Any] | None:
        payloads = self._extract_sync_payloads(frame)
        return payloads[0] if payloads else None

    def _decode_sync_data(self, data: Any) -> dict[str, Any] | None:
        if isinstance(data, dict):
            return data
        if not isinstance(data, str):
            return None
        decoded = self._decode_json_value(data, base64_allowed=True)
        if decoded is not None:
            return decoded
        try:
            decrypted = self.upstream.decrypt(data)
        except Exception:
            return None
        return self._decode_json_value(decrypted, base64_allowed=False)

    @staticmethod
    def _decode_json_value(value: Any, *, base64_allowed: bool = True) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return value
        if not isinstance(value, str) or not value:
            return None
        candidates = [value]
        if base64_allowed:
            try:
                candidates.append(base64.b64decode(value + "=" * (-len(value) % 4)).decode("utf-8"))
            except Exception:
                pass
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    @classmethod
    def _as_dict(cls, value: Any) -> dict[str, Any]:
        return cls._decode_json_value(value, base64_allowed=False) or {}

    @staticmethod
    def _strip_goofish(value: Any) -> str:
        return str(value or "").split("@", 1)[0]

    @staticmethod
    def _with_goofish_suffix(value: str) -> str:
        return value if "@" in value else f"{value}@goofish"

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    @staticmethod
    def _as_bool(value: Any) -> bool:
        return value is True or value == 1 or str(value).lower() == "true"

    @classmethod
    def _extract_push_message_id(
        cls, message_node: dict[str, Any], meta: dict[str, Any]
    ) -> str | None:
        value = message_node.get("3") or meta.get("messageId") or cls._message_id_from_meta(meta)
        return str(value) if value else None

    @classmethod
    def _message_id_from_meta(cls, meta: dict[str, Any]) -> str | None:
        for key in ("bizTag", "extJson"):
            nested = cls._as_dict(meta.get(key))
            value = nested.get("messageId")
            if value:
                return str(value)
        return None

    @classmethod
    def _extract_response_message_id(cls, frame: dict[str, Any]) -> str | None:
        body = frame.get("body")
        if not isinstance(body, dict):
            return None
        value: Any = body.get("messageId") or body.get("1")
        if isinstance(value, dict):
            value = value.get("messageId") or value.get("1")
        return str(value) if value else None

    @classmethod
    def _extract_item_id(cls, payload: Any) -> str | None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in {"itemId", "item_id"} and value:
                    return str(value)
                nested = cls._extract_item_id(value)
                if nested:
                    return nested
        elif isinstance(payload, list):
            for value in payload:
                nested = cls._extract_item_id(value)
                if nested:
                    return nested
        elif isinstance(payload, str):
            text = payload.strip()
            if "item" in text.lower() and ("?" in text or "&" in text):
                try:
                    query = parse_qs(urlparse(text).query)
                except ValueError:
                    query = {}
                lowered = {key.lower(): values for key, values in query.items()}
                for key in ("itemid", "item_id", "auctionid"):
                    values = lowered.get(key)
                    if values and values[0]:
                        return str(values[0])
            decoded = cls._decode_json_value(text, base64_allowed=True)
            if decoded is not None:
                return cls._extract_item_id(decoded)
        return None

    @staticmethod
    def _first_scalar(value: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, (str, int, float)) and str(candidate).strip():
                return str(candidate).strip()
        return None

    @classmethod
    def _extract_created_at_ms(cls, message_node: dict[str, Any]) -> int | None:
        for key in ("5", "createAt", "createdAt", "time", "timestamp"):
            value = cls._as_int(message_node.get(key))
            if value is not None:
                return value
        return None

    async def _emit_state(self, state: ConnectionState, message: str | None) -> None:
        if self._on_state:
            await self._on_state(self.account.account_id, state, message)
