"""Account-scoped buyer order synchronization over MTOP HTTP."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .models import AccountConfig
from .order_models import BuyerOrder, BuyerOrderListResult, OrderSyncError
from .product_models import ProductPublishError
from .product_publisher import MtopProductPublisher


SHANGHAI = ZoneInfo("Asia/Shanghai")
BUYER_ORDER_REQUEST_ATTEMPTS = 3
BUYER_ORDER_RETRY_DELAYS = (0.5, 1.5)
BUYER_ORDER_STATUSES = {"ALL", "NOT_PAY", "NOT_SHIP", "SHIPPED", "NOT_RATE", "REFUND"}
BUYER_STATUS_MAP = {
    "wait_buyer_pay": "pending_payment",
    "not_pay": "pending_payment",
    "pending_payment": "pending_payment",
    "wait_seller_send_goods": "waiting_seller_delivery",
    "wait_seller_send": "waiting_seller_delivery",
    "not_ship": "waiting_seller_delivery",
    "wait_buyer_confirm_goods": "shipped",
    "wait_buyer_confirm": "shipped",
    "shipped": "shipped",
    "trade_success": "completed",
    "success": "completed",
    "refund": "refunding",
    "refund_in_progress": "refunding",
    "refunding": "refunding",
    "refund_success": "refunded",
    "refunded": "refunded",
    "close_by_buyer": "closed",
    "close_by_seller": "closed",
    "close_by_out": "closed",
    "trade_closed": "closed",
    "closed": "closed",
}

logger = logging.getLogger(__name__)


class MtopBuyerOrderOperations(MtopProductPublisher):
    """Read the account's purchases from the public web order page API."""

    def __init__(
        self,
        account: AccountConfig,
        *,
        page_delay_seconds: float = 1.2,
        sleep_handler: Callable[[float], None] = time.sleep,
        **kwargs: Any,
    ) -> None:
        try:
            super().__init__(account, **kwargs)
        except ProductPublishError as exc:
            raise OrderSyncError(
                exc.kind,
                str(exc).replace("无法发布商品", "无法同步买入订单").replace("发布签名", "订单同步签名"),
                retryable=exc.retryable,
            ) from exc
        self._page_delay_seconds = max(0.0, page_delay_seconds)
        self._sleep_handler = sleep_handler

    def list_bought_orders(
        self,
        *,
        order_status: str = "ALL",
        max_pages: int | None = None,
    ) -> BuyerOrderListResult:
        normalized_status = order_status.strip().upper()
        if normalized_status not in BUYER_ORDER_STATUSES:
            raise ValueError(f"unsupported buyer order status: {normalized_status}")
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be positive")

        orders: list[BuyerOrder] = []
        seen_order_ids: set[str] = set()
        seen_cursors: set[str] = set()
        previous_page_ids: tuple[str, ...] | None = None
        offset_row: Any = None
        page = 1
        total_count = 0
        complete = True

        try:
            while True:
                payload: dict[str, Any] = {
                    "pageNumber": page,
                    "orderStatus": normalized_status,
                }
                if offset_row not in (None, ""):
                    payload["offsetRow"] = offset_row

                response = self._request_page(payload, page)
                self._ensure_success(response, operation="同步闲鱼买入订单")
                data = response.get("data") if isinstance(response, Mapping) else {}
                data = data if isinstance(data, Mapping) else {}
                raw_items = data.get("items")
                raw_items = raw_items if isinstance(raw_items, list) else []
                total_count = self._as_int(data.get("totalCount"), total_count)

                current_page_ids: list[str] = []
                for raw in raw_items:
                    if not isinstance(raw, Mapping):
                        continue
                    parsed = self._parse_order(raw)
                    if parsed is None:
                        continue
                    current_page_ids.append(parsed.order_id)
                    if parsed.order_id in seen_order_ids:
                        continue
                    seen_order_ids.add(parsed.order_id)
                    orders.append(parsed)

                page_signature = tuple(current_page_ids)
                if previous_page_ids is not None and page_signature and page_signature == previous_page_ids:
                    complete = False
                    logger.warning(
                        "Xianyu bought-order pagination repeated a page account=%s page=%s",
                        self.account.account_id,
                        page,
                    )
                    break
                previous_page_ids = page_signature

                next_page = self._as_bool(data.get("nextPage"))
                if not next_page or not raw_items:
                    break
                if max_pages is not None and page >= max_pages:
                    complete = False
                    break

                next_offset = data.get("lastEndRow")
                cursor_key = self._cursor_key(next_offset)
                if not cursor_key or cursor_key in seen_cursors:
                    complete = False
                    logger.warning(
                        "Xianyu bought-order pagination cursor missing or repeated account=%s page=%s",
                        self.account.account_id,
                        page,
                    )
                    break
                seen_cursors.add(cursor_key)
                offset_row = next_offset
                page += 1
                if self._page_delay_seconds:
                    self._sleep_handler(self._page_delay_seconds)
        except ProductPublishError as exc:
            raise OrderSyncError(
                exc.kind,
                str(exc).replace("发布", "买入订单同步"),
                retryable=exc.retryable,
                cookie_updates=self.cookie_updates(),
                raw_response=exc.raw_response,
            ) from exc
        except requests.RequestException as exc:
            raise OrderSyncError(
                "network",
                f"同步闲鱼买入订单网络请求失败（{exc.__class__.__name__}）",
                retryable=True,
                cookie_updates=self.cookie_updates(),
            ) from exc

        return BuyerOrderListResult(
            items=tuple(orders),
            pages=page,
            total_count=total_count,
            complete=complete,
            cookie_updates=self.cookie_updates(),
        )

    def _request_page(self, payload: Mapping[str, Any], page: int) -> dict[str, Any]:
        for attempt in range(1, BUYER_ORDER_REQUEST_ATTEMPTS + 1):
            try:
                return self._post_mtop(
                    "mtop.idle.web.trade.bought.list",
                    "1.0",
                    payload,
                    spm_pre="",
                    spm_cnt="a21ybx.bought.0.0",
                    extra_params={"valueType": "string"},
                    extra_headers={
                        "Origin": "https://www.goofish.com",
                        "Referer": "https://www.goofish.com/bought",
                    },
                    tracking_log_prefix=None,
                )
            except requests.RequestException as exc:
                retryable = self._is_retryable_order_error(exc)
                logger.warning(
                    "Xianyu bought-order request failed account=%s page=%s attempt=%s "
                    "route=%s error_type=%s retryable=%s",
                    self.account.account_id,
                    page,
                    attempt,
                    "proxy" if self._proxy_url else "direct",
                    exc.__class__.__name__,
                    retryable,
                )
                if not retryable or attempt >= BUYER_ORDER_REQUEST_ATTEMPTS:
                    raise OrderSyncError(
                        "network",
                        f"同步闲鱼买入订单网络请求失败（{exc.__class__.__name__}），已尝试 {attempt} 次",
                        retryable=retryable,
                        cookie_updates=self.cookie_updates(),
                    ) from exc
                self._reset_session()
                self._sleep_handler(BUYER_ORDER_RETRY_DELAYS[attempt - 1])
        raise AssertionError("buyer order request loop exited unexpectedly")

    @staticmethod
    def _is_retryable_order_error(exc: requests.RequestException) -> bool:
        if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
            return True
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return exc.response.status_code in {502, 503, 504}
        return False

    @classmethod
    def _parse_order(cls, raw: Mapping[str, Any]) -> BuyerOrder | None:
        common = cls._mapping(raw.get("commonData"))
        head = cls._mapping(cls._mapping(raw.get("head")).get("data"))
        content = cls._mapping(cls._mapping(raw.get("content")).get("data"))
        detail = cls._mapping(content.get("detailInfo"))
        price_info = cls._mapping(content.get("priceInfo"))
        seller = cls._mapping(head.get("userInfo"))
        order_id = cls._text(common.get("orderId") or common.get("orderIdStr"))
        if not order_id:
            return None

        platform_status = cls._text(common.get("tradeStatusEnum")).lower()
        status_text = cls._text(head.get("statusViewMsg"))
        status = BUYER_STATUS_MAP.get(platform_status) or cls._status_from_text(status_text)
        refund_status = ""
        if status == "refunding":
            status = "unknown"
            refund_status = "pending"
        elif status == "refunded":
            status = "closed"
            refund_status = "refunded"
        image_url = cls._text(detail.get("auctionPic"))
        if image_url.startswith("//"):
            image_url = f"https:{image_url}"
        return BuyerOrder(
            order_id=order_id,
            item_id=cls._text(common.get("itemId")),
            title=cls._text(detail.get("auctionTitle")),
            image_url=image_url,
            seller_id=cls._text(common.get("peerUserId") or seller.get("userId")),
            seller_name=cls._text(
                seller.get("userAliasNick") or seller.get("userNick") or seller.get("nick")
            ),
            price=cls._text(price_info.get("price") or price_info.get("auctionPriceDesc")),
            quantity=max(1, cls._as_int(price_info.get("buyAmount"), 1)),
            status=status,
            status_text=status_text or platform_status or "订单状态待确认",
            platform_status=platform_status,
            platform_created_at=cls._parse_platform_time(head.get("createTime")),
            refund_status=refund_status,
            raw_summary={
                "source": "buyer_bought",
                "tradeStatusEnum": platform_status,
                "orderDetailUrl": cls._text(common.get("orderDetailUrl")),
            },
        )

    @staticmethod
    def _status_from_text(value: str) -> str:
        if "待付款" in value or "等待付款" in value:
            return "pending_payment"
        if "待发货" in value or "等待卖家发货" in value:
            return "waiting_seller_delivery"
        if "待收货" in value or "确认收货" in value:
            return "shipped"
        if "交易成功" in value or "已完成" in value:
            return "completed"
        if "退款成功" in value or "已退款" in value:
            return "refunded"
        if "退款" in value:
            return "refunding"
        if "关闭" in value or "取消" in value:
            return "closed"
        return "unknown"

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _as_bool(value: Any) -> bool:
        return value is True or str(value or "").strip().lower() == "true"

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _cursor_key(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, Mapping):
            return "|".join(f"{key}={value[key]}" for key in sorted(value))
        return str(value)

    @staticmethod
    def _parse_platform_time(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(text, pattern).replace(tzinfo=SHANGHAI).astimezone(UTC)
            except ValueError:
                continue
        return None
