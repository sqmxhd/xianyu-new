"""Periodic read-only refreshes for active seller order details."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from contextlib import suppress
from datetime import UTC, datetime

from .order_action_service import OrderActionService
from .realtime import realtime_broker
from .store import AccountStore


logger = logging.getLogger(__name__)


class ActiveOrderRefreshScheduler:
    def __init__(
        self,
        store: AccountStore,
        service: OrderActionService,
        *,
        scan_seconds: int = 30,
        refresh_seconds: int = 90,
        jitter_seconds: int = 20,
        batch_size: int = 10,
        concurrency: int = 2,
    ) -> None:
        self.store = store
        self.service = service
        self.scan_seconds = max(10, scan_seconds)
        self.refresh_seconds = max(60, refresh_seconds)
        self.jitter_seconds = max(0, jitter_seconds)
        self.batch_size = max(1, min(batch_size, 50))
        self.concurrency = max(1, min(concurrency, 5))
        self._task: asyncio.Task[None] | None = None
        self._next_attempt_at: dict[str, float] = {}

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run(), name="xianyu-active-order-refresh-scheduler"
            )

    async def shutdown(self) -> None:
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.scan_due()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Active order detail refresh scan failed")
            await asyncio.sleep(self.scan_seconds)

    async def scan_due(self) -> None:
        orders = await self.store.list_active_seller_orders_for_refresh(
            max(self.batch_size * 5, self.batch_size)
        )
        now = datetime.now(UTC)
        now_mono = time.monotonic()
        due = []
        for order in orders:
            if self._next_attempt_at.get(order.order_pk, 0) > now_mono:
                continue
            if order.last_detail_synced_at is not None:
                age = (now - order.last_detail_synced_at).total_seconds()
                if age < self.refresh_seconds:
                    self._next_attempt_at[order.order_pk] = (
                        now_mono + self.refresh_seconds - age
                    )
                    continue
            due.append(order)
            if len(due) >= self.batch_size:
                break
        if not due:
            return
        semaphore = asyncio.Semaphore(self.concurrency)

        async def refresh_one(order) -> None:
            async with semaphore:
                await self._refresh_one(order.order_pk)

        await asyncio.gather(*(refresh_one(order) for order in due))

    async def _refresh_one(self, order_pk: str) -> None:
        now_mono = time.monotonic()
        try:
            refreshed = await self.service.refresh_scheduled(order_pk)
            self._next_attempt_at[order_pk] = (
                now_mono
                + self.refresh_seconds
                + random.randint(0, self.jitter_seconds)
            )
            await realtime_broker.publish(
                {
                    "event": "order_upsert",
                    "account_id": refreshed.account_id,
                    "data": refreshed.model_dump(mode="json"),
                }
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._next_attempt_at[order_pk] = (
                now_mono
                + max(180, self.refresh_seconds * 2)
                + random.randint(0, self.jitter_seconds)
            )
            failed = await self.store.mark_order_detail_refresh_failure(
                order_pk,
                f"{exc.__class__.__name__}: {exc}",
            )
            if failed is not None:
                await realtime_broker.publish(
                    {
                        "event": "order_upsert",
                        "account_id": failed.account_id,
                        "data": failed.model_dump(mode="json"),
                    }
                )
            logger.warning(
                "Active order detail refresh failed order_pk=%s error_type=%s",
                order_pk,
                exc.__class__.__name__,
            )
