"""Scheduling and persistence for per-account Cookie renewal."""

from __future__ import annotations

import asyncio
import logging
import math
import random
import inspect
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from .account_network import AccountNetworkPolicyError, account_network_mode
from .cookie_renewal import CookieRenewalError, CookieRenewalService
from .executors import run_platform_blocking
from .realtime import realtime_broker
from .schemas import CookieRenewalStatusPayload
from .settings import settings
from .store import AccountRecord, AccountStore


RETRY_DELAYS = (60, 300, 1800)
logger = logging.getLogger(__name__)


class CookieRenewalCooldownError(RuntimeError):
    def __init__(self, remaining_seconds: int) -> None:
        self.remaining_seconds = max(1, remaining_seconds)
        super().__init__("manual Cookie renewal is cooling down")


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class CookieRenewalManager:
    def __init__(
        self,
        store: AccountStore,
        runtime_manager: Any,
        service: CookieRenewalService | None = None,
        *,
        enabled: bool = settings.cookie_renewal_enabled,
        interval_hours: float = settings.cookie_renewal_interval_hours,
        keepalive_seconds: int = settings.cookie_keepalive_interval_seconds,
        scan_seconds: int = settings.cookie_renewal_scan_seconds,
        manual_cooldown_seconds: int = settings.cookie_renewal_manual_cooldown_seconds,
    ) -> None:
        self._store = store
        self._runtime_manager = runtime_manager
        self._service = service or CookieRenewalService()
        self._enabled = enabled
        self._interval = timedelta(hours=max(interval_hours, 1 / 60))
        self._keepalive_interval = timedelta(seconds=max(keepalive_seconds, 60))
        self._scan_seconds = max(scan_seconds, 10)
        self._manual_cooldown = timedelta(seconds=max(manual_cooldown_seconds, 0))
        self._loop_task: asyncio.Task[None] | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._keepalive_tasks: dict[str, asyncio.Task[None]] = {}
        self._last_keepalive_at: dict[str, datetime] = {}
        self._trigger_sources: dict[str, str | None] = {}
        self._lock = asyncio.Lock()
        self._renewal_slot = asyncio.Semaphore(settings.cookie_renewal_concurrency)

    async def start(self) -> None:
        if self._enabled and (self._loop_task is None or self._loop_task.done()):
            self._loop_task = asyncio.create_task(
                self._scheduler_loop(), name="xianyu-cookie-renewal"
            )

    async def shutdown(self) -> None:
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._loop_task
        async with self._lock:
            tasks = [*self._tasks.values(), *self._keepalive_tasks.values()]
            self._tasks.clear()
            self._keepalive_tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def trigger(
        self,
        account_id: str,
        *,
        trigger: str = "manual",
        error_source: str | None = None,
    ) -> CookieRenewalStatusPayload | None:
        account = await self._store.get_account(account_id)
        if account is None:
            return None

        async with self._lock:
            existing = self._tasks.get(account_id)
            if existing is not None and not existing.done():
                return await self._store.get_cookie_renewal_status(account_id)
            current = await self._store.get_cookie_renewal_status(account_id)
            if (
                trigger == "manual"
                and self._manual_cooldown > timedelta(0)
                and current is not None
                and current.last_succeeded_at is not None
            ):
                remaining = (
                    as_utc(current.last_succeeded_at) + self._manual_cooldown - utcnow()
                ).total_seconds()
                if remaining > 0:
                    raise CookieRenewalCooldownError(math.ceil(remaining))
            status = await self._store.begin_cookie_renewal(account_id, trigger)
            if status is None:
                return None
            await self._publish_status(status)
            task = asyncio.create_task(
                self._execute(account_id), name=f"cookie-renewal:{account_id}"
            )
            self._tasks[account_id] = task
            self._trigger_sources[account_id] = error_source
            task.add_done_callback(
                lambda completed, key=account_id: self._discard_task(key, completed)
            )
            return status

    async def handle_auth_expired(
        self,
        account_id: str,
        *,
        source: str,
        message: str,
    ) -> CookieRenewalStatusPayload | None:
        """Deduplicate one HTTP recovery for an authoritative platform auth failure."""

        status = await self._store.get_cookie_renewal_status(account_id)
        if status is None:
            return None
        if status.manual_action_required:
            return status
        existing = self._tasks.get(account_id)
        if existing is not None and not existing.done():
            return status
        logger.warning(
            "Platform authentication expired account=%s source=%s: %s",
            account_id,
            source,
            message,
        )
        return await self.trigger(
            account_id,
            trigger="auth_recovery",
            error_source=source,
        )

    async def mark_login_success(
        self,
        account_id: str,
    ) -> CookieRenewalStatusPayload | None:
        status = await self._store.reset_cookie_renewal_after_login(
            account_id,
            next_attempt_at=self._next_regular_attempt(),
        )
        self._last_keepalive_at[account_id] = utcnow()
        if status is not None:
            await self._publish_status(status)
        return status

    async def _execute(self, account_id: str) -> None:
        account = await self._store.get_account(account_id)
        if account is None:
            return
        status = await self._store.get_cookie_renewal_status(account_id)
        attempt_count = status.attempt_count if status else 1
        try:
            try:
                account_network_mode(account)
            except AccountNetworkPolicyError as exc:
                raise CookieRenewalError(str(exc), kind="proxy_failed") from exc
            async with self._renewal_slot:
                result = await run_platform_blocking(
                    self._invoke_identity_aware,
                    self._service.renew,
                    account.cookie,
                    account.proxy,
                    account.client_identity,
                )
            next_attempt = self._next_regular_attempt()
            persisted_status, persisted = await self._store.persist_cookie_renewal(
                account_id,
                expected_cookie=account.cookie,
                new_cookie=result.new_cookie,
                updated_cookie_names=result.updated_cookie_names,
                message=result.message,
                next_attempt_at=next_attempt,
            )
            if persisted_status is not None:
                await self._publish_status(persisted_status)
            if not persisted:
                return

            latest = await self._store.get_account(account_id)
            runtime_applied: bool | None = None
            success_message = result.message
            if latest is not None and latest.enabled:
                try:
                    if latest.runtime and latest.runtime.state == "auth_expired":
                        started = await self._runtime_manager.start(
                            latest,
                            force_restart=True,
                        )
                        runtime_applied = started.runtime.state == "online"
                    else:
                        runtime_applied = await self._runtime_manager.replace_cookie(
                            account_id,
                            result.new_cookie,
                            mark_online=True,
                        )
                except Exception as exc:
                    runtime_applied = False
                    logger.warning(
                        "Renewed Cookie could not be applied to IM runtime account=%s: %s",
                        account_id,
                        exc,
                    )
                if runtime_applied is False:
                    success_message = f"{result.message}（IM 当前未应用，将在下次连接时使用）"
            elif latest is not None:
                success_message = f"{result.message}（账户未启用，运行时无需更新）"

            completed = await self._store.finish_cookie_renewal(
                account_id,
                message=success_message,
                runtime_applied=runtime_applied,
            )
            if completed is not None:
                await self._publish_status(completed)
        except asyncio.CancelledError:
            raise
        except CookieRenewalError as exc:
            auth_expired = exc.kind == "auth_expired"
            failed = await self._store.fail_cookie_renewal(
                account_id,
                message=(
                    f"{exc}；自动 HTTP 恢复失败，请重新扫码登录"
                    if auth_expired
                    else str(exc)
                ),
                next_attempt_at=(
                    None
                    if auth_expired
                    else self._next_failure_attempt(account, status, attempt_count)
                ),
                error_kind=exc.kind,
                phase="renewing",
                error_source=self._trigger_sources.get(account_id),
            )
            if failed is not None:
                await self._publish_status(failed)
        except Exception:
            logger.exception("Cookie renewal failed for account %s", account_id)
            failed = await self._store.fail_cookie_renewal(
                account_id,
                message="Cookie 续期发生内部错误",
                next_attempt_at=self._next_failure_attempt(account, status, attempt_count),
                error_kind="internal_error",
                phase="renewing",
                error_source=self._trigger_sources.get(account_id),
            )
            if failed is not None:
                await self._publish_status(failed)

    async def _scheduler_loop(self) -> None:
        while True:
            try:
                await self._scan_due_accounts()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Cookie renewal scheduler scan failed")
            await asyncio.sleep(self._scan_seconds)

    async def _scan_due_accounts(self) -> None:
        now = utcnow()
        for account in await self._store.list_accounts():
            if not account.enabled or not account.cookie:
                continue
            status = await self._store.get_cookie_renewal_status(account.account_id)
            if status is None:
                continue
            if status.manual_action_required:
                continue
            if account.runtime and account.runtime.state == "auth_expired":
                await self.handle_auth_expired(
                    account.account_id,
                    source="im_runtime",
                    message=account.runtime.message or "IM 运行时认证失效",
                )
                continue
            if status.next_attempt_at is None:
                scheduled = await self._store.reschedule_cookie_renewal(
                    account.account_id,
                    now + timedelta(seconds=random.uniform(5, min(300, self._scan_seconds * 2))),
                )
                if scheduled is not None:
                    await self._publish_status(scheduled)
                continue
            if status.last_succeeded_at is not None:
                base_attempt = as_utc(status.last_succeeded_at) + self._interval
                max_jitter = min(self._interval.total_seconds() * 0.1, 3600)
                if as_utc(status.next_attempt_at) > base_attempt + timedelta(
                    seconds=max_jitter + 5
                ):
                    clamped = await self._store.reschedule_cookie_renewal(
                        account.account_id,
                        max(now, base_attempt),
                    )
                    if clamped is not None:
                        status = clamped
                        await self._publish_status(clamped)
            defer_until = self._recent_success_defer_until(account, status, now)
            if defer_until is not None:
                if (
                    status.next_attempt_at is None
                    or abs(
                        (as_utc(status.next_attempt_at) - defer_until).total_seconds()
                    ) > 1
                ):
                    deferred = await self._store.reschedule_cookie_renewal(
                        account.account_id,
                        defer_until,
                    )
                    if deferred is not None:
                        status = deferred
                        await self._publish_status(deferred)
                await self._start_keepalive_if_due(account, status, now)
                continue
            if not self._is_due(account, status, now):
                await self._start_keepalive_if_due(account, status, now)
                continue
            await self.trigger(account.account_id, trigger="scheduled")

    def _is_due(
        self,
        account: AccountRecord,
        status: CookieRenewalStatusPayload,
        now: datetime,
    ) -> bool:
        if status.state in {"running", "applying"}:
            updated_at = as_utc(status.updated_at) if status.updated_at else now
            return now - updated_at >= timedelta(minutes=5)
        if status.next_attempt_at is not None:
            return as_utc(status.next_attempt_at) <= now
        return False

    def _next_regular_attempt(self) -> datetime:
        jitter_seconds = random.uniform(0, min(self._interval.total_seconds() * 0.1, 3600))
        return utcnow() + self._interval + timedelta(seconds=jitter_seconds)

    def _recent_success_defer_until(
        self,
        account: AccountRecord,
        status: CookieRenewalStatusPayload,
        now: datetime,
    ) -> datetime | None:
        if (
            status.last_succeeded_at is None
        ):
            return None
        base_attempt = as_utc(status.last_succeeded_at) + self._interval
        latest_success = next(
            (attempt for attempt in status.recent_attempts if attempt.state == "succeeded"),
            None,
        )
        defer_until = base_attempt
        if latest_success is not None and latest_success.next_attempt_at is not None:
            recorded_attempt = as_utc(latest_success.next_attempt_at)
            max_jitter = min(self._interval.total_seconds() * 0.1, 3600)
            if recorded_attempt <= base_attempt + timedelta(seconds=max_jitter + 5):
                defer_until = max(base_attempt, recorded_attempt)
        return defer_until if defer_until > now else None

    def _next_failure_attempt(
        self,
        account: AccountRecord,
        status: CookieRenewalStatusPayload | None,
        attempt_count: int,
    ) -> datetime:
        now = utcnow()
        if status is not None:
            defer_until = self._recent_success_defer_until(account, status, now)
            if defer_until is not None:
                return defer_until
        if attempt_count > len(RETRY_DELAYS):
            return self._next_regular_attempt()
        delay = RETRY_DELAYS[min(max(attempt_count - 1, 0), len(RETRY_DELAYS) - 1)]
        return now + timedelta(seconds=delay)

    def _discard_task(self, account_id: str, completed: asyncio.Task[None]) -> None:
        current = self._tasks.get(account_id)
        if current is completed:
            self._tasks.pop(account_id, None)
            self._trigger_sources.pop(account_id, None)

    async def _start_keepalive_if_due(
        self,
        account: AccountRecord,
        status: CookieRenewalStatusPayload,
        now: datetime,
    ) -> None:
        verified_at = status.last_verified_at or status.last_succeeded_at
        anchor = self._last_keepalive_at.get(account.account_id) or (
            as_utc(verified_at) if verified_at else None
        )
        if anchor is None or now - anchor < self._keepalive_interval:
            return
        if account.account_id in self._tasks:
            return
        existing = self._keepalive_tasks.get(account.account_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(
            self._run_keepalive(account.account_id),
            name=f"cookie-keepalive:{account.account_id}",
        )
        self._keepalive_tasks[account.account_id] = task
        task.add_done_callback(
            lambda completed, key=account.account_id: self._discard_keepalive_task(
                key, completed
            )
        )

    async def _run_keepalive(self, account_id: str) -> None:
        account = await self._store.get_account(account_id)
        if account is None or not account.enabled or not account.cookie:
            return
        self._last_keepalive_at[account_id] = utcnow()
        try:
            try:
                account_network_mode(account)
            except AccountNetworkPolicyError as exc:
                raise CookieRenewalError(str(exc), kind="proxy_failed") from exc
            async with self._renewal_slot:
                result = await run_platform_blocking(
                    self._invoke_identity_aware,
                    self._service.keep_alive,
                    account.cookie,
                    account.proxy,
                    account.client_identity,
                )
            status, persisted = await self._store.record_cookie_validation(
                account_id,
                expected_cookie=account.cookie,
                new_cookie=result.new_cookie,
                source="cookie_keepalive",
                message=result.message,
            )
            if not persisted:
                return
            if result.new_cookie != account.cookie:
                with suppress(Exception):
                    await self._runtime_manager.replace_cookie(account_id, result.new_cookie)
            if status is not None:
                await self._publish_status(status)
        except CookieRenewalError as exc:
            if exc.kind == "auth_expired":
                await self.handle_auth_expired(
                    account_id,
                    source="cookie_keepalive",
                    message=str(exc),
                )
                return
            state = account.runtime.state if account.runtime else "error"
            await self._store.add_runtime_event(
                account_id,
                state,
                f"Cookie 轻量验证未完成：{exc}",
            )
        except Exception:
            logger.exception("Cookie keepalive failed for account %s", account_id)

    def _discard_keepalive_task(
        self,
        account_id: str,
        completed: asyncio.Task[None],
    ) -> None:
        if self._keepalive_tasks.get(account_id) is completed:
            self._keepalive_tasks.pop(account_id, None)

    @staticmethod
    def _invoke_identity_aware(
        method: Any,
        cookie: str,
        proxy: Any,
        identity: Any,
    ) -> Any:
        """Keep compatibility with injected renewal services using the old signature."""

        parameters = inspect.signature(method).parameters
        if "identity" in parameters or len(parameters) >= 3:
            return method(cookie, proxy, identity)
        return method(cookie, proxy)

    @staticmethod
    async def _publish_status(status: CookieRenewalStatusPayload) -> None:
        try:
            await realtime_broker.publish(
                {
                    "event": "cookie_renewal_status",
                    "account_id": status.account_id,
                    "data": status.model_dump(mode="json"),
                }
            )
        except Exception:
            logger.exception(
                "Cookie renewal realtime publish failed for account %s",
                status.account_id,
            )
