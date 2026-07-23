"""In-process diagnostics for the single API/IM runtime."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import deque
from contextlib import suppress
from datetime import UTC, datetime
from math import ceil
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from .executors import executor_health
from .settings import settings


WORKER_HEARTBEAT_KEY = "xianyu:worker:heartbeat"


class EventLoopMonitor:
    def __init__(self) -> None:
        self._interval = settings.event_loop_monitor_interval_seconds
        self._warning = settings.event_loop_lag_warning_seconds
        self._samples: deque[float] = deque(
            maxlen=max(10, ceil(60 / self._interval))
        )
        self._task: asyncio.Task[None] | None = None
        self._started_at = datetime.now(UTC)
        self._started_monotonic = time.monotonic()
        self._last_sample_at: datetime | None = None
        self._consecutive_warnings = 0
        self._warning_count = 0

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run(),
                name="event-loop-health-monitor",
            )

    async def shutdown(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            expected = asyncio.get_running_loop().time() + self._interval
            await asyncio.sleep(self._interval)
            lag = max(0.0, asyncio.get_running_loop().time() - expected)
            self.record(lag)

    def record(self, lag_seconds: float) -> None:
        lag_ms = max(0.0, lag_seconds * 1000)
        self._samples.append(lag_ms)
        self._last_sample_at = datetime.now(UTC)
        if lag_seconds >= self._warning:
            self._consecutive_warnings += 1
            self._warning_count += 1
        else:
            self._consecutive_warnings = 0

    def snapshot(self) -> dict[str, Any]:
        samples = sorted(self._samples)
        p95 = samples[max(0, ceil(len(samples) * 0.95) - 1)] if samples else 0.0
        current = self._samples[-1] if self._samples else 0.0
        maximum = samples[-1] if samples else 0.0
        status = "critical" if maximum >= 1000 else "warning" if p95 >= 100 else "healthy"
        return {
            "status": status,
            "current_lag_ms": round(current, 2),
            "max_lag_ms_60s": round(maximum, 2),
            "p95_lag_ms_60s": round(p95, 2),
            "sample_count": len(samples),
            "consecutive_warnings": self._consecutive_warnings,
            "warning_count": self._warning_count,
            "last_sample_at": self._last_sample_at,
        }

    async def process_snapshot(self, realtime: dict[str, Any]) -> dict[str, Any]:
        return {
            "process_id": os.getpid(),
            "started_at": self._started_at,
            "uptime_seconds": round(time.monotonic() - self._started_monotonic, 1),
            "thread_count": threading.active_count(),
            "event_loop": self.snapshot(),
            "executors": executor_health(),
            "realtime": realtime,
            "worker": await read_worker_heartbeat(),
        }


async def read_worker_heartbeat() -> dict[str, Any]:
    client = redis.Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=1,
        socket_timeout=2,
    )
    try:
        raw = await client.get(WORKER_HEARTBEAT_KEY)
    except (RedisError, OSError) as exc:
        return {"online": False, "error": f"{exc.__class__.__name__}: {str(exc)[:200]}"}
    finally:
        await client.aclose()
    if not raw:
        return {"online": False}
    try:
        payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"online": False, "error": "invalid worker heartbeat payload"}
    if not isinstance(payload, dict):
        return {"online": False, "error": "invalid worker heartbeat payload"}
    updated_at = payload.get("updated_at")
    try:
        age = max(0.0, time.time() - float(updated_at))
    except (TypeError, ValueError):
        age = None
    return {
        **payload,
        "online": age is not None and age <= 15,
        "heartbeat_age_seconds": round(age, 1) if age is not None else None,
    }


event_loop_monitor = EventLoopMonitor()
