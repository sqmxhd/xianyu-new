"""Scheduler that creates durable bought and sold order synchronization tasks."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from .order_management_service import (
    OrderManagementRepository,
    create_and_enqueue_order_sync,
    utcnow,
)
from .store import AccountStore


logger = logging.getLogger(__name__)


class OrderManagementScheduler:
    def __init__(
        self,
        store: AccountStore,
        repository: OrderManagementRepository,
        *,
        scan_seconds: int = 30,
    ) -> None:
        self.store = store
        self.repository = repository
        self.scan_seconds = max(10, scan_seconds)
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        accounts = await self.store.list_accounts()
        await self.repository.ensure_account_settings(
            [account.account_id for account in accounts]
        )
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run(), name="xianyu-order-management-scheduler"
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
                logger.exception("Order management scheduler scan failed")
            await asyncio.sleep(self.scan_seconds)

    async def scan_due(self) -> None:
        accounts = await self.store.list_accounts()
        await self.repository.ensure_account_settings(
            [account.account_id for account in accounts]
        )
        for setting, mode in await self.repository.list_due_settings(utcnow()):
            try:
                await create_and_enqueue_order_sync(
                    self.store,
                    self.repository,
                    account_id=setting.account_id,
                    scope=setting.scope,
                    mode=mode,
                    trigger="scheduled",
                )
            except Exception:
                logger.exception(
                    "Failed to enqueue scheduled order sync account=%s mode=%s",
                    setting.account_id,
                    mode,
                )
            finally:
                await self.repository.reschedule(setting.account_id, mode, setting.scope)
