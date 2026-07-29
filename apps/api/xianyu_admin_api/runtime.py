"""Runtime manager used by the web backend."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote, urlparse

import requests

from .schemas import (
    AccountPayload,
    ConversationAccountSyncPayload,
    DeliverySendResultPayload,
    ProxyConfigPayload,
    ProxyTestPayload,
    PlatformBlacklistPayload,
    RecallMessageResultPayload,
    RuntimeState,
    SendImageResultPayload,
    SendTextPayload,
    SendTextResultPayload,
)
from .account_network import build_core_account_proxy
from .store import AccountRecord, AccountStore
from .executors import run_external_blocking
from .proxy_location import lookup_proxy_ip
from .realtime import realtime_broker
from .settings import settings

logger = logging.getLogger(__name__)
CookieAuthFailureHandler = Callable[[str, str, str], Awaitable[Any]]


@dataclass(slots=True)
class ConversationSyncHealth:
    syncing: bool = False
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


@dataclass(slots=True)
class ProcessingErrorHealth:
    count: int = 0
    last_error: str | None = None
    last_error_at: datetime | None = None


class AccountRuntimeManager:
    """Thin web-facing manager around ``integrations.xianyu_core``.

    This class owns only orchestration state. Protocol behavior stays in
    ``integrations/xianyu_core`` and upstream behavior stays in
    ``third_party/XianYuApis``.
    """

    def __init__(self, store: AccountStore) -> None:
        self._store = store
        self._core: Any | None = None
        self._lock = asyncio.Lock()
        self._account_locks: dict[str, asyncio.Lock] = {}
        self._runtime_start_slot = asyncio.Semaphore(settings.runtime_start_concurrency)
        self._account_generations: dict[str, int] = {}
        self._desired_running: dict[str, bool] = {}
        self._sync_lock = asyncio.Lock()
        self._account_sync_slots: dict[str, asyncio.Semaphore] = {}
        self._conversation_global_slot = asyncio.Semaphore(
            settings.conversation_sync_concurrency
        )
        self._conversation_sync_tasks: dict[tuple[str, int | None, int], asyncio.Task[Any]] = {}
        self._message_sync_tasks: dict[
            tuple[str, str, int | None, int], asyncio.Task[Any]
        ] = {}
        self._conversation_sync_cache: dict[
            tuple[str, int | None, int], tuple[float, Any]
        ] = {}
        self._message_sync_cache: dict[
            tuple[str, str, int | None, int], tuple[float, Any]
        ] = {}
        self._conversation_reconcile_task: asyncio.Task[None] | None = None
        self._conversation_sync_health: dict[str, ConversationSyncHealth] = {}
        self._conversation_warm_locks: dict[str, asyncio.Lock] = {}
        self._conversation_full_sync_completed: set[str] = set()
        self._connection_watchdog_task: asyncio.Task[None] | None = None
        self._message_retry_tasks: set[asyncio.Task[None]] = set()
        self._maintenance_tasks: set[asyncio.Task[Any]] = set()
        self._identity_query_slot = asyncio.Semaphore(3)
        self._conversation_hydration_tasks: dict[str, asyncio.Task[None]] = {}
        self._conversation_hydration_pending: dict[str, dict[str, Any]] = {}
        self._hydration_attempts: dict[tuple[str, str, str], float] = {}
        self._side_effect_queues: dict[str, asyncio.Queue[tuple[AccountRecord, Any]]] = {}
        self._side_effect_tasks: dict[str, asyncio.Task[None]] = {}
        self._side_effect_dropped: dict[str, int] = {}
        self._processing_errors: dict[str, ProcessingErrorHealth] = {}
        self._cookie_auth_failure_handler: CookieAuthFailureHandler | None = None

    def set_cookie_auth_failure_handler(
        self,
        handler: CookieAuthFailureHandler,
    ) -> None:
        self._cookie_auth_failure_handler = handler

    async def _report_cookie_auth_failure(
        self,
        account_id: str,
        source: str,
        message: str,
    ) -> None:
        if self._cookie_auth_failure_handler is None:
            return
        await self._cookie_auth_failure_handler(account_id, source, message)

    @staticmethod
    def _is_platform_auth_failure(error: object) -> bool:
        value = str(error or "")
        upper = value.upper()
        return "FAIL_SYS_SESSION_EXPIRED" in upper or "Session过期" in value

    def _account_lock(self, account_id: str) -> asyncio.Lock:
        return self._account_locks.setdefault(account_id, asyncio.Lock())

    def _sync_slot(self, account_id: str) -> asyncio.Semaphore:
        return self._account_sync_slots.setdefault(account_id, asyncio.Semaphore(1))

    def _conversation_warm_lock(self, account_id: str) -> asyncio.Lock:
        return self._conversation_warm_locks.setdefault(account_id, asyncio.Lock())

    def _conversation_health(self, account_id: str) -> ConversationSyncHealth:
        return self._conversation_sync_health.setdefault(account_id, ConversationSyncHealth())

    def _pending_sync_count(self, account_id: str) -> int:
        conversation_tasks = sum(
            1
            for key, task in self._conversation_sync_tasks.items()
            if key[0] == account_id and not task.done()
        )
        message_tasks = sum(
            1
            for key, task in self._message_sync_tasks.items()
            if key[0] == account_id and not task.done()
        )
        return conversation_tasks + message_tasks

    def _next_generation(self, account_id: str) -> int:
        generation = self._account_generations.get(account_id, 0) + 1
        self._account_generations[account_id] = generation
        return generation

    def _is_current_generation(self, account_id: str, generation: int) -> bool:
        return self._account_generations.get(account_id) == generation

    def _track_maintenance_task(self, task: asyncio.Task[Any]) -> None:
        self._maintenance_tasks.add(task)

        def completed(done: asyncio.Task[Any]) -> None:
            self._maintenance_tasks.discard(done)
            try:
                done.result()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Runtime maintenance task failed")

        task.add_done_callback(completed)

    async def start(
        self,
        account: AccountRecord,
        *,
        force_restart: bool = False,
    ) -> AccountPayload:
        async with self._runtime_start_slot:
            async with self._account_lock(account.account_id):
                self._desired_running[account.account_id] = bool(
                    account.enabled and account.cookie
                )
                return await self._start_locked(account, force_restart=force_restart)

    async def _start_locked(
        self,
        account: AccountRecord,
        *,
        force_restart: bool,
    ) -> AccountPayload:
        core = self._get_core()
        if not account.enabled:
            self._next_generation(account.account_id)
            await core.stop_account(account.account_id)
            await self._store.set_runtime_state(
                account.account_id,
                "disabled",
                "账户已禁用，未启动",
            )
            return await self._latest_payload(account)

        if not account.cookie:
            self._next_generation(account.account_id)
            await core.stop_account(account.account_id)
            await self._store.set_runtime_state(
                account.account_id,
                "auth_expired",
                "缺少闲鱼 Cookie，无法建立真实连接",
            )
            return await self._latest_payload(account)

        if (
            not force_restart
            and account.runtime is not None
            and account.runtime.state in {"auth_expired", "risk_blocked"}
        ):
            self._desired_running[account.account_id] = False
            return await self._latest_payload(account)

        if core.is_account_running(account.account_id) and not force_restart:
            if core.is_account_online(account.account_id):
                latest = await self._store.get_account(account.account_id)
                if latest is not None and latest.runtime.state != "online":
                    await self._store.set_runtime_state(
                        account.account_id,
                        "online",
                        "连接已在运行，忽略重复启动",
                    )
                self._schedule_account_identity_refresh(account.account_id)
            return await self._latest_payload(account)

        await self._store.set_runtime_state(account.account_id, "connecting", "正在启动连接")
        generation = self._next_generation(account.account_id)

        async def on_message(event: Any) -> None:
            await self._handle_message(event, generation=generation)

        async def on_state(account_id: str, state: Any, message: str | None) -> None:
            await self._handle_state(
                account_id,
                state,
                message,
                generation=generation,
            )

        async def on_cookie(
            account_id: str,
            expected_cookie: str,
            new_cookie: str,
        ) -> None:
            await self._handle_cookie_refresh(
                account_id,
                expected_cookie,
                new_cookie,
                generation=generation,
            )

        async def on_im_token(account_id: str, token: str, expires_at_ms: int) -> None:
            await self._handle_im_token(
                account_id,
                token,
                expires_at_ms,
                generation=generation,
            )

        async def on_verification(verification: Any) -> None:
            await self._handle_verification(verification, generation=generation)

        try:
            account_config = self._build_core_account(account)
            online = await core.start_account(
                account_config,
                on_message=on_message,
                on_state=on_state,
                on_cookie=on_cookie,
                on_im_token=on_im_token,
                on_verification=on_verification,
                force_restart=force_restart,
            )
            if not online:
                latest = await self._store.get_account(account.account_id)
                if core.is_account_online(account.account_id):
                    await self._store.set_runtime_state(
                        account.account_id,
                        "online",
                        "连接已就绪",
                    )
                elif latest is None or latest.runtime.state not in {
                    "auth_expired",
                    "risk_blocked",
                }:
                    await self._store.set_runtime_state(
                        account.account_id,
                        "reconnecting",
                        "连接尚未就绪，后台将继续重试",
                    )
            if core.is_account_online(account.account_id):
                self._schedule_account_identity_refresh(account.account_id)
        except Exception as exc:
            state = self._classify_error(exc)
            await self._store.set_runtime_state(account.account_id, state, str(exc))

        return await self._latest_payload(account)

    async def stop(self, account_id: str) -> None:
        async with self._account_lock(account_id):
            self._desired_running[account_id] = False
            self._next_generation(account_id)
            async with self._lock:
                core = self._core
            if core is not None:
                try:
                    await core.stop_account(account_id)
                except Exception as exc:
                    await self._store.set_runtime_state(account_id, "error", str(exc))
                    return
            await self._store.set_runtime_state(account_id, "stopped", "已停止")

    async def prepare_delete(self, account_id: str, timeout: float = 5.0) -> bool:
        """Fence one account immediately, then stop its runtime within a bounded wait."""

        self._desired_running[account_id] = False
        self._next_generation(account_id)
        try:
            await asyncio.wait_for(self.stop(account_id), timeout=timeout)
        except TimeoutError:
            return False
        return True

    async def forget_account(self, account_id: str) -> None:
        """Discard account-scoped orchestration state after durable deletion."""

        self._desired_running.pop(account_id, None)
        self._next_generation(account_id)
        async with self._sync_lock:
            tasks = [
                task
                for key, task in (
                    *self._conversation_sync_tasks.items(),
                    *self._message_sync_tasks.items(),
                )
                if key[0] == account_id
            ]
            self._conversation_sync_tasks = {
                key: task
                for key, task in self._conversation_sync_tasks.items()
                if key[0] != account_id
            }
            self._message_sync_tasks = {
                key: task
                for key, task in self._message_sync_tasks.items()
                if key[0] != account_id
            }
            self._conversation_sync_cache = {
                key: value
                for key, value in self._conversation_sync_cache.items()
                if key[0] != account_id
            }
            self._conversation_sync_health.pop(account_id, None)
            self._processing_errors.pop(account_id, None)
            self._side_effect_dropped.pop(account_id, None)
            self._conversation_warm_locks.pop(account_id, None)
            self._conversation_full_sync_completed.discard(account_id)
            hydration_task = self._conversation_hydration_tasks.pop(account_id, None)
            if hydration_task is not None:
                tasks.append(hydration_task)
            self._conversation_hydration_pending.pop(account_id, None)
            self._hydration_attempts = {
                key: value
                for key, value in self._hydration_attempts.items()
                if key[0] != account_id
            }
            self._message_sync_cache = {
                key: value
                for key, value in self._message_sync_cache.items()
                if key[0] != account_id
            }
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        side_effect_task = self._side_effect_tasks.pop(account_id, None)
        self._side_effect_queues.pop(account_id, None)
        if side_effect_task is not None:
            side_effect_task.cancel()
            await asyncio.gather(side_effect_task, return_exceptions=True)
        self._account_sync_slots.pop(account_id, None)
        account_lock = self._account_locks.get(account_id)
        if account_lock is not None and not account_lock.locked():
            self._account_locks.pop(account_id, None)

    async def restore_enabled_accounts(self) -> None:
        accounts = [
            account
            for account in await self._store.list_accounts()
            if account.enabled
            and account.runtime is not None
            and account.runtime.state not in {"auth_expired", "risk_blocked"}
        ]
        async def restore(account: AccountRecord, position: int) -> None:
            if position and settings.runtime_start_jitter_seconds:
                await asyncio.sleep(
                    random.uniform(0, settings.runtime_start_jitter_seconds)
                )
            await self.start(account)

        if accounts:
            await asyncio.gather(
                *(restore(account, position) for position, account in enumerate(accounts)),
                return_exceptions=True,
            )
        if self._conversation_reconcile_task is None:
            self._conversation_reconcile_task = asyncio.create_task(
                self._reconcile_conversations_loop()
            )
        if self._connection_watchdog_task is None:
            self._connection_watchdog_task = asyncio.create_task(
                self._connection_watchdog_loop(),
                name="xianyu-connection-watchdog",
            )

    async def shutdown(self) -> None:
        if self._connection_watchdog_task is not None:
            self._connection_watchdog_task.cancel()
            try:
                await self._connection_watchdog_task
            except asyncio.CancelledError:
                pass
            self._connection_watchdog_task = None
        if self._conversation_reconcile_task is not None:
            self._conversation_reconcile_task.cancel()
            try:
                await self._conversation_reconcile_task
            except asyncio.CancelledError:
                pass
            self._conversation_reconcile_task = None
        retry_tasks = tuple(self._message_retry_tasks)
        for task in retry_tasks:
            task.cancel()
        if retry_tasks:
            await asyncio.gather(*retry_tasks, return_exceptions=True)
        maintenance_tasks = tuple(self._maintenance_tasks)
        for task in maintenance_tasks:
            task.cancel()
        if maintenance_tasks:
            await asyncio.gather(*maintenance_tasks, return_exceptions=True)
        self._conversation_hydration_tasks.clear()
        self._conversation_hydration_pending.clear()
        self._hydration_attempts.clear()
        side_effect_tasks = tuple(self._side_effect_tasks.values())
        for task in side_effect_tasks:
            task.cancel()
        if side_effect_tasks:
            await asyncio.gather(*side_effect_tasks, return_exceptions=True)
        self._side_effect_tasks.clear()
        self._side_effect_queues.clear()
        async with self._sync_lock:
            sync_tasks = tuple(
                set(self._conversation_sync_tasks.values())
                | set(self._message_sync_tasks.values())
            )
            self._conversation_sync_tasks.clear()
            self._message_sync_tasks.clear()
            self._conversation_sync_cache.clear()
            self._message_sync_cache.clear()
        for task in sync_tasks:
            task.cancel()
        if sync_tasks:
            await asyncio.gather(*sync_tasks, return_exceptions=True)
        async with self._lock:
            core = self._core
        if core is not None:
            for account_id in tuple(self._account_generations):
                self._next_generation(account_id)
            await core.stop_all()

    async def replace_cookie(
        self,
        account_id: str,
        cookie: str,
        *,
        mark_online: bool = False,
    ) -> bool:
        async with self._account_lock(account_id):
            async with self._lock:
                core = self._core
            if core is None:
                return False
            try:
                replaced = await core.replace_cookie(account_id, cookie)
            except Exception:
                latest = await self._store.get_account(account_id)
                if latest is None or not latest.enabled:
                    return False
                await self._start_locked(latest, force_restart=True)
                replaced = True
            if replaced and mark_online and core.is_account_online(account_id):
                await self._store.set_runtime_state(
                    account_id, "online", "Cookie 续期成功，运行时凭据已更新"
                )
            if replaced and core.is_account_online(account_id):
                self._schedule_account_identity_refresh(account_id, force=True)
            return bool(replaced)

    def is_online(self, account_id: str) -> bool:
        return bool(self._core and self._core.is_account_online(account_id))

    def connection_health(self, account_id: str) -> dict[str, Any]:
        if self._core is None:
            core_health: dict[str, Any] = {
                "running": False,
                "online": False,
                "connected_at_ms": None,
                "last_heartbeat_at_ms": None,
                "reconnect_count": 0,
                "last_disconnect_reason": None,
            }
        else:
            core_health = self._core.account_connection_health(account_id)
        side_effect_queue = self._side_effect_queues.get(account_id)
        processing = self._processing_errors.get(account_id)
        retry_prefix = f"xianyu-message-retry:{account_id}:"
        core_health.update(
            {
                "sync_queue_depth": self._pending_sync_count(account_id),
                "side_effect_queue_depth": (
                    side_effect_queue.qsize() if side_effect_queue is not None else 0
                ),
                "side_effect_queue_capacity": (
                    side_effect_queue.maxsize if side_effect_queue is not None else 200
                ),
                "side_effect_queue_dropped": self._side_effect_dropped.get(account_id, 0),
                "message_retry_pending": sum(
                    1
                    for task in self._message_retry_tasks
                    if not task.done() and task.get_name().startswith(retry_prefix)
                ),
                "processing_errors_total": processing.count if processing else 0,
                "last_processing_error": processing.last_error if processing else None,
                "last_processing_error_at": processing.last_error_at if processing else None,
            }
        )
        return core_health

    async def sync_order_headinfo(self, order: Any) -> Any:
        if not order.item_id:
            raise RuntimeError("订单缺少商品 ID，无法查询平台当前状态")
        core = self._core
        if core is None or not core.is_account_online(order.account_id):
            raise RuntimeError("闲鱼 IM 当前未在线")
        try:
            raw_data = await core.get_order_headinfo(
                order.account_id,
                order.item_id,
                order.conversation_id,
            )
        except Exception as exc:
            if self._is_platform_auth_failure(exc):
                await self._report_cookie_auth_failure(
                    order.account_id,
                    "order_headinfo",
                    str(exc),
                )
            raise
        updated = await self._store.apply_order_headinfo(order.order_pk, raw_data)
        if updated is None:
            raise RuntimeError("订单状态保存失败")
        await realtime_broker.publish(
            {
                "event": "order_upsert",
                "account_id": updated.account_id,
                "data": updated.model_dump(mode="json"),
            }
        )
        return updated

    async def sync_conversation_item(
        self,
        account_id: str,
        conversation_id: str,
        *,
        publish: bool = True,
    ) -> Any:
        conversation = await self._store.get_conversation(account_id, conversation_id)
        if conversation is None:
            raise RuntimeError("会话不存在")
        if not conversation.item_id:
            raise RuntimeError("会话缺少商品 ID")
        if (
            conversation.item_context_source == "headinfo"
            and conversation.item_context_at is not None
            and (datetime.now(UTC) - conversation.item_context_at).total_seconds() < 1800
        ):
            return conversation
        core = self._core
        if core is None or not core.is_account_online(account_id):
            raise RuntimeError("闲鱼 IM 当前未在线")
        try:
            raw_data = await core.get_order_headinfo(
                account_id,
                conversation.item_id,
                conversation_id,
            )
        except Exception as exc:
            if self._is_platform_auth_failure(exc):
                await self._report_cookie_auth_failure(
                    account_id,
                    "conversation_headinfo",
                    str(exc),
                )
            raise
        updated = await self._store.apply_conversation_headinfo(
            account_id,
            conversation_id,
            raw_data,
        )
        if updated is None:
            raise RuntimeError("商品上下文保存失败")
        if publish:
            await realtime_broker.publish(
                {
                    "event": "conversation_upsert",
                    "account_id": updated.account_id,
                    "data": updated.model_dump(mode="json"),
                }
            )
        return updated

    async def sync_conversations(
        self, account_id: str, *, cursor: int | None = None, limit: int = 20
    ) -> tuple[list[Any], bool, int | None]:
        if not self.is_online(account_id):
            raise RuntimeError("闲鱼 IM 当前未在线")
        key = (account_id, cursor, limit)
        async with self._sync_lock:
            cached = self._conversation_sync_cache.get(key)
            if cached and time.monotonic() - cached[0] <= 5:
                return cached[1]
            task = self._conversation_sync_tasks.get(key)
            if task is None:
                if self._pending_sync_count(account_id) >= 8:
                    raise RuntimeError("同步请求过多，请稍后重试")
                task = asyncio.create_task(
                    self._sync_conversations_once(
                        account_id,
                        cursor=cursor,
                        limit=limit,
                    )
                )
                self._conversation_sync_tasks[key] = task
        try:
            result = await asyncio.shield(task)
        except Exception:
            raise
        else:
            async with self._sync_lock:
                self._conversation_sync_cache[key] = (time.monotonic(), result)
            return result
        finally:
            if task.done():
                async with self._sync_lock:
                    if self._conversation_sync_tasks.get(key) is task:
                        self._conversation_sync_tasks.pop(key, None)

    async def _sync_conversations_once(
        self, account_id: str, *, cursor: int | None, limit: int
    ) -> tuple[list[Any], bool, int | None]:
        health = self._conversation_health(account_id)
        health.syncing = True
        health.last_attempt_at = datetime.now(UTC)
        await self._publish_conversation_sync_status(account_id)
        try:
            async with self._conversation_global_slot, self._sync_slot(account_id):
                core = self._core
                if core is None or not core.is_account_online(account_id):
                    raise RuntimeError("闲鱼 IM 当前未在线")
                page = await core.list_conversations(account_id, cursor=cursor, limit=limit)
        except Exception as exc:
            health.syncing = False
            health.last_error_at = datetime.now(UTC)
            health.last_error = str(exc)[:300]
            health.consecutive_failures += 1
            await self._publish_conversation_sync_status(account_id)
            raise
        try:
            rows = [
                {
                    "conversation_id": summary.conversation_id,
                    "peer_user_id": summary.peer_user_id,
                    "peer_name": summary.peer_name,
                    "item_id": summary.item_id,
                    "item_title": summary.item_title,
                    "item_price": summary.item_price,
                    "item_image_url": summary.item_image_url,
                    "item_url": summary.item_url,
                    "last_message_content": summary.last_message_content,
                    "last_message_type": self._enum_value(summary.last_message_type, "unknown"),
                    "last_message_direction": (
                        self._enum_value(summary.last_message_direction, "inbound")
                        if summary.last_message_direction
                        else None
                    ),
                    "last_message_at_ms": summary.last_message_at_ms,
                    "unread_count": summary.unread_count,
                }
                for summary in page.items
            ]
            items, changed_items = await self._store.upsert_conversations(account_id, rows)
        except Exception as exc:
            health.syncing = False
            health.last_error_at = datetime.now(UTC)
            health.last_error = str(exc)[:300]
            health.consecutive_failures += 1
            await self._publish_conversation_sync_status(account_id)
            raise
        health.syncing = False
        health.last_success_at = datetime.now(UTC)
        health.last_error = None
        health.consecutive_failures = 0
        if changed_items:
            await realtime_broker.publish(
                {
                    "event": "conversation_batch",
                    "account_id": account_id,
                    "data": [item.model_dump(mode="json") for item in changed_items],
                }
            )
        self._schedule_conversation_hydration(account_id, items)
        await self._publish_conversation_sync_status(account_id)
        return items, page.has_more, page.next_cursor

    def _schedule_account_identity_refresh(
        self,
        account_id: str,
        *,
        force: bool = False,
    ) -> None:
        core = self._core
        if core is None or not callable(getattr(core, "get_account_identity", None)):
            return
        key = (account_id, "account", account_id)
        if not force and time.monotonic() - self._hydration_attempts.get(key, 0) < 3600:
            return
        self._hydration_attempts[key] = time.monotonic()
        task = asyncio.create_task(
            self._refresh_account_identity(account_id, force=force),
            name=f"xianyu-account-identity:{account_id}",
        )
        self._track_maintenance_task(task)

    async def _refresh_account_identity(self, account_id: str, *, force: bool) -> None:
        account = await self._store.get_account(account_id)
        if account is None or not account.enabled:
            return
        if (
            not force
            and account.platform_display_name
            and account.platform_identity_checked_at is not None
            and (datetime.now(UTC) - account.platform_identity_checked_at).total_seconds()
            < 86_400
        ):
            return
        core = self._core
        if (
            core is None
            or not core.is_account_online(account_id)
            or not callable(getattr(core, "get_account_identity", None))
        ):
            return
        try:
            async with self._identity_query_slot:
                identity = await core.get_account_identity(account_id)
            updated = await self._store.update_account_platform_identity(
                account_id,
                platform_user_id=str(identity.get("platform_user_id") or ""),
                display_name=identity.get("display_name"),
                avatar_url=identity.get("avatar_url"),
                source="mtop_nav",
            )
            if updated is not None:
                await realtime_broker.publish(
                    {
                        "event": "account_upsert",
                        "account_id": account_id,
                        "data": updated.to_payload().model_dump(mode="json"),
                    }
                )
        except Exception as exc:
            if self._is_platform_auth_failure(exc):
                await self._report_cookie_auth_failure(
                    account_id,
                    "account_identity",
                    str(exc),
                )
            logger.info("Account identity refresh failed for %s: %s", account_id, exc)

    def _schedule_conversation_hydration(
        self,
        account_id: str,
        conversations: list[Any],
    ) -> None:
        if (
            not conversations
            or not callable(
                getattr(self._store, "backfill_conversation_item_from_product", None)
            )
            or not callable(getattr(self._store, "apply_conversation_peer_profile", None))
        ):
            return
        pending = self._conversation_hydration_pending.setdefault(account_id, {})
        for conversation in conversations:
            if (
                not getattr(conversation, "peer_avatar_url", None)
                or (
                    getattr(conversation, "item_id", None)
                    and not getattr(conversation, "item_image_url", None)
                )
            ):
                pending[conversation.conversation_id] = conversation
        if not pending:
            return
        existing = self._conversation_hydration_tasks.get(account_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(
            self._hydrate_conversations(account_id),
            name=f"xianyu-conversation-hydration:{account_id}",
        )
        self._conversation_hydration_tasks[account_id] = task

        def completed(done: asyncio.Task[None]) -> None:
            if self._conversation_hydration_tasks.get(account_id) is done:
                self._conversation_hydration_tasks.pop(account_id, None)

        task.add_done_callback(completed)
        self._track_maintenance_task(task)

    async def _hydrate_conversations(self, account_id: str) -> None:
        while True:
            pending = self._conversation_hydration_pending.get(account_id)
            if not pending:
                self._conversation_hydration_pending.pop(account_id, None)
                return
            conversation_id = next(iter(pending))
            conversation = pending.pop(conversation_id)
            updated = conversation
            try:
                if updated.item_id and not updated.item_image_url:
                    cached = await self._store.backfill_conversation_item_from_product(
                        account_id,
                        updated.conversation_id,
                    )
                    if cached is not None:
                        updated = cached
                if updated.item_id and not updated.item_image_url:
                    item_key = (account_id, "item", updated.item_id)
                    if time.monotonic() - self._hydration_attempts.get(item_key, 0) >= 21_600:
                        self._hydration_attempts[item_key] = time.monotonic()
                        updated = await self.sync_conversation_item(
                            account_id,
                            updated.conversation_id,
                            publish=False,
                        )
                if updated.peer_user_id and not updated.peer_avatar_url:
                    peer_key = (account_id, "peer", updated.peer_user_id)
                    if time.monotonic() - self._hydration_attempts.get(peer_key, 0) >= 21_600:
                        self._hydration_attempts[peer_key] = time.monotonic()
                        core = self._core
                        if (
                            core is not None
                            and core.is_account_online(account_id)
                            and callable(getattr(core, "get_user_profile", None))
                        ):
                            async with self._identity_query_slot:
                                profile = await core.get_user_profile(
                                    account_id,
                                    updated.conversation_id,
                                )
                            profiled = await self._store.apply_conversation_peer_profile(
                                account_id,
                                updated.conversation_id,
                                updated.peer_user_id,
                                display_name=profile.get("display_name"),
                                avatar_url=profile.get("avatar_url"),
                                source="user_query",
                            )
                            if profiled is not None:
                                updated = profiled
                if updated != conversation:
                    await realtime_broker.publish(
                        {
                            "event": "conversation_upsert",
                            "account_id": account_id,
                            "data": updated.model_dump(mode="json"),
                        }
                    )
            except Exception as exc:
                if self._is_platform_auth_failure(exc):
                    await self._report_cookie_auth_failure(
                        account_id,
                        "conversation_hydration",
                        str(exc),
                    )
                logger.info(
                    "Conversation hydration failed for %s/%s: %s",
                    account_id,
                    conversation.conversation_id,
                    exc,
                )
            await asyncio.sleep(random.uniform(0.35, 0.75))

    async def conversation_sync_status(
        self,
        account_id: str,
        *,
        conversation_count: int | None = None,
    ) -> ConversationAccountSyncPayload:
        health = self._conversation_health(account_id)
        connection = self.connection_health(account_id)
        count = (
            conversation_count
            if conversation_count is not None
            else await self._store.count_conversations(account_id)
        )
        if not connection.get("online"):
            state = "offline"
        elif health.syncing:
            state = "syncing"
        elif health.last_error and health.consecutive_failures:
            state = "error"
        elif health.last_success_at:
            state = "healthy" if count else "empty"
        else:
            state = "pending"
        return ConversationAccountSyncPayload(
            account_id=account_id,
            state=state,  # type: ignore[arg-type]
            conversation_count=count,
            rpc_healthy=bool(connection.get("rpc_healthy")),
            last_attempt_at=health.last_attempt_at,
            last_success_at=health.last_success_at,
            last_error_at=health.last_error_at,
            last_error=health.last_error,
            consecutive_failures=health.consecutive_failures,
        )

    async def list_conversation_sync_statuses(
        self, accounts: list[AccountRecord]
    ) -> list[ConversationAccountSyncPayload]:
        return list(
            await asyncio.gather(
                *(self.conversation_sync_status(account.account_id) for account in accounts)
            )
        )

    async def _publish_conversation_sync_status(self, account_id: str) -> None:
        status = await self.conversation_sync_status(account_id)
        await realtime_broker.publish(
            {
                "event": "conversation_sync_status",
                "account_id": account_id,
                "data": status.model_dump(mode="json"),
            }
        )

    async def sync_messages(
        self,
        account_id: str,
        conversation_id: str,
        *,
        cursor: int | None = None,
        limit: int = 20,
    ) -> tuple[list[Any], bool, int | None]:
        if not self.is_online(account_id):
            raise RuntimeError("闲鱼 IM 当前未在线")
        key = (account_id, conversation_id, cursor, limit)
        async with self._sync_lock:
            cached = self._message_sync_cache.get(key)
            if cached and time.monotonic() - cached[0] <= 3:
                return cached[1]
            task = self._message_sync_tasks.get(key)
            if task is None:
                if self._pending_sync_count(account_id) >= 8:
                    raise RuntimeError("同步请求过多，请稍后重试")
                task = asyncio.create_task(
                    self._sync_messages_once(
                        account_id,
                        conversation_id,
                        cursor=cursor,
                        limit=limit,
                    )
                )
                self._message_sync_tasks[key] = task
        try:
            result = await asyncio.shield(task)
        except Exception:
            raise
        else:
            async with self._sync_lock:
                self._message_sync_cache[key] = (time.monotonic(), result)
            return result
        finally:
            if task.done():
                async with self._sync_lock:
                    if self._message_sync_tasks.get(key) is task:
                        self._message_sync_tasks.pop(key, None)

    async def _sync_messages_once(
        self,
        account_id: str,
        conversation_id: str,
        *,
        cursor: int | None,
        limit: int,
    ) -> tuple[list[Any], bool, int | None]:
        async with self._conversation_global_slot, self._sync_slot(account_id):
            core = self._core
            if core is None or not core.is_account_online(account_id):
                raise RuntimeError("闲鱼 IM 当前未在线")
            page = await core.list_messages(
                account_id,
                conversation_id,
                cursor=cursor,
                limit=limit,
            )
        message_ids = {item.message_id for item in page.items if item.message_id}
        timestamps = {item.created_at_ms for item in page.items if item.created_at_ms}
        for event in page.items:
            await self._store.record_message(
                account_id=account_id,
                conversation_id=conversation_id,
                direction=self._enum_value(event.direction, "inbound"),
                message_type=self._enum_value(event.message_type, "unknown"),
                content=event.content,
                message_id=event.message_id,
                peer_user_id=event.peer_user_id,
                peer_name=event.peer_name,
                item_id=event.item_id,
                raw_payload=event.raw_payload,
                created_at_ms=event.created_at_ms,
                count_unread=False,
                promote_activity=False,
            )
        reconciled = await self._store.reconcile_conversation_summaries(
            account_id,
            conversation_id,
        )
        if reconciled:
            await realtime_broker.publish(
                {
                    "event": "conversation_batch",
                    "account_id": account_id,
                    "data": [item.model_dump(mode="json") for item in reconciled],
                }
            )
        cached = await self._store.list_messages(account_id, conversation_id, limit=500)
        items = [
            item
            for item in cached
            if (item.message_id and item.message_id in message_ids)
            or (not item.message_id and item.created_at_ms in timestamps)
        ]
        return items, page.has_more, page.next_cursor

    async def send_text(
        self,
        account: AccountRecord,
        conversation_id: str,
        payload: SendTextPayload,
    ) -> SendTextResultPayload:
        if payload.client_request_id:
            pending, created = await self._store.begin_outbound_text(
                account_id=account.account_id,
                conversation_id=conversation_id,
                client_request_id=payload.client_request_id,
                peer_user_id=payload.receiver_user_id,
                text=payload.text,
            )
            if pending is None:
                return SendTextResultPayload(
                    success=False,
                    account_id=account.account_id,
                    conversation_id=conversation_id,
                    client_request_id=payload.client_request_id,
                    error="failed to create the outbound text record",
                )
            if not created:
                return SendTextResultPayload(
                    success=pending.send_status == "sent",
                    account_id=account.account_id,
                    conversation_id=conversation_id,
                    client_request_id=payload.client_request_id,
                    message_id=pending.message_id,
                    error=(
                        pending.send_error
                        if pending.send_status == "failed"
                        else None
                        if pending.send_status == "sent"
                        else "text send is already in progress"
                    ),
                    message=pending,
                )
            await self._after_message_persisted(
                pending,
                account_id=account.account_id,
                conversation_id=conversation_id,
                direction="outbound",
            )
            core = self._core
            if core is None:
                result_success = False
                result_message_id = None
                result_error = "account runtime is not running"
                result_raw: object | None = None
            else:
                result = await core.send_text(
                    account.account_id,
                    conversation_id,
                    payload.receiver_user_id,
                    payload.text,
                )
                result_success = bool(getattr(result, "success", False))
                result_message_id = getattr(result, "message_id", None)
                result_error = getattr(result, "error", None)
                result_raw = getattr(result, "raw_payload", None)
            message = await self._store.complete_outbound_text(
                account_id=account.account_id,
                client_request_id=payload.client_request_id,
                success=result_success,
                message_id=result_message_id,
                error=result_error,
                raw_payload=result_raw,
            )
            if message is not None:
                await self._after_message_persisted(
                    message,
                    account_id=account.account_id,
                    conversation_id=conversation_id,
                    direction="outbound",
                )
            return SendTextResultPayload(
                success=result_success,
                account_id=account.account_id,
                conversation_id=conversation_id,
                client_request_id=payload.client_request_id,
                message_id=result_message_id,
                error=result_error,
                message=message,
            )

        core = self._core
        if core is None:
            message = await self._store.record_message(
                account_id=account.account_id,
                conversation_id=conversation_id,
                direction="outbound",
                message_type="text",
                content=payload.text,
                peer_user_id=payload.receiver_user_id,
                send_success=False,
                send_error="account runtime is not running",
            )
            await self._after_message_persisted(
                message,
                account_id=account.account_id,
                conversation_id=conversation_id,
                direction="outbound",
            )
            return SendTextResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                error="account runtime is not running",
                message=message,
            )

        result = await core.send_text(
            account.account_id,
            conversation_id,
            payload.receiver_user_id,
            payload.text,
        )
        message = await self._store.record_message(
            account_id=account.account_id,
            conversation_id=conversation_id,
            direction="outbound",
            message_type="text",
            content=payload.text,
            message_id=getattr(result, "message_id", None),
            peer_user_id=payload.receiver_user_id,
            send_success=getattr(result, "success", False),
            send_error=getattr(result, "error", None),
            raw_payload=getattr(result, "raw_payload", None),
        )
        await self._after_message_persisted(
            message,
            account_id=account.account_id,
            conversation_id=conversation_id,
            direction="outbound",
        )
        return SendTextResultPayload(
            success=getattr(result, "success", False),
            account_id=account.account_id,
            conversation_id=conversation_id,
            message_id=getattr(result, "message_id", None),
            error=getattr(result, "error", None),
            message=message,
        )

    async def send_image(
        self,
        account: AccountRecord,
        conversation_id: str,
        client_request_id: str,
        image_data: bytes,
    ) -> SendImageResultPayload:
        conversation = await self._store.get_conversation(
            account.account_id,
            conversation_id,
        )
        if conversation is None:
            return SendImageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                client_request_id=client_request_id,
                error="conversation not found",
            )
        receiver_user_id = (conversation.peer_user_id or "").strip()
        if not receiver_user_id:
            return SendImageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                client_request_id=client_request_id,
                error="conversation is missing its receiver user ID",
            )

        pending, created = await self._store.begin_outbound_image(
            account_id=account.account_id,
            conversation_id=conversation_id,
            client_request_id=client_request_id,
            peer_user_id=receiver_user_id,
        )
        if pending is None:
            return SendImageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                client_request_id=client_request_id,
                error="failed to create the outbound image record",
            )
        if not created:
            return SendImageResultPayload(
                success=pending.send_status == "sent",
                account_id=account.account_id,
                conversation_id=conversation_id,
                client_request_id=client_request_id,
                message_id=pending.message_id,
                error=(
                    pending.send_error
                    if pending.send_status == "failed"
                    else None if pending.send_status == "sent" else "image send is already in progress"
                ),
                message=pending,
            )

        await self._after_message_persisted(
            pending,
            account_id=account.account_id,
            conversation_id=conversation_id,
            direction="outbound",
        )
        core = self._core
        if core is None:
            result_success = False
            result_message_id = None
            result_error = "account runtime is not running"
            result_raw: object | None = None
        else:
            result = await core.send_image(
                account.account_id,
                conversation_id,
                receiver_user_id,
                image_data,
            )
            result_success = bool(getattr(result, "success", False))
            result_message_id = getattr(result, "message_id", None)
            result_error = getattr(result, "error", None)
            result_raw = getattr(result, "raw_payload", None)

        media = (
            result_raw.get("media")
            if isinstance(result_raw, dict) and isinstance(result_raw.get("media"), dict)
            else None
        )
        message = await self._store.complete_outbound_image(
            account_id=account.account_id,
            client_request_id=client_request_id,
            success=result_success,
            message_id=result_message_id,
            error=result_error,
            raw_payload=result_raw,
            media=media,
        )
        if message is not None:
            await self._after_message_persisted(
                message,
                account_id=account.account_id,
                conversation_id=conversation_id,
                direction="outbound",
            )
        return SendImageResultPayload(
            success=result_success,
            account_id=account.account_id,
            conversation_id=conversation_id,
            client_request_id=client_request_id,
            message_id=result_message_id,
            error=result_error,
            message=message,
        )

    async def recall_message(
        self,
        account: AccountRecord,
        conversation_id: str,
        message_pk: str,
    ) -> RecallMessageResultPayload:
        message = await self._store.get_message(
            account.account_id,
            conversation_id,
            message_pk,
        )
        if message is None:
            return RecallMessageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                message_pk=message_pk,
                error="message not found",
            )
        if message.recalled_at is not None:
            return RecallMessageResultPayload(
                success=True,
                account_id=account.account_id,
                conversation_id=conversation_id,
                message_pk=message_pk,
                message=message,
            )
        if message.direction != "outbound" or message.send_status != "sent":
            return RecallMessageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                message_pk=message_pk,
                error="only acknowledged outbound messages can be recalled",
                message=message,
            )
        if not message.message_id:
            return RecallMessageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                message_pk=message_pk,
                error="message is missing its platform ID",
                message=message,
            )
        created_at = message.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        elapsed = (datetime.now(UTC) - created_at.astimezone(UTC)).total_seconds()
        if elapsed < -10 or elapsed > 120:
            return RecallMessageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                message_pk=message_pk,
                error="message is outside the two-minute recall window",
                message=message,
            )
        core = self._core
        if core is None:
            return RecallMessageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                message_pk=message_pk,
                error="account runtime is not running",
                message=message,
            )
        result = await core.recall_message(
            account.account_id,
            conversation_id,
            message.message_id,
        )
        if not bool(getattr(result, "success", False)):
            return RecallMessageResultPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                message_pk=message_pk,
                error=getattr(result, "error", None) or "platform did not confirm the recall",
                message=message,
            )
        recalled = await self._store.mark_message_recalled(
            account.account_id,
            conversation_id,
            message_pk,
        )
        await self._after_message_persisted(
            recalled,
            account_id=account.account_id,
            conversation_id=conversation_id,
            direction="outbound",
        )
        return RecallMessageResultPayload(
            success=True,
            account_id=account.account_id,
            conversation_id=conversation_id,
            message_pk=message_pk,
            message=recalled,
        )

    async def get_platform_blacklist(
        self,
        account: AccountRecord,
        conversation_id: str,
    ) -> PlatformBlacklistPayload:
        core = self._core
        if core is None:
            return PlatformBlacklistPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                error="account runtime is not running",
            )
        result = await core.get_platform_blacklist(account.account_id, conversation_id)
        if self._is_platform_auth_failure(getattr(result, "error", None)):
            await self._report_cookie_auth_failure(
                account.account_id,
                "conversation_blacklist_query",
                str(getattr(result, "error", "") or "平台会话已过期"),
            )
        return PlatformBlacklistPayload(
            success=bool(getattr(result, "success", False)),
            account_id=account.account_id,
            conversation_id=conversation_id,
            blocked=getattr(result, "blocked", None),
            error=getattr(result, "error", None),
        )

    async def set_platform_blacklist(
        self,
        account: AccountRecord,
        conversation_id: str,
        blocked: bool,
    ) -> PlatformBlacklistPayload:
        core = self._core
        if core is None:
            return PlatformBlacklistPayload(
                success=False,
                account_id=account.account_id,
                conversation_id=conversation_id,
                error="account runtime is not running",
            )
        result = await core.set_platform_blacklist(
            account.account_id,
            conversation_id,
            blocked,
        )
        if self._is_platform_auth_failure(getattr(result, "error", None)):
            await self._report_cookie_auth_failure(
                account.account_id,
                "conversation_blacklist_update",
                str(getattr(result, "error", "") or "平台会话已过期"),
            )
        return PlatformBlacklistPayload(
            success=bool(getattr(result, "success", False)),
            account_id=account.account_id,
            conversation_id=conversation_id,
            blocked=getattr(result, "blocked", None),
            error=getattr(result, "error", None),
        )

    async def send_delivery_record(
        self,
        account: AccountRecord,
        record_id: str,
    ) -> DeliverySendResultPayload | None:
        record = await self._store.get_delivery_record(account.account_id, record_id)
        if record is None:
            return None
        claimed = await self._store.claim_delivery_record_for_send(
            account_id=account.account_id,
            record_id=record_id,
        )
        if claimed is None:
            current = await self._store.get_delivery_record(account.account_id, record_id)
            if current is None:
                return None
            state_errors = {
                "sending": "delivery record is already being sent",
                "sent": "delivery record was already sent",
                "uncertain": "delivery result is uncertain and must be verified before retrying",
                "cancelled": "delivery record was cancelled",
            }
            return DeliverySendResultPayload(
                success=False,
                record=current,
                error=state_errors.get(current.status, "delivery record cannot be sent"),
            )
        record = claimed

        core = self._core
        if core is None:
            try:
                message = await self._store.record_message(
                    account_id=account.account_id,
                    conversation_id=record.conversation_id,
                    direction="outbound",
                    message_type="text",
                    content=record.content,
                    peer_user_id=record.receiver_user_id,
                    send_success=False,
                    send_error="account runtime is not running",
                )
            except Exception:
                logger.exception(
                    "Failed to persist unsent delivery message account=%s record=%s",
                    account.account_id,
                    record.record_id,
                )
                message = None
            updated = await self._store.update_delivery_record_after_send(
                account_id=account.account_id,
                record_id=record.record_id,
                status="failed",
                send_message_pk=getattr(message, "message_pk", None) if message else None,
                send_error="account runtime is not running",
            )
            assert updated is not None
            return DeliverySendResultPayload(
                success=False,
                record=updated,
                message=message,
                error="account runtime is not running",
            )

        try:
            result = await core.send_text(
                account.account_id,
                record.conversation_id,
                record.receiver_user_id,
                record.content,
            )
        except asyncio.CancelledError:
            await asyncio.shield(
                self._store.update_delivery_record_after_send(
                    account_id=account.account_id,
                    record_id=record.record_id,
                    status="uncertain",
                    send_error="delivery request was interrupted; platform result is uncertain",
                )
            )
            raise
        except Exception as exc:
            error = f"{exc.__class__.__name__}: {exc}"
            updated = await self._store.update_delivery_record_after_send(
                account_id=account.account_id,
                record_id=record.record_id,
                status="uncertain",
                send_error=error,
            )
            assert updated is not None
            return DeliverySendResultPayload(
                success=False,
                record=updated,
                error=error,
            )

        try:
            message = await self._store.record_message(
                account_id=account.account_id,
                conversation_id=record.conversation_id,
                direction="outbound",
                message_type="text",
                content=record.content,
                message_id=getattr(result, "message_id", None),
                peer_user_id=record.receiver_user_id,
                send_success=getattr(result, "success", False),
                send_error=getattr(result, "error", None),
                raw_payload=getattr(result, "raw_payload", None),
            )
        except Exception:
            logger.exception(
                "Failed to persist delivery message account=%s record=%s",
                account.account_id,
                record.record_id,
            )
            message = None
        success = getattr(result, "success", False)
        raw_payload = getattr(result, "raw_payload", None)
        request_was_submitted = isinstance(raw_payload, dict) and "request" in raw_payload
        final_status = "sent" if success else "uncertain" if request_was_submitted else "failed"
        updated = await self._store.update_delivery_record_after_send(
            account_id=account.account_id,
            record_id=record.record_id,
            status=final_status,
            send_message_pk=getattr(message, "message_pk", None) if message else None,
            send_error=getattr(result, "error", None),
        )
        assert updated is not None
        return DeliverySendResultPayload(
            success=success,
            record=updated,
            message=message,
            error=getattr(result, "error", None),
        )

    async def test_proxy(self, proxy: ProxyConfigPayload) -> ProxyTestPayload:
        if not proxy.enabled:
            return ProxyTestPayload(ok=False, message="代理已停用，未执行网络请求")

        validation_error = self._validate_proxy(proxy)
        if validation_error:
            return ProxyTestPayload(ok=False, message=validation_error)

        assert proxy.host is not None
        assert proxy.port is not None
        display_url = self._format_proxy_url(proxy)
        connection_url = self._connection_proxy_url(proxy)

        started = time.perf_counter()
        try:
            status_code, exit_ipv4, exit_ipv6, probe_errors = await run_external_blocking(
                self._probe_proxy, connection_url
            )
            exit_ip = exit_ipv4 or exit_ipv6
            ipv4_location = None
            ipv6_location = None
            try:
                if exit_ipv4:
                    ipv4_location = lookup_proxy_ip(exit_ipv4)
                if exit_ipv6:
                    ipv6_location = lookup_proxy_ip(exit_ipv6)
            except Exception:
                logger.warning(
                    "proxy egress location lookup failed for ipv4=%s ipv6=%s",
                    exit_ipv4,
                    exit_ipv6,
                    exc_info=True,
                )
            primary_location = ipv4_location or ipv6_location
            latency_ms = int((time.perf_counter() - started) * 1000)
            egress_labels = [
                label
                for label in (
                    f"IPv4 {exit_ipv4}" if exit_ipv4 else None,
                    f"IPv6 {exit_ipv6}" if exit_ipv6 else None,
                )
                if label
            ]
            if egress_labels:
                message = (
                    f"代理可用，出口 {'，'.join(egress_labels)}，闲鱼站点响应 {status_code}"
                )
            else:
                message = f"代理可用，闲鱼站点响应 {status_code}；出口 IP 获取失败"
                if probe_errors:
                    message += f"（已尝试 {len(probe_errors)} 个探针）"
            return ProxyTestPayload(
                ok=True,
                proxy_url=display_url,
                message=message,
                latency_ms=latency_ms,
                exit_ip=exit_ip,
                exit_ipv4=exit_ipv4,
                exit_ipv6=exit_ipv6,
                exit_country=primary_location.country if primary_location else None,
                exit_region=ipv4_location.region if ipv4_location else None,
                exit_city=ipv4_location.city if ipv4_location else None,
                exit_isp=ipv4_location.isp if ipv4_location else None,
                exit_ipv6_country=ipv6_location.country if ipv6_location else None,
                exit_ipv6_continent=ipv6_location.continent if ipv6_location else None,
                platform_status_code=status_code,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return ProxyTestPayload(
                ok=False,
                proxy_url=display_url,
                message=f"代理链路不可用：{exc}",
                latency_ms=latency_ms,
            )

    @staticmethod
    def _probe_proxy(
        proxy_url: str,
    ) -> tuple[int, str | None, str | None, list[str]]:
        with requests.Session() as session:
            session.trust_env = False
            session.proxies.update({"http": proxy_url, "https": proxy_url})
            response = session.get(
                "https://www.goofish.com/",
                timeout=8,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if response.status_code >= 500:
                raise RuntimeError(f"upstream returned HTTP {response.status_code}")

            exit_ipv4: str | None = None
            exit_ipv6: str | None = None
            probe_errors: list[str] = []
            for probe_url in settings.proxy_ip_check_urls:
                try:
                    ip_response = session.get(
                        probe_url,
                        timeout=8,
                        headers={"User-Agent": "xianyu-admin/1.0"},
                    )
                    ip_response.raise_for_status()
                    for address in AccountRuntimeManager._parse_probe_ips(ip_response):
                        if address.version == 4 and exit_ipv4 is None:
                            exit_ipv4 = str(address)
                        elif address.version == 6 and exit_ipv6 is None:
                            exit_ipv6 = str(address)
                    if exit_ipv4 and exit_ipv6:
                        break
                except Exception as exc:
                    host = urlparse(probe_url).hostname or "unknown"
                    probe_errors.append(f"{host}: {type(exc).__name__}")
                    logger.info("proxy IP probe failed via %s: %s", host, exc)
            return response.status_code, exit_ipv4, exit_ipv6, probe_errors

    @staticmethod
    def _parse_probe_ips(
        response: requests.Response,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        try:
            payload = response.json()
        except ValueError:
            payload = response.text.strip()
        if isinstance(payload, dict):
            raw = str(payload.get("ip") or payload.get("origin") or "")
        else:
            raw = str(payload)

        addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        for candidate in raw.replace("\n", ",").split(","):
            try:
                address = ipaddress.ip_address(candidate.strip())
            except ValueError:
                continue
            if address.is_global and address not in addresses:
                addresses.append(address)
        if not addresses:
            raise RuntimeError("出口 IP 查询返回无效结果")
        return addresses

    def _get_core(self) -> Any:
        if self._core is not None:
            return self._core

        from integrations.xianyu_core import XianyuCoreRuntime
        from .executors import run_media_blocking, run_platform_blocking

        self._core = XianyuCoreRuntime(
            platform_runner=run_platform_blocking,
            media_runner=run_media_blocking,
        )
        return self._core

    @staticmethod
    def _build_core_account(account: AccountRecord) -> Any:
        from integrations.xianyu_core import AccountConfig

        return AccountConfig(
            account_id=account.account_id,
            cookie=account.cookie,
            nickname=account.display_name,
            enabled=account.enabled,
            proxy=build_core_account_proxy(account),
            client_identity=account.client_identity,
            im_token=account.im_token,
            im_token_expires_at_ms=(
                int(
                    (
                        account.im_token_expires_at
                        if account.im_token_expires_at.tzinfo
                        else account.im_token_expires_at.replace(tzinfo=UTC)
                    ).timestamp()
                    * 1000
                )
                if account.im_token_expires_at
                else None
            ),
        )

    async def _handle_message(self, event: Any, *, generation: int | None = None) -> None:
        account_id = getattr(event, "account_id", None)
        conversation_id = getattr(event, "conversation_id", None)
        if not account_id or not conversation_id:
            return
        if generation is not None and not self._is_current_generation(account_id, generation):
            return

        direction = self._enum_value(getattr(event, "direction", None), "inbound")
        message_type = self._enum_value(getattr(event, "message_type", None), "unknown")
        try:
            message = await self._record_inbound_event(
                event,
                account_id=account_id,
                conversation_id=conversation_id,
                direction=direction,
                message_type=message_type,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._record_processing_error(
                account_id,
                "消息持久化失败，已转入后台重试",
                exc,
            )
            task = asyncio.create_task(
                self._retry_message_persistence(event, generation=generation),
                name=f"xianyu-message-retry:{account_id}:{conversation_id}",
            )
            self._message_retry_tasks.add(task)
            task.add_done_callback(self._message_retry_tasks.discard)
            return

        await self._after_message_persisted(
            message,
            account_id=account_id,
            conversation_id=conversation_id,
            direction=direction,
        )

    async def _record_inbound_event(
        self,
        event: Any,
        *,
        account_id: str,
        conversation_id: str,
        direction: str,
        message_type: str,
    ) -> Any:
        attachments = [
            {
                "attachment_type": str(
                    getattr(item, "attachment_type", "") or ""
                ),
                "remote_url": str(getattr(item, "remote_url", "") or ""),
                "mime_type": getattr(item, "mime_type", None),
                "size_bytes": getattr(item, "size_bytes", None),
            }
            for item in (getattr(event, "attachments", None) or [])
        ]
        return await self._store.record_message(
            account_id=account_id,
            conversation_id=conversation_id,
            direction=direction,
            message_type=message_type,
            content=getattr(event, "content", "") or "",
            message_id=getattr(event, "message_id", None),
            peer_user_id=getattr(event, "peer_user_id", None),
            peer_name=getattr(event, "peer_name", None),
            item_id=getattr(event, "item_id", None),
            raw_payload=getattr(event, "raw_payload", None),
            created_at_ms=getattr(event, "created_at_ms", None),
            attachments=attachments,
        )

    async def _retry_message_persistence(
        self,
        event: Any,
        *,
        generation: int | None,
    ) -> None:
        account_id = str(getattr(event, "account_id", "") or "")
        conversation_id = str(getattr(event, "conversation_id", "") or "")
        direction = self._enum_value(getattr(event, "direction", None), "inbound")
        message_type = self._enum_value(getattr(event, "message_type", None), "unknown")
        last_error: Exception | None = None
        for delay in (1, 3, 10):
            await asyncio.sleep(delay)
            if generation is not None and not self._is_current_generation(account_id, generation):
                return
            try:
                message = await self._record_inbound_event(
                    event,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    direction=direction,
                    message_type=message_type,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                continue
            await self._after_message_persisted(
                message,
                account_id=account_id,
                conversation_id=conversation_id,
                direction=direction,
            )
            return
        if last_error is not None:
            await self._record_processing_error(
                account_id,
                "消息持久化重试耗尽",
                last_error,
            )

    async def _after_message_persisted(
        self,
        message: Any,
        *,
        account_id: str,
        conversation_id: str,
        direction: str,
    ) -> None:
        if message:
            await realtime_broker.publish(
                {"event": "message_upsert", "data": message.model_dump(mode="json")}
            )
            try:
                conversation = await self._store.get_conversation(
                    account_id,
                    conversation_id,
                )
                if conversation is not None:
                    await realtime_broker.publish(
                        {
                            "event": "conversation_upsert",
                            "data": conversation.model_dump(mode="json"),
                        }
                    )
                list_orders = getattr(self._store, "list_orders", None)
                conversation_orders = (
                    await list_orders(
                        account_id=account_id,
                        conversation_id=conversation_id,
                        limit=20,
                    )
                    if list_orders is not None
                    else []
                )
                changed_order = next(
                    (
                        item
                        for item in conversation_orders
                        if item.source_message_pk == message.message_pk
                    ),
                    None,
                )
                if changed_order is not None:
                    await realtime_broker.publish(
                        {
                            "event": "order_upsert",
                            "account_id": account_id,
                            "data": changed_order.model_dump(mode="json"),
                        }
                    )
            except Exception as exc:
                await self._record_processing_error(
                    account_id,
                    "会话实时事件发布失败",
                    exc,
                )
            try:
                from .chatwoot import enqueue_local_message_sync

                await enqueue_local_message_sync(
                    self._store,
                    account_id=account_id,
                    message_pk=message.message_pk,
                    send_status=getattr(message, "send_status", None),
                    recalled=getattr(message, "recalled_at", None) is not None,
                )
            except Exception as exc:
                await self._record_processing_error(
                    account_id,
                    "Chatwoot 消息同步入队失败",
                    exc,
                )
        if message and direction == "inbound":
            account = await self._store.get_account(account_id)
            if account:
                await self._enqueue_side_effects(account, message)

    async def _enqueue_side_effects(self, account: AccountRecord, message: Any) -> None:
        account_id = account.account_id
        queue = self._side_effect_queues.get(account_id)
        if queue is None:
            queue = asyncio.Queue(maxsize=200)
            self._side_effect_queues[account_id] = queue
        task = self._side_effect_tasks.get(account_id)
        if task is None or task.done():
            task = asyncio.create_task(
                self._side_effect_worker(account_id, queue),
                name=f"xianyu-side-effects:{account_id}",
            )
            self._side_effect_tasks[account_id] = task
        try:
            queue.put_nowait((account, message))
        except asyncio.QueueFull:
            self._side_effect_dropped[account_id] = (
                self._side_effect_dropped.get(account_id, 0) + 1
            )
            await self._record_processing_error(
                account_id,
                "消息后处理队列已满",
                RuntimeError("notification/auto-reply queue capacity exceeded"),
            )

    async def _side_effect_worker(
        self,
        account_id: str,
        queue: asyncio.Queue[tuple[AccountRecord, Any]],
    ) -> None:
        while True:
            account, message = await queue.get()
            try:
                try:
                    await self._handle_auto_reply(account, message)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await self._record_processing_error(account_id, "自动回复处理失败", exc)
            finally:
                queue.task_done()

    async def _record_processing_error(
        self,
        account_id: str,
        prefix: str,
        exc: Exception,
    ) -> None:
        detail = f"{prefix}: {exc.__class__.__name__}: {str(exc)[:500]}"
        health = self._processing_errors.setdefault(account_id, ProcessingErrorHealth())
        health.count += 1
        health.last_error = detail
        health.last_error_at = datetime.now(UTC)
        logger.error(detail)
        try:
            await self._store.add_runtime_event(account_id, "error", detail)
        except Exception:
            logger.exception("Failed to persist runtime processing error for %s", account_id)

    async def _handle_state(
        self,
        account_id: str,
        state: Any,
        message: str | None,
        *,
        generation: int | None = None,
    ) -> None:
        if generation is not None and not self._is_current_generation(account_id, generation):
            return
        state_value = getattr(state, "value", str(state))
        if state_value not in {
            "disabled",
            "stopped",
            "connecting",
            "online",
            "reconnecting",
            "offline",
            "auth_expired",
            "risk_blocked",
            "proxy_failed",
            "error",
        }:
            state_value = "error"
        if state_value in {"auth_expired", "risk_blocked"}:
            self._desired_running[account_id] = False
        await self._store.set_runtime_state(account_id, state_value, message)
        account = await self._store.get_account(account_id)
        if account is not None:
            await realtime_broker.publish(
                {
                    "event": "account_status",
                    "account_id": account_id,
                    "data": account.runtime.to_payload().model_dump(mode="json"),
                }
            )
        try:
            from .chatwoot import enqueue_account_status_sync

            await enqueue_account_status_sync(
                self._store,
                account_id=account_id,
                state=state_value,
                message=message,
            )
        except Exception as exc:
            await self._record_processing_error(
                account_id,
                "Chatwoot 账户状态同步入队失败",
                exc,
            )
        if state_value == "online":
            self._track_maintenance_task(
                asyncio.create_task(
                    self._warm_conversations(account_id),
                    name=f"xianyu-warm-conversations:{account_id}",
                )
            )

    async def _handle_verification(
        self,
        verification: Any,
        *,
        generation: int | None = None,
    ) -> None:
        account_id = str(getattr(verification, "account_id", "") or "")
        if not account_id:
            return
        if generation is not None and not self._is_current_generation(account_id, generation):
            return
        await self._store.record_im_verification(
            account_id,
            str(getattr(verification, "reason_code", "") or "INTERACTIVE_VERIFICATION_REQUIRED"),
            getattr(verification, "verification_url", None),
            getattr(verification, "detected_at_ms", None),
        )

    async def _warm_conversations(self, account_id: str) -> None:
        await self._warm_account_conversations(account_id)

    async def _warm_account_conversations(self, account_id: str) -> None:
        async with self._conversation_warm_lock(account_id):
            full_sync = account_id not in self._conversation_full_sync_completed
            cursor: int | None = None
            pages = 0
            while True:
                last_error: Exception | None = None
                for attempt, base_delay in enumerate((0.0, 2.0, 5.0), start=1):
                    if base_delay:
                        await asyncio.sleep(base_delay + random.uniform(0, base_delay * 0.3))
                    try:
                        _, has_more, next_cursor = await self.sync_conversations(
                            account_id,
                            cursor=cursor,
                            limit=100,
                        )
                        last_error = None
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        last_error = exc
                        logger.warning(
                            "Conversation sync failed account=%s attempt=%s: %s",
                            account_id,
                            attempt,
                            exc,
                        )
                if last_error is not None:
                    account = await self._store.get_account(account_id)
                    state = account.runtime.state if account and account.runtime else "error"
                    await self._store.add_runtime_event(
                        account_id,
                        state,
                        f"会话自动同步失败：{str(last_error)[:240]}",
                    )
                    return

                pages += 1
                if not full_sync or not has_more or next_cursor is None:
                    if not has_more or next_cursor is None:
                        self._conversation_full_sync_completed.add(account_id)
                    return
                if pages >= settings.conversation_full_sync_max_pages:
                    logger.warning(
                        "Conversation full sync page limit reached account=%s pages=%s",
                        account_id,
                        pages,
                    )
                    return
                if next_cursor == cursor:
                    logger.warning(
                        "Conversation full sync cursor did not advance account=%s cursor=%s",
                        account_id,
                        cursor,
                    )
                    return
                cursor = next_cursor

    async def _reconcile_conversations_loop(self) -> None:
        interval = max(30, settings.conversation_sync_interval_seconds)
        while True:
            await asyncio.sleep(interval)
            try:
                accounts = await self._store.list_accounts()
                eligible = [
                    account
                    for account in accounts
                    if account.enabled and self.is_online(account.account_id)
                ]
                await asyncio.gather(
                    *(self._warm_conversations(account.account_id) for account in eligible),
                    return_exceptions=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Conversation reconciliation loop failed")

    async def _connection_watchdog_loop(self) -> None:
        while True:
            await asyncio.sleep(15)
            try:
                core = self._core
                accounts = await self._store.list_accounts()
                recoveries: list[Awaitable[Any]] = []
                for account in accounts:
                    if not account.enabled or not account.cookie:
                        continue
                    if not self._desired_running.get(account.account_id, False):
                        continue
                    if core is not None and core.is_account_running(account.account_id):
                        continue
                    async def recover(target: AccountRecord = account) -> None:
                        await self._store.add_runtime_event(
                            target.account_id,
                            "reconnecting",
                            "连接任务意外结束，看门狗正在恢复",
                        )
                        await self.start(target, force_restart=True)

                    recoveries.append(recover())
                if recoveries:
                    await asyncio.gather(*recoveries, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Connection watchdog scan failed")

    async def _handle_cookie_refresh(
        self,
        account_id: str,
        expected_cookie: str,
        new_cookie: str,
        *,
        generation: int | None = None,
    ) -> None:
        if generation is not None and not self._is_current_generation(account_id, generation):
            return
        persisted = await self._store.compare_and_set_account_cookie(
            account_id, expected_cookie, new_cookie
        )
        if persisted:
            return
        latest = await self._store.get_account(account_id)
        if latest is not None and latest.cookie:
            self._track_maintenance_task(
                asyncio.create_task(
                    self.replace_cookie(account_id, latest.cookie),
                    name=f"xianyu-cookie-conflict:{account_id}",
                )
            )

    async def _handle_im_token(
        self,
        account_id: str,
        token: str,
        expires_at_ms: int,
        *,
        generation: int | None = None,
    ) -> None:
        if generation is not None and not self._is_current_generation(account_id, generation):
            return
        await self._store.save_im_token(account_id, token, expires_at_ms)

    async def _handle_auto_reply(self, account: AccountRecord, inbound_message: Any) -> None:
        if getattr(inbound_message, "direction", None) != "inbound":
            return
        message_type = getattr(inbound_message, "message_type", None)
        if message_type not in {"text", "image"}:
            return

        conversation_id = getattr(inbound_message, "conversation_id", "")
        content = getattr(inbound_message, "content", "") or ""
        if not content and message_type == "image":
            content = "[图片]"
        decision = await self._store.decide_auto_reply(
            account.account_id,
            content,
            getattr(inbound_message, "conversation_id", None),
            getattr(inbound_message, "item_id", None),
            inbound_message,
        )
        if not decision.should_reply:
            return

        inbound_message_pk = getattr(inbound_message, "message_pk", None)
        reply_text = decision.reply_text
        execution_id = await self._store.claim_auto_reply_execution(
            account_id=account.account_id,
            conversation_id=conversation_id,
            inbound_message_pk=inbound_message_pk,
            rule_id=decision.rule_id,
            matched_keyword=decision.matched_keyword or (
                "AI" if decision.reason == "ai" else None
            ),
            reply_text=reply_text or "",
        )
        if execution_id is None:
            return
        if decision.reason == "ai":
            try:
                reply_text = await self._generate_ai_reply(
                    account.account_id,
                    conversation_id,
                    decision.rule_id,
                )
            except Exception as exc:
                await self._store.finish_auto_reply_execution(
                    execution_id,
                    reply_text="",
                    success=False,
                    error=str(exc),
                )
                return
        if not reply_text:
            await self._store.finish_auto_reply_execution(
                execution_id,
                reply_text="",
                success=False,
                error="empty reply",
            )
            return

        receiver_user_id = getattr(inbound_message, "peer_user_id", None)
        if not receiver_user_id:
            await self._store.finish_auto_reply_execution(
                execution_id,
                reply_text=reply_text,
                success=False,
                error="missing receiver user id",
            )
            return

        core = self._core
        if core is None:
            await self._store.finish_auto_reply_execution(
                execution_id,
                reply_text=reply_text,
                success=False,
                error="account runtime is not running",
            )
            return

        if not await self._store.auto_reply_send_allowed(
            account.account_id, conversation_id, inbound_message_pk
        ):
            await self._store.finish_auto_reply_execution(
                execution_id,
                reply_text=reply_text,
                success=False,
                error="cancelled because the conversation changed before send",
            )
            return

        result = await core.send_text(
            account.account_id,
            conversation_id,
            receiver_user_id,
            reply_text,
        )
        outbound_message = await self._store.record_message(
            account_id=account.account_id,
            conversation_id=conversation_id,
            direction="outbound",
            message_type="text",
            content=reply_text,
            message_id=getattr(result, "message_id", None),
            peer_user_id=receiver_user_id,
            send_success=getattr(result, "success", False),
            send_error=getattr(result, "error", None),
            raw_payload=getattr(result, "raw_payload", None),
        )
        await self._store.finish_auto_reply_execution(
            execution_id,
            outbound_message_pk=getattr(outbound_message, "message_pk", None)
            if outbound_message
            else None,
            reply_text=reply_text,
            success=getattr(result, "success", False),
            error=getattr(result, "error", None),
        )

    async def _generate_ai_reply(
        self,
        account_id: str,
        conversation_id: str,
        rule_id: str | None,
    ) -> str:
        config = await self._store.get_ai_reply_request(
            account_id,
            conversation_id,
            rule_id,
        )
        if config is None:
            raise RuntimeError("AI reply configuration is incomplete")
        return await run_external_blocking(self._request_ai_reply, config)

    @staticmethod
    def _request_ai_reply(config: Any) -> str:
        base_url = config.base_url.rstrip("/")
        url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.model,
                "messages": [
                    {"role": "system", "content": config.system_prompt},
                    *config.messages,
                ],
                "temperature": config.temperature,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("AI provider returned an invalid response") from exc
        reply = str(content).strip()
        if not reply:
            raise RuntimeError("AI provider returned an empty reply")
        return reply[:4000]

    @staticmethod
    def _classify_error(exc: Exception) -> RuntimeState:
        message = str(exc).lower()
        if "proxy" in message or "socks" in message:
            return "proxy_failed"
        if "cookie" in message or "token" in message or "auth" in message or "unb" in message:
            return "auth_expired"
        return "error"

    @staticmethod
    def _validate_proxy(proxy: ProxyConfigPayload) -> str | None:
        if proxy.scheme not in {"socks5", "socks5h"}:
            return "只支持 socks5 / socks5h"
        if not proxy.host:
            return "代理 Host 必填"
        if not proxy.port:
            return "代理端口必填"
        return None

    @staticmethod
    def _format_proxy_url(proxy: ProxyConfigPayload) -> str:
        auth = ""
        if proxy.username:
            auth = quote(proxy.username, safe="")
            if proxy.password:
                auth += ":******"
            auth += "@"
        return f"{proxy.scheme}://{auth}{proxy.host}:{proxy.port}"

    @staticmethod
    def _connection_proxy_url(proxy: ProxyConfigPayload) -> str:
        auth = ""
        if proxy.username:
            auth = quote(proxy.username, safe="")
            if proxy.password:
                auth += f":{quote(proxy.password, safe='')}"
            auth += "@"
        return f"{proxy.scheme}://{auth}{proxy.host}:{proxy.port}"

    async def _latest_payload(self, fallback: AccountRecord) -> AccountPayload:
        latest = await self._store.get_account(fallback.account_id)
        return latest.to_payload() if latest else fallback.to_payload()

    @staticmethod
    def _enum_value(value: Any, fallback: str) -> str:
        if value is None:
            return fallback
        return getattr(value, "value", str(value))
