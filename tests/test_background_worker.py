import asyncio
import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    BackgroundTaskCreatePayload,
    BackgroundTaskPayload,
    UserCreatePayload,
)
from apps.api.xianyu_admin_api.queue import TASK_QUEUE_NAME, enqueue_background_task
from apps.api.xianyu_admin_api.store import AccountStore
from apps.api.xianyu_admin_api.worker import _account_consumer, _next_task_id


class BackgroundTaskClaimTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
        self.store = AccountStore(
            session_factory=self.session_factory
        )
        account = await self.store.create_account(
            AccountCreatePayload(cookie="unb=worker")
        )
        self.task = await self.store.create_background_task(
            BackgroundTaskCreatePayload(
                account_id=account.account_id,
                task_type="xianyu.noop",
            )
        )
        assert self.task is not None

    async def test_atomic_claim_only_allows_one_winner(self) -> None:
        first, second = await asyncio.gather(
            self.store.claim_background_task(self.task.task_id),
            self.store.claim_background_task(self.task.task_id),
        )
        self.assertEqual(sum(item is not None for item in (first, second)), 1)

    async def test_database_fallback_recovers_missing_redis_delivery(self) -> None:
        with patch(
            "apps.api.xianyu_admin_api.worker._pop_redis_task_id",
            new=AsyncMock(return_value=None),
        ):
            self.assertEqual(await _next_task_id(self.store), self.task.task_id)

    async def test_database_selection_excludes_tasks_already_scheduled_locally(self) -> None:
        second = await self.store.create_background_task(
            BackgroundTaskCreatePayload(
                account_id=self.task.account_id,
                task_type="xianyu.noop",
            )
        )
        assert second is not None

        selected = await self.store.get_next_pending_background_task({self.task.task_id})

        assert selected is not None
        self.assertEqual(selected.task_id, second.task_id)

    async def test_future_task_cannot_be_selected_or_claimed_early(self) -> None:
        await self.store.finish_background_task(self.task.task_id, status="success")
        future_task = await self.store.create_background_task(
            BackgroundTaskCreatePayload(
                account_id=self.task.account_id,
                task_type="product.verify_publish",
                dedupe_key="future-product-verification",
                run_after=datetime.now(UTC) + timedelta(minutes=5),
            )
        )
        assert future_task is not None

        self.assertIsNone(await self.store.get_next_pending_background_task())
        self.assertIsNone(await self.store.claim_background_task(future_task.task_id))

        due_task = await self.store.create_background_task(
            BackgroundTaskCreatePayload(
                account_id=self.task.account_id,
                task_type="product.verify_publish",
                dedupe_key="due-product-verification",
                run_after=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        assert due_task is not None
        selected = await self.store.get_next_pending_background_task()
        assert selected is not None
        self.assertEqual(selected.task_id, due_task.task_id)

    async def test_queue_delivery_uses_fixed_redis_queue(self) -> None:
        client = AsyncMock()
        with patch(
            "apps.api.xianyu_admin_api.queue.redis.Redis.from_url",
            return_value=client,
        ):
            result = await enqueue_background_task(self.store, self.task)
        self.assertTrue(result.queued)
        self.assertEqual(result.backend, "redis")
        self.assertEqual(client.lpush.await_args.args[0], TASK_QUEUE_NAME)
        client.aclose.assert_awaited_once()

    async def test_login_records_client_ip_and_source(self) -> None:
        created = await self.store.create_user(
            UserCreatePayload(
                username="login-admin",
                password="password-123",
                role="admin",
            )
        )
        authenticated = await self.store.authenticate_user(
            created.username,
            "password-123",
            client_ip="203.0.113.9",
            login_source="x_forwarded_for",
        )
        assert authenticated is not None
        self.assertEqual(authenticated.last_login_ip, "203.0.113.9")
        self.assertEqual(authenticated.last_login_source, "x_forwarded_for")
        self.assertIsNotNone(authenticated.last_login_at)

    async def test_worker_lease_rejects_wrong_owner_and_expires_without_replay(self) -> None:
        claimed = await self.store.claim_background_task(
            self.task.task_id,
            worker_id="worker-a",
            lease_seconds=30,
        )
        assert claimed is not None
        assert claimed.lease_expires_at is not None
        self.assertEqual(claimed.worker_id, "worker-a")
        self.assertEqual(claimed.attempt_count, 1)

        self.assertFalse(
            await self.store.renew_background_task_lease(
                self.task.task_id,
                worker_id="worker-b",
                lease_seconds=30,
            )
        )
        self.assertIsNone(
            await self.store.finish_background_task(
                self.task.task_id,
                status="success",
                result={"ok": True},
                worker_id="worker-b",
            )
        )

        failed_count = await self.store.fail_stale_background_tasks(
            now=claimed.lease_expires_at + timedelta(seconds=1)
        )
        self.assertEqual(failed_count, 1)
        stored = await self.store.get_background_task(self.task.task_id)
        assert stored is not None
        self.assertEqual(stored.status, "failed")
        self.assertIsNone(stored.lease_expires_at)
        self.assertIn("was not replayed", stored.error or "")
        self.assertIsNone(
            await self.store.finish_background_task(
                self.task.task_id,
                status="success",
                result={"ok": True},
                worker_id="worker-a",
            )
        )

    async def test_retry_keeps_attempt_history_and_assigns_new_owner(self) -> None:
        claimed = await self.store.claim_background_task(
            self.task.task_id,
            worker_id="worker-a",
            lease_seconds=30,
        )
        assert claimed is not None
        await self.store.finish_background_task(
            self.task.task_id,
            status="failed",
            error="explicit failure",
            worker_id="worker-a",
        )
        reset = await self.store.reset_background_task_for_retry(self.task.task_id)
        assert reset is not None
        self.assertEqual(reset.status, "pending")
        self.assertIsNone(reset.worker_id)

        reclaimed = await self.store.claim_background_task(
            self.task.task_id,
            worker_id="worker-b",
            lease_seconds=30,
        )
        assert reclaimed is not None
        self.assertEqual(reclaimed.worker_id, "worker-b")
        self.assertEqual(reclaimed.attempt_count, 2)


class AccountConsumerTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def task(task_id: str, account_id: str) -> BackgroundTaskPayload:
        now = datetime.now(UTC)
        return BackgroundTaskPayload(
            task_id=task_id,
            account_id=account_id,
            task_type="xianyu.noop",
            status="pending",
            payload={},
            created_at=now,
            updated_at=now,
        )

    async def test_same_account_is_serial_and_other_accounts_can_overlap(self) -> None:
        tasks = {
            task.task_id: task
            for task in (
                self.task("a1", "account-a"),
                self.task("a2", "account-a"),
                self.task("b1", "account-b"),
            )
        }
        store = SimpleNamespace(
            claim_background_task=AsyncMock(side_effect=lambda task_id: tasks[task_id])
        )
        queue_a: asyncio.Queue[BackgroundTaskPayload] = asyncio.Queue()
        queue_b: asyncio.Queue[BackgroundTaskPayload] = asyncio.Queue()
        scheduled = set(tasks)
        active: set[str] = set()
        prefetch = asyncio.Semaphore(0)
        slots = asyncio.Semaphore(2)
        running_accounts: set[str] = set()
        overlap = asyncio.Event()
        order: list[str] = []

        async def execute(_store, task):  # type: ignore[no-untyped-def]
            self.assertNotIn(task.account_id, running_accounts)
            running_accounts.add(task.account_id)
            order.append(task.task_id)
            if len(running_accounts) == 2:
                overlap.set()
            try:
                await asyncio.wait_for(overlap.wait(), timeout=1)
            finally:
                running_accounts.remove(task.account_id)

        consumers = [
            asyncio.create_task(
                _account_consumer(store, queue_a, slots, scheduled, active, prefetch)
            ),
            asyncio.create_task(
                _account_consumer(store, queue_b, slots, scheduled, active, prefetch)
            ),
        ]
        with patch(
            "apps.api.xianyu_admin_api.worker._execute_claimed_task",
            new=execute,
        ):
            queue_a.put_nowait(tasks["a1"])
            queue_a.put_nowait(tasks["a2"])
            queue_b.put_nowait(tasks["b1"])
            await asyncio.wait_for(
                asyncio.gather(queue_a.join(), queue_b.join()),
                timeout=2,
            )
        for consumer in consumers:
            consumer.cancel()
        await asyncio.gather(*consumers, return_exceptions=True)
        self.assertLess(order.index("a1"), order.index("a2"))


if __name__ == "__main__":
    unittest.main()
