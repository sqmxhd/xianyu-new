"""Account-scoped MTOP operations for the seller product catalog."""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

import requests

from .models import AccountConfig
from .product_models import (
    ManagedProduct,
    ProductActionItemResult,
    ProductBatchActionResult,
    ProductListResult,
    ProductOperationError,
    ProductPublishError,
)
from .product_publisher import MtopProductPublisher


ALREADY_POLISHED_MARKERS = (
    "宝贝已经擦亮过了",
    "IDLEITEM_POLISH_AGAIN",
    "一天只能擦亮一次",
    "POLISH_DUPLICATE",
)
MAX_CATALOG_PAGES = 100
PERSONAL_WEB_CHANNEL = "personal_web"
SELLER_CENTER_CHANNEL = "seller_center"
ITEM_DOWNSHELF_API = "mtop.taobao.idle.item.downshelf"
ITEM_DELETE_API = "com.taobao.idle.item.delete"
ITEM_DELETED_MARKER = "FAIL_BIZ_ITEM_DEL_NOT_FOUND"
WANT_LABEL_PATTERN = re.compile(
    r"(?P<count>[\d,]+(?:\.\d+)?)\s*(?P<unit>万)?\s*\+?\s*人想要"
)


def extract_product_want_metric(card_data: Mapping[str, Any]) -> tuple[int | None, str | None]:
    """Extract the platform's optional display label for a product's want count."""

    label_data_vo = card_data.get("itemLabelDataVO")
    if not isinstance(label_data_vo, Mapping):
        return None, None
    label_data = label_data_vo.get("labelData")
    if not isinstance(label_data, Mapping):
        return None, None
    for label_group in label_data.values():
        if not isinstance(label_group, Mapping):
            continue
        tags = label_group.get("tagList")
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if not isinstance(tag, Mapping):
                continue
            tag_data = tag.get("data")
            if not isinstance(tag_data, Mapping):
                continue
            content = str(tag_data.get("content") or "").strip()
            label_id = str(tag_data.get("labelId") or "").strip()
            if not content or (label_id != "9" and "人想要" not in content):
                continue
            match = WANT_LABEL_PATTERN.search(content)
            if match is None:
                return None, content
            try:
                count = Decimal(match.group("count").replace(",", ""))
            except InvalidOperation:
                return None, content
            if match.group("unit") == "万":
                count *= 10_000
            return int(count), content
    return None, None


class MtopProductOperations(MtopProductPublisher):
    """Manage one account's products without sharing its long-lived IM session."""

    def __init__(
        self,
        account: AccountConfig,
        *,
        sleep_handler: Callable[[float], None] = time.sleep,
        **kwargs: Any,
    ) -> None:
        super().__init__(account, **kwargs)
        self._sleep_handler = sleep_handler

    def list_selling_items(
        self,
        *,
        page_size: int = 20,
        max_pages: int | None = None,
        page_delay: tuple[float, float] = (0.8, 1.8),
    ) -> ProductListResult:
        items: list[ManagedProduct] = []
        page = 1
        pages_fetched = 0
        complete = False
        page_limit = min(max_pages, MAX_CATALOG_PAGES) if max_pages is not None else MAX_CATALOG_PAGES
        try:
            while page <= page_limit:
                response = self._post_mtop(
                    "mtop.idle.web.xyh.item.list",
                    "1.0",
                    {
                        "needGroupInfo": False,
                        "pageNumber": page,
                        "pageSize": page_size,
                        "groupName": "在售",
                        "groupId": "58877261",
                        "defaultGroup": True,
                        "userId": self._cookie_value("unb"),
                    },
                    spm_pre="a21ybx.collection.menu.1.272b5141NafCNK",
                    spm_cnt="a21ybx.im.0.0",
                )
                self._ensure_operation_success(response, "同步在售商品")
                page_items = self._parse_product_cards(response.get("data"))
                pages_fetched += 1
                items.extend(page_items)
                if len(page_items) < page_size:
                    complete = True
                    break
                page += 1
                if page <= page_limit:
                    self._sleep_handler(random.uniform(*page_delay))
            return ProductListResult(
                items=tuple(items),
                pages=pages_fetched,
                complete=complete,
                cookie_updates=self.cookie_updates(),
            )
        except ProductOperationError as exc:
            exc.cookie_updates.update(self.cookie_updates())
            raise
        except requests.RequestException as exc:
            raise ProductOperationError(
                "network",
                f"同步在售商品网络请求失败（{exc.__class__.__name__}）",
                retryable=True,
                cookie_updates=self.cookie_updates(),
            ) from exc

    def polish_item(self, item_id: str) -> ProductActionItemResult:
        try:
            response = self._post_mtop(
                "mtop.taobao.idle.item.polish",
                "1.0",
                {"itemId": str(item_id)},
                spm_pre="a21ybx.collection.menu.1.272b5141NafCNK",
                spm_cnt="a21ybx.im.0.0",
            )
            if self._is_success(response):
                return ProductActionItemResult(str(item_id), True, raw_response=response)
            message = self._error_message(response)
            if any(marker in message for marker in ALREADY_POLISHED_MARKERS):
                return ProductActionItemResult(
                    str(item_id), True, skipped=True, message="今日已经擦亮", raw_response=response
                )
            self._ensure_operation_success(response, "擦亮商品")
            raise AssertionError("unreachable")
        except ProductOperationError:
            raise
        except requests.RequestException as exc:
            raise ProductOperationError(
                "network",
                f"擦亮商品网络请求失败（{exc.__class__.__name__}）",
                retryable=True,
                cookie_updates=self.cookie_updates(),
            ) from exc

    def offline_personal_item(self, item_id: str) -> ProductActionItemResult:
        """Downshelf one account-scoped item without a detail preflight."""

        clean_item_id = str(item_id).strip()
        response = self._personal_write_request(
            ITEM_DOWNSHELF_API,
            "2.0",
            clean_item_id,
            operation="下架商品",
        )
        return ProductActionItemResult(
            clean_item_id,
            True,
            message="平台已受理下架，等待商品同步校正",
            channel=PERSONAL_WEB_CHANNEL,
            platform_code=f"{PERSONAL_WEB_CHANNEL}:{self._response_code(response)}",
            verified=False,
            raw_response=response,
        )

    def delete_personal_item(self, item_id: str) -> ProductActionItemResult:
        """Delete one account-scoped item without a detail preflight."""

        clean_item_id = str(item_id).strip()
        try:
            response = self._personal_write_request(
                ITEM_DELETE_API,
                "1.1",
                clean_item_id,
                operation="删除商品",
            )
        except ProductOperationError as exc:
            if self._contains_marker(exc.raw_response, (ITEM_DELETED_MARKER,)):
                return ProductActionItemResult(
                    clean_item_id,
                    True,
                    skipped=True,
                    message="平台确认商品已经删除",
                    channel=PERSONAL_WEB_CHANNEL,
                    platform_code=f"{PERSONAL_WEB_CHANNEL}:{ITEM_DELETED_MARKER}",
                    verified=True,
                    raw_response=exc.raw_response,
                )
            raise
        return ProductActionItemResult(
            clean_item_id,
            True,
            message="平台已受理删除，等待商品同步校正",
            channel=PERSONAL_WEB_CHANNEL,
            platform_code=f"{PERSONAL_WEB_CHANNEL}:{self._response_code(response)}",
            verified=False,
            raw_response=response,
        )

    def _personal_write_request(
        self,
        api_name: str,
        version: str,
        item_id: str,
        *,
        operation: str,
    ) -> dict[str, Any]:
        try:
            response = self._post_mtop(
                api_name,
                version,
                {"itemId": item_id},
                spm_pre="a21ybx.personal.feeds.1.0",
                spm_cnt="a21ybx.item.0.0",
                extra_headers={"Referer": f"https://www.goofish.com/item?id={item_id}"},
                tracking_log_prefix="item",
            )
            self._ensure_operation_success(response, operation)
            return response
        except ProductOperationError:
            raise
        except ProductPublishError as exc:
            uncertain = exc.kind != "auth"
            raise ProductOperationError(
                "result_unknown" if uncertain else exc.kind,
                f"{operation}请求结果无法确认，禁止直接重试" if uncertain else str(exc),
                uncertain=uncertain,
                verification_required=exc.kind == "risk_control",
                cookie_updates=self.cookie_updates(),
                raw_response=exc.raw_response,
            ) from exc
        except requests.RequestException as exc:
            raise ProductOperationError(
                "result_unknown",
                f"{operation}请求已发出但未收到明确结果，禁止直接重试",
                uncertain=True,
                cookie_updates=self.cookie_updates(),
            ) from exc

    @staticmethod
    def _response_code(response: Mapping[str, Any]) -> str:
        ret = response.get("ret") if isinstance(response, Mapping) else None
        if isinstance(ret, list) and ret:
            return str(ret[0]).split("::", 1)[0]
        return "UNKNOWN"

    def offline_items(self, item_ids: list[str]) -> ProductBatchActionResult:
        """Preserved seller-center batch path for accounts with shop permissions."""

        cleaned = list(dict.fromkeys(str(item_id).strip() for item_id in item_ids if str(item_id).strip()))
        if not cleaned:
            return ProductBatchActionResult((), self.cookie_updates())
        try:
            response = self._post_mtop(
                "mtop.alibaba.idle.seller.pc.item.batch.offline",
                "1.0",
                {"itemIds": ",".join(cleaned)},
                spm_pre="a21107h.42826273.0.0",
                spm_cnt="a21107h.42826273.0.0",
                extra_params={"needLoginPC": "true", "showErrorToast": "true"},
                extra_headers={
                    "Referer": "https://seller.goofish.com/?site=COMMONPRO",
                    "idle_site_biz_code": "COMMONPRO",
                },
            )
            self._ensure_operation_success(response, "下架商品")
            data = response.get("data") if isinstance(response.get("data"), Mapping) else {}
            if data.get("code") not in (None, "", "success"):
                raise ProductOperationError(
                    "platform_rejected",
                    f"下架商品失败: {data.get('msg') or data}",
                    cookie_updates=self.cookie_updates(),
                    raw_response=response,
                )
            inner = data.get("data") if isinstance(data.get("data"), Mapping) else {}
            raw_results = inner.get("itemProcessResultList") if isinstance(inner, Mapping) else None
            result_map = {
                str(item.get("itemId") or ""): bool(item.get("success"))
                for item in (raw_results or [])
                if isinstance(item, Mapping)
            }
            results = tuple(
                ProductActionItemResult(
                    item_id,
                    result_map.get(item_id, False),
                    message=(
                        "下架成功"
                        if result_map.get(item_id) is True
                        else "平台下架失败"
                        if result_map.get(item_id) is False
                        else "平台未返回该商品的明确处理结果"
                    ),
                    channel=SELLER_CENTER_CHANNEL,
                    platform_code=f"{SELLER_CENTER_CHANNEL}:{self._response_code(response)}",
                    verified=False,
                    raw_response=response,
                )
                for item_id in cleaned
            )
            return ProductBatchActionResult(results, self.cookie_updates())
        except ProductOperationError:
            raise
        except requests.RequestException as exc:
            raise ProductOperationError(
                "result_unknown",
                "下架请求已发出但未收到明确结果，请先同步商品状态",
                uncertain=True,
                cookie_updates=self.cookie_updates(),
            ) from exc

    def delete_item(self, item_id: str) -> ProductActionItemResult:
        """Preserved seller-center delete path for accounts with shop permissions."""

        try:
            response = self._post_mtop(
                "mtop.alibaba.idle.seller.pc.item.delete",
                "1.0",
                {"itemId": str(item_id), "draftId": None},
                spm_pre="a21107h.42829799.0.0",
                spm_cnt="a21107h.42829799.0.0",
                extra_params={"needLoginPC": "true", "showErrorToast": "true"},
                extra_headers={
                    "Referer": "https://seller.goofish.com/?site=COMMONPRO",
                    "idle_site_biz_code": "COMMONPRO",
                },
            )
            self._ensure_operation_success(response, "删除商品")
            data = response.get("data")
            success = data is True or (
                isinstance(data, Mapping)
                and (data.get("code") == "success" or data.get("data") is True)
            )
            if not success:
                message = data.get("msg") if isinstance(data, Mapping) else None
                raise ProductOperationError(
                    "platform_rejected",
                    f"删除商品失败: {message or data or '平台未确认成功'}",
                    cookie_updates=self.cookie_updates(),
                    raw_response=response,
                )
            return ProductActionItemResult(
                str(item_id),
                True,
                message="删除成功",
                channel=SELLER_CENTER_CHANNEL,
                platform_code=f"{SELLER_CENTER_CHANNEL}:{self._response_code(response)}",
                verified=False,
                raw_response=response,
            )
        except ProductOperationError:
            raise
        except requests.RequestException as exc:
            raise ProductOperationError(
                "result_unknown",
                "删除请求已发出但未收到明确结果，禁止直接重试",
                uncertain=True,
                cookie_updates=self.cookie_updates(),
            ) from exc

    def _ensure_operation_success(self, response: Mapping[str, Any], operation: str) -> None:
        try:
            self._ensure_success(response, operation=operation)
        except ProductPublishError as exc:
            raise ProductOperationError(
                exc.kind,
                str(exc),
                retryable=exc.retryable,
                uncertain=exc.uncertain,
                verification_required=exc.kind == "risk_control",
                cookie_updates=self.cookie_updates(),
                raw_response=response,
            ) from exc

    @staticmethod
    def _parse_product_cards(data: Any) -> list[ManagedProduct]:
        if not isinstance(data, Mapping):
            return []
        cards = data.get("cardList")
        if not isinstance(cards, list):
            return []
        result: list[ManagedProduct] = []
        for card in cards:
            if not isinstance(card, Mapping):
                continue
            value = card.get("cardData")
            if not isinstance(value, Mapping):
                continue
            item_id = str(value.get("id") or value.get("itemId") or "").strip()
            if not item_id:
                continue
            price_info = value.get("priceInfo") if isinstance(value.get("priceInfo"), Mapping) else {}
            pic_info = value.get("picInfo") if isinstance(value.get("picInfo"), Mapping) else {}
            cover_url = str(pic_info.get("picUrl") or pic_info.get("url") or "")
            if cover_url.startswith("//"):
                cover_url = f"https:{cover_url}"
            want_count, want_text = extract_product_want_metric(value)
            result.append(
                ManagedProduct(
                    item_id=item_id,
                    title=str(value.get("title") or ""),
                    price=f"{price_info.get('preText') or ''}{price_info.get('price') or ''}",
                    category_id=str(value.get("categoryId") or ""),
                    cover_url=cover_url,
                    detail_url=str(value.get("detailUrl") or f"https://www.goofish.com/item?id={item_id}"),
                    platform_item_status=str(value.get("itemStatus") or ""),
                    want_count=want_count,
                    want_text=want_text,
                    raw_data=dict(value),
                )
            )
        return result
