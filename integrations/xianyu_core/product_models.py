"""Stable product publishing models exposed by the Xianyu adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping


DELIVERY_CHOICES = {"free_shipping", "distance", "fixed", "pickup_only"}


@dataclass(slots=True, frozen=True)
class ProductPublishRequest:
    """Immutable input used for one publish attempt."""

    title: str
    description: str
    image_urls: tuple[str, ...]
    price: Decimal | None
    original_price: Decimal | None = None
    stock: int = 1
    delivery_choice: str = "free_shipping"
    post_price: Decimal | None = None
    can_self_pickup: bool = False
    category_hint: str | None = None
    unique_code: str = ""
    location: Mapping[str, Any] | None = None
    image_data: Mapping[str, "ProductImageData"] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProductImageData:
    data: bytes
    filename: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    sha256: str


@dataclass(slots=True, frozen=True)
class PublishedImage:
    url: str
    width: int
    height: int


@dataclass(slots=True, frozen=True)
class ProductPublishResult:
    """Normalized platform response and cookie changes from a publish attempt."""

    item_id: str | None
    item_url: str | None
    verified: bool
    cookie_updates: Mapping[str, str] = field(default_factory=dict)
    raw_response: Mapping[str, Any] = field(default_factory=dict)


class ProductPublishError(RuntimeError):
    """Classified publishing failure consumed by the task worker."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        retryable: bool = False,
        uncertain: bool = False,
        cookie_updates: Mapping[str, str] | None = None,
        raw_response: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.uncertain = uncertain
        self.cookie_updates = dict(cookie_updates or {})
        self.raw_response = dict(raw_response or {})


@dataclass(slots=True, frozen=True)
class ManagedProduct:
    item_id: str
    title: str = ""
    price: str = ""
    category_id: str = ""
    cover_url: str = ""
    detail_url: str = ""
    platform_item_status: str = ""
    want_count: int | None = None
    want_text: str | None = None
    raw_data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProductListResult:
    items: tuple[ManagedProduct, ...]
    pages: int
    complete: bool
    cookie_updates: Mapping[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProductActionItemResult:
    item_id: str
    success: bool
    skipped: bool = False
    message: str = ""
    channel: str = ""
    platform_code: str | None = None
    verified: bool = False
    raw_response: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProductBatchActionResult:
    items: tuple[ProductActionItemResult, ...]
    cookie_updates: Mapping[str, str] = field(default_factory=dict)


class ProductOperationError(RuntimeError):
    def __init__(
        self,
        kind: str,
        message: str,
        *,
        retryable: bool = False,
        uncertain: bool = False,
        verification_required: bool = False,
        cookie_updates: Mapping[str, str] | None = None,
        raw_response: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.uncertain = uncertain
        self.verification_required = verification_required
        self.cookie_updates = dict(cookie_updates or {})
        self.raw_response = dict(raw_response or {})
