"""Stable seller-order models exposed by the Xianyu adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True, frozen=True)
class SellerOrder:
    order_id: str
    item_id: str = ""
    title: str = ""
    image_url: str = ""
    buyer_id: str = ""
    buyer_name: str = ""
    receiver_name: str = ""
    receiver_phone: str = ""
    receiver_address: str = ""
    price: str = ""
    quantity: int = 1
    status: str = "unknown"
    status_text: str = ""
    platform_status: str = ""
    platform_created_at: datetime | None = None
    platform_paid_at: datetime | None = None
    platform_completed_at: datetime | None = None
    is_bargain: bool = False
    seller_rate_status: str = ""
    refund_status: str = ""
    raw_summary: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class OrderDetailSnapshot:
    """Normalized seller-order detail used for preflight and read-back."""

    order_id: str
    item_id: str = ""
    buyer_id: str = ""
    price: str = ""
    quantity: int = 1
    status: str = "unknown"
    status_text: str = ""
    platform_status: str = ""
    receiver_name: str = ""
    receiver_phone: str = ""
    receiver_address: str = ""
    is_bargain: bool = False
    raw_response: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class OrderActionResult:
    action: str
    order_id: str
    success: bool
    message: str
    platform_code: str | None = None
    already_applied: bool = False
    raw_response: Mapping[str, Any] = field(default_factory=dict)


class OrderActionError(RuntimeError):
    def __init__(
        self,
        kind: str,
        message: str,
        *,
        uncertain: bool = False,
        verification_required: bool = False,
        cookie_updates: Mapping[str, str] | None = None,
        raw_response: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.uncertain = uncertain
        self.verification_required = verification_required
        self.cookie_updates = dict(cookie_updates or {})
        self.raw_response = dict(raw_response or {})


@dataclass(slots=True, frozen=True)
class SellerOrderListResult:
    items: tuple[SellerOrder, ...]
    pages: int
    total_count: int
    complete: bool
    cookie_updates: Mapping[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class BuyerOrder:
    order_id: str
    item_id: str = ""
    title: str = ""
    image_url: str = ""
    seller_id: str = ""
    seller_name: str = ""
    price: str = ""
    quantity: int = 1
    status: str = "unknown"
    status_text: str = ""
    platform_status: str = ""
    platform_created_at: datetime | None = None
    platform_paid_at: datetime | None = None
    platform_completed_at: datetime | None = None
    refund_status: str = ""
    raw_summary: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class BuyerOrderListResult:
    items: tuple[BuyerOrder, ...]
    pages: int
    total_count: int
    complete: bool
    cookie_updates: Mapping[str, str] = field(default_factory=dict)


class OrderSyncError(RuntimeError):
    def __init__(
        self,
        kind: str,
        message: str,
        *,
        retryable: bool = False,
        cookie_updates: Mapping[str, str] | None = None,
        raw_response: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.cookie_updates = dict(cookie_updates or {})
        self.raw_response = dict(raw_response or {})
