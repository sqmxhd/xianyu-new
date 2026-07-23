"""Durable preflight and execution service for seller order actions."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from integrations.xianyu_core import (
    AccountConfig,
    MtopOrderActions,
    OrderActionError,
    OrderActionResult,
)

from .account_network import build_core_account_proxy
from .database import SessionLocal
from .executors import run_db_blocking, run_platform_blocking
from .order_action_policy import order_action_availability
from .orm import OrderEventORM, OrderOperationORM, OrderORM
from .product_publish_service import merge_account_cookie_updates
from .schemas import (
    OrderAction,
    OrderOperationExecutePayload,
    OrderOperationExecuteRequest,
    OrderOperationPayload,
    OrderOperationPreviewPayload,
)
from .store import AccountRecord, AccountStore


OperationsFactory = Callable[..., MtopOrderActions]
_ORDER_LOCKS: dict[str, asyncio.Lock] = {}


def utcnow() -> datetime:
    return datetime.now(UTC)


class OrderActionConflict(RuntimeError):
    pass


class OrderActionRepository:
    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    async def get_by_idempotency(
        self, account_id: str, idempotency_key: str
    ) -> OrderOperationPayload | None:
        return await run_db_blocking(
            self._get_by_idempotency_sync, account_id, idempotency_key
        )

    async def create(
        self,
        *,
        order_pk: str,
        account_id: str,
        platform_order_id: str,
        action: str,
        idempotency_key: str,
        requested_by: str | None,
        pre_status: str,
        request_summary: Mapping[str, Any],
    ) -> tuple[OrderOperationPayload, bool]:
        return await run_db_blocking(
            self._create_sync,
            order_pk,
            account_id,
            platform_order_id,
            action,
            idempotency_key,
            requested_by,
            pre_status,
            dict(request_summary),
        )

    async def finish(
        self,
        operation_id: str,
        *,
        status: str,
        message: str | None,
        error: str | None,
        platform_code: str | None,
        post_status: str | None,
        response_summary: Mapping[str, Any] | None,
        apply_action_state: bool = False,
    ) -> OrderOperationPayload:
        return await run_db_blocking(
            self._finish_sync,
            operation_id,
            status,
            message,
            error,
            platform_code,
            post_status,
            dict(response_summary or {}),
            apply_action_state,
        )

    def _get_by_idempotency_sync(
        self, account_id: str, idempotency_key: str
    ) -> OrderOperationPayload | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(OrderOperationORM).where(
                    OrderOperationORM.account_id == account_id,
                    OrderOperationORM.idempotency_key == idempotency_key,
                )
            ).first()
            return self._to_payload(row) if row else None

    def _create_sync(
        self,
        order_pk: str,
        account_id: str,
        platform_order_id: str,
        action: str,
        idempotency_key: str,
        requested_by: str | None,
        pre_status: str,
        request_summary: dict[str, Any],
    ) -> tuple[OrderOperationPayload, bool]:
        now = utcnow()
        with self._session_factory() as session:
            order = session.get(OrderORM, order_pk, with_for_update=True)
            if order is None:
                raise ValueError("order not found")
            active = session.scalars(
                select(OrderOperationORM).where(
                    OrderOperationORM.order_pk == order_pk,
                    OrderOperationORM.status == "processing",
                )
            ).first()
            if active is not None:
                raise OrderActionConflict("该订单已有操作正在执行")
            row = OrderOperationORM(
                operation_id=uuid.uuid4().hex,
                order_pk=order_pk,
                account_id=account_id,
                platform_order_id=platform_order_id,
                action=action,
                status="processing",
                idempotency_key=idempotency_key,
                requested_by=requested_by,
                pre_status=pre_status,
                request_json=json.dumps(request_summary, ensure_ascii=False),
                created_at=now,
                updated_at=now,
                started_at=now,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                existing = session.scalars(
                    select(OrderOperationORM).where(
                        OrderOperationORM.account_id == account_id,
                        OrderOperationORM.idempotency_key == idempotency_key,
                    )
                ).first()
                if existing is not None:
                    return self._to_payload(existing), False
                raise exc
            return self._to_payload(row), True

    def _finish_sync(
        self,
        operation_id: str,
        status: str,
        message: str | None,
        error: str | None,
        platform_code: str | None,
        post_status: str | None,
        response_summary: dict[str, Any],
        apply_action_state: bool,
    ) -> OrderOperationPayload:
        now = utcnow()
        with self._session_factory() as session:
            row = session.get(OrderOperationORM, operation_id)
            if row is None:
                raise ValueError("order operation not found")
            row.status = status
            row.message = message
            row.error = error
            row.platform_code = platform_code
            row.post_status = post_status
            row.response_json = json.dumps(response_summary, ensure_ascii=False)
            row.updated_at = now
            row.finished_at = now
            if apply_action_state and status == "succeeded":
                order = session.get(OrderORM, row.order_pk)
                if order is not None:
                    previous_status = order.status
                    request_summary = self._load(row.request_json)
                    request_summary = (
                        request_summary if isinstance(request_summary, Mapping) else {}
                    )
                    if row.action in {
                        "confirm_shipping",
                        "offline_shipping",
                        "free_shipping",
                    }:
                        order.status = "shipped"
                        order.status_text = "已发货"
                        order.platform_status = "已发货"
                        order.logistics_type = {
                            "confirm_shipping": "dummy",
                            "offline_shipping": "offline",
                            "free_shipping": "bargain_free_shipping",
                        }[row.action]
                        if row.action == "offline_shipping":
                            order.carrier_code = str(
                                request_summary.get("carrier_code") or ""
                            ).strip() or order.carrier_code
                            order.tracking_no = str(
                                request_summary.get("tracking_no") or ""
                            ).strip() or order.tracking_no
                    elif row.action == "close_order":
                        order.status = "closed"
                        order.status_text = "交易关闭"
                        order.platform_status = "交易关闭"
                    elif row.action == "rate_buyer":
                        order.seller_rate_status = "4"
                    elif row.action == "refuse_refund":
                        order.refund_status = "rejected"
                        order.platform_refund_actions = json.dumps(
                            [], ensure_ascii=False
                        )
                        order.refund_refuse_options = json.dumps(
                            [], ensure_ascii=False
                        )
                    order.last_synced_at = now
                    order.sync_state = "confirmed"
                    order.sync_error = None
                    order.updated_at = now
                    event_status = order.status
                    session.add(
                        OrderEventORM(
                            event_pk=uuid.uuid4().hex,
                            order_pk=order.order_pk,
                            account_id=order.account_id,
                            conversation_id=order.conversation_id,
                            message_pk=f"action:{row.operation_id}",
                            platform_order_id=order.platform_order_id,
                            item_id=order.item_id,
                            event_type=f"platform_action_{row.action}",
                            status=event_status,
                            status_text=message,
                            raw_summary=json.dumps(
                                {
                                    "action": row.action,
                                    "previous_status": previous_status,
                                    "platform_code": platform_code,
                                },
                                ensure_ascii=False,
                            ),
                            created_at=now,
                        )
                    )
                    row.post_status = order.status
            session.commit()
            return self._to_payload(row)

    @staticmethod
    def _load(raw: str | None) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    @classmethod
    def _to_payload(cls, row: OrderOperationORM) -> OrderOperationPayload:
        return OrderOperationPayload(
            operation_id=row.operation_id,
            order_pk=row.order_pk,
            account_id=row.account_id,
            platform_order_id=row.platform_order_id,
            action=row.action,  # type: ignore[arg-type]
            status=row.status,  # type: ignore[arg-type]
            idempotency_key=row.idempotency_key,
            requested_by=row.requested_by,
            pre_status=row.pre_status,
            post_status=row.post_status,
            message=row.message,
            error=row.error,
            platform_code=row.platform_code,
            request_summary=cls._load(row.request_json),
            response_summary=cls._load(row.response_json),
            created_at=row.created_at,
            updated_at=row.updated_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )


class OrderActionService:
    def __init__(
        self,
        store: AccountStore,
        repository: OrderActionRepository | None = None,
        *,
        operations_factory: OperationsFactory = MtopOrderActions,
    ) -> None:
        self.store = store
        self.repository = repository or OrderActionRepository(store.session_factory)
        self.operations_factory = operations_factory

    async def preview(self, order_pk: str, action: OrderAction) -> OrderOperationPreviewPayload:
        order = await self.refresh(order_pk)
        availability = {item.action: item for item in order_action_availability(order)}
        selected = availability[action]
        return OrderOperationPreviewPayload(
            eligible=selected.enabled,
            reasons=[] if selected.enabled else [selected.reason],
            action=selected,
            order=order,
        )

    async def refresh(self, order_pk: str):
        order = await self.store.get_order(order_pk)
        if order is None:
            raise ValueError("order not found")
        if not order.platform_order_id:
            raise OrderActionConflict("订单缺少平台订单号")
        account = await self.store.get_account(order.account_id)
        if account is None:
            raise ValueError("account not found")
        client = self.operations_factory(self._to_core_account(account))
        try:
            return await self._refresh_platform_state(
                client,
                order,
                require_headinfo=(
                    order.data_source != "seller_sold"
                    or order.headinfo_confirmed_at is not None
                ),
                source="order_detail_refresh",
            )
        finally:
            client.close()

    async def refresh_scheduled(self, order_pk: str):
        lock = _ORDER_LOCKS.setdefault(order_pk, asyncio.Lock())
        if lock.locked():
            raise OrderActionConflict("订单正在执行其他平台操作")
        async with lock:
            return await self.refresh(order_pk)

    async def execute(
        self,
        order_pk: str,
        request: OrderOperationExecuteRequest,
        *,
        requested_by: str | None,
    ) -> OrderOperationExecutePayload:
        lock = _ORDER_LOCKS.setdefault(order_pk, asyncio.Lock())
        async with lock:
            order = await self.store.get_order(order_pk)
            if order is None:
                raise ValueError("order not found")
            existing = await self.repository.get_by_idempotency(
                order.account_id, request.idempotency_key
            )
            if existing is not None:
                if existing.order_pk != order_pk or existing.action != request.action:
                    raise OrderActionConflict("幂等键已用于其他订单操作")
                current = await self.store.get_order(order_pk)
                assert current is not None
                return OrderOperationExecutePayload(operation=existing, order=current)

            account = await self.store.get_account(order.account_id)
            if account is None:
                raise ValueError("account not found")
            client = self.operations_factory(self._to_core_account(account))
            try:
                refreshed = await self._refresh_platform_state(
                    client,
                    order,
                    require_headinfo=(
                        order.data_source != "seller_sold"
                        or order.headinfo_confirmed_at is not None
                    ),
                    source="order_action_preflight",
                )
                selected = {
                    item.action: item for item in order_action_availability(refreshed)
                }[request.action]
                if not selected.enabled:
                    raise OrderActionConflict(selected.reason)
                if request.action == "offline_shipping":
                    if not request.tracking_no:
                        raise OrderActionConflict("请填写快递单号")
                    if not request.carrier_code:
                        raise OrderActionConflict("请填写快递公司编码")
                if request.action == "refuse_refund":
                    await self._validate_refuse_request(client, refreshed, request)

                operation, operation_created = await self.repository.create(
                    order_pk=order_pk,
                    account_id=refreshed.account_id,
                    platform_order_id=refreshed.platform_order_id or "",
                    action=request.action,
                    idempotency_key=request.idempotency_key,
                    requested_by=requested_by,
                    pre_status=refreshed.status,
                    request_summary={
                        "action": request.action,
                        "feedback": request.feedback if request.action == "rate_buyer" else None,
                        "close_reason": (
                            request.close_reason if request.action == "close_order" else None
                        ),
                        "tracking_no": (
                            request.tracking_no
                            if request.action == "offline_shipping"
                            else None
                        ),
                        "carrier_code": (
                            request.carrier_code
                            if request.action == "offline_shipping"
                            else None
                        ),
                        "refund_reason_id": (
                            request.refund_reason_id
                            if request.action == "refuse_refund"
                            else None
                        ),
                    },
                )
                if not operation_created or operation.status != "processing":
                    current = await self.store.get_order(order_pk)
                    assert current is not None
                    return OrderOperationExecutePayload(operation=operation, order=current)

                try:
                    result = await run_platform_blocking(
                        client.execute,
                        request.action,
                        refreshed.platform_order_id or "",
                        item_id=refreshed.item_id or "",
                        buyer_id=refreshed.buyer_user_id or refreshed.peer_user_id or "",
                        feedback=request.feedback or "不错的买家，期待再次交易",
                        close_reason=request.close_reason or "其他原因",
                        tracking_no=request.tracking_no or "",
                        carrier_code=request.carrier_code or "",
                        carrier_brand_code=request.carrier_brand_code or "",
                        sender_address_id=(
                            request.sender_address_id
                            or str(
                                refreshed.platform_shipping_context.get(
                                    "sender_address_id"
                                )
                                or ""
                            )
                        ),
                        refund_id=refreshed.refund_id or "",
                        refund_reason_id=request.refund_reason_id or "",
                        refund_proof=request.refund_proof,
                        refund_logistic_info=request.refund_logistic_info,
                        refund_negotiation_apply=request.refund_negotiation_apply,
                    )
                    await merge_account_cookie_updates(
                        self.store,
                        refreshed.account_id,
                        client.cookie_updates(),
                        source=f"order_action_{request.action}",
                    )
                    operation = await self.repository.finish(
                        operation.operation_id,
                        status="succeeded",
                        message=result.message,
                        error=None,
                        platform_code=result.platform_code,
                        post_status=None,
                        response_summary=self._result_summary(result),
                        apply_action_state=True,
                    )
                    await self._best_effort_readback(client, order_pk)
                except OrderActionError as exc:
                    await merge_account_cookie_updates(
                        self.store,
                        refreshed.account_id,
                        exc.cookie_updates or client.cookie_updates(),
                        source=f"order_action_{request.action}_error",
                    )
                    operation = await self.repository.finish(
                        operation.operation_id,
                        status="uncertain" if exc.uncertain else "failed",
                        message=None,
                        error=str(exc),
                        platform_code=self._response_code(exc.raw_response),
                        post_status=refreshed.status,
                        response_summary={"ret": exc.raw_response.get("ret")},
                    )
                except Exception as exc:
                    operation = await self.repository.finish(
                        operation.operation_id,
                        status="uncertain",
                        message=None,
                        error=f"{exc.__class__.__name__}: {exc}",
                        platform_code=None,
                        post_status=refreshed.status,
                        response_summary={"exception": exc.__class__.__name__},
                    )
                current = await self.store.get_order(order_pk)
                assert current is not None
                return OrderOperationExecutePayload(operation=operation, order=current)
            finally:
                client.close()

    async def _validate_refuse_request(
        self,
        client: MtopOrderActions,
        order: Any,
        request: OrderOperationExecuteRequest,
    ) -> None:
        reason_id = str(request.refund_reason_id or "").strip()
        if not reason_id:
            raise OrderActionConflict("请选择拒绝退款原因")
        allowed_ids = {
            str(item.get("id") or "").strip()
            for item in order.refund_refuse_options
            if isinstance(item, Mapping)
        }
        if reason_id not in allowed_ids:
            raise OrderActionConflict("拒绝退款原因已变化，请刷新后重新选择")
        rendered = await run_platform_blocking(
            client.get_refuse_refund_options,
            order.refund_id or "",
            reason_id,
        )
        proof = rendered.get("refuseProof")
        proof = proof if isinstance(proof, Mapping) else {}
        if bool(proof.get("mustProof")):
            proof_type = str(proof.get("bizType") or "NORMAL").upper()
            if proof_type == "LOGISTIC" and not request.refund_logistic_info:
                raise OrderActionConflict("该拒绝原因要求填写退款物流信息")
            if proof_type != "LOGISTIC" and not request.refund_proof:
                raise OrderActionConflict("该拒绝原因要求上传拒绝退款凭证")

    async def _best_effort_readback(
        self, client: MtopOrderActions, order_pk: str
    ) -> None:
        try:
            order = await self.store.get_order(order_pk)
            if order is None:
                return
            await self._refresh_platform_state(
                client,
                order,
                require_headinfo=(
                    order.data_source != "seller_sold"
                    or order.headinfo_confirmed_at is not None
                ),
                source="order_action_readback",
            )
        except Exception:
            return

    async def _refresh_platform_state(
        self,
        client: MtopOrderActions,
        order: Any,
        *,
        require_headinfo: bool,
        source: str,
    ):
        refreshed = order
        if order.item_id and order.conversation_id:
            try:
                raw_headinfo = await run_platform_blocking(
                    client.get_order_headinfo,
                    order.item_id,
                    order.conversation_id,
                )
                refreshed = await self.store.apply_order_headinfo(
                    order.order_pk, raw_headinfo
                )
                if refreshed is None:
                    raise ValueError("order not found")
                if refreshed.order_pk != order.order_pk:
                    raise OrderActionConflict("会话返回了不同订单，已阻止平台操作")
                await merge_account_cookie_updates(
                    self.store,
                    refreshed.account_id,
                    client.cookie_updates(),
                    source=f"{source}_headinfo",
                )
            except Exception:
                if require_headinfo:
                    raise
        elif require_headinfo:
            raise OrderActionConflict("订单缺少会话或商品信息，无法刷新平台操作能力")

        snapshot = await run_platform_blocking(
            client.get_order_detail, refreshed.platform_order_id or ""
        )
        await merge_account_cookie_updates(
            self.store,
            refreshed.account_id,
            client.cookie_updates(),
            source=source,
        )
        updated = await self.store.apply_order_detail_snapshot(order.order_pk, snapshot)
        if updated is None:
            raise ValueError("order not found")
        refreshed = updated

        capabilities = {
            str(item or "").strip().upper()
            for item in refreshed.platform_capabilities
            if str(item or "").strip()
        }
        if "LOGISTICS_SEND" in capabilities:
            shipping_options = await run_platform_blocking(
                client.get_shipping_options,
                refreshed.platform_order_id or "",
            )
            applied_shipping = await self.store.apply_order_shipping_options(
                order.order_pk, shipping_options
            )
            if applied_shipping is None:
                raise ValueError("order not found")
            refreshed = applied_shipping
            await merge_account_cookie_updates(
                self.store,
                refreshed.account_id,
                client.cookie_updates(),
                source=f"{source}_shipping",
            )
        else:
            cleared_shipping = await self.store.apply_order_shipping_options(
                order.order_pk, {}
            )
            if cleared_shipping is not None:
                refreshed = cleared_shipping

        if (
            capabilities & {"DEAL_REFUND", "VIEW_REFUND"}
            or refreshed.refund_status in {"pending", "processing", "refunding"}
        ):
            refund_detail = await run_platform_blocking(
                client.get_refund_detail,
                refreshed.platform_order_id or "",
            )
            applied_refund = await self.store.apply_order_refund_detail(
                order.order_pk, refund_detail
            )
            if applied_refund is None:
                raise ValueError("order not found")
            refreshed = applied_refund
            if (
                "REFUSE_REFUND" in refreshed.platform_refund_actions
                and refreshed.refund_id
            ):
                refuse_options = await run_platform_blocking(
                    client.get_refuse_refund_options,
                    refreshed.refund_id,
                )
                applied_options = await self.store.apply_order_refuse_options(
                    order.order_pk, refuse_options
                )
                if applied_options is None:
                    raise ValueError("order not found")
                refreshed = applied_options
            await merge_account_cookie_updates(
                self.store,
                refreshed.account_id,
                client.cookie_updates(),
                source=f"{source}_refund",
            )
        return refreshed

    @staticmethod
    def _result_summary(result: OrderActionResult) -> dict[str, Any]:
        ret = result.raw_response.get("ret") if isinstance(result.raw_response, Mapping) else None
        return {
            "success": result.success,
            "already_applied": result.already_applied,
            "platform_code": result.platform_code,
            "ret": ret,
        }

    @staticmethod
    def _response_code(response: Mapping[str, Any]) -> str | None:
        ret = response.get("ret") if isinstance(response, Mapping) else None
        if isinstance(ret, list) and ret:
            return str(ret[0]).split("::", 1)[0]
        return None

    @staticmethod
    def _to_core_account(account: AccountRecord) -> AccountConfig:
        return AccountConfig(
            account_id=account.account_id,
            cookie=account.cookie,
            nickname=account.display_name,
            enabled=account.enabled,
            proxy=build_core_account_proxy(account),
        )
