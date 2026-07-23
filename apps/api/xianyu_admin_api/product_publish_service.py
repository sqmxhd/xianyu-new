"""Business orchestration for account-scoped product publish tasks."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import redis.asyncio as redis
from redis.exceptions import LockError

from integrations.xianyu_core import (
    AccountConfig,
    MtopProductPublisher,
    ProductImageData,
    ProductPublishError,
    ProductPublishRequest,
)

from .account_network import build_core_account_proxy
from .schemas import (
    ProductLocationListPayload,
    ProductLocationOptionPayload,
    ProductPublishTaskPayload,
)
from .executors import run_media_blocking, run_platform_blocking
from .product_images import product_image_storage
from .realtime import publish_cross_process
from .settings import settings
from .store import AccountRecord, AccountStore


PublisherFactory = Callable[..., MtopProductPublisher]
logger = logging.getLogger(__name__)
PRODUCT_LOCATION_CACHE_TTL = timedelta(minutes=15)
PRODUCT_LOCATION_STALE_TTL = timedelta(hours=24)
_product_location_locks: dict[str, asyncio.Lock] = {}


class ProductPublishLockError(RuntimeError):
    """Another worker is already changing products for the same account."""


async def _renew_product_operation_lock(lock: redis.lock.Lock) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            if not await lock.extend(15 * 60, replace_ttl=True):
                return
        except Exception:
            logger.exception("Failed to renew account product-operation lock")
            return


@asynccontextmanager
async def account_product_operation_lock(account_id: str):
    client = redis.Redis.from_url(settings.redis_url)
    lock = client.lock(
        f"xianyu:lock:product-operation:{account_id}",
        timeout=15 * 60,
        blocking_timeout=15 * 60,
    )
    acquired = False
    renew_task: asyncio.Task[None] | None = None
    try:
        acquired = bool(await lock.acquire())
        if not acquired:
            raise ProductPublishLockError("该账户已有商品发布任务正在执行")
        renew_task = asyncio.create_task(
            _renew_product_operation_lock(lock),
            name=f"product-operation-lock-renewal:{account_id}",
        )
        yield
    finally:
        if renew_task is not None:
            renew_task.cancel()
            with suppress(asyncio.CancelledError):
                await renew_task
        if acquired:
            try:
                await lock.release()
            except LockError:
                pass
        await client.aclose()


account_publish_lock = account_product_operation_lock


async def execute_product_publish(
    store: AccountStore,
    account_id: str,
    task_id: str,
    *,
    publisher_factory: PublisherFactory = MtopProductPublisher,
) -> tuple[ProductPublishTaskPayload, bool]:
    """Execute exactly one pending platform task and persist every terminal state."""

    task = await store.get_product_publish_task(account_id, task_id)
    if task is None:
        raise ValueError("product publish task not found")
    if task.status != "pending":
        return task, False
    if task.mode != "platform_api":
        raise ValueError(f"unsupported product publish mode: {task.mode}")

    account = await store.get_account(account_id)
    if account is None:
        raise ValueError("account not found")

    async with account_publish_lock(account_id):
        task = await store.get_product_publish_task(account_id, task_id)
        if task is None:
            raise ValueError("product publish task not found")
        if task.status != "pending":
            return task, False

        starting = await store.update_product_publish_task_after_execute(
            account_id=account_id,
            task_id=task_id,
            status="running",
            phase="starting",
            error=None,
        )
        if starting is not None:
            await _publish_task_realtime(starting)
        loop = asyncio.get_running_loop()

        async def persist_progress(phase: str) -> None:
            updated = await store.update_product_publish_task_after_execute(
                account_id=account_id,
                task_id=task_id,
                status="running",
                phase=phase,
                error=None,
            )
            if updated is not None:
                await _publish_task_realtime(updated)

        def update_progress(phase: str) -> None:
            future = asyncio.run_coroutine_threadsafe(
                persist_progress(phase),
                loop,
            )
            try:
                future.result(timeout=10)
            except Exception:
                logger.warning(
                    "Failed to persist product publish progress account=%s task=%s phase=%s",
                    account_id,
                    task_id,
                    phase,
                    exc_info=True,
                )

        cookie_changed = False
        try:
            request = await _request_from_snapshot(
                store,
                account_id,
                task.snapshot,
                task.unique_code,
            )
            publisher = publisher_factory(
                _to_core_account(account),
                progress_handler=update_progress,
            )
            try:
                result = await run_platform_blocking(publisher.publish, request)
            finally:
                publisher.close()
            cookie_changed = await merge_account_cookie_updates(
                store,
                account_id,
                result.cookie_updates,
            )
            status = "success" if result.verified else "verification_required"
            updated = await store.update_product_publish_task_after_execute(
                account_id=account_id,
                task_id=task_id,
                status=status,
                phase="completed" if result.verified else "verification_required",
                item_id=result.item_id,
                item_url=result.item_url,
                failure_kind=None if result.verified else "verification_required",
                error=None if result.verified else "商品已返回 ID，但列表核验未通过，请到闲鱼确认",
                raw_result=dict(result.raw_response),
                retryable=False,
                result_certainty="confirmed_success" if result.verified else "published_unconfirmed",
            )
            if updated is None:
                raise RuntimeError("product publish task disappeared after execution")
            await _publish_task_realtime(updated)
            return updated, cookie_changed
        except ProductPublishError as exc:
            cookie_changed = await merge_account_cookie_updates(
                store,
                account_id,
                exc.cookie_updates,
            )
            status = "verification_required" if exc.uncertain else "failed"
            updated = await store.update_product_publish_task_after_execute(
                account_id=account_id,
                task_id=task_id,
                status=status,
                phase="verification_required" if exc.uncertain else "failed",
                failure_kind=exc.kind,
                error=str(exc),
                raw_result=exc.raw_response,
                retryable=bool(exc.retryable and not exc.uncertain),
                result_certainty="result_unknown" if exc.uncertain else "confirmed_failed",
            )
            if updated is not None:
                await _publish_task_realtime(updated)
            raise
        except Exception as exc:
            updated = await store.update_product_publish_task_after_execute(
                account_id=account_id,
                task_id=task_id,
                status="failed",
                phase="failed",
                failure_kind="internal",
                error=str(exc),
                retryable=False,
                result_certainty="confirmed_failed",
            )
            if updated is not None:
                await _publish_task_realtime(updated)
            raise


async def _publish_task_realtime(task: ProductPublishTaskPayload) -> None:
    await publish_cross_process(
        {
            "event": "product_publish_task_upsert",
            "account_id": task.account_id,
            "data": task.model_dump(mode="json"),
        }
    )


async def list_platform_product_locations(
    store: AccountStore,
    account_id: str,
    *,
    longitude: float = 118.78248347393424,
    latitude: float = 31.91629189813543,
    force_refresh: bool = False,
    publisher_factory: PublisherFactory = MtopProductPublisher,
) -> ProductLocationListPayload:
    account = await store.get_account(account_id)
    if account is None:
        raise ValueError("account not found")
    cache_key = _product_location_cache_key(longitude, latitude)
    lock_key = f"{account_id}:{cache_key}"
    lock = _product_location_locks.setdefault(lock_key, asyncio.Lock())
    async with lock:
        cache = await store.get_product_location_cache(account_id, cache_key)
        cached_items = _validate_cached_product_locations(cache.options if cache else [])
        now = datetime.now(UTC)
        cache_age = now - cache.fetched_at if cache is not None else None
        if (
            not force_refresh
            and cache is not None
            and cached_items
            and cache_age is not None
            and cache_age <= PRODUCT_LOCATION_CACHE_TTL
        ):
            catalog_items = await store.upsert_product_platform_locations(account_id, cached_items)
            return ProductLocationListPayload(
                items=catalog_items or cached_items,
                data_source="cache",
                fetched_at=cache.fetched_at,
            )

        publisher = publisher_factory(_to_core_account(account))
        try:
            candidates = await run_platform_blocking(
                publisher.list_location_candidates,
                longitude=longitude,
                latitude=latitude,
            )
            await merge_account_cookie_updates(store, account_id, publisher.cookie_updates())
            items = [ProductLocationOptionPayload.model_validate(item) for item in candidates]
            catalog_items = await store.upsert_product_platform_locations(account_id, items)
            persisted = await store.upsert_product_location_cache(
                account_id=account_id,
                cache_key=cache_key,
                longitude=longitude,
                latitude=latitude,
                options=[item.model_dump(mode="json") for item in items],
            )
            fetched_at = persisted.fetched_at if persisted is not None else datetime.now(UTC)
            return ProductLocationListPayload(
                items=catalog_items or items,
                data_source="live",
                fetched_at=fetched_at,
            )
        except ProductPublishError as exc:
            await merge_account_cookie_updates(store, account_id, exc.cookie_updates)
            if (
                exc.kind == "network"
                and exc.retryable
                and cache is not None
                and cached_items
                and cache_age is not None
                and cache_age <= PRODUCT_LOCATION_STALE_TTL
            ):
                logger.warning(
                    "Using stale Xianyu product location cache account=%s cache_age_seconds=%s",
                    account_id,
                    round(cache_age.total_seconds()),
                )
                catalog_items = await store.upsert_product_platform_locations(account_id, cached_items)
                return ProductLocationListPayload(
                    items=catalog_items or cached_items,
                    data_source="stale",
                    fetched_at=cache.fetched_at,
                    warning="闲鱼所在地网络请求失败，当前使用最近一次成功结果",
                )
            raise
        finally:
            publisher.close()


def _product_location_cache_key(longitude: float, latitude: float) -> str:
    return f"{longitude:.4f}:{latitude:.4f}"


def _validate_cached_product_locations(
    values: list[dict[str, Any]],
) -> list[ProductLocationOptionPayload]:
    items: list[ProductLocationOptionPayload] = []
    for value in values:
        try:
            items.append(ProductLocationOptionPayload.model_validate(value))
        except Exception:
            logger.warning("Ignoring invalid cached Xianyu product location", exc_info=True)
    return items


async def merge_account_cookie_updates(
    store: AccountStore,
    account_id: str,
    updates: Mapping[str, str],
    *,
    source: str = "product_publish",
) -> bool:
    """Merge response cookie deltas onto the latest persisted cookie with CAS."""

    clean_updates = {str(key): str(value) for key, value in updates.items() if key and value}
    if not clean_updates:
        return False

    for _ in range(3):
        account = await store.get_account(account_id)
        if account is None:
            raise ValueError("account not found while merging publish cookies")
        current = _parse_cookie(account.cookie)
        current_unb = current.get("unb")
        updated_unb = clean_updates.get("unb")
        if updated_unb and current_unb and updated_unb != current_unb:
            raise ProductPublishError("cookie_conflict", "商品操作响应 Cookie 的 unb 与当前账户不一致")
        merged = dict(current)
        merged.update(clean_updates)
        merged_cookie = _serialize_cookie(merged)
        if merged_cookie == account.cookie:
            return False
        if await store.compare_and_set_account_cookie(
            account_id,
            account.cookie,
            merged_cookie,
            source=source,
        ):
            return True
    raise ProductPublishError("cookie_conflict", "商品操作响应 Cookie 合并冲突，请刷新账户后重试")


async def _request_from_snapshot(
    store: AccountStore,
    account_id: str,
    snapshot: Mapping[str, Any],
    unique_code: str,
) -> ProductPublishRequest:
    images = snapshot.get("images")
    if not isinstance(images, list):
        images = []
    image_refs = tuple(str(value).strip() for value in images if str(value).strip())
    image_data: dict[str, ProductImageData] = {}
    for image_ref in image_refs:
        if not image_ref.startswith("asset:"):
            continue
        asset_id = image_ref.removeprefix("asset:")
        asset = await store.get_product_image_asset(account_id, asset_id)
        if asset is None:
            raise ProductPublishError("image_missing", f"商品图片资产不存在: {asset_id}")
        try:
            raw = await run_media_blocking(product_image_storage.read, account_id, asset_id)
        except (OSError, ValueError) as exc:
            raise ProductPublishError("image_missing", f"商品图片文件不可用: {asset.original_filename}") from exc
        if len(raw) != asset.size_bytes or hashlib.sha256(raw).hexdigest() != asset.sha256:
            raise ProductPublishError("image_invalid", f"商品图片文件校验失败: {asset.original_filename}")
        image_data[image_ref] = ProductImageData(
            data=raw,
            filename=f"product_{asset.asset_id}.jpg",
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            size_bytes=asset.size_bytes,
            sha256=asset.sha256,
        )
    return ProductPublishRequest(
        title=str(snapshot.get("title") or "").strip(),
        description=str(snapshot.get("description") or snapshot.get("title") or "").strip(),
        image_urls=image_refs,
        price=_decimal(snapshot.get("price"), required=True),
        original_price=_decimal(snapshot.get("original_price")),
        stock=int(snapshot.get("stock") or 1),
        delivery_choice=str(snapshot.get("delivery_choice") or "free_shipping"),
        post_price=_decimal(snapshot.get("post_price")),
        can_self_pickup=bool(snapshot.get("can_self_pickup")),
        category_hint=str(snapshot.get("category_hint") or "").strip() or None,
        unique_code=str(snapshot.get("unique_code") or unique_code),
        location=snapshot.get("location") if isinstance(snapshot.get("location"), Mapping) else None,
        image_data=image_data,
    )


def _decimal(value: Any, *, required: bool = False) -> Decimal | None:
    if value in (None, ""):
        if required:
            raise ProductPublishError("validation", "商品价格不能为空")
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProductPublishError("validation", f"商品价格格式无效: {value}") from exc
    if result < 0 or (required and result <= 0):
        raise ProductPublishError("validation", "商品价格必须大于 0")
    return result


def _to_core_account(account: AccountRecord) -> AccountConfig:
    return AccountConfig(
        account_id=account.account_id,
        cookie=account.cookie,
        nickname=account.display_name,
        enabled=account.enabled,
        proxy=build_core_account_proxy(account),
    )


def _parse_cookie(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in value.split(";"):
        key, separator, cookie_value = part.strip().partition("=")
        if separator and key:
            result[key] = cookie_value
    return result


def _serialize_cookie(values: Mapping[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in values.items() if key)
