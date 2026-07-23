"""Durable product catalog synchronization and seller operations."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session, selectinload, sessionmaker

from integrations.xianyu_core import (
    AccountConfig,
    ManagedProduct,
    MtopProductOperations,
    ProductActionItemResult,
    ProductOperationError,
)

from .account_network import build_core_account_proxy
from .database import SessionLocal
from .executors import run_db_blocking, run_platform_blocking
from .orm import (
    AccountORM,
    ProductItemORM,
    ProductOperationItemORM,
    ProductOperationRunORM,
    ProductPublishTaskORM,
    ProductSyncSettingORM,
)
from .product_publish_service import (
    account_product_operation_lock,
    merge_account_cookie_updates,
)
from .queue import enqueue_background_task
from .schemas import (
    BackgroundTaskCreatePayload,
    BackgroundTaskPayload,
    ProductAccountSummaryPayload,
    ProductItemPayload,
    ProductLocalCleanupPayload,
    ProductOperationItemPayload,
    ProductOperationRunPayload,
    ProductSyncSettingPayload,
    ProductSyncSettingUpdatePayload,
)
from .store import AccountRecord, AccountStore


logger = logging.getLogger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
ACTIVE_RUN_STATUSES = {"pending", "running"}


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ProductLocalCleanupConflict(RuntimeError):
    pass


class ProductManagementRepository:
    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    async def ensure_account_settings(self, account_ids: list[str]) -> None:
        await run_db_blocking(self._ensure_account_settings_sync, account_ids)

    async def list_account_summaries(self) -> list[ProductAccountSummaryPayload]:
        return await run_db_blocking(self._list_account_summaries_sync)

    async def get_setting(self, account_id: str) -> ProductSyncSettingPayload | None:
        return await run_db_blocking(self._get_setting_sync, account_id)

    async def update_setting(
        self, account_id: str, payload: ProductSyncSettingUpdatePayload
    ) -> ProductSyncSettingPayload | None:
        return await run_db_blocking(self._update_setting_sync, account_id, payload)

    async def list_items(
        self,
        account_id: str,
        *,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 500,
    ) -> list[ProductItemPayload]:
        return await run_db_blocking(
            self._list_items_sync, account_id, status, keyword, limit
        )

    async def delete_local_item(
        self, account_id: str, item_id: str
    ) -> ProductLocalCleanupPayload | None:
        return await run_db_blocking(self._delete_local_item_sync, account_id, item_id)

    async def create_run(
        self,
        account_id: str,
        operation: str,
        trigger: str,
        *,
        item_ids: list[str] | None = None,
        full_sync: bool = False,
    ) -> ProductOperationRunPayload:
        return await run_db_blocking(
            self._create_run_sync,
            account_id,
            operation,
            trigger,
            item_ids or [],
            full_sync,
        )

    async def get_run(self, run_id: str) -> ProductOperationRunPayload | None:
        return await run_db_blocking(self._get_run_sync, run_id)

    async def list_runs(
        self, account_id: str, limit: int = 50
    ) -> list[ProductOperationRunPayload]:
        return await run_db_blocking(self._list_runs_sync, account_id, limit)

    async def start_run(self, run_id: str) -> ProductOperationRunPayload | None:
        return await run_db_blocking(self._start_run_sync, run_id)

    async def add_run_item(
        self,
        run_id: str,
        item_id: str,
        status: str,
        message: str | None = None,
        platform_code: str | None = None,
    ) -> None:
        await run_db_blocking(
            self._add_run_item_sync,
            run_id,
            item_id,
            status,
            message,
            platform_code,
        )

    async def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        total_count: int,
        success_count: int,
        failed_count: int,
        skipped_count: int,
        error: str | None = None,
    ) -> ProductOperationRunPayload | None:
        return await run_db_blocking(
            self._finish_run_sync,
            run_id,
            status,
            total_count,
            success_count,
            failed_count,
            skipped_count,
            error,
        )

    async def apply_sync(
        self,
        account_id: str,
        items: tuple[ManagedProduct, ...],
        *,
        full: bool,
        complete: bool,
    ) -> None:
        await run_db_blocking(self._apply_sync_sync, account_id, items, full, complete)

    async def fail_sync(self, account_id: str, error: str) -> None:
        await run_db_blocking(self._fail_sync_sync, account_id, error)

    async def operation_candidates(
        self, account_id: str, item_ids: list[str], *, all_selling: bool = False
    ) -> list[ProductItemPayload]:
        return await run_db_blocking(
            self._operation_candidates_sync, account_id, item_ids, all_selling
        )

    async def mark_item_status(
        self,
        account_id: str,
        item_id: str,
        status: str,
        *,
        pending_confirmation: bool = False,
    ) -> None:
        await run_db_blocking(
            self._mark_item_status_sync,
            account_id,
            item_id,
            status,
            pending_confirmation,
        )

    async def mark_polished(self, account_id: str, item_id: str, when: datetime) -> None:
        await run_db_blocking(self._mark_polished_sync, account_id, item_id, when)

    async def complete_polish(self, account_id: str, when: datetime) -> None:
        await run_db_blocking(self._complete_polish_sync, account_id, when)

    async def list_due_settings(
        self, now: datetime
    ) -> list[tuple[ProductSyncSettingPayload, bool, bool]]:
        return await run_db_blocking(self._list_due_settings_sync, now)

    async def reschedule(
        self, account_id: str, *, sync: bool = False, polish: bool = False
    ) -> None:
        await run_db_blocking(self._reschedule_sync, account_id, sync, polish)

    def _ensure_account_settings_sync(self, account_ids: list[str]) -> None:
        with self._session_factory() as session:
            for account_id in account_ids:
                if session.get(AccountORM, account_id) is not None:
                    self._get_or_create_setting(session, account_id)
            session.commit()

    def _list_account_summaries_sync(self) -> list[ProductAccountSummaryPayload]:
        with self._session_factory() as session:
            accounts = session.scalars(
                select(AccountORM)
                .where(AccountORM.product_management_visible.is_(True))
                .order_by(AccountORM.created_at)
            ).all()
            for account in accounts:
                self._get_or_create_setting(session, account.account_id)
            session.flush()
            counts = session.execute(
                select(ProductItemORM.account_id, ProductItemORM.platform_status, func.count())
                .group_by(ProductItemORM.account_id, ProductItemORM.platform_status)
            ).all()
            count_map = {(account_id, status): int(count) for account_id, status, count in counts}
            result = [
                ProductAccountSummaryPayload(
                    account_id=account.account_id,
                    account_name=(
                        account.platform_display_name or account.remark or account.account_name
                    ),
                    enabled=account.enabled,
                    runtime_state=account.runtime.state if account.runtime else "stopped",
                    selling_count=count_map.get((account.account_id, "selling"), 0),
                    offline_count=count_map.get((account.account_id, "offline"), 0),
                    unknown_count=sum(
                        count_map.get((account.account_id, value), 0)
                        for value in ("unknown", "not_selling")
                    ),
                    setting=self._setting_to_payload(
                        self._get_or_create_setting(session, account.account_id)
                    ),
                )
                for account in accounts
            ]
            session.commit()
            return result

    def _get_setting_sync(self, account_id: str) -> ProductSyncSettingPayload | None:
        with self._session_factory() as session:
            if session.get(AccountORM, account_id) is None:
                return None
            row = self._get_or_create_setting(session, account_id)
            session.commit()
            return self._setting_to_payload(row)

    def _update_setting_sync(
        self, account_id: str, payload: ProductSyncSettingUpdatePayload
    ) -> ProductSyncSettingPayload | None:
        with self._session_factory() as session:
            if session.get(AccountORM, account_id) is None:
                return None
            row = self._get_or_create_setting(session, account_id)
            changes = payload.model_dump(exclude_none=True)
            for key, value in changes.items():
                setattr(row, key, value)
            row.updated_at = utcnow()
            if any(key.startswith("sync_") or key == "full_sync_interval_hours" for key in changes):
                row.next_sync_at = self._next_sync(row)
            if any(key.startswith("polish_") or key == "auto_polish_enabled" for key in changes):
                row.next_polish_at = self._next_polish(row) if row.auto_polish_enabled else None
            session.commit()
            return self._setting_to_payload(row)

    def _list_items_sync(
        self, account_id: str, status: str | None, keyword: str | None, limit: int
    ) -> list[ProductItemPayload]:
        with self._session_factory() as session:
            stmt = select(ProductItemORM).where(ProductItemORM.account_id == account_id)
            if status and status != "all":
                stmt = stmt.where(ProductItemORM.platform_status == status)
            clean_keyword = (keyword or "").strip()
            if clean_keyword:
                pattern = f"%{clean_keyword}%"
                stmt = stmt.where(
                    ProductItemORM.title.ilike(pattern) | ProductItemORM.item_id.ilike(pattern)
                )
            rows = session.scalars(
                stmt.order_by(
                    case((ProductItemORM.published_at.is_(None), 1), else_=0),
                    ProductItemORM.published_at.desc(),
                    ProductItemORM.created_at.desc(),
                    ProductItemORM.item_id.desc(),
                )
                .limit(max(1, min(limit, 1000)))
            ).all()
            return [self._item_to_payload(row) for row in rows]

    def _delete_local_item_sync(
        self, account_id: str, item_id: str
    ) -> ProductLocalCleanupPayload | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ProductItemORM)
                .where(
                    ProductItemORM.account_id == account_id,
                    ProductItemORM.item_id == item_id,
                )
                .with_for_update()
            )
            if row is None:
                return None
            if row.platform_status != "deleted":
                raise ProductLocalCleanupConflict("仅已从闲鱼平台删除的商品可以清理本地数据")
            if row.sync_state != "current":
                raise ProductLocalCleanupConflict("平台删除结果尚未核检，请等待自动核检或手动同步")

            now = utcnow()
            hidden_count = session.execute(
                update(ProductPublishTaskORM)
                .where(
                    ProductPublishTaskORM.account_id == account_id,
                    ProductPublishTaskORM.item_id == item_id,
                    ProductPublishTaskORM.catalog_hidden_at.is_(None),
                )
                .values(catalog_hidden_at=now, updated_at=now)
            ).rowcount
            session.delete(row)
            session.commit()
            return ProductLocalCleanupPayload(
                account_id=account_id,
                item_id=item_id,
                hidden_publish_task_count=max(0, hidden_count or 0),
            )

    def _create_run_sync(
        self,
        account_id: str,
        operation: str,
        trigger: str,
        item_ids: list[str],
        full_sync: bool,
    ) -> ProductOperationRunPayload:
        with self._session_factory() as session:
            active = session.scalars(
                select(ProductOperationRunORM)
                .options(selectinload(ProductOperationRunORM.items))
                .where(
                    ProductOperationRunORM.account_id == account_id,
                    ProductOperationRunORM.operation == operation,
                    ProductOperationRunORM.status.in_(ACTIVE_RUN_STATUSES),
                )
                .order_by(ProductOperationRunORM.created_at.desc())
                .limit(1)
            ).first()
            if active is not None:
                try:
                    active_item_ids = json.loads(active.requested_item_ids or "[]")
                except (TypeError, json.JSONDecodeError):
                    active_item_ids = []
                same_manual_request = (
                    trigger == "manual"
                    and operation == active.operation
                    and set(active_item_ids) == set(item_ids)
                    and bool(active.full_sync) == bool(full_sync)
                )
                if trigger not in {"manual", "publish"} or same_manual_request:
                    return self._run_to_payload(active)
            now = utcnow()
            row = ProductOperationRunORM(
                run_id=uuid.uuid4().hex,
                account_id=account_id,
                operation=operation,
                trigger=trigger,
                status="pending",
                full_sync=full_sync,
                requested_item_ids=json.dumps(item_ids, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._run_to_payload(row)

    def _get_run_sync(self, run_id: str) -> ProductOperationRunPayload | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(ProductOperationRunORM)
                .options(selectinload(ProductOperationRunORM.items))
                .where(ProductOperationRunORM.run_id == run_id)
            ).first()
            return self._run_to_payload(row) if row else None

    def _list_runs_sync(self, account_id: str, limit: int) -> list[ProductOperationRunPayload]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ProductOperationRunORM)
                .options(selectinload(ProductOperationRunORM.items))
                .where(ProductOperationRunORM.account_id == account_id)
                .order_by(ProductOperationRunORM.created_at.desc())
                .limit(max(1, min(limit, 200)))
            ).all()
            return [self._run_to_payload(row) for row in rows]

    def _start_run_sync(self, run_id: str) -> ProductOperationRunPayload | None:
        with self._session_factory() as session:
            row = session.get(ProductOperationRunORM, run_id)
            if row is None:
                return None
            if row.status == "pending":
                row.status = "running"
                row.started_at = utcnow()
                row.updated_at = row.started_at
                session.commit()
            return self._run_to_payload(row)

    def _add_run_item_sync(
        self,
        run_id: str,
        item_id: str,
        status: str,
        message: str | None,
        platform_code: str | None,
    ) -> None:
        with self._session_factory() as session:
            now = utcnow()
            session.add(
                ProductOperationItemORM(
                    result_id=uuid.uuid4().hex,
                    run_id=run_id,
                    item_id=item_id,
                    status=status,
                    message=message,
                    platform_code=platform_code,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

    def _finish_run_sync(
        self,
        run_id: str,
        status: str,
        total_count: int,
        success_count: int,
        failed_count: int,
        skipped_count: int,
        error: str | None,
    ) -> ProductOperationRunPayload | None:
        with self._session_factory() as session:
            row = session.get(ProductOperationRunORM, run_id)
            if row is None:
                return None
            now = utcnow()
            row.status = status
            row.total_count = total_count
            row.success_count = success_count
            row.failed_count = failed_count
            row.skipped_count = skipped_count
            row.error = error
            row.finished_at = now
            row.updated_at = now
            session.commit()
            refreshed = session.scalars(
                select(ProductOperationRunORM)
                .options(selectinload(ProductOperationRunORM.items))
                .where(ProductOperationRunORM.run_id == run_id)
            ).first()
            return self._run_to_payload(refreshed) if refreshed else None

    def _apply_sync_sync(
        self,
        account_id: str,
        items: tuple[ManagedProduct, ...],
        full: bool,
        complete: bool,
    ) -> None:
        with self._session_factory() as session:
            now = utcnow()
            seen_ids: set[str] = set()
            synced_rows: dict[str, ProductItemORM] = {}
            for item in items:
                seen_ids.add(item.item_id)
                row = session.get(ProductItemORM, (account_id, item.item_id))
                if row is None:
                    row = ProductItemORM(
                        account_id=account_id,
                        item_id=item.item_id,
                        created_at=now,
                    )
                    session.add(row)
                synced_rows[item.item_id] = row
                row.title = item.title
                row.price = item.price
                row.category_id = item.category_id or None
                row.cover_url = item.cover_url or None
                row.detail_url = item.detail_url or None
                row.platform_item_status = item.platform_item_status or None
                row.want_count = item.want_count
                row.want_text = item.want_text
                row.platform_status = "selling"
                row.sync_state = "current"
                row.missing_sync_count = 0
                row.last_seen_at = now
                row.last_synced_at = now
                row.raw_data = json.dumps(dict(item.raw_data), ensure_ascii=False)
                row.updated_at = now
            if seen_ids:
                publish_tasks = session.scalars(
                    select(ProductPublishTaskORM).where(
                        ProductPublishTaskORM.account_id == account_id,
                        ProductPublishTaskORM.item_id.in_(seen_ids),
                        ProductPublishTaskORM.status.in_(("success", "verification_required")),
                    )
                ).all()
                for task in publish_tasks:
                    task.status = "success"
                    task.phase = "completed"
                    task.failure_kind = None
                    task.error = None
                    task.retryable = False
                    task.result_certainty = "confirmed_success"
                    task.finished_at = task.finished_at or now
                    task.updated_at = now
                    product_row = synced_rows.get(task.item_id or "")
                    if product_row is None:
                        product_row = session.get(
                            ProductItemORM,
                            {"account_id": account_id, "item_id": task.item_id},
                        )
                    if product_row is not None and product_row.published_at_source != "platform":
                        task_finished_at = as_utc(task.finished_at)
                        product_published_at = as_utc(product_row.published_at)
                        if task_finished_at is not None and (
                            product_published_at is None or task_finished_at < product_published_at
                        ):
                            product_row.published_at = task_finished_at
                            product_row.published_at_source = "publish_task"
            if full and complete:
                existing = session.scalars(
                    select(ProductItemORM).where(ProductItemORM.account_id == account_id)
                ).all()
                for row in existing:
                    if row.item_id in seen_ids:
                        continue
                    if row.platform_status in {"offline", "deleted"}:
                        if row.sync_state == "pending_confirmation":
                            row.sync_state = "current"
                            row.last_synced_at = now
                            row.updated_at = now
                        continue
                    row.missing_sync_count += 1
                    row.sync_state = (
                        "missing" if row.missing_sync_count >= 2 else "pending_confirmation"
                    )
                    if row.missing_sync_count >= 2:
                        row.platform_status = "not_selling"
                    row.last_synced_at = now
                    row.updated_at = now
            setting = self._get_or_create_setting(session, account_id)
            setting.last_sync_at = now
            if full and complete:
                setting.last_full_sync_at = now
            setting.last_sync_status = "success"
            setting.last_sync_error = None
            setting.next_sync_at = self._next_sync(setting, now=now)
            setting.updated_at = now
            session.commit()

    def _fail_sync_sync(self, account_id: str, error: str) -> None:
        with self._session_factory() as session:
            if session.get(AccountORM, account_id) is None:
                return
            setting = self._get_or_create_setting(session, account_id)
            setting.last_sync_status = "failed"
            setting.last_sync_error = error
            setting.next_sync_at = self._next_sync(setting)
            setting.updated_at = utcnow()
            session.commit()

    def _operation_candidates_sync(
        self, account_id: str, item_ids: list[str], all_selling: bool
    ) -> list[ProductItemPayload]:
        with self._session_factory() as session:
            stmt = select(ProductItemORM).where(ProductItemORM.account_id == account_id)
            if all_selling:
                stmt = stmt.where(ProductItemORM.platform_status == "selling")
            else:
                stmt = stmt.where(ProductItemORM.item_id.in_(item_ids))
            rows = session.scalars(stmt.order_by(ProductItemORM.last_seen_at.desc())).all()
            return [self._item_to_payload(row) for row in rows]

    def _mark_item_status_sync(
        self,
        account_id: str,
        item_id: str,
        status: str,
        pending_confirmation: bool,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(ProductItemORM, (account_id, item_id))
            if row is None:
                return
            row.platform_status = status
            row.sync_state = "pending_confirmation" if pending_confirmation else "current"
            row.missing_sync_count = 0
            row.updated_at = utcnow()
            session.commit()

    def _mark_polished_sync(self, account_id: str, item_id: str, when: datetime) -> None:
        with self._session_factory() as session:
            row = session.get(ProductItemORM, (account_id, item_id))
            if row is None:
                return
            normalized = as_utc(when) or utcnow()
            row.last_polished_at = normalized
            row.last_polished_on = normalized.astimezone(SHANGHAI).date().isoformat()
            row.updated_at = normalized
            session.commit()

    def _complete_polish_sync(self, account_id: str, when: datetime) -> None:
        with self._session_factory() as session:
            row = session.get(ProductSyncSettingORM, account_id)
            if row is None:
                return
            normalized = as_utc(when) or utcnow()
            row.last_polish_at = normalized
            row.next_polish_at = self._next_polish(row, now=normalized)
            row.updated_at = normalized
            session.commit()

    def _list_due_settings_sync(
        self, now: datetime
    ) -> list[tuple[ProductSyncSettingPayload, bool, bool]]:
        normalized_now = as_utc(now) or utcnow()
        with self._session_factory() as session:
            rows = session.scalars(
                select(ProductSyncSettingORM)
                .join(AccountORM, AccountORM.account_id == ProductSyncSettingORM.account_id)
                .where(AccountORM.enabled.is_(True), AccountORM.cookie != "")
            ).all()
            result = []
            for row in rows:
                sync_due = bool(
                    row.sync_enabled
                    and row.next_sync_at is not None
                    and (as_utc(row.next_sync_at) or normalized_now) <= normalized_now
                )
                polish_due = bool(
                    row.auto_polish_enabled
                    and row.next_polish_at is not None
                    and (as_utc(row.next_polish_at) or normalized_now) <= normalized_now
                )
                if sync_due or polish_due:
                    result.append((self._setting_to_payload(row), sync_due, polish_due))
            return result

    def _reschedule_sync(self, account_id: str, sync: bool, polish: bool) -> None:
        with self._session_factory() as session:
            row = session.get(ProductSyncSettingORM, account_id)
            if row is None:
                return
            if sync:
                row.next_sync_at = self._next_sync(row)
            if polish:
                row.next_polish_at = self._next_polish(row)
            row.updated_at = utcnow()
            session.commit()

    @staticmethod
    def _item_to_payload(row: ProductItemORM) -> ProductItemPayload:
        return ProductItemPayload(
            account_id=row.account_id,
            item_id=row.item_id,
            title=row.title or "",
            price=row.price or "",
            category_id=row.category_id,
            cover_url=row.cover_url,
            detail_url=row.detail_url,
            platform_item_status=row.platform_item_status,
            want_count=row.want_count,
            want_text=row.want_text,
            platform_status=row.platform_status,  # type: ignore[arg-type]
            sync_state=row.sync_state,
            missing_sync_count=row.missing_sync_count,
            last_seen_at=as_utc(row.last_seen_at),
            last_synced_at=as_utc(row.last_synced_at),
            last_polished_on=row.last_polished_on,
            last_polished_at=as_utc(row.last_polished_at),
            published_at=as_utc(row.published_at),
            published_at_source=(
                row.published_at_source
                if row.published_at_source in {"platform", "publish_task"}
                else "unknown"
            ),
            created_at=as_utc(row.created_at),
            updated_at=as_utc(row.updated_at),
        )

    @staticmethod
    def _setting_to_payload(row: ProductSyncSettingORM) -> ProductSyncSettingPayload:
        return ProductSyncSettingPayload(
            account_id=row.account_id,
            sync_enabled=row.sync_enabled,
            sync_interval_minutes=row.sync_interval_minutes,
            sync_jitter_minutes=row.sync_jitter_minutes,
            full_sync_interval_hours=row.full_sync_interval_hours,
            publish_verify_delay_seconds=row.publish_verify_delay_seconds,
            auto_polish_enabled=row.auto_polish_enabled,
            polish_hour=row.polish_hour,
            polish_jitter_minutes=row.polish_jitter_minutes,
            last_sync_at=as_utc(row.last_sync_at),
            last_full_sync_at=as_utc(row.last_full_sync_at),
            last_sync_status=row.last_sync_status,
            last_sync_error=row.last_sync_error,
            next_sync_at=as_utc(row.next_sync_at),
            last_polish_at=as_utc(row.last_polish_at),
            next_polish_at=as_utc(row.next_polish_at),
            created_at=as_utc(row.created_at),
            updated_at=as_utc(row.updated_at),
        )

    @staticmethod
    def _run_to_payload(row: ProductOperationRunORM) -> ProductOperationRunPayload:
        try:
            requested = json.loads(row.requested_item_ids or "[]")
        except (TypeError, json.JSONDecodeError):
            requested = []
        item_rows = list(row.items) if "items" in row.__dict__ else []
        return ProductOperationRunPayload(
            run_id=row.run_id,
            account_id=row.account_id,
            operation=row.operation,  # type: ignore[arg-type]
            trigger=row.trigger,  # type: ignore[arg-type]
            status=row.status,  # type: ignore[arg-type]
            full_sync=row.full_sync,
            requested_item_ids=[str(value) for value in requested if str(value)],
            total_count=row.total_count,
            success_count=row.success_count,
            failed_count=row.failed_count,
            skipped_count=row.skipped_count,
            error=row.error,
            created_at=as_utc(row.created_at),
            updated_at=as_utc(row.updated_at),
            started_at=as_utc(row.started_at),
            finished_at=as_utc(row.finished_at),
            items=[
                ProductOperationItemPayload(
                    result_id=item.result_id,
                    run_id=item.run_id,
                    item_id=item.item_id,
                    status=item.status,
                    message=item.message,
                    platform_code=item.platform_code,
                    created_at=as_utc(item.created_at),
                    updated_at=as_utc(item.updated_at),
                )
                for item in item_rows
            ],
        )

    def _get_or_create_setting(
        self, session: Session, account_id: str
    ) -> ProductSyncSettingORM:
        row = session.get(ProductSyncSettingORM, account_id)
        if row is not None:
            return row
        now = utcnow()
        row = ProductSyncSettingORM(
            account_id=account_id,
            sync_enabled=True,
            sync_interval_minutes=20,
            sync_jitter_minutes=5,
            full_sync_interval_hours=6,
            publish_verify_delay_seconds=30,
            auto_polish_enabled=False,
            polish_hour=8,
            polish_jitter_minutes=10,
            next_sync_at=now + timedelta(minutes=random.randint(1, 5)),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        return row

    @staticmethod
    def _next_sync(row: ProductSyncSettingORM, *, now: datetime | None = None) -> datetime | None:
        if not row.sync_enabled:
            return None
        base = as_utc(now) or utcnow()
        jitter = random.randint(0, max(0, row.sync_jitter_minutes))
        return base + timedelta(minutes=max(5, row.sync_interval_minutes) + jitter)

    @staticmethod
    def _next_polish(row: ProductSyncSettingORM, *, now: datetime | None = None) -> datetime | None:
        if not row.auto_polish_enabled:
            return None
        current = (as_utc(now) or utcnow()).astimezone(SHANGHAI)
        target = current.replace(
            hour=max(0, min(23, row.polish_hour)), minute=0, second=0, microsecond=0
        )
        target += timedelta(minutes=random.randint(0, max(0, row.polish_jitter_minutes)))
        if target <= current:
            target += timedelta(days=1)
        return target.astimezone(UTC)


OperationsFactory = Callable[..., MtopProductOperations]


class ProductManagementService:
    def __init__(
        self,
        store: AccountStore,
        repository: ProductManagementRepository | None = None,
        *,
        operations_factory: OperationsFactory = MtopProductOperations,
    ) -> None:
        self.store = store
        self.repository = repository or ProductManagementRepository()
        self.operations_factory = operations_factory

    async def execute_run(self, run_id: str) -> dict[str, object]:
        run = await self.repository.start_run(run_id)
        if run is None:
            raise ValueError("product operation run not found")
        if run.status not in {"running", "pending"}:
            return {"ok": run.status in {"success", "partial_success"}, "run": run.model_dump(mode="json")}
        account = await self.store.get_account(run.account_id)
        if account is None:
            raise ValueError("account not found")
        async with account_product_operation_lock(run.account_id):
            client = self.operations_factory(self._to_core_account(account))
            cookie_changed = False
            try:
                if run.operation == "sync":
                    result = await self._execute_sync(run, client)
                elif run.operation == "polish":
                    result = await self._execute_polish(run, client)
                elif run.operation == "offline":
                    result = await self._execute_offline(run, client)
                elif run.operation == "delete":
                    result = await self._execute_delete(run, client)
                else:
                    raise ValueError(f"unsupported product operation: {run.operation}")
                cookie_changed = await merge_account_cookie_updates(
                    self.store,
                    run.account_id,
                    client.cookie_updates(),
                    source="product_management",
                )
                result["cookie_changed"] = cookie_changed
                return result
            except ProductOperationError as exc:
                cookie_changed = await merge_account_cookie_updates(
                    self.store,
                    run.account_id,
                    exc.cookie_updates or client.cookie_updates(),
                    source="product_management",
                )
                if run.operation == "sync":
                    await self.repository.fail_sync(run.account_id, str(exc))
                status = (
                    "verification_required"
                    if exc.uncertain or exc.verification_required
                    else "failed"
                )
                failed = await self.repository.finish_run(
                    run.run_id,
                    status=status,
                    total_count=len(run.requested_item_ids),
                    success_count=0,
                    failed_count=len(run.requested_item_ids),
                    skipped_count=0,
                    error=str(exc),
                )
                return {
                    "ok": False,
                    "uncertain": exc.uncertain,
                    "verification_required": exc.verification_required,
                    "cookie_changed": cookie_changed,
                    "run": failed.model_dump(mode="json") if failed else None,
                }
            except Exception as exc:
                if run.operation == "sync":
                    await self.repository.fail_sync(run.account_id, str(exc))
                await self.repository.finish_run(
                    run.run_id,
                    status="failed",
                    total_count=len(run.requested_item_ids),
                    success_count=0,
                    failed_count=len(run.requested_item_ids),
                    skipped_count=0,
                    error=str(exc),
                )
                raise
            finally:
                client.close()

    async def _execute_sync(
        self, run: ProductOperationRunPayload, client: MtopProductOperations
    ) -> dict[str, object]:
        result = await run_platform_blocking(
            client.list_selling_items,
            page_size=20,
            max_pages=None if run.full_sync else 1,
        )
        await self.repository.apply_sync(
            run.account_id,
            result.items,
            full=run.full_sync,
            complete=result.complete,
        )
        finished = await self.repository.finish_run(
            run.run_id,
            status="success",
            total_count=len(result.items),
            success_count=len(result.items),
            failed_count=0,
            skipped_count=0,
        )
        return {"ok": True, "run": finished.model_dump(mode="json") if finished else None}

    async def _execute_polish(
        self, run: ProductOperationRunPayload, client: MtopProductOperations
    ) -> dict[str, object]:
        candidates = await self.repository.operation_candidates(
            run.account_id,
            run.requested_item_ids,
            all_selling=not run.requested_item_ids,
        )
        today = utcnow().astimezone(SHANGHAI).date().isoformat()
        success = failed = skipped = 0
        abort_error: str | None = None
        for index, item in enumerate(candidates):
            if item.platform_status != "selling" or item.last_polished_on == today:
                skipped += 1
                await self.repository.add_run_item(
                    run.run_id, item.item_id, "skipped", "今日已擦亮或商品不在售"
                )
                continue
            try:
                action = await run_platform_blocking(client.polish_item, item.item_id)
                await self._record_action(run, action)
                if action.success:
                    await self.repository.mark_polished(run.account_id, item.item_id, utcnow())
                    skipped += int(action.skipped)
                    success += int(not action.skipped)
                else:
                    failed += 1
            except ProductOperationError as exc:
                failed += 1
                await self.repository.add_run_item(
                    run.run_id, item.item_id, "failed", str(exc), exc.kind
                )
                if exc.kind in {"auth", "risk_control", "cookie_conflict"}:
                    abort_error = str(exc)
                    break
            if index < len(candidates) - 1:
                await asyncio.sleep(random.uniform(2, 5))
        result = await self._finish_action_run(
            run, len(candidates), success, failed, skipped, abort_error
        )
        if result.get("ok"):
            await self.repository.complete_polish(run.account_id, utcnow())
        return result

    async def _execute_offline(
        self, run: ProductOperationRunPayload, client: MtopProductOperations
    ) -> dict[str, object]:
        candidates = await self.repository.operation_candidates(
            run.account_id, run.requested_item_ids
        )
        ids = [item.item_id for item in candidates if item.platform_status == "selling"]
        success = failed = 0
        skipped = len(candidates) - len(ids)
        uncertain = False
        verification_required = False
        error: str | None = None
        for index, item_id in enumerate(ids):
            try:
                action = await run_platform_blocking(client.offline_personal_item, item_id)
                await self._record_action(run, action)
                if action.success:
                    skipped += int(action.skipped)
                    success += int(not action.skipped)
                    await self.repository.mark_item_status(
                        run.account_id,
                        action.item_id,
                        "offline",
                        pending_confirmation=not action.verified,
                    )
                else:
                    failed += 1
            except ProductOperationError as exc:
                failed += 1
                uncertain = uncertain or exc.uncertain
                verification_required = verification_required or exc.verification_required
                error = str(exc)
                await self.repository.add_run_item(
                    run.run_id,
                    item_id,
                    "verification_required"
                    if exc.uncertain or exc.verification_required
                    else "failed",
                    str(exc),
                    f"personal_web:{exc.kind}",
                )
                if (
                    exc.uncertain
                    or exc.verification_required
                    or exc.retryable
                    or exc.kind in {"auth", "risk_control", "cookie_conflict"}
                ):
                    break
            if index < len(ids) - 1:
                await asyncio.sleep(random.uniform(3, 8))
        skipped = max(skipped, len(candidates) - success - failed)
        status = (
            "verification_required"
            if uncertain or verification_required
            else "partial_success"
            if success and failed
            else "success"
            if not failed
            else "failed"
        )
        finished = await self.repository.finish_run(
            run.run_id,
            status=status,
            total_count=len(candidates),
            success_count=success,
            failed_count=failed,
            skipped_count=skipped,
            error=error,
        )
        return {
            "ok": status in {"success", "partial_success"},
            "uncertain": uncertain,
            "verification_required": verification_required,
            "run": finished.model_dump(mode="json") if finished else None,
        }

    async def _execute_delete(
        self, run: ProductOperationRunPayload, client: MtopProductOperations
    ) -> dict[str, object]:
        candidates = await self.repository.operation_candidates(
            run.account_id, run.requested_item_ids
        )
        success = failed = 0
        skipped = 0
        uncertain = False
        verification_required = False
        error: str | None = None
        for index, item in enumerate(candidates):
            try:
                action = await run_platform_blocking(client.delete_personal_item, item.item_id)
                await self._record_action(run, action)
                if action.success:
                    skipped += int(action.skipped)
                    success += int(not action.skipped)
                    await self.repository.mark_item_status(
                        run.account_id,
                        item.item_id,
                        "deleted",
                        pending_confirmation=not action.verified,
                    )
                else:
                    failed += 1
            except ProductOperationError as exc:
                failed += 1
                uncertain = uncertain or exc.uncertain
                verification_required = verification_required or exc.verification_required
                error = str(exc)
                await self.repository.add_run_item(
                    run.run_id,
                    item.item_id,
                    "verification_required"
                    if exc.uncertain or exc.verification_required
                    else "failed",
                    str(exc),
                    f"personal_web:{exc.kind}",
                )
                if (
                    exc.uncertain
                    or exc.verification_required
                    or exc.retryable
                    or exc.kind in {"auth", "risk_control", "cookie_conflict"}
                ):
                    break
            if index < len(candidates) - 1:
                await asyncio.sleep(random.uniform(3, 8))
        skipped = max(skipped, len(candidates) - success - failed)
        status = (
            "verification_required"
            if uncertain or verification_required
            else "partial_success"
            if success and failed
            else "success"
            if not failed
            else "failed"
        )
        finished = await self.repository.finish_run(
            run.run_id,
            status=status,
            total_count=len(candidates),
            success_count=success,
            failed_count=failed,
            skipped_count=skipped,
            error=error,
        )
        return {
            "ok": status in {"success", "partial_success"},
            "uncertain": uncertain,
            "verification_required": verification_required,
            "run": finished.model_dump(mode="json") if finished else None,
        }

    async def _record_action(
        self, run: ProductOperationRunPayload, action: ProductActionItemResult
    ) -> None:
        await self.repository.add_run_item(
            run.run_id,
            action.item_id,
            "skipped" if action.skipped else "success" if action.success else "failed",
            action.message or None,
            action.platform_code or action.channel or None,
        )

    async def _finish_action_run(
        self,
        run: ProductOperationRunPayload,
        total: int,
        success: int,
        failed: int,
        skipped: int,
        error: str | None = None,
    ) -> dict[str, object]:
        status = (
            "partial_success"
            if success and failed
            else "failed"
            if failed and not success and not skipped
            else "success"
        )
        finished = await self.repository.finish_run(
            run.run_id,
            status=status,
            total_count=total,
            success_count=success,
            failed_count=failed,
            skipped_count=skipped,
            error=error,
        )
        return {"ok": status in {"success", "partial_success"}, "run": finished.model_dump(mode="json") if finished else None}

    @staticmethod
    def _to_core_account(account: AccountRecord) -> AccountConfig:
        return AccountConfig(
            account_id=account.account_id,
            cookie=account.cookie,
            nickname=account.display_name,
            enabled=account.enabled,
            proxy=build_core_account_proxy(account),
        )


async def create_and_enqueue_product_run(
    store: AccountStore,
    repository: ProductManagementRepository,
    *,
    account_id: str,
    operation: str,
    trigger: str,
    item_ids: list[str] | None = None,
    full_sync: bool = False,
) -> tuple[ProductOperationRunPayload, BackgroundTaskPayload]:
    run = await repository.create_run(
        account_id,
        operation,
        trigger,
        item_ids=item_ids,
        full_sync=full_sync,
    )
    task = await store.create_background_task(
        BackgroundTaskCreatePayload(
            account_id=account_id,
            task_type=f"product.{operation}_items" if operation != "sync" else "product.sync_account",
            dedupe_key=f"product-operation:{run.run_id}",
            payload={"account_id": account_id, "run_id": run.run_id},
        )
    )
    assert task is not None
    if task.status == "pending" and task.queued_at is None:
        try:
            result = await enqueue_background_task(store, task)
            if not result.queued:
                raise RuntimeError(result.message)
            await store.mark_background_task_queued(task.task_id)
        except Exception as exc:
            error = f"queue unavailable: {exc.__class__.__name__}: {exc}"
            await store.finish_background_task(task.task_id, status="failed", error=error)
            await repository.finish_run(
                run.run_id,
                status="failed",
                total_count=len(item_ids or []),
                success_count=0,
                failed_count=len(item_ids or []),
                skipped_count=0,
                error=error,
            )
            raise
    refreshed_task = await store.get_background_task(task.task_id)
    refreshed_run = await repository.get_run(run.run_id)
    return refreshed_run or run, refreshed_task or task
