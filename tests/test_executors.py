import asyncio
import os
import threading
import unittest


os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from apps.api.xianyu_admin_api.executors import (
    BoundedExecutor,
    ExecutorSaturatedError,
)


class BoundedExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.executor = BoundedExecutor("test", max_workers=1, max_queue=1)

    async def asyncTearDown(self) -> None:
        self.executor.shutdown()

    async def test_capacity_is_finite_and_rejection_is_counted(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def block() -> str:
            started.set()
            release.wait(timeout=2)
            return "done"

        first = asyncio.create_task(self.executor.run(block))
        await asyncio.wait_for(asyncio.to_thread(started.wait), timeout=1)
        second = asyncio.create_task(self.executor.run(lambda: "queued"))
        while self.executor.snapshot()["queued"] != 1:
            await asyncio.sleep(0)

        with self.assertRaises(ExecutorSaturatedError):
            await self.executor.run(lambda: "rejected")

        release.set()
        self.assertEqual(await first, "done")
        self.assertEqual(await second, "queued")
        self.assertEqual(self.executor.snapshot()["rejected"], 1)

    async def test_cancellation_waits_for_running_thread_before_returning(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def block() -> None:
            started.set()
            release.wait(timeout=2)

        task = asyncio.create_task(self.executor.run(block))
        await asyncio.wait_for(asyncio.to_thread(started.wait), timeout=1)
        task.cancel()
        await asyncio.sleep(0.05)
        self.assertFalse(task.done())
        self.assertEqual(self.executor.snapshot()["active"], 1)

        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.executor.snapshot()["active"], 0)

    async def test_failure_metrics_are_recorded(self) -> None:
        def fail() -> None:
            raise ValueError("failure")

        with self.assertRaisesRegex(ValueError, "failure"):
            await self.executor.run(fail)
        snapshot = self.executor.snapshot()
        self.assertEqual(snapshot["completed"], 1)
        self.assertEqual(snapshot["failed"], 1)


if __name__ == "__main__":
    unittest.main()
