"""Scheduler that only creates durable product-management tasks."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import timedelta

from .product_management_service import (
    ProductManagementRepository,
    create_and_enqueue_product_run,
    utcnow,
)
from .store import AccountStore


logger = logging.getLogger(__name__)


class ProductManagementScheduler:
    def __init__(
        self,
        store: AccountStore,
        repository: ProductManagementRepository,
        *,
        scan_seconds: int = 30,
    ) -> None:
        self.store = store
        self.repository = repository
        self.scan_seconds = max(10, scan_seconds)
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        accounts = await self.store.list_accounts()
        await self.repository.ensure_account_settings([account.account_id for account in accounts])
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run(), name="xianyu-product-management-scheduler"
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
                logger.exception("Product management scheduler scan failed")
            await asyncio.sleep(self.scan_seconds)

    async def scan_due(self) -> None:
        now = utcnow()
        accounts = await self.store.list_accounts()
        await self.repository.ensure_account_settings([account.account_id for account in accounts])
        for setting, sync_due, polish_due in await self.repository.list_due_settings(now):
            if sync_due:
                last_full = setting.last_full_sync_at
                full = last_full is None or now - last_full >= timedelta(
                    hours=setting.full_sync_interval_hours
                )
                try:
                    await create_and_enqueue_product_run(
                        self.store,
                        self.repository,
                        account_id=setting.account_id,
                        operation="sync",
                        trigger="scheduled",
                        full_sync=full,
                    )
                except Exception:
                    logger.exception(
                        "Failed to enqueue scheduled product sync account=%s",
                        setting.account_id,
                    )
                finally:
                    await self.repository.reschedule(setting.account_id, sync=True)
            if polish_due:
                try:
                    await create_and_enqueue_product_run(
                        self.store,
                        self.repository,
                        account_id=setting.account_id,
                        operation="polish",
                        trigger="scheduled",
                    )
                except Exception:
                    logger.exception(
                        "Failed to enqueue scheduled product polish account=%s",
                        setting.account_id,
                    )
                finally:
                    await self.repository.reschedule(setting.account_id, polish=True)
