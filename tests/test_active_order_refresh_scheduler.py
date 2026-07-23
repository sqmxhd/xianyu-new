import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from apps.api.xianyu_admin_api.active_order_refresh_scheduler import (
    ActiveOrderRefreshScheduler,
)


class _Payload(SimpleNamespace):
    def model_dump(self, **_kwargs):
        return dict(self.__dict__)


class ActiveOrderRefreshSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_due_active_order_is_refreshed_once_and_throttled(self) -> None:
        order = _Payload(
            order_pk="order-pk-1",
            account_id="account-1",
            last_detail_synced_at=None,
        )
        refreshed = _Payload(order_pk="order-pk-1", account_id="account-1")
        store = SimpleNamespace(
            list_active_seller_orders_for_refresh=AsyncMock(return_value=[order]),
            mark_order_detail_refresh_failure=AsyncMock(),
        )
        service = SimpleNamespace(
            refresh_scheduled=AsyncMock(return_value=refreshed)
        )
        scheduler = ActiveOrderRefreshScheduler(
            store,
            service,
            refresh_seconds=60,
            jitter_seconds=0,
            batch_size=5,
        )

        await scheduler.scan_due()
        await scheduler.scan_due()

        service.refresh_scheduled.assert_awaited_once_with("order-pk-1")
        store.mark_order_detail_refresh_failure.assert_not_awaited()

    async def test_refresh_failure_is_persisted_and_backed_off(self) -> None:
        order = _Payload(
            order_pk="order-pk-2",
            account_id="account-1",
            last_detail_synced_at=None,
        )
        failed = _Payload(order_pk="order-pk-2", account_id="account-1")
        store = SimpleNamespace(
            list_active_seller_orders_for_refresh=AsyncMock(return_value=[order]),
            mark_order_detail_refresh_failure=AsyncMock(return_value=failed),
        )
        service = SimpleNamespace(
            refresh_scheduled=AsyncMock(side_effect=RuntimeError("temporary"))
        )
        scheduler = ActiveOrderRefreshScheduler(
            store,
            service,
            refresh_seconds=60,
            jitter_seconds=0,
        )

        await scheduler.scan_due()
        await scheduler.scan_due()

        service.refresh_scheduled.assert_awaited_once_with("order-pk-2")
        store.mark_order_detail_refresh_failure.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
