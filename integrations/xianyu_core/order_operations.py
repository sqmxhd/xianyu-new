"""Account-scoped seller order synchronization over MTOP HTTP."""

from __future__ import annotations

import time
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .models import AccountConfig
from .order_models import OrderSyncError, SellerOrder, SellerOrderListResult
from .product_models import ProductPublishError
from .product_publisher import MtopProductPublisher


SHANGHAI = ZoneInfo("Asia/Shanghai")
ORDER_PAGE_SIZE = 30
ORDER_REQUEST_ATTEMPTS = 3
ORDER_RETRY_DELAYS = (0.5, 1.5)
STATUS_MAP = {
    "待付款": "pending_payment",
    "待发货": "paid_waiting_delivery",
    "已发货": "shipped",
    "交易成功": "completed",
    "交易关闭": "closed",
    "退款中": "refunding",
    "退款成功": "refunded",
    "已退款": "refunded",
    "退款关闭": "closed",
}

logger = logging.getLogger(__name__)


class MtopOrderOperations(MtopProductPublisher):
    """Read seller-center orders without sharing the long-lived IM session."""

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
                str(exc).replace("无法发布商品", "无法同步订单").replace("发布签名", "订单同步签名"),
                retryable=exc.retryable,
            ) from exc
        self._page_delay_seconds = max(0.0, page_delay_seconds)
        self._sleep_handler = sleep_handler

    def list_sold_orders(
        self,
        *,
        query_code: str = "ALL",
        max_pages: int | None = None,
    ) -> SellerOrderListResult:
        normalized_query = query_code.strip().upper()
        if normalized_query not in {"ALL", "NOT_SHIP"}:
            raise ValueError("query_code must be ALL or NOT_SHIP")
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be positive")

        orders: list[SellerOrder] = []
        seen: set[str] = set()
        page = 1
        total_count = 0
        complete = True
        try:
            while True:
                response: dict[str, Any] | None = None
                for attempt in range(1, ORDER_REQUEST_ATTEMPTS + 1):
                    try:
                        response = self._post_mtop(
                            "mtop.taobao.idle.trade.merchant.sold.get",
                            "1.0",
                            {
                                "pageNumber": page,
                                "rowsPerPage": ORDER_PAGE_SIZE,
                                "orderIds": "",
                                "queryCode": normalized_query,
                                "orderSearchParam": "{}",
                            },
                            spm_pre="",
                            spm_cnt="a21107h.42831410.0.0",
                            extra_params={
                                "type": "json",
                                "valueType": "string",
                            },
                            extra_headers={
                                "Origin": "https://seller.goofish.com",
                                "Referer": "https://seller.goofish.com/?site=COMMONPRO#/seller-trade/order-manage",
                                "idle_site_biz_code": "COMMONPRO",
                                "idle_user_group_member_id": "",
                            },
                            tracking_log_prefix=None,
                        )
                        break
                    except requests.RequestException as exc:
                        retryable = self._is_retryable_order_error(exc)
                        logger.warning(
                            "Xianyu sold-order request failed account=%s page=%s attempt=%s "
                            "route=%s error_type=%s retryable=%s",
                            self.account.account_id,
                            page,
                            attempt,
                            "proxy" if self._proxy_url else "direct",
                            exc.__class__.__name__,
                            retryable,
                        )
                        if not retryable or attempt >= ORDER_REQUEST_ATTEMPTS:
                            raise OrderSyncError(
                                "network",
                                f"同步闲鱼已售订单网络请求失败（{exc.__class__.__name__}），已尝试 {attempt} 次",
                                retryable=retryable,
                                cookie_updates=self.cookie_updates(),
                            ) from exc
                        self._reset_session()
                        self._sleep_handler(ORDER_RETRY_DELAYS[attempt - 1])
                assert response is not None
                self._ensure_success(response, operation="同步闲鱼已售订单")
                data = response.get("data") if isinstance(response, Mapping) else {}
                module = data.get("module") if isinstance(data, Mapping) else {}
                module = module if isinstance(module, Mapping) else {}
                raw_items = module.get("items")
                raw_items = raw_items if isinstance(raw_items, list) else []
                total_count = self._as_int(module.get("totalCount"), total_count)

                for raw in raw_items:
                    if not isinstance(raw, Mapping):
                        continue
                    parsed = self._parse_order(raw)
                    if parsed is None or parsed.order_id in seen:
                        continue
                    seen.add(parsed.order_id)
                    orders.append(parsed)

                next_page = self._as_bool(module.get("nextPage"))
                if not next_page or not raw_items:
                    break
                if max_pages is not None and page >= max_pages:
                    complete = False
                    break
                page += 1
                if self._page_delay_seconds:
                    self._sleep_handler(self._page_delay_seconds)
        except ProductPublishError as exc:
            permission_denied = "权限" in str(exc) or "PERMISSION_EXCEPTION" in str(exc)
            kind = "permission" if permission_denied else exc.kind
            message = (
                "账号暂无闲鱼卖家中心订单列表权限；请先确认该账号能在卖家中心打开订单管理页"
                if permission_denied
                else str(exc).replace("发布", "订单同步")
            )
            raise OrderSyncError(
                kind,
                message,
                retryable=exc.retryable,
                cookie_updates=self.cookie_updates(),
                raw_response=exc.raw_response,
            ) from exc
        except requests.RequestException as exc:
            raise OrderSyncError(
                "network",
                f"同步闲鱼已售订单网络请求失败（{exc.__class__.__name__}）",
                retryable=True,
                cookie_updates=self.cookie_updates(),
            ) from exc

        return SellerOrderListResult(
            items=tuple(orders),
            pages=page,
            total_count=total_count,
            complete=complete,
            cookie_updates=self.cookie_updates(),
        )

    @staticmethod
    def _is_retryable_order_error(exc: requests.RequestException) -> bool:
        if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
            return True
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return exc.response.status_code in {502, 503, 504}
        return False

    @classmethod
    def _parse_order(cls, raw: Mapping[str, Any]) -> SellerOrder | None:
        common = cls._mapping(raw.get("commonData"))
        buyer = cls._mapping(raw.get("buyerInfoVO"))
        price = cls._mapping(raw.get("priceVO"))
        item = cls._mapping(raw.get("itemInfoVO") or raw.get("itemInfo"))
        right = cls._mapping(raw.get("rightVO"))
        order_id = cls._text(common.get("orderId") or common.get("bizOrderId"))
        if not order_id:
            return None
        platform_status = cls._text(common.get("orderStatus"))
        in_refund = cls._as_bool(common.get("inRefund"))
        status = STATUS_MAP.get(platform_status, "unknown")
        refund_status = "pending" if in_refund else ""
        if status == "refunding":
            status = "unknown"
            refund_status = "pending"
        elif status == "refunded":
            status = "closed"
            refund_status = "refunded"
        quantity = max(1, cls._as_int(price.get("buyNum"), 1))
        title = cls._text(
            item.get("title")
            or item.get("itemTitle")
            or common.get("itemTitle")
            or raw.get("itemTitle")
        )
        image_url = cls._text(
            item.get("picUrl")
            or item.get("imageUrl")
            or common.get("picUrl")
            or raw.get("picUrl")
        )
        if image_url.startswith("//"):
            image_url = f"https:{image_url}"
        button_list = right.get("btnList") if isinstance(right.get("btnList"), list) else []
        is_bargain = any(
            isinstance(button, Mapping) and button.get("tradeAction") == "SKIP_PIN"
            for button in button_list
        )
        seller_rate_status = cls._text(common.get("sellerRateStatus"))
        return SellerOrder(
            order_id=order_id,
            item_id=cls._text(common.get("itemId")),
            title=title,
            image_url=image_url,
            buyer_id=cls._text(buyer.get("buyerId") or buyer.get("userId")),
            buyer_name=cls._text(buyer.get("userNick") or buyer.get("nick")),
            receiver_name=cls._text(buyer.get("name")),
            receiver_phone=cls._text(buyer.get("phone")),
            receiver_address=cls._text(buyer.get("address")),
            price=cls._text(
                price.get("totalPrice") or price.get("confirmFee") or price.get("auctionPrice")
            ),
            quantity=quantity,
            status=status,
            status_text=platform_status or "订单状态待确认",
            platform_status=platform_status,
            platform_created_at=cls._parse_platform_time(common.get("createTime")),
            platform_paid_at=cls._parse_platform_time(common.get("paySuccessTime")),
            platform_completed_at=cls._parse_platform_time(common.get("finishTime")),
            is_bargain=is_bargain,
            seller_rate_status=seller_rate_status,
            refund_status=refund_status,
            raw_summary={
                "source": "seller_sold",
                "orderStatus": platform_status,
                "inRefund": in_refund,
                "sellerRateStatus": seller_rate_status,
                "isBargain": is_bargain,
            },
        )

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
