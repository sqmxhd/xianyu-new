"""Queue worker for Xianyu admin background tasks."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as redis
import requests
from redis.exceptions import RedisError

from .queue import TASK_QUEUE_NAME, resolve_broker_url
from .product_publish_service import execute_product_publish
from .product_management_service import (
    ProductManagementRepository,
    ProductManagementService,
    create_and_enqueue_product_run,
)
from .order_management_service import OrderManagementRepository, OrderManagementService
from .browser_profiles import browser_profile_storage
from .executors import run_browser_blocking, run_external_blocking, run_media_blocking
from .product_images import product_image_storage
from .process_health import WORKER_HEARTBEAT_KEY
from .realtime import close_cross_process_publisher
from .schemas import BackgroundTaskCreatePayload, BackgroundTaskPayload, DeliverySendResultPayload
from .security import create_access_token
from .settings import settings
from .store import AccountStore


logger = logging.getLogger(__name__)


def _new_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def _worker_heartbeat_loop(
    worker_id: str,
    scheduled_ids: set[str],
    active_ids: set[str],
    concurrency: int,
) -> None:
    client = redis.Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )
    try:
        while True:
            payload = {
                "worker_id": worker_id,
                "process_id": os.getpid(),
                "concurrency": concurrency,
                "active_tasks": sorted(active_ids),
                "queued_tasks": max(0, len(scheduled_ids) - len(active_ids)),
                "updated_at": time.time(),
            }
            try:
                await client.set(
                    WORKER_HEARTBEAT_KEY,
                    json.dumps(payload, separators=(",", ":")),
                    ex=15,
                )
            except (RedisError, OSError):
                logger.warning("Worker heartbeat update failed", exc_info=True)
            await asyncio.sleep(5)
    finally:
        await client.aclose()


async def _stale_task_sweeper_loop(store: AccountStore) -> None:
    interval_seconds = max(5, min(settings.worker_lease_renew_seconds, 30))
    while True:
        try:
            failed_count = await store.fail_stale_background_tasks()
            if failed_count:
                logger.error(
                    "Marked %s background task(s) failed after their worker lease expired; "
                    "tasks were not replayed",
                    failed_count,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to sweep expired background task leases")
        await asyncio.sleep(interval_seconds)


async def _product_image_sweeper_loop(store: AccountStore) -> None:
    while True:
        try:
            deleted = await store.cleanup_expired_product_images()
            for account_id, asset_id in deleted:
                await run_media_blocking(product_image_storage.delete, account_id, asset_id)
            if deleted:
                logger.info("Cleaned %s expired product image asset(s)", len(deleted))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to clean expired product image assets")
        await asyncio.sleep(60 * 60)


async def _pop_redis_task_id(store: AccountStore, timeout: int = 5) -> str | None:
    _ = store
    broker_url = resolve_broker_url()
    if not broker_url:
        return None

    client = redis.Redis.from_url(
        broker_url,
        socket_connect_timeout=2,
        socket_timeout=max(5, timeout + 2),
        health_check_interval=30,
    )
    try:
        try:
            item = await client.brpop(TASK_QUEUE_NAME, timeout=timeout)
        except (RedisError, OSError):
            logger.warning("Redis task pop failed; falling back to the database", exc_info=True)
            return None
    finally:
        await client.aclose()

    if item is None:
        return None

    _, raw = item
    try:
        payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except json.JSONDecodeError:
        return None
    task_id = payload.get("task_id")
    return task_id if isinstance(task_id, str) and task_id else None


async def _next_task_id(
    store: AccountStore,
    exclude_task_ids: set[str] | None = None,
) -> str | None:
    pending = await store.get_next_pending_background_task(exclude_task_ids)
    if pending is not None:
        return pending.task_id
    return await _pop_redis_task_id(store)


def _post_delivery_to_runtime_owner(
    account_id: str,
    record_id: str,
    access_token: str,
) -> DeliverySendResultPayload:
    url = (
        f"{settings.internal_api_url}/api/accounts/{account_id}"
        f"/delivery/records/{record_id}/send"
    )
    with requests.Session() as client:
        client.trust_env = False
        response = client.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
    try:
        body = response.json()
    except ValueError:
        body = None
    if response.status_code >= 400:
        detail = body.get("detail") if isinstance(body, dict) else response.text[:300]
        raise RuntimeError(f"runtime owner rejected delivery: HTTP {response.status_code}: {detail}")
    return DeliverySendResultPayload.model_validate(body)


async def _send_delivery_through_runtime_owner(
    store: AccountStore,
    account_id: str,
    record_id: str,
) -> DeliverySendResultPayload:
    users = await store.list_users()
    admin = next((user for user in users if user.enabled and user.role == "admin"), None)
    if admin is None:
        raise RuntimeError("no enabled admin is available for the internal runtime command")
    access_token, _ = create_access_token(
        user_id=admin.user_id,
        username=admin.username,
        role=admin.role,
    )
    return await run_external_blocking(
        _post_delivery_to_runtime_owner,
        account_id,
        record_id,
        access_token,
    )


def _post_runtime_cookie_reload(account_id: str, access_token: str) -> bool:
    url = f"{settings.internal_api_url}/api/internal/accounts/{account_id}/runtime/reload-cookie"
    with requests.Session() as client:
        client.trust_env = False
        response = client.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"runtime cookie reload failed: HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        return False
    return bool(body.get("applied")) if isinstance(body, dict) else False


async def _reload_runtime_cookie(store: AccountStore, account_id: str) -> bool:
    users = await store.list_users()
    admin = next((user for user in users if user.enabled and user.role == "admin"), None)
    if admin is None:
        raise RuntimeError("no enabled admin is available for runtime cookie reload")
    access_token, _ = create_access_token(
        user_id=admin.user_id,
        username=admin.username,
        role=admin.role,
    )
    return await run_external_blocking(_post_runtime_cookie_reload, account_id, access_token)


def _is_cookie_auth_failure(error: object) -> bool:
    message = str(error or "")
    upper = message.upper()
    return bool(
        "FAIL_SYS_SESSION_EXPIRED" in upper
        or "Session过期" in message
        or "登录凭据已失效" in message
        or "登录状态已失效" in message
    )


def _post_cookie_auth_failure(
    account_id: str,
    source: str,
    message: str,
    access_token: str,
) -> None:
    url = f"{settings.internal_api_url}/api/internal/accounts/{account_id}/cookie-auth-failure"
    with requests.Session() as client:
        client.trust_env = False
        response = client.post(
            url,
            json={"source": source, "message": message[:500]},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"cookie auth failure report failed: HTTP {response.status_code}")


async def _report_cookie_auth_failure(
    store: AccountStore,
    account_id: str,
    source: str,
    message: str,
) -> None:
    users = await store.list_users()
    admin = next((user for user in users if user.enabled and user.role == "admin"), None)
    if admin is None:
        return
    access_token, _ = create_access_token(
        user_id=admin.user_id,
        username=admin.username,
        role=admin.role,
    )
    await run_external_blocking(
        _post_cookie_auth_failure,
        account_id,
        source,
        message,
        access_token,
    )


def _post_account_deletion_complete(
    account_id: str,
    task_id: str,
    access_token: str,
) -> bool:
    url = f"{settings.internal_api_url}/api/internal/accounts/{account_id}/deletion-complete"
    with requests.Session() as client:
        client.trust_env = False
        response = client.post(
            url,
            params={"task_id": task_id},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
    return response.status_code < 400


async def _notify_account_deletion_complete(
    store: AccountStore,
    account_id: str,
    task_id: str,
) -> bool:
    users = await store.list_users()
    admin = next((user for user in users if user.enabled and user.role == "admin"), None)
    if admin is None:
        return False
    access_token, _ = create_access_token(
        user_id=admin.user_id,
        username=admin.username,
        role=admin.role,
    )
    return await run_external_blocking(
        _post_account_deletion_complete,
        account_id,
        task_id,
        access_token,
    )


async def execute_task(store: AccountStore, task: BackgroundTaskPayload) -> dict[str, Any]:
    """Execute one task.

    Concrete business executors are intentionally registered by task_type.
    Unknown task types fail explicitly instead of pretending success.
    """

    if task.task_type in {"system.healthcheck", "xianyu.noop"}:
        return {
            "ok": True,
            "task_type": task.task_type,
            "worker": "xianyu_admin_api.worker",
        }

    if task.task_type == "account.delete":
        payload = task.payload if isinstance(task.payload, dict) else {}
        account_id = task.account_id or payload.get("account_id")
        if not isinstance(account_id, str) or not account_id:
            raise ValueError("account.delete requires account_id")
        await run_browser_blocking(browser_profile_storage.delete_account, account_id)
        await run_media_blocking(product_image_storage.delete_account, account_id)
        deleted = await store.delete_account(account_id)
        notified = False
        try:
            notified = await _notify_account_deletion_complete(
                store,
                account_id,
                task.task_id,
            )
        except Exception:
            notified = False
        return {
            "ok": True,
            "account_id": account_id,
            "deleted": deleted,
            "runtime_notified": notified,
        }

    if task.task_type == "delivery.send_record":
        payload = task.payload if isinstance(task.payload, dict) else {}
        account_id = task.account_id or payload.get("account_id")
        record_id = payload.get("record_id")
        if not isinstance(account_id, str) or not isinstance(record_id, str):
            raise ValueError("delivery.send_record requires account_id and record_id")

        if await store.get_account(account_id) is None:
            raise ValueError("account not found")

        result = await _send_delivery_through_runtime_owner(store, account_id, record_id)
        if not result.success:
            raise RuntimeError(result.error or "delivery send failed")
        return result.model_dump(mode="json")

    if task.task_type == "product.publish_task":
        payload = task.payload if isinstance(task.payload, dict) else {}
        account_id = task.account_id or payload.get("account_id")
        publish_task_id = payload.get("task_id")
        if not isinstance(account_id, str) or not isinstance(publish_task_id, str):
            raise ValueError("product.publish_task requires account_id and task_id")

        publish_task = await store.get_product_publish_task(account_id, publish_task_id)
        if publish_task is None:
            raise ValueError("product publish task not found")
        if publish_task.mode == "manual_export":
            draft = await store.get_product_draft(account_id, publish_task.draft_id)
            if draft is None:
                raise ValueError("product draft not found")
            updated = await store.update_product_publish_task_after_execute(
                account_id=account_id,
                task_id=publish_task_id,
                status="success",
                phase="completed",
            )
            return {
                "ok": True,
                "mode": publish_task.mode,
                "task": updated.model_dump(mode="json") if updated else None,
                "manual_export": draft.model_dump(mode="json"),
            }

        if publish_task.mode == "platform_api":
            updated, cookie_changed = await execute_product_publish(
                store,
                account_id,
                publish_task_id,
            )
            runtime_cookie_reloaded = False
            runtime_cookie_reload_error = None
            if cookie_changed:
                try:
                    runtime_cookie_reloaded = await _reload_runtime_cookie(store, account_id)
                except Exception as exc:  # Cookie is durable; watchdog can recover runtime later.
                    runtime_cookie_reload_error = str(exc)
            product_verification_task = None
            product_verification_error = None
            if updated.item_id:
                try:
                    repository = ProductManagementRepository(store.session_factory)
                    setting = await repository.get_setting(account_id)
                    delay_seconds = (
                        setting.publish_verify_delay_seconds if setting is not None else 30
                    )
                    product_verification_task = await store.create_background_task(
                        BackgroundTaskCreatePayload(
                            account_id=account_id,
                            task_type="product.verify_publish",
                            dedupe_key=f"product-publish-verify:{publish_task_id}",
                            run_after=datetime.now(UTC) + timedelta(seconds=delay_seconds),
                            payload={"account_id": account_id, "task_id": publish_task_id},
                        )
                    )
                    if product_verification_task is None:
                        raise RuntimeError("failed to create delayed product verification task")
                except Exception as exc:  # Publishing succeeded; verification is compensating work.
                    product_verification_error = str(exc)
                    logger.exception(
                        "Failed to schedule delayed product verification account=%s task=%s",
                        account_id,
                        publish_task_id,
                    )
            return {
                "ok": updated.status in {"success", "verification_required"},
                "mode": publish_task.mode,
                "task": updated.model_dump(mode="json"),
                "cookie_changed": cookie_changed,
                "runtime_cookie_reloaded": runtime_cookie_reloaded,
                "runtime_cookie_reload_error": runtime_cookie_reload_error,
                "product_verification_task": (
                    product_verification_task.model_dump(mode="json")
                    if product_verification_task
                    else None
                ),
                "product_verification_error": product_verification_error,
            }

        raise NotImplementedError(f"{publish_task.mode} product publisher is not implemented")

    if task.task_type == "product.verify_publish":
        payload = task.payload if isinstance(task.payload, dict) else {}
        account_id = task.account_id or payload.get("account_id")
        publish_task_id = payload.get("task_id")
        if not isinstance(account_id, str) or not isinstance(publish_task_id, str):
            raise ValueError("product.verify_publish requires account_id and task_id")
        publish_task = await store.get_product_publish_task(account_id, publish_task_id)
        if publish_task is None:
            raise ValueError("product publish task not found")
        if not publish_task.item_id:
            return {"ok": False, "skipped": True, "reason": "publish task has no item id"}
        repository = ProductManagementRepository(store.session_factory)
        product_sync_run, product_sync_task = await create_and_enqueue_product_run(
            store,
            repository,
            account_id=account_id,
            operation="sync",
            trigger="publish",
            full_sync=False,
        )
        return {
            "ok": True,
            "publish_task_id": publish_task_id,
            "item_id": publish_task.item_id,
            "product_sync_run": product_sync_run.model_dump(mode="json"),
            "product_sync_task": product_sync_task.model_dump(mode="json"),
        }

    if task.task_type == "product.verify_operation":
        payload = task.payload if isinstance(task.payload, dict) else {}
        account_id = task.account_id or payload.get("account_id")
        operation_run_id = payload.get("run_id")
        if not isinstance(account_id, str) or not isinstance(operation_run_id, str):
            raise ValueError("product.verify_operation requires account_id and run_id")
        repository = ProductManagementRepository(store.session_factory)
        operation_run = await repository.get_run(operation_run_id)
        if operation_run is None:
            raise ValueError("product operation run not found")
        if operation_run.operation not in {"offline", "delete"}:
            raise ValueError("product.verify_operation only supports offline or delete runs")
        if operation_run.success_count < 1:
            return {
                "ok": True,
                "skipped": True,
                "reason": "operation run has no successful writes",
            }
        product_sync_run, product_sync_task = await create_and_enqueue_product_run(
            store,
            repository,
            account_id=account_id,
            operation="sync",
            trigger="scheduled",
            full_sync=True,
        )
        return {
            "ok": True,
            "operation_run_id": operation_run_id,
            "product_sync_run": product_sync_run.model_dump(mode="json"),
            "product_sync_task": product_sync_task.model_dump(mode="json"),
        }

    if task.task_type in {
        "product.sync_account",
        "product.polish_items",
        "product.offline_items",
        "product.delete_items",
    }:
        payload = task.payload if isinstance(task.payload, dict) else {}
        account_id = task.account_id or payload.get("account_id")
        run_id = payload.get("run_id")
        if not isinstance(account_id, str) or not isinstance(run_id, str):
            raise ValueError(f"{task.task_type} requires account_id and run_id")
        repository = ProductManagementRepository(store.session_factory)
        service = ProductManagementService(store, repository)
        result = await service.execute_run(run_id)
        runtime_cookie_reloaded = False
        runtime_cookie_reload_error = None
        if result.get("cookie_changed"):
            try:
                runtime_cookie_reloaded = await _reload_runtime_cookie(store, account_id)
            except Exception as exc:
                runtime_cookie_reload_error = str(exc)
        operation_verification_task = None
        operation_verification_error = None
        run = result.get("run")
        success_count = run.get("success_count", 0) if isinstance(run, dict) else 0
        if (
            task.task_type in {"product.offline_items", "product.delete_items"}
            and result.get("ok")
            and isinstance(success_count, int)
            and success_count > 0
        ):
            try:
                setting = await repository.get_setting(account_id)
                delay_seconds = (
                    setting.publish_verify_delay_seconds if setting is not None else 30
                )
                operation_verification_task = await store.create_background_task(
                    BackgroundTaskCreatePayload(
                        account_id=account_id,
                        task_type="product.verify_operation",
                        dedupe_key=f"product-operation-verify:{run_id}",
                        run_after=datetime.now(UTC) + timedelta(seconds=delay_seconds),
                        payload={"account_id": account_id, "run_id": run_id},
                    )
                )
                if operation_verification_task is None:
                    raise RuntimeError("failed to create delayed product operation verification")
            except Exception as exc:
                operation_verification_error = str(exc)
                logger.exception(
                    "Failed to schedule product operation verification account=%s run=%s",
                    account_id,
                    run_id,
                )
        result["runtime_cookie_reloaded"] = runtime_cookie_reloaded
        result["runtime_cookie_reload_error"] = runtime_cookie_reload_error
        result["operation_verification_task"] = (
            operation_verification_task.model_dump(mode="json")
            if operation_verification_task
            else None
        )
        result["operation_verification_error"] = operation_verification_error
        if (
            not result.get("ok")
            and not result.get("uncertain")
            and not result.get("verification_required")
        ):
            error = run.get("error") if isinstance(run, dict) else None
            raise RuntimeError(str(error or f"{task.task_type} failed"))
        return result

    if task.task_type == "order.sync_account":
        payload = task.payload if isinstance(task.payload, dict) else {}
        account_id = task.account_id or payload.get("account_id")
        run_id = payload.get("run_id")
        if not isinstance(account_id, str) or not isinstance(run_id, str):
            raise ValueError("order.sync_account requires account_id and run_id")
        repository = OrderManagementRepository(store.session_factory)
        service = OrderManagementService(store, repository)
        result = await service.execute_run(run_id)
        runtime_cookie_reloaded = False
        runtime_cookie_reload_error = None
        if result.get("cookie_changed"):
            try:
                runtime_cookie_reloaded = await _reload_runtime_cookie(store, account_id)
            except Exception as exc:
                runtime_cookie_reload_error = str(exc)
        result["runtime_cookie_reloaded"] = runtime_cookie_reloaded
        result["runtime_cookie_reload_error"] = runtime_cookie_reload_error
        if not result.get("ok"):
            run = result.get("run")
            error = run.get("error") if isinstance(run, dict) else None
            raise RuntimeError(str(error or "order synchronization failed"))
        return result

    raise NotImplementedError(f"unsupported task type: {task.task_type}")


async def process_one(store: AccountStore, *, worker_id: str | None = None) -> bool:
    task_id = await _next_task_id(store)
    if not task_id:
        return False

    effective_worker_id = worker_id or _new_worker_id()
    task = await store.claim_background_task(
        task_id,
        worker_id=effective_worker_id,
        lease_seconds=settings.worker_lease_seconds,
    )
    if task is None:
        return True

    await _execute_claimed_task(store, task, worker_id=effective_worker_id)
    return True


async def _renew_task_lease(
    store: AccountStore,
    task_id: str,
    worker_id: str,
) -> None:
    interval_seconds = min(
        settings.worker_lease_renew_seconds,
        max(1, settings.worker_lease_seconds // 2),
    )
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            renewed = await store.renew_background_task_lease(
                task_id,
                worker_id=worker_id,
                lease_seconds=settings.worker_lease_seconds,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to renew background task lease task=%s", task_id)
            continue
        if not renewed:
            logger.error(
                "Background task lease ownership was lost task=%s worker=%s",
                task_id,
                worker_id,
            )
            return


async def _execute_claimed_task(
    store: AccountStore,
    task: BackgroundTaskPayload,
    *,
    worker_id: str | None = None,
) -> None:
    lease_task = (
        asyncio.create_task(
            _renew_task_lease(store, task.task_id, worker_id),
            name=f"background-task-lease:{task.task_id}",
        )
        if worker_id
        else None
    )

    async def finish(
        *,
        status: str,
        result: object | None = None,
        error: str | None = None,
    ) -> None:
        if lease_task is not None:
            lease_task.cancel()
            await asyncio.gather(lease_task, return_exceptions=True)
        completed = await store.finish_background_task(
            task.task_id,
            status=status,
            result=result,
            error=error,
            worker_id=worker_id,
        )
        if completed is None:
            logger.error(
                "Background task completion was rejected because lease ownership changed "
                "task=%s worker=%s",
                task.task_id,
                worker_id,
            )

    try:
        result = await execute_task(store, task)
    except asyncio.CancelledError:
        await asyncio.shield(
            finish(
                status="failed",
                error="worker stopped while task result may be incomplete",
            )
        )
        raise
    except Exception as exc:  # noqa: BLE001 - worker must persist operational failure.
        if task.account_id and _is_cookie_auth_failure(exc):
            try:
                await _report_cookie_auth_failure(
                    store,
                    task.account_id,
                    task.task_type,
                    str(exc),
                )
            except Exception:
                pass
        await finish(status="failed", error=str(exc))
        return

    await finish(status="success", result=result)


async def _account_consumer(
    store: AccountStore,
    queue: asyncio.Queue[BackgroundTaskPayload],
    global_slots: asyncio.Semaphore,
    scheduled_ids: set[str],
    active_ids: set[str],
    prefetch_slots: asyncio.Semaphore,
    worker_id: str | None = None,
) -> None:
    while True:
        task = await queue.get()
        try:
            async with global_slots:
                claim_kwargs = (
                    {
                        "worker_id": worker_id,
                        "lease_seconds": settings.worker_lease_seconds,
                    }
                    if worker_id
                    else {}
                )
                claimed = await store.claim_background_task(task.task_id, **claim_kwargs)
                if claimed is not None:
                    active_ids.add(task.task_id)
                    try:
                        if worker_id:
                            await _execute_claimed_task(
                                store,
                                claimed,
                                worker_id=worker_id,
                            )
                        else:
                            await _execute_claimed_task(store, claimed)
                    finally:
                        active_ids.discard(task.task_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Background account consumer failed task=%s", task.task_id)
        finally:
            scheduled_ids.discard(task.task_id)
            prefetch_slots.release()
            queue.task_done()


async def run_worker(*, once: bool = False, idle_sleep_seconds: float = 2.0) -> None:
    store = AccountStore()
    worker_id = _new_worker_id()
    if once:
        await store.fail_stale_background_tasks()
        await process_one(store, worker_id=worker_id)
        return

    concurrency = settings.worker_concurrency
    global_slots = asyncio.Semaphore(concurrency)
    prefetch_slots = asyncio.Semaphore(max(concurrency * 4, concurrency))
    account_queues: dict[str, asyncio.Queue[BackgroundTaskPayload]] = {}
    consumers: dict[str, asyncio.Task[None]] = {}
    scheduled_ids: set[str] = set()
    active_ids: set[str] = set()
    heartbeat_task = asyncio.create_task(
        _worker_heartbeat_loop(worker_id, scheduled_ids, active_ids, concurrency),
        name="background-worker-heartbeat",
    )
    stale_sweeper_task = asyncio.create_task(
        _stale_task_sweeper_loop(store),
        name="background-worker-stale-task-sweeper",
    )
    product_image_sweeper_task = asyncio.create_task(
        _product_image_sweeper_loop(store),
        name="background-worker-product-image-sweeper",
    )
    try:
        while True:
            await prefetch_slots.acquire()
            task_id = await _next_task_id(store, scheduled_ids)
            if not task_id:
                prefetch_slots.release()
                await asyncio.sleep(idle_sleep_seconds)
                continue
            task = await store.get_background_task(task_id)
            if task is None or task.status != "pending" or task.task_id in scheduled_ids:
                prefetch_slots.release()
                continue
            scheduled_ids.add(task.task_id)
            account_key = task.account_id or f"system:{task.task_id}"
            queue = account_queues.setdefault(account_key, asyncio.Queue())
            consumer = consumers.get(account_key)
            if consumer is None or consumer.done():
                consumer = asyncio.create_task(
                    _account_consumer(
                        store,
                        queue,
                        global_slots,
                        scheduled_ids,
                        active_ids,
                        prefetch_slots,
                        worker_id,
                    ),
                    name=f"background-account:{account_key}",
                )
                consumers[account_key] = consumer
            queue.put_nowait(task)
    finally:
        heartbeat_task.cancel()
        stale_sweeper_task.cancel()
        product_image_sweeper_task.cancel()
        for consumer in consumers.values():
            consumer.cancel()
        await asyncio.gather(
            heartbeat_task,
            stale_sweeper_task,
            product_image_sweeper_task,
            return_exceptions=True,
        )
        if consumers:
            await asyncio.gather(*consumers.values(), return_exceptions=True)
        await close_cross_process_publisher()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Xianyu admin background task worker")
    parser.add_argument("--once", action="store_true", help="process at most one task and exit")
    parser.add_argument("--idle-sleep", type=float, default=2.0, help="idle sleep seconds")
    args = parser.parse_args()

    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"xianyu queue worker started at {started_at}; redis configured={bool(settings.redis_url)}")
    asyncio.run(run_worker(once=args.once, idle_sleep_seconds=args.idle_sleep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
