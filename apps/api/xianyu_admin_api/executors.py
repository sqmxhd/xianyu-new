"""Bounded executors for blocking work in the single API process."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, ParamSpec, TypeVar

from .settings import settings


P = ParamSpec("P")
T = TypeVar("T")


class ExecutorSaturatedError(RuntimeError):
    """Raised before submission when a bounded executor has no queue capacity."""


class BoundedExecutor:
    """Thread pool with finite admission and cheap operational counters."""

    def __init__(
        self,
        name: str,
        *,
        max_workers: int,
        max_queue: int,
    ) -> None:
        self.name = name
        self.max_workers = max(1, max_workers)
        self.max_queue = max(0, max_queue)
        self.capacity = self.max_workers + self.max_queue
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix=f"xianyu-{name}",
        )
        self._lock = threading.Lock()
        self._queued = 0
        self._active = 0
        self._submitted = 0
        self._completed = 0
        self._failed = 0
        self._rejected = 0
        self._total_queue_wait_ms = 0.0
        self._total_duration_ms = 0.0
        self._last_duration_ms: float | None = None

    async def run(
        self,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        queued_at = time.monotonic()
        with self._lock:
            if self._queued + self._active >= self.capacity:
                self._rejected += 1
                raise ExecutorSaturatedError(
                    f"{self.name} blocking executor is saturated "
                    f"({self.capacity} active or queued calls)"
                )
            self._queued += 1
            self._submitted += 1
        state = {"queued": True}

        def invoke() -> T:
            started_at = time.monotonic()
            queue_wait_ms = (started_at - queued_at) * 1000
            with self._lock:
                if state["queued"]:
                    self._queued -= 1
                    state["queued"] = False
                self._active += 1
                self._total_queue_wait_ms += queue_wait_ms
            failed = False
            try:
                return func(*args, **kwargs)
            except BaseException:
                failed = True
                raise
            finally:
                duration_ms = (time.monotonic() - started_at) * 1000
                with self._lock:
                    self._active -= 1
                    self._completed += 1
                    self._failed += int(failed)
                    self._total_duration_ms += duration_ms
                    self._last_duration_ms = duration_ms

        loop = asyncio.get_running_loop()
        try:
            future = loop.run_in_executor(self._executor, invoke)
        except RuntimeError:
            # Submission can fail during process shutdown. The callable never ran.
            with self._lock:
                if state["queued"]:
                    self._queued -= 1
                    state["queued"] = False
            raise

        def release_cancelled(done: asyncio.Future[T]) -> None:
            if not done.cancelled():
                return
            with self._lock:
                if state["queued"]:
                    self._queued -= 1
                    state["queued"] = False

        future.add_done_callback(release_cancelled)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # A thread cannot be stopped safely. Keep account/session locks held
            # until its bounded I/O call really exits, then propagate cancellation.
            try:
                await asyncio.shield(future)
            except (Exception, asyncio.CancelledError):
                pass
            raise

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            completed = self._completed
            return {
                "name": self.name,
                "max_workers": self.max_workers,
                "max_queue": self.max_queue,
                "capacity": self.capacity,
                "active": self._active,
                "queued": self._queued,
                "submitted": self._submitted,
                "completed": completed,
                "failed": self._failed,
                "rejected": self._rejected,
                "average_queue_wait_ms": (
                    round(self._total_queue_wait_ms / completed, 2)
                    if completed
                    else 0.0
                ),
                "average_duration_ms": (
                    round(self._total_duration_ms / completed, 2)
                    if completed
                    else 0.0
                ),
                "last_duration_ms": (
                    round(self._last_duration_ms, 2)
                    if self._last_duration_ms is not None
                    else None
                ),
            }

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


db_executor = BoundedExecutor(
    "db",
    max_workers=settings.db_blocking_workers,
    max_queue=settings.db_blocking_queue,
)
platform_executor = BoundedExecutor(
    "platform",
    max_workers=settings.platform_blocking_workers,
    max_queue=settings.platform_blocking_queue,
)
media_executor = BoundedExecutor(
    "media",
    max_workers=settings.media_blocking_workers,
    max_queue=settings.media_blocking_queue,
)
external_executor = BoundedExecutor(
    "external",
    max_workers=settings.external_blocking_workers,
    max_queue=settings.external_blocking_queue,
)
browser_executor = BoundedExecutor(
    "browser",
    max_workers=settings.browser_blocking_workers,
    max_queue=settings.browser_blocking_queue,
)
qr_login_executor = BoundedExecutor(
    "qr",
    max_workers=settings.qr_login_workers,
    max_queue=settings.qr_login_max_active_sessions,
)

_EXECUTORS = (
    db_executor,
    platform_executor,
    media_executor,
    external_executor,
    browser_executor,
    qr_login_executor,
)


async def run_qr_blocking(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    return await qr_login_executor.run(partial(func, *args, **kwargs))


async def run_db_blocking(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    return await db_executor.run(func, *args, **kwargs)


async def run_platform_blocking(
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    return await platform_executor.run(func, *args, **kwargs)


async def run_media_blocking(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    return await media_executor.run(func, *args, **kwargs)


async def run_external_blocking(
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    return await external_executor.run(func, *args, **kwargs)


async def run_browser_blocking(
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    return await browser_executor.run(func, *args, **kwargs)


def executor_health() -> list[dict[str, Any]]:
    return [executor.snapshot() for executor in _EXECUTORS]


def shutdown_executors() -> None:
    for executor in _EXECUTORS:
        executor.shutdown()
