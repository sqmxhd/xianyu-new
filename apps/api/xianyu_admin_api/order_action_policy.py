"""Server-owned order action capability rules."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .schemas import OrderActionAvailabilityPayload


ACTION_META = {
    "confirm_shipping": ("确认无物流发货", False),
    "offline_shipping": ("自行寄件发货", False),
    "free_shipping": ("确认免拼发货", False),
    "close_order": ("关闭订单", True),
    "rate_buyer": ("评价买家", False),
    "refuse_refund": ("拒绝退款", True),
}

ACTION_CAPABILITY = {
    "confirm_shipping": "LOGISTICS_SEND",
    "offline_shipping": "LOGISTICS_SEND",
    "free_shipping": "GROUPON_FREE_SHIPPING",
    "close_order": "CLOSE_ORDER",
    "rate_buyer": "RATE",
}


def _string_set(raw_value: Any) -> set[str]:
    if isinstance(raw_value, str):
        try:
            loaded = json.loads(raw_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            loaded = []
        raw_value = loaded if isinstance(loaded, list) else []
    return {
        str(item or "").strip().upper()
        for item in (raw_value or [])
        if str(item or "").strip()
    }


def _object_list(raw_value: Any) -> list[dict[str, Any]]:
    if isinstance(raw_value, str):
        try:
            loaded = json.loads(raw_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            loaded = []
        raw_value = loaded
    if not isinstance(raw_value, list):
        return []
    return [dict(item) for item in raw_value if isinstance(item, dict)]


def order_action_availability(order: Any) -> list[OrderActionAvailabilityPayload]:
    def value(name: str, default: Any = None) -> Any:
        if isinstance(order, Mapping):
            return order.get(name, default)
        return getattr(order, name, default)

    common_reason = ""
    if value("trade_role") != "seller":
        common_reason = "仅支持平台已确认的卖出订单"
    elif not value("platform_confirmed"):
        common_reason = "订单尚未经过卖家列表或会话订单信息确认"
    elif not str(value("platform_order_id") or "").strip():
        common_reason = "订单缺少平台订单号"

    status = str(value("status") or "unknown")
    refund_status = str(value("refund_status") or "").strip().lower()
    refund_finished = refund_status in {"refunded", "success", "completed"}
    refund_active = refund_status in {
        "pending",
        "processing",
        "refunding",
        "requested",
    }
    capabilities = _string_set(value("platform_capabilities", []))
    shipping_methods = _string_set(value("platform_shipping_methods", []))
    refund_actions = _string_set(value("platform_refund_actions", []))
    capability_is_authoritative = bool(value("headinfo_confirmed_at"))
    results: list[OrderActionAvailabilityPayload] = []
    for action, (label, danger) in ACTION_META.items():
        reason = common_reason
        required_capability = ACTION_CAPABILITY.get(action)
        if (
            not reason
            and capability_is_authoritative
            and required_capability
            and required_capability not in capabilities
        ):
            reason = f"平台当前未提供{label}操作"
        if not reason and action in {
            "confirm_shipping",
            "offline_shipping",
            "free_shipping",
        }:
            if refund_finished:
                reason = "订单已经退款，不能执行发货"
            elif status != "paid_waiting_delivery":
                reason = "仅待发货订单可以确认发货"
            elif action == "confirm_shipping" and "DUMMY_CONSIGN" not in shipping_methods:
                reason = "平台当前未提供无需邮寄方式"
            elif action == "offline_shipping" and "OFFLINE_CONSIGN" not in shipping_methods:
                reason = "平台当前未提供自行寄件方式"
            elif action == "free_shipping" and not value("is_bargain", False):
                reason = "当前订单不是小刀/免拼订单"
            elif action == "free_shipping" and not str(value("item_id") or "").strip():
                reason = "订单缺少商品 ID"
            elif action == "free_shipping" and not str(
                value("buyer_user_id") or value("peer_user_id") or ""
            ).strip():
                reason = "订单缺少买家 ID"
        elif not reason and action == "close_order":
            if refund_active:
                reason = "退款申请处理中，不能直接关闭订单"
            elif status not in {"pending_payment", "paid_waiting_delivery"}:
                reason = "仅待付款或待发货订单可以关闭"
        elif not reason and action == "rate_buyer":
            if status != "completed":
                reason = "仅交易成功订单可以评价"
            elif str(value("seller_rate_status") or "") == "4":
                reason = "订单已经评价"
        elif not reason and action == "refuse_refund":
            if "REFUSE_REFUND" not in refund_actions:
                reason = "平台当前未提供拒绝退款操作"
            elif not str(value("refund_id") or "").strip():
                reason = "退款申请缺少退款单号"
            elif not refund_active:
                reason = "当前没有待处理的退款申请"
            elif not _object_list(value("refund_refuse_options", [])):
                reason = "平台尚未返回可用的拒绝原因"
        results.append(
            OrderActionAvailabilityPayload(
                action=action,  # type: ignore[arg-type]
                enabled=not reason,
                reason=reason,
                label=label,
                danger=danger,
            )
        )
    return results
