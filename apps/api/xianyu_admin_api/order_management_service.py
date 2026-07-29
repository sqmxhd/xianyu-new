"""Durable account-scoped order synchronization and work queues."""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from redis.exceptions import LockError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from integrations.xianyu_core import (
    AccountConfig,
    BuyerOrder,
    MtopBuyerOrderOperations,
    MtopOrderOperations,
    OrderSyncError,
    SellerOrder,
)

from .account_network import build_core_account_proxy
from .database import SessionLocal
from .executors import run_db_blocking, run_platform_blocking
from .orm import (
    AccountORM,
    OrderEventORM,
    OrderORM,
    OrderSyncRunORM,
    OrderSyncSettingORM,
    ProductItemORM,
    RuntimeStatusORM,
)
from .product_publish_service import merge_account_cookie_updates
from .queue import enqueue_background_task
from .schemas import (
    BackgroundTaskCreatePayload,
    BackgroundTaskPayload,
    OrderAccountSummaryPayload,
    OrderSyncRunPayload,
    OrderSyncSettingPayload,
    OrderSyncSettingUpdatePayload,
)
from .settings import settings
from .store import AccountRecord, AccountStore


ACTIVE_RUN_STATUSES = {"pending", "running"}
OrderOperationsFactory = Callable[..., MtopOrderOperations]
BuyerOrderOperationsFactory = Callable[..., MtopBuyerOrderOperations]


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class OrderSyncLockError(RuntimeError):
    pass


async def _renew_order_sync_lock(lock: redis.lock.Lock) -> None:
    while True:
        await asyncio.sleep(45)
        try:
            if not await lock.extend(10 * 60, replace_ttl=True):
                return
        except Exception:
            return


@asynccontextmanager
async def account_order_sync_lock(account_id: str):
    client = redis.Redis.from_url(settings.redis_url)
    lock = client.lock(
        f"xianyu:lock:order-sync:{account_id}",
        timeout=10 * 60,
        blocking_timeout=30,
    )
    acquired = False
    renew_task: asyncio.Task[None] | None = None
    try:
        acquired = bool(await lock.acquire())
        if not acquired:
            raise OrderSyncLockError("该账户已有订单同步任务正在执行")
        renew_task = asyncio.create_task(
            _renew_order_sync_lock(lock), name=f"order-sync-lock-renewal:{account_id}"
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


class OrderManagementRepository:
    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    async def ensure_account_settings(self, account_ids: list[str]) -> None:
        await run_db_blocking(self._ensure_account_settings_sync, account_ids)

    async def list_account_summaries(self, scope: str = "sold") -> list[OrderAccountSummaryPayload]:
        return await run_db_blocking(self._list_account_summaries_sync, scope)

    async def get_setting(
        self, account_id: str, scope: str = "sold"
    ) -> OrderSyncSettingPayload | None:
        return await run_db_blocking(self._get_setting_sync, account_id, scope)

    async def update_setting(
        self, account_id: str, payload: OrderSyncSettingUpdatePayload, scope: str = "sold"
    ) -> OrderSyncSettingPayload | None:
        return await run_db_blocking(self._update_setting_sync, account_id, payload, scope)

    async def create_run(
        self, account_id: str, mode: str, trigger: str, scope: str = "sold"
    ) -> OrderSyncRunPayload:
        return await run_db_blocking(self._create_run_sync, account_id, mode, trigger, scope)

    async def start_run(self, run_id: str) -> OrderSyncRunPayload | None:
        return await run_db_blocking(self._start_run_sync, run_id)

    async def get_run(self, run_id: str) -> OrderSyncRunPayload | None:
        return await run_db_blocking(self._get_run_sync, run_id)

    async def list_runs(
        self, account_id: str, limit: int = 30, scope: str = "sold"
    ) -> list[OrderSyncRunPayload]:
        return await run_db_blocking(self._list_runs_sync, account_id, limit, scope)

    async def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        total_count: int,
        inserted_count: int,
        updated_count: int,
        skipped_count: int,
        error: str | None = None,
    ) -> OrderSyncRunPayload | None:
        return await run_db_blocking(
            self._finish_run_sync,
            run_id,
            status,
            total_count,
            inserted_count,
            updated_count,
            skipped_count,
            error,
        )

    async def apply_orders(
        self, account_id: str, orders: tuple[SellerOrder, ...], *, mode: str
    ) -> tuple[int, int, int]:
        return await run_db_blocking(self._apply_orders_sync, account_id, orders, mode)

    async def apply_buyer_orders(
        self, account_id: str, orders: tuple[BuyerOrder, ...], *, mode: str
    ) -> tuple[int, int, int]:
        return await run_db_blocking(self._apply_buyer_orders_sync, account_id, orders, mode)

    async def fail_sync(
        self, account_id: str, error: str, *, scope: str = "sold", pause: bool = False
    ) -> None:
        await run_db_blocking(self._fail_sync_sync, account_id, error, scope, pause)

    async def list_due_settings(self, now: datetime) -> list[tuple[OrderSyncSettingPayload, str]]:
        return await run_db_blocking(self._list_due_settings_sync, now)

    async def reschedule(self, account_id: str, mode: str, scope: str = "sold") -> None:
        await run_db_blocking(self._reschedule_sync, account_id, mode, scope)

    def _ensure_account_settings_sync(self, account_ids: list[str]) -> None:
        with self._session_factory() as session:
            for account_id in account_ids:
                if session.get(AccountORM, account_id) is not None:
                    self._get_or_create_setting(session, account_id)
            session.commit()

    def _list_account_summaries_sync(self, scope: str) -> list[OrderAccountSummaryPayload]:
        self._validate_scope(scope)
        with self._session_factory() as session:
            accounts = session.scalars(
                select(AccountORM)
                .where(AccountORM.order_management_visible.is_(True))
                .order_by(AccountORM.created_at)
            ).all()
            for account in accounts:
                self._get_or_create_setting(session, account.account_id)
            session.flush()
            role = "buyer" if scope == "bought" else "seller"
            counts = session.execute(
                select(OrderORM.account_id, OrderORM.status, func.count())
                .where(
                    OrderORM.trade_role == role,
                    OrderORM.platform_confirmed.is_(True),
                )
                .group_by(OrderORM.account_id, OrderORM.status)
            ).all()
            count_map: dict[str, dict[str, int]] = {}
            for account_id, status, count in counts:
                count_map.setdefault(account_id, {})[status] = int(count)
            result: list[OrderAccountSummaryPayload] = []
            for account in accounts:
                setting = session.get(OrderSyncSettingORM, account.account_id)
                runtime = session.get(RuntimeStatusORM, account.account_id)
                assert setting is not None
                account_counts = count_map.get(account.account_id, {})
                result.append(
                    OrderAccountSummaryPayload(
                        account_id=account.account_id,
                        account_name=(
                            account.display_name
                        ),
                        scope=scope,  # type: ignore[arg-type]
                        enabled=account.enabled,
                        runtime_state=(runtime.state if runtime else "stopped"),  # type: ignore[arg-type]
                        total_count=sum(account_counts.values()),
                        active_count=(
                            sum(
                                account_counts.get(status, 0)
                                for status in (
                                    "pending_payment",
                                    "waiting_seller_delivery",
                                    "shipped",
                                    "refunding",
                                )
                            )
                            if scope == "bought"
                            else sum(
                                account_counts.get(status, 0)
                                for status in ("pending_payment", "paid_waiting_delivery", "refunding")
                            )
                        ),
                        pending_count=account_counts.get(
                            "waiting_seller_delivery" if scope == "bought" else "paid_waiting_delivery",
                            0,
                        ),
                        refunding_count=account_counts.get("refunding", 0),
                        setting=self._setting_to_payload(setting, scope),
                    )
                )
            session.commit()
            return result

    def _get_setting_sync(
        self, account_id: str, scope: str
    ) -> OrderSyncSettingPayload | None:
        self._validate_scope(scope)
        with self._session_factory() as session:
            if session.get(AccountORM, account_id) is None:
                return None
            row = self._get_or_create_setting(session, account_id)
            session.commit()
            return self._setting_to_payload(row, scope)

    def _update_setting_sync(
        self, account_id: str, payload: OrderSyncSettingUpdatePayload, scope: str
    ) -> OrderSyncSettingPayload | None:
        self._validate_scope(scope)
        with self._session_factory() as session:
            if session.get(AccountORM, account_id) is None:
                return None
            row = self._get_or_create_setting(session, account_id)
            row.updated_at = utcnow()
            if scope == "bought":
                row.bought_sync_enabled = payload.sync_enabled
                row.bought_full_interval_minutes = payload.full_interval_minutes
                row.bought_jitter_seconds = payload.jitter_seconds
                self._schedule(row, scope, "full", row.updated_at)
            else:
                row.sync_enabled = payload.sync_enabled
                row.pending_interval_seconds = payload.pending_interval_seconds
                row.full_interval_minutes = payload.full_interval_minutes
                row.jitter_seconds = payload.jitter_seconds
                self._schedule(row, scope, "pending", row.updated_at)
                self._schedule(row, scope, "full", row.updated_at)
            session.commit()
            return self._setting_to_payload(row, scope)

    def _create_run_sync(
        self, account_id: str, mode: str, trigger: str, scope: str
    ) -> OrderSyncRunPayload:
        self._validate_scope(scope)
        if mode not in {"full", "pending"}:
            raise ValueError("unsupported order sync mode")
        if scope == "bought" and mode != "full":
            raise ValueError("bought order sync only supports full mode")
        with self._session_factory() as session:
            active = session.scalars(
                select(OrderSyncRunORM)
                .where(
                    OrderSyncRunORM.account_id == account_id,
                    OrderSyncRunORM.scope == scope,
                    OrderSyncRunORM.status.in_(ACTIVE_RUN_STATUSES),
                )
                .order_by(OrderSyncRunORM.created_at.desc())
            ).first()
            if active is not None:
                return self._run_to_payload(active)
            if session.get(AccountORM, account_id) is None:
                raise ValueError("account not found")
            now = utcnow()
            row = OrderSyncRunORM(
                run_id=uuid.uuid4().hex,
                account_id=account_id,
                scope=scope,
                mode=mode,
                trigger=trigger,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            return self._run_to_payload(row)

    def _start_run_sync(self, run_id: str) -> OrderSyncRunPayload | None:
        with self._session_factory() as session:
            row = session.get(OrderSyncRunORM, run_id)
            if row is None:
                return None
            if row.status == "pending":
                row.status = "running"
                row.started_at = utcnow()
                row.updated_at = row.started_at
                session.commit()
            return self._run_to_payload(row)

    def _get_run_sync(self, run_id: str) -> OrderSyncRunPayload | None:
        with self._session_factory() as session:
            row = session.get(OrderSyncRunORM, run_id)
            return self._run_to_payload(row) if row is not None else None

    def _list_runs_sync(
        self, account_id: str, limit: int, scope: str
    ) -> list[OrderSyncRunPayload]:
        self._validate_scope(scope)
        with self._session_factory() as session:
            rows = session.scalars(
                select(OrderSyncRunORM)
                .where(
                    OrderSyncRunORM.account_id == account_id,
                    OrderSyncRunORM.scope == scope,
                )
                .order_by(OrderSyncRunORM.created_at.desc())
                .limit(max(1, min(limit, 200)))
            ).all()
            return [self._run_to_payload(row) for row in rows]

    def _finish_run_sync(
        self,
        run_id: str,
        status: str,
        total_count: int,
        inserted_count: int,
        updated_count: int,
        skipped_count: int,
        error: str | None,
    ) -> OrderSyncRunPayload | None:
        with self._session_factory() as session:
            row = session.get(OrderSyncRunORM, run_id)
            if row is None:
                return None
            now = utcnow()
            row.status = status
            row.total_count = total_count
            row.inserted_count = inserted_count
            row.updated_count = updated_count
            row.skipped_count = skipped_count
            row.error = error
            row.finished_at = now
            row.updated_at = now
            setting = self._get_or_create_setting(session, row.account_id)
            if row.scope == "bought":
                setting.bought_last_sync_at = now
                setting.bought_last_sync_status = status
                setting.bought_last_sync_error = error
                if status == "success":
                    setting.bought_last_full_sync_at = now
                self._schedule(setting, "bought", "full", now)
            else:
                setting.last_sync_at = now
                setting.last_sync_status = status
                setting.last_sync_error = error
                if status == "success":
                    if row.mode == "full":
                        setting.last_full_sync_at = now
                        setting.last_pending_sync_at = now
                    else:
                        setting.last_pending_sync_at = now
                self._schedule(setting, "sold", row.mode, now)
                if row.mode == "full":
                    self._schedule(setting, "sold", "pending", now)
            session.commit()
            return self._run_to_payload(row)

    def _apply_orders_sync(
        self, account_id: str, orders: tuple[SellerOrder, ...], mode: str
    ) -> tuple[int, int, int]:
        inserted = 0
        updated = 0
        skipped = 0
        now = utcnow()
        with self._session_factory() as session:
            item_ids = {order.item_id for order in orders if order.item_id}
            product_map = {
                row.item_id: row
                for row in session.scalars(
                    select(ProductItemORM).where(
                        ProductItemORM.account_id == account_id,
                        ProductItemORM.item_id.in_(item_ids),
                    )
                ).all()
            } if item_ids else {}
            order_ids = [order.order_id for order in orders]
            existing_map = {
                row.platform_order_id: row
                for row in session.scalars(
                    select(OrderORM).where(
                        OrderORM.account_id == account_id,
                        OrderORM.platform_order_id.in_(order_ids),
                    )
                ).all()
                if row.platform_order_id
            } if order_ids else {}
            for incoming in orders:
                row = existing_map.get(incoming.order_id)
                previous_status = row.status if row is not None else None
                product = product_map.get(incoming.item_id)
                if row is None:
                    row = OrderORM(
                        order_pk=uuid.uuid4().hex,
                        account_id=account_id,
                        platform_order_id=incoming.order_id,
                        conversation_id="",
                        status=incoming.status,
                        created_at=incoming.platform_created_at or now,
                        updated_at=now,
                    )
                    session.add(row)
                    existing_map[incoming.order_id] = row
                    inserted += 1
                row.trade_role = "seller"
                row.data_source = "seller_sold"
                row.first_seen_source = row.first_seen_source or "seller_sold"
                row.platform_confirmed = True
                row.sync_state = "confirmed"
                row.sync_error = None
                row.peer_user_id = incoming.buyer_id or row.peer_user_id
                row.peer_name = incoming.buyer_name or row.peer_name
                row.buyer_user_id = incoming.buyer_id or row.buyer_user_id
                row.buyer_name = incoming.buyer_name or row.buyer_name
                row.receiver_name = incoming.receiver_name or row.receiver_name
                row.receiver_phone = incoming.receiver_phone or row.receiver_phone
                row.receiver_address = incoming.receiver_address or row.receiver_address
                row.item_id = incoming.item_id or row.item_id
                row.title = incoming.title or (product.title if product else "") or row.title
                row.image_url = incoming.image_url or (product.cover_url if product else "") or row.image_url
                row.price = incoming.price or row.price
                row.quantity = incoming.quantity
                row.status = incoming.status
                row.status_text = incoming.status_text or row.status_text
                row.platform_status = incoming.platform_status or row.platform_status
                row.platform_created_at = incoming.platform_created_at or row.platform_created_at
                row.platform_paid_at = incoming.platform_paid_at or row.platform_paid_at
                row.platform_completed_at = incoming.platform_completed_at or row.platform_completed_at
                row.is_bargain = bool(row.is_bargain or incoming.is_bargain)
                row.seller_rate_status = incoming.seller_rate_status or row.seller_rate_status
                row.refund_status = incoming.refund_status or None
                row.last_event_at = (
                    incoming.platform_completed_at
                    or incoming.platform_paid_at
                    or incoming.platform_created_at
                    or row.last_event_at
                )
                row.last_synced_at = now
                row.raw_summary = json.dumps(incoming.raw_summary, ensure_ascii=False)
                row.updated_at = now
                if previous_status is not None:
                    if previous_status == incoming.status:
                        skipped += 1
                    else:
                        updated += 1
                if previous_status != incoming.status:
                    session.flush([row])
                    session.add(
                        OrderEventORM(
                            event_pk=uuid.uuid4().hex,
                            order_pk=row.order_pk,
                            account_id=account_id,
                            conversation_id=row.conversation_id,
                            message_pk=f"sold:{uuid.uuid4().hex}",
                            platform_order_id=incoming.order_id,
                            item_id=incoming.item_id or None,
                            event_type="platform_sync",
                            status=incoming.status,
                            status_text=incoming.status_text,
                            raw_summary=json.dumps(incoming.raw_summary, ensure_ascii=False),
                            created_at=now,
                        )
                    )
            session.commit()
        return inserted, updated, skipped

    def _apply_buyer_orders_sync(
        self, account_id: str, orders: tuple[BuyerOrder, ...], mode: str
    ) -> tuple[int, int, int]:
        if mode != "full":
            raise ValueError("bought order sync only supports full mode")
        inserted = 0
        updated = 0
        skipped = 0
        now = utcnow()
        with self._session_factory() as session:
            order_ids = [order.order_id for order in orders]
            existing_map = {
                row.platform_order_id: row
                for row in session.scalars(
                    select(OrderORM).where(
                        OrderORM.account_id == account_id,
                        OrderORM.platform_order_id.in_(order_ids),
                    )
                ).all()
                if row.platform_order_id
            } if order_ids else {}
            for incoming in orders:
                row = existing_map.get(incoming.order_id)
                previous_state = (
                    (row.status, row.trade_role, row.data_source) if row is not None else None
                )
                if row is None:
                    row = OrderORM(
                        order_pk=uuid.uuid4().hex,
                        account_id=account_id,
                        platform_order_id=incoming.order_id,
                        conversation_id="",
                        status=incoming.status,
                        created_at=incoming.platform_created_at or now,
                        updated_at=now,
                    )
                    session.add(row)
                    existing_map[incoming.order_id] = row
                    inserted += 1
                row.trade_role = "buyer"
                row.data_source = "buyer_bought"
                row.first_seen_source = row.first_seen_source or "buyer_bought"
                row.platform_confirmed = True
                row.sync_state = "confirmed"
                row.sync_error = None
                row.peer_user_id = incoming.seller_id or row.peer_user_id
                row.peer_name = incoming.seller_name or row.peer_name
                row.item_id = incoming.item_id or row.item_id
                row.title = incoming.title or row.title
                row.image_url = incoming.image_url or row.image_url
                row.price = incoming.price or row.price
                row.quantity = incoming.quantity
                row.status = incoming.status
                row.status_text = incoming.status_text or row.status_text
                row.platform_status = incoming.platform_status or row.platform_status
                row.platform_created_at = incoming.platform_created_at or row.platform_created_at
                row.platform_paid_at = incoming.platform_paid_at or row.platform_paid_at
                row.platform_completed_at = incoming.platform_completed_at or row.platform_completed_at
                row.refund_status = incoming.refund_status or None
                row.last_event_at = (
                    incoming.platform_completed_at
                    or incoming.platform_paid_at
                    or incoming.platform_created_at
                    or row.last_event_at
                )
                row.last_synced_at = now
                row.raw_summary = json.dumps(incoming.raw_summary, ensure_ascii=False)
                row.updated_at = now
                current_state = (row.status, row.trade_role, row.data_source)
                if previous_state is not None:
                    if previous_state == current_state:
                        skipped += 1
                    else:
                        updated += 1
                if previous_state != current_state:
                    session.flush([row])
                    session.add(
                        OrderEventORM(
                            event_pk=uuid.uuid4().hex,
                            order_pk=row.order_pk,
                            account_id=account_id,
                            conversation_id=row.conversation_id,
                            message_pk=f"bought:{uuid.uuid4().hex}",
                            platform_order_id=incoming.order_id,
                            item_id=incoming.item_id or None,
                            event_type="platform_sync",
                            status=incoming.status,
                            status_text=incoming.status_text,
                            raw_summary=json.dumps(incoming.raw_summary, ensure_ascii=False),
                            created_at=now,
                        )
                    )
            session.commit()
        return inserted, updated, skipped

    def _fail_sync_sync(
        self, account_id: str, error: str, scope: str, pause: bool
    ) -> None:
        self._validate_scope(scope)
        with self._session_factory() as session:
            if session.get(AccountORM, account_id) is None:
                return
            row = self._get_or_create_setting(session, account_id)
            now = utcnow()
            if scope == "bought":
                row.bought_last_sync_at = now
                row.bought_last_sync_status = "failed"
                row.bought_last_sync_error = error
                if pause:
                    row.bought_sync_enabled = False
            else:
                row.last_sync_at = now
                row.last_sync_status = "failed"
                row.last_sync_error = error
                if pause:
                    row.sync_enabled = False
            session.commit()

    def _list_due_settings_sync(
        self, now: datetime
    ) -> list[tuple[OrderSyncSettingPayload, str]]:
        with self._session_factory() as session:
            rows = session.scalars(select(OrderSyncSettingORM)).all()
            result: list[tuple[OrderSyncSettingPayload, str]] = []
            for row in rows:
                if row.bought_sync_enabled and (
                    row.bought_next_full_sync_at is None
                    or as_utc(row.bought_next_full_sync_at) <= now
                ):
                    result.append((self._setting_to_payload(row, "bought"), "full"))
                if row.sync_enabled:
                    if row.next_full_sync_at is None or as_utc(row.next_full_sync_at) <= now:
                        result.append((self._setting_to_payload(row, "sold"), "full"))
                    elif row.next_pending_sync_at is None or as_utc(row.next_pending_sync_at) <= now:
                        result.append((self._setting_to_payload(row, "sold"), "pending"))
            return result

    def _reschedule_sync(self, account_id: str, mode: str, scope: str) -> None:
        self._validate_scope(scope)
        with self._session_factory() as session:
            row = session.get(OrderSyncSettingORM, account_id)
            if row is None:
                return
            self._schedule(row, scope, mode, utcnow())
            session.commit()

    @staticmethod
    def _schedule(
        row: OrderSyncSettingORM, scope: str, mode: str, now: datetime
    ) -> None:
        if scope == "bought":
            jitter = random.randint(0, max(0, row.bought_jitter_seconds))
            row.bought_next_full_sync_at = now + timedelta(
                minutes=row.bought_full_interval_minutes,
                seconds=jitter,
            )
            return
        jitter = random.randint(0, max(0, row.jitter_seconds))
        if mode == "full":
            row.next_full_sync_at = now + timedelta(minutes=row.full_interval_minutes, seconds=jitter)
        else:
            row.next_pending_sync_at = now + timedelta(seconds=row.pending_interval_seconds + jitter)

    def _get_or_create_setting(
        self, session: Session, account_id: str
    ) -> OrderSyncSettingORM:
        row = session.get(OrderSyncSettingORM, account_id)
        if row is not None:
            return row
        now = utcnow()
        row = OrderSyncSettingORM(
            account_id=account_id,
            sync_enabled=True,
            pending_interval_seconds=90,
            full_interval_minutes=15,
            jitter_seconds=20,
            bought_sync_enabled=True,
            bought_full_interval_minutes=15,
            bought_jitter_seconds=20,
            created_at=now,
            updated_at=now,
        )
        self._schedule(row, "sold", "pending", now)
        self._schedule(row, "sold", "full", now)
        self._schedule(row, "bought", "full", now)
        session.add(row)
        return row

    @staticmethod
    def _setting_to_payload(
        row: OrderSyncSettingORM, scope: str
    ) -> OrderSyncSettingPayload:
        if scope == "bought":
            return OrderSyncSettingPayload(
                account_id=row.account_id,
                scope="bought",
                sync_enabled=row.bought_sync_enabled,
                pending_interval_seconds=90,
                full_interval_minutes=row.bought_full_interval_minutes,
                jitter_seconds=row.bought_jitter_seconds,
                last_sync_at=as_utc(row.bought_last_sync_at),
                last_pending_sync_at=None,
                last_full_sync_at=as_utc(row.bought_last_full_sync_at),
                last_sync_status=row.bought_last_sync_status,
                last_sync_error=row.bought_last_sync_error,
                next_pending_sync_at=None,
                next_full_sync_at=as_utc(row.bought_next_full_sync_at),
                created_at=as_utc(row.created_at),
                updated_at=as_utc(row.updated_at),
            )
        return OrderSyncSettingPayload(
            account_id=row.account_id,
            scope="sold",
            sync_enabled=row.sync_enabled,
            pending_interval_seconds=row.pending_interval_seconds,
            full_interval_minutes=row.full_interval_minutes,
            jitter_seconds=row.jitter_seconds,
            last_sync_at=as_utc(row.last_sync_at),
            last_pending_sync_at=as_utc(row.last_pending_sync_at),
            last_full_sync_at=as_utc(row.last_full_sync_at),
            last_sync_status=row.last_sync_status,
            last_sync_error=row.last_sync_error,
            next_pending_sync_at=as_utc(row.next_pending_sync_at),
            next_full_sync_at=as_utc(row.next_full_sync_at),
            created_at=as_utc(row.created_at),
            updated_at=as_utc(row.updated_at),
        )

    @staticmethod
    def _run_to_payload(row: OrderSyncRunORM) -> OrderSyncRunPayload:
        return OrderSyncRunPayload(
            run_id=row.run_id,
            account_id=row.account_id,
            scope=row.scope,  # type: ignore[arg-type]
            mode=row.mode,  # type: ignore[arg-type]
            trigger=row.trigger,
            status=row.status,  # type: ignore[arg-type]
            total_count=row.total_count,
            inserted_count=row.inserted_count,
            updated_count=row.updated_count,
            skipped_count=row.skipped_count,
            error=row.error,
            created_at=as_utc(row.created_at),
            updated_at=as_utc(row.updated_at),
            started_at=as_utc(row.started_at),
            finished_at=as_utc(row.finished_at),
        )

    @staticmethod
    def _validate_scope(scope: str) -> None:
        if scope not in {"bought", "sold"}:
            raise ValueError("unsupported order sync scope")


class OrderManagementService:
    def __init__(
        self,
        store: AccountStore,
        repository: OrderManagementRepository | None = None,
        *,
        operations_factory: OrderOperationsFactory = MtopOrderOperations,
        buyer_operations_factory: BuyerOrderOperationsFactory = MtopBuyerOrderOperations,
    ) -> None:
        self.store = store
        self.repository = repository or OrderManagementRepository(store.session_factory)
        self.operations_factory = operations_factory
        self.buyer_operations_factory = buyer_operations_factory

    async def execute_run(self, run_id: str) -> dict[str, object]:
        run = await self.repository.start_run(run_id)
        if run is None:
            raise ValueError("order sync run not found")
        if run.status != "running":
            return {"ok": run.status == "success", "run": run.model_dump(mode="json")}
        account = await self.store.get_account(run.account_id)
        if account is None:
            raise ValueError("account not found")
        client: MtopOrderOperations | MtopBuyerOrderOperations | None = None
        try:
            async with account_order_sync_lock(run.account_id):
                if run.scope == "bought":
                    client = self.buyer_operations_factory(self._to_core_account(account))
                    result = await run_platform_blocking(
                        client.list_bought_orders,
                        order_status="ALL",
                        max_pages=None,
                    )
                else:
                    client = self.operations_factory(self._to_core_account(account))
                    result = await run_platform_blocking(
                        client.list_sold_orders,
                        query_code="ALL" if run.mode == "full" else "NOT_SHIP",
                        max_pages=None if run.mode == "full" else 1,
                    )
                cookie_changed = await merge_account_cookie_updates(
                    self.store,
                    run.account_id,
                    result.cookie_updates,
                    source=f"order_sync_{run.scope}",
                )
                if run.scope == "bought":
                    inserted, updated, skipped = await self.repository.apply_buyer_orders(
                        run.account_id, result.items, mode=run.mode
                    )
                else:
                    inserted, updated, skipped = await self.repository.apply_orders(
                        run.account_id, result.items, mode=run.mode
                    )
                finished = await self.repository.finish_run(
                    run.run_id,
                    status="success",
                    total_count=len(result.items),
                    inserted_count=inserted,
                    updated_count=updated,
                    skipped_count=skipped,
                )
            return {
                "ok": True,
                "cookie_changed": cookie_changed,
                "complete": result.complete,
                "platform_total_count": result.total_count,
                "run": finished.model_dump(mode="json") if finished else None,
            }
        except OrderSyncError as exc:
            cookie_changed = await merge_account_cookie_updates(
                self.store,
                run.account_id,
                exc.cookie_updates or (client.cookie_updates() if client else {}),
                source=f"order_sync_{run.scope}",
            )
            await self.repository.fail_sync(
                run.account_id,
                str(exc),
                scope=run.scope,
                pause=not exc.retryable,
            )
            failed = await self.repository.finish_run(
                run.run_id,
                status="failed",
                total_count=0,
                inserted_count=0,
                updated_count=0,
                skipped_count=0,
                error=str(exc),
            )
            return {
                "ok": False,
                "cookie_changed": cookie_changed,
                "retryable": exc.retryable,
                "run": failed.model_dump(mode="json") if failed else None,
            }
        except Exception as exc:
            await self.repository.fail_sync(run.account_id, str(exc), scope=run.scope)
            failed = await self.repository.finish_run(
                run.run_id,
                status="failed",
                total_count=0,
                inserted_count=0,
                updated_count=0,
                skipped_count=0,
                error=str(exc),
            )
            return {
                "ok": False,
                "cookie_changed": False,
                "run": failed.model_dump(mode="json") if failed else None,
            }
        finally:
            if client is not None:
                client.close()

    @staticmethod
    def _to_core_account(account: AccountRecord) -> AccountConfig:
        return AccountConfig(
            account_id=account.account_id,
            cookie=account.cookie,
            nickname=account.display_name,
            enabled=account.enabled,
            proxy=build_core_account_proxy(account),
        )


async def create_and_enqueue_order_sync(
    store: AccountStore,
    repository: OrderManagementRepository,
    *,
    account_id: str,
    scope: str = "sold",
    mode: str,
    trigger: str,
) -> tuple[OrderSyncRunPayload, BackgroundTaskPayload]:
    run = await repository.create_run(account_id, mode, trigger, scope)
    task = await store.create_background_task(
        BackgroundTaskCreatePayload(
            account_id=account_id,
            task_type="order.sync_account",
            dedupe_key=f"order-sync:{run.run_id}",
            payload={"account_id": account_id, "scope": scope, "run_id": run.run_id},
        )
    )
    assert task is not None
    if task.status == "pending" and task.queued_at is None:
        try:
            queued = await enqueue_background_task(store, task)
            if not queued.queued:
                raise RuntimeError(queued.message)
            await store.mark_background_task_queued(task.task_id)
        except Exception as exc:
            error = f"queue unavailable: {exc.__class__.__name__}: {exc}"
            await store.finish_background_task(task.task_id, status="failed", error=error)
            await repository.finish_run(
                run.run_id,
                status="failed",
                total_count=0,
                inserted_count=0,
                updated_count=0,
                skipped_count=0,
                error=error,
            )
            raise
    return (
        await repository.get_run(run.run_id) or run,
        await store.get_background_task(task.task_id) or task,
    )
