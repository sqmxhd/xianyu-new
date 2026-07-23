import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from apps.api.xianyu_admin_api.runtime import AccountRuntimeManager
from apps.api.xianyu_admin_api.schemas import BackgroundTaskPayload
from apps.api.xianyu_admin_api.store import AccountRecord, RuntimeStatusRecord
from apps.api.xianyu_admin_api.worker import execute_task
from integrations.xianyu_core.models import ConnectionState, ConversationPage
from integrations.xianyu_core.client import XianyuCoreRuntime


class _RuntimeStore:
    def __init__(self, account: AccountRecord) -> None:
        self.account = account
        self.events: list[tuple[str, str | None]] = []
        self.record_error: Exception | None = None

    async def set_runtime_state(self, _account_id: str, state: str, message: str | None = None):  # type: ignore[no-untyped-def]
        self.account.runtime.state = state  # type: ignore[assignment,union-attr]
        self.account.runtime.message = message  # type: ignore[union-attr]
        return self.account.runtime

    async def get_account(self, _account_id: str) -> AccountRecord:
        return self.account

    async def add_runtime_event(self, _account_id: str, state: str, message: str | None = None) -> None:
        self.events.append((state, message))

    async def record_message(self, **_kwargs):  # type: ignore[no-untyped-def]
        if self.record_error is not None:
            raise self.record_error
        return None


class _RuntimeCore:
    def __init__(self) -> None:
        self.running = False
        self.online = False
        self.start_calls = 0
        self.start_result = True

    async def start_account(
        self,
        account,
        *,
        on_message,
        on_state,
        on_cookie,
        on_im_token,
        on_verification,
        force_restart=False,
    ):  # type: ignore[no-untyped-def]
        self.start_calls += 1
        self.running = True
        self.online = True
        await on_state(account.account_id, ConnectionState.ONLINE, None)
        return self.start_result

    async def stop_account(self, _account_id: str) -> None:
        self.running = False
        self.online = False

    async def stop_all(self) -> None:
        self.running = False
        self.online = False

    def is_account_running(self, _account_id: str) -> bool:
        return self.running

    def is_account_online(self, _account_id: str) -> bool:
        return self.online

    async def list_conversations(self, _account_id: str, *, cursor: int | None, limit: int) -> ConversationPage:
        return ConversationPage()

    def account_connection_health(self, _account_id: str):  # type: ignore[no-untyped-def]
        return {"running": self.running, "online": self.online}


class RuntimeLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def test_runtime_states_expose_contextual_recovery_actions(self) -> None:
        expected = {
            "disabled": "none",
            "deleting": "none",
            "online": "none",
            "connecting": "none",
            "reconnecting": "none",
            "stopped": "reconnect",
            "offline": "reconnect",
            "error": "reconnect",
            "risk_blocked": "verify",
            "auth_expired": "relogin",
            "proxy_failed": "fix_proxy",
        }
        for state, action in expected.items():
            with self.subTest(state=state):
                payload = RuntimeStatusRecord(
                    account_id="account-1",
                    state=state,  # type: ignore[arg-type]
                ).to_payload()
                self.assertEqual(payload.recovery_action, action)

    def make_runtime(self) -> tuple[AccountRuntimeManager, _RuntimeStore, _RuntimeCore]:
        account = AccountRecord(
            account_id="account-1",
            account_name="seller",
            cookie="unb=seller-1; _m_h5_tk=token",
        )
        store = _RuntimeStore(account)
        core = _RuntimeCore()
        runtime = AccountRuntimeManager(store)  # type: ignore[arg-type]
        runtime._core = core
        return runtime, store, core

    async def test_repeated_start_is_idempotent_but_forced_restart_is_explicit(self) -> None:
        runtime, store, core = self.make_runtime()

        await runtime.start(store.account)
        await runtime.start(store.account)
        self.assertEqual(core.start_calls, 1)

        await runtime.start(store.account, force_restart=True)
        self.assertEqual(core.start_calls, 2)
        await runtime.shutdown()

    async def test_core_stop_account_does_not_touch_other_sessions(self) -> None:
        class Session:
            def __init__(self) -> None:
                self.stopped = False

            async def stop(self) -> None:
                self.stopped = True

        runtime = XianyuCoreRuntime()
        first = Session()
        second = Session()
        runtime._sessions = {"account-1": first, "account-2": second}  # type: ignore[assignment]

        await runtime.stop_account("account-1")

        self.assertTrue(first.stopped)
        self.assertFalse(second.stopped)
        self.assertNotIn("account-1", runtime._sessions)
        self.assertIn("account-2", runtime._sessions)

    async def test_risk_blocked_account_does_not_restart_without_explicit_recovery(self) -> None:
        runtime, store, core = self.make_runtime()
        store.account.runtime.state = "risk_blocked"  # type: ignore[union-attr]

        await runtime.start(store.account)

        self.assertEqual(core.start_calls, 0)
        self.assertFalse(runtime._desired_running[store.account.account_id])
        await runtime.shutdown()

    async def test_manual_stop_disables_watchdog_recovery(self) -> None:
        runtime, store, core = self.make_runtime()

        await runtime.start(store.account)
        await runtime.stop(store.account.account_id)

        self.assertFalse(core.running)
        self.assertFalse(runtime._desired_running[store.account.account_id])
        self.assertEqual(store.account.runtime.state, "stopped")  # type: ignore[union-attr]
        await runtime.shutdown()

    async def test_online_state_wins_at_initial_wait_timeout_boundary(self) -> None:
        runtime, store, core = self.make_runtime()
        core.start_result = False

        await runtime.start(store.account)

        self.assertTrue(core.online)
        self.assertEqual(store.account.runtime.state, "online")  # type: ignore[union-attr]
        await runtime.shutdown()

    async def test_message_persistence_failure_is_retried_without_state_change(self) -> None:
        runtime, store, _core = self.make_runtime()
        store.record_error = RuntimeError("database unavailable")
        event = SimpleNamespace(
            account_id="account-1",
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="hello",
            message_id="message-1",
            peer_user_id="buyer-1",
            peer_name="buyer",
            item_id=None,
            raw_payload={},
            created_at_ms=1_700_000_000_000,
        )

        await runtime._handle_message(event)

        self.assertEqual(store.account.runtime.state, "stopped")  # type: ignore[union-attr]
        self.assertEqual(len(runtime._message_retry_tasks), 1)
        self.assertIn("后台重试", store.events[0][1])
        await runtime.shutdown()

    async def test_persisted_message_fetches_conversation_directly_for_realtime(self) -> None:
        conversation = SimpleNamespace(
            conversation_id="conversation-beyond-list-limit",
            model_dump=lambda **_kwargs: {"conversation_id": "conversation-beyond-list-limit"},
        )
        store = SimpleNamespace(
            get_conversation=AsyncMock(return_value=conversation),
        )
        runtime = AccountRuntimeManager(store)  # type: ignore[arg-type]
        message = SimpleNamespace(
            message_pk="message-1",
            model_dump=lambda **_kwargs: {"message_pk": "message-1"},
        )
        publish = AsyncMock()

        with patch(
            "apps.api.xianyu_admin_api.runtime.realtime_broker.publish",
            new=publish,
        ):
            await runtime._after_message_persisted(
                message,
                account_id="account-1",
                conversation_id="conversation-beyond-list-limit",
                direction="outbound",
            )

        store.get_conversation.assert_awaited_once_with(
            "account-1",
            "conversation-beyond-list-limit",
        )
        self.assertEqual(publish.await_count, 2)
        self.assertEqual(publish.await_args_list[1].args[0]["event"], "conversation_upsert")


class _WorkerStore:
    async def get_account(self, _account_id: str):  # type: ignore[no-untyped-def]
        return object()


class WorkerRuntimeOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_product_publish_schedules_one_durable_delayed_verification(self) -> None:
        now = datetime.now(UTC)
        task = BackgroundTaskPayload(
            task_id="publish-background-task",
            account_id="account-1",
            task_type="product.publish_task",
            payload={"account_id": "account-1", "task_id": "publish-task-1"},
            created_at=now,
            updated_at=now,
        )
        publish_task = SimpleNamespace(mode="platform_api")
        updated = SimpleNamespace(
            item_id="item-1",
            status="success",
            model_dump=lambda mode=None: {"task_id": "publish-task-1", "item_id": "item-1"},
        )

        async def create_scheduled(payload):  # type: ignore[no-untyped-def]
            return BackgroundTaskPayload(
                task_id="verification-task-1",
                account_id=payload.account_id,
                task_type=payload.task_type,
                dedupe_key=payload.dedupe_key,
                run_after=payload.run_after,
                payload=payload.payload,
                created_at=now,
                updated_at=now,
            )

        store = SimpleNamespace(
            session_factory=object(),
            get_product_publish_task=AsyncMock(return_value=publish_task),
            create_background_task=AsyncMock(side_effect=create_scheduled),
        )
        repository = SimpleNamespace(
            get_setting=AsyncMock(return_value=SimpleNamespace(publish_verify_delay_seconds=45))
        )
        started_at = datetime.now(UTC)
        with (
            patch(
                "apps.api.xianyu_admin_api.worker.execute_product_publish",
                new=AsyncMock(return_value=(updated, False)),
            ),
            patch(
                "apps.api.xianyu_admin_api.worker.ProductManagementRepository",
                return_value=repository,
            ),
        ):
            output = await execute_task(store, task)  # type: ignore[arg-type]
        finished_at = datetime.now(UTC)

        self.assertTrue(output["ok"])
        store.create_background_task.assert_awaited_once()
        payload = store.create_background_task.await_args.args[0]
        self.assertEqual(payload.task_type, "product.verify_publish")
        self.assertEqual(payload.dedupe_key, "product-publish-verify:publish-task-1")
        self.assertGreaterEqual(payload.run_after, started_at + timedelta(seconds=45))
        self.assertLessEqual(payload.run_after, finished_at + timedelta(seconds=45))

    async def test_product_write_schedules_delayed_catalog_reconciliation(self) -> None:
        now = datetime.now(UTC)
        task = BackgroundTaskPayload(
            task_id="offline-background-task",
            account_id="account-1",
            task_type="product.offline_items",
            payload={"account_id": "account-1", "run_id": "operation-run-1"},
            created_at=now,
            updated_at=now,
        )

        async def create_scheduled(payload):  # type: ignore[no-untyped-def]
            return BackgroundTaskPayload(
                task_id="operation-verification-task",
                account_id=payload.account_id,
                task_type=payload.task_type,
                dedupe_key=payload.dedupe_key,
                run_after=payload.run_after,
                payload=payload.payload,
                created_at=now,
                updated_at=now,
            )

        store = SimpleNamespace(
            session_factory=object(),
            create_background_task=AsyncMock(side_effect=create_scheduled),
        )
        repository = SimpleNamespace(
            get_setting=AsyncMock(return_value=SimpleNamespace(publish_verify_delay_seconds=30))
        )
        service = SimpleNamespace(
            execute_run=AsyncMock(
                return_value={
                    "ok": True,
                    "cookie_changed": False,
                    "run": {"run_id": "operation-run-1", "success_count": 1},
                }
            )
        )
        started_at = datetime.now(UTC)
        with (
            patch(
                "apps.api.xianyu_admin_api.worker.ProductManagementRepository",
                return_value=repository,
            ),
            patch(
                "apps.api.xianyu_admin_api.worker.ProductManagementService",
                return_value=service,
            ),
        ):
            output = await execute_task(store, task)  # type: ignore[arg-type]
        finished_at = datetime.now(UTC)

        self.assertTrue(output["ok"])
        store.create_background_task.assert_awaited_once()
        payload = store.create_background_task.await_args.args[0]
        self.assertEqual(payload.task_type, "product.verify_operation")
        self.assertEqual(payload.dedupe_key, "product-operation-verify:operation-run-1")
        self.assertGreaterEqual(payload.run_after, started_at + timedelta(seconds=30))
        self.assertLessEqual(payload.run_after, finished_at + timedelta(seconds=30))

    async def test_product_operation_verification_enqueues_full_catalog_sync(self) -> None:
        now = datetime.now(UTC)
        task = BackgroundTaskPayload(
            task_id="operation-verification-task",
            account_id="account-1",
            task_type="product.verify_operation",
            payload={"account_id": "account-1", "run_id": "operation-run-1"},
            created_at=now,
            updated_at=now,
        )
        repository = SimpleNamespace(
            get_run=AsyncMock(
                return_value=SimpleNamespace(operation="offline", success_count=1)
            )
        )
        store = SimpleNamespace(session_factory=object())
        sync_run = SimpleNamespace(model_dump=lambda mode=None: {"run_id": "sync-run"})
        sync_task = SimpleNamespace(model_dump=lambda mode=None: {"task_id": "sync-task"})
        enqueue = AsyncMock(return_value=(sync_run, sync_task))

        with (
            patch(
                "apps.api.xianyu_admin_api.worker.ProductManagementRepository",
                return_value=repository,
            ),
            patch(
                "apps.api.xianyu_admin_api.worker.create_and_enqueue_product_run",
                new=enqueue,
            ),
        ):
            output = await execute_task(store, task)  # type: ignore[arg-type]

        self.assertTrue(output["ok"])
        enqueue.assert_awaited_once_with(
            store,
            repository,
            account_id="account-1",
            operation="sync",
            trigger="scheduled",
            full_sync=True,
        )

    async def test_delete_route_stops_only_target_and_queues_cleanup(self) -> None:
        from apps.api.xianyu_admin_api import main

        now = datetime.now(UTC)
        account = AccountRecord(
            account_id="account-delete",
            account_name="delete-me",
            cookie="unb=delete-me; _m_h5_tk=token",
        )
        task = BackgroundTaskPayload(
            task_id="delete-task-route",
            account_id=account.account_id,
            task_type="account.delete",
            payload={"account_id": account.account_id},
            created_at=now,
            updated_at=now,
        )

        class Store:
            async def get_account(self, _account_id: str):  # type: ignore[no-untyped-def]
                return account

            async def set_runtime_state(self, _account_id: str, state: str, message: str):  # type: ignore[no-untyped-def]
                account.runtime.state = state  # type: ignore[assignment,union-attr]
                account.runtime.message = message  # type: ignore[union-attr]

            async def create_background_task(self, _payload):  # type: ignore[no-untyped-def]
                return task

            async def get_background_task(self, _task_id: str):  # type: ignore[no-untyped-def]
                return task

        prepare_delete = AsyncMock(return_value=True)
        prepare_browser_delete = AsyncMock()
        enqueue = AsyncMock()
        with (
            patch.object(main, "store", Store()),
            patch.object(main.runtime_manager, "prepare_delete", prepare_delete),
            patch.object(
                main.im_verification_manager,
                "prepare_account_deletion",
                prepare_browser_delete,
            ),
            patch.object(main.realtime_broker, "publish", new=AsyncMock()),
            patch.object(main, "_enqueue_or_fail", enqueue),
        ):
            result = await main.delete_account(account.account_id)

        prepare_delete.assert_awaited_once_with(account.account_id, timeout=5)
        prepare_browser_delete.assert_awaited_once_with(account.account_id)
        enqueue.assert_awaited_once_with(task)
        self.assertEqual(result.task_id, task.task_id)
        self.assertEqual(account.runtime.state, "deleting")  # type: ignore[union-attr]

    async def test_delivery_task_delegates_to_runtime_owner(self) -> None:
        now = datetime.now(UTC)
        task = BackgroundTaskPayload(
            task_id="task-1",
            account_id="account-1",
            task_type="delivery.send_record",
            payload={"record_id": "record-1"},
            created_at=now,
            updated_at=now,
        )
        result = SimpleNamespace(
            success=True,
            error=None,
            model_dump=lambda mode=None: {"success": True, "record": {"record_id": "record-1"}},
        )

        store = _WorkerStore()
        with patch(
            "apps.api.xianyu_admin_api.worker._send_delivery_through_runtime_owner",
            new=AsyncMock(return_value=result),
        ) as delegated:
            output = await execute_task(store, task)  # type: ignore[arg-type]

        delegated.assert_awaited_once_with(ANY, "account-1", "record-1")
        self.assertTrue(output["success"])

    async def test_delivery_enqueue_is_idempotent_for_the_same_record(self) -> None:
        from apps.api.xianyu_admin_api import main

        now = datetime.now(UTC)
        account = AccountRecord(
            account_id="account-delivery",
            account_name="delivery-account",
            cookie="unb=delivery; _m_h5_tk=token",
        )
        record = SimpleNamespace(record_id="record-idempotent", status="pending")
        task = BackgroundTaskPayload(
            task_id="delivery-task-idempotent",
            account_id=account.account_id,
            task_type="delivery.send_record",
            dedupe_key="delivery-send:record-idempotent",
            payload={"account_id": account.account_id, "record_id": record.record_id},
            created_at=now,
            updated_at=now,
        )
        store = SimpleNamespace(
            get_account=AsyncMock(return_value=account),
            get_delivery_record=AsyncMock(return_value=record),
            create_background_task=AsyncMock(return_value=task),
            reset_background_task_for_retry=AsyncMock(return_value=None),
            get_background_task=AsyncMock(return_value=task),
        )

        async def mark_queued(created: BackgroundTaskPayload) -> None:
            created.queued_at = now

        enqueue = AsyncMock(side_effect=mark_queued)
        main.delivery_enqueue_locks.pop(record.record_id, None)
        try:
            with (
                patch.object(main, "store", store),
                patch.object(main, "_enqueue_or_fail", enqueue),
            ):
                first = await main.enqueue_delivery_record(account.account_id, record.record_id)
                second = await main.enqueue_delivery_record(account.account_id, record.record_id)
        finally:
            main.delivery_enqueue_locks.pop(record.record_id, None)

        self.assertEqual(first.task_id, second.task_id)
        self.assertEqual(enqueue.await_count, 1)
        self.assertEqual(store.create_background_task.await_count, 2)
        payload = store.create_background_task.await_args.args[0]
        self.assertEqual(payload.dedupe_key, "delivery-send:record-idempotent")

    async def test_account_delete_runs_in_worker_and_notifies_runtime_owner(self) -> None:
        now = datetime.now(UTC)
        task = BackgroundTaskPayload(
            task_id="delete-task-1",
            account_id="account-1",
            task_type="account.delete",
            payload={"account_id": "account-1"},
            created_at=now,
            updated_at=now,
        )

        store = SimpleNamespace(delete_account=AsyncMock(return_value=True))
        with (
            patch(
                "apps.api.xianyu_admin_api.worker.browser_profile_storage.delete_account"
            ) as delete_browser_profile,
            patch(
                "apps.api.xianyu_admin_api.worker.product_image_storage.delete_account"
            ) as delete_images,
            patch(
                "apps.api.xianyu_admin_api.worker._notify_account_deletion_complete",
                new=AsyncMock(return_value=True),
            ) as notify,
        ):
            output = await execute_task(store, task)  # type: ignore[arg-type]

        store.delete_account.assert_awaited_once_with("account-1")
        delete_browser_profile.assert_called_once_with("account-1")
        delete_images.assert_called_once_with("account-1")
        notify.assert_awaited_once_with(store, "account-1", "delete-task-1")
        self.assertTrue(output["deleted"])


if __name__ == "__main__":
    unittest.main()
