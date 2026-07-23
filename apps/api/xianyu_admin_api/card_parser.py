"""Conservative product/order card extraction from message raw payloads."""

from __future__ import annotations

import json
import base64
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse


ITEM_ID_KEYS = {"itemid", "item_id", "itemId", "itemID", "auctionid", "auctionId"}
ORDER_ID_KEYS = {
    "orderid",
    "order_id",
    "orderId",
    "bizorderid",
    "bizOrderId",
    "tradeid",
    "trade_id",
    "tradeId",
    "orderNo",
}
TITLE_KEYS = {"title", "itemtitle", "itemTitle", "subject", "name", "itemName", "goodsTitle"}
PRICE_KEYS = {"price", "amount", "payAmount", "actualFee", "salePrice", "currentPrice"}
STATUS_KEYS = {"status", "statusText", "orderStatus", "tradeStatus", "tradeStatusText"}
IMAGE_KEYS = {
    "image",
    "imageUrl",
    "picUrl",
    "pictureUrl",
    "mainPic",
    "mainImage",
    "cover",
    "coverUrl",
    "url",
}
URL_KEYS = {"targetUrl", "itemUrl", "jumpUrl", "detailUrl", "url"}
XIANYU_ITEM_URL = "https://h5.m.goofish.com/item?id={}"


@dataclass(slots=True)
class ParsedMessageCard:
    card_type: str
    item_id: str | None = None
    order_id: str | None = None
    title: str | None = None
    price: str | None = None
    status: str | None = None
    image_url: str | None = None
    url: str | None = None
    raw_summary: dict[str, Any] | None = None


@dataclass(slots=True)
class ParsedItemContext:
    item_id: str
    title: str | None = None
    price: str | None = None
    image_url: str | None = None
    url: str | None = None
    source: str = "message"


@dataclass(slots=True)
class ParsedOrderEvent:
    event_type: str
    status: str
    status_text: str
    order_id: str | None = None
    item_id: str | None = None
    title: str | None = None
    price: str | None = None
    image_url: str | None = None
    peer_user_id: str | None = None
    task_name: str | None = None
    trade_role: str = "unknown"
    raw_summary: dict[str, Any] | None = None


def normalize_item_url(raw_url: Any, item_id: Any) -> str | None:
    """Return a browser-safe Xianyu item URL for a numeric item id."""

    normalized_item_id = _numeric_item_id(item_id)
    normalized_raw_url = _normalize_scalar(raw_url)
    parsed = urlparse(normalized_raw_url) if normalized_raw_url else None
    query_item_id = (
        _numeric_item_id(
            _query_value(
                parse_qs(parsed.query) if parsed else {},
                "itemId",
                "item_id",
                "itemid",
                "id",
            )
        )
        if parsed
        else None
    )
    resolved_item_id = normalized_item_id or query_item_id
    if not resolved_item_id:
        return None

    if (
        parsed
        and parsed.scheme == "https"
        and _is_goofish_host(parsed.hostname)
        and query_item_id == resolved_item_id
    ):
        return normalized_raw_url
    return XIANYU_ITEM_URL.format(resolved_item_id)


ORDER_STATE_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("关闭了订单", "订单关闭", "交易关闭"), "closed", "closed"),
    (("交易成功", "你已确认收货", "已确认收货", "完成了评价", "已完成"), "completed", "completed"),
    (("卖家已发货", "已发货", "提醒收货", "及时确认收货", "记得确认收货"), "shipped", "shipped"),
    (("已付款", "等待你发货", "待卖家发货", "待发货"), "paid", "paid_waiting_delivery"),
    (("待付款", "等待你付款", "修改价格"), "pending_payment", "pending_payment"),
)


def parse_order_event(
    raw_payload: Any,
    *,
    content: str = "",
    fallback_item_id: str | None = None,
    fallback_peer_user_id: str | None = None,
) -> ParsedOrderEvent | None:
    """Decode Xianyu dxCard order events and conservative trade system tips."""

    payload = _maybe_json(raw_payload)
    if not isinstance(payload, dict):
        return None
    custom = _find_custom(payload)
    card_data = _decode_custom_data(custom.get("data") if custom else None)
    card_main = _nested_dict(card_data, "dxCard", "item", "main")
    extension = _find_message_extension(payload)
    reminder = _parse_url_query(_normalize_scalar(extension.get("reminderUrl")))
    target_url = _normalize_scalar(card_main.get("targetUrl")) if card_main else None
    target = _parse_url_query(target_url)
    ex_content = card_main.get("exContent") if card_main else None
    if not isinstance(ex_content, dict):
        ex_content = {}

    order_id = _query_value(target, "id", "orderId", "order_id")
    item_id = (
        _query_value(reminder, "itemId", "item_id", "itemid")
        or fallback_item_id
    )
    peer_user_id = (
        _query_value(reminder, "userId", "peerUserId", "peer_user_id")
        or fallback_peer_user_id
    )
    title = _normalize_scalar(ex_content.get("title"))
    description = _normalize_scalar(ex_content.get("desc"))
    image_url = _first_image(ex_content)
    task_name = _nested_scalar(card_data, "dxCard", "item", "extension", "bizTag", "taskName")
    if not task_name:
        biz_tag = _maybe_json(extension.get("bizTag"))
        if isinstance(biz_tag, dict):
            task_name = _normalize_scalar(biz_tag.get("taskName"))
    update_key = _nested_scalar(card_data, "dxCard", "item", "extension", "extJson", "updateKey")
    status_source = " ".join(filter(None, (content, title, description, task_name, update_key)))
    event_type, status = _normalize_order_state(status_source)
    role_text = (_query_value(target, "role") or "").strip().lower()
    task_role_text = (task_name or "").strip().lower()
    if role_text == "seller" or task_role_text.endswith("_卖家") or "_seller" in task_role_text:
        trade_role = "seller"
    elif role_text == "buyer" or task_role_text.endswith("_买家") or "_buyer" in task_role_text:
        trade_role = "buyer"
    else:
        trade_role = "unknown"

    is_dx_order = bool(card_main and (order_id or "order" in (target_url or "").lower()))
    is_trade_tip = _is_trade_tip(status_source)
    if not is_dx_order and not is_trade_tip:
        return None

    status_text = title or description or content.strip() or task_name or "订单状态更新"
    return ParsedOrderEvent(
        event_type=event_type,
        status=status,
        status_text=status_text[:255],
        order_id=order_id,
        item_id=item_id,
        title=title,
        price=_extract_price(description or ""),
        image_url=image_url,
        peer_user_id=peer_user_id,
        task_name=task_name,
        trade_role=trade_role,
        raw_summary={
            "source": "dx_card" if is_dx_order else "trade_tip",
            "target_url": target_url,
            "task_name": task_name,
            "update_key": update_key,
            "description": description,
            "trade_role": trade_role,
        },
    )


def parse_message_cards(
    raw_payload: Any,
    *,
    content: str = "",
    fallback_item_id: str | None = None,
) -> list[ParsedMessageCard]:
    """Extract product/order summaries without relying on a single upstream shape.

    The parser intentionally requires concrete product/order identifiers or
    multiple card-like fields. Ordinary text messages should not produce cards.
    """

    cards: list[ParsedMessageCard] = []
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    for node in _walk_payload(raw_payload):
        if not isinstance(node, dict):
            continue
        card = _parse_dict_node(node)
        if card is None:
            continue
        key = (card.card_type, card.item_id, card.order_id, card.title)
        if key in seen:
            continue
        seen.add(key)
        cards.append(card)

    parsed_order = parse_order_event(
        raw_payload,
        content=content,
        fallback_item_id=fallback_item_id,
    )
    if parsed_order is not None:
        key = ("order", parsed_order.item_id, parsed_order.order_id, parsed_order.title)
        if key not in seen:
            cards.append(
                ParsedMessageCard(
                    card_type="order",
                    item_id=parsed_order.item_id,
                    order_id=parsed_order.order_id,
                    title=parsed_order.title,
                    price=parsed_order.price,
                    status=parsed_order.status_text,
                    image_url=parsed_order.image_url,
                    url=(parsed_order.raw_summary or {}).get("target_url"),
                    raw_summary=parsed_order.raw_summary,
                )
            )

    return cards[:5]


def parse_item_context(
    raw_payload: Any,
    *,
    fallback_item_id: str | None = None,
) -> ParsedItemContext | None:
    """Return the item a conversation is about, without creating a message card."""

    best: ParsedItemContext | None = None
    for node in _walk_payload(raw_payload):
        if not isinstance(node, dict):
            continue
        item_id = _first_value(node, ITEM_ID_KEYS)
        if not item_id:
            continue
        candidate = ParsedItemContext(
            item_id=item_id,
            title=_first_value(node, TITLE_KEYS),
            price=_first_value(node, PRICE_KEYS),
            image_url=_first_image(node),
            url=_first_value(node, URL_KEYS),
            source="item_card" if "itemCard" in node or _looks_like_item_card(node) else "message",
        )
        if best is None or _context_score(candidate) > _context_score(best):
            best = candidate

    extension = _find_message_extension(raw_payload)
    reminder_url = _normalize_scalar(extension.get("reminderUrl"))
    reminder_item_id = _query_value(
        _parse_url_query(reminder_url),
        "itemId",
        "item_id",
        "itemid",
    )
    effective_item_id = (best.item_id if best else None) or reminder_item_id or fallback_item_id
    if not effective_item_id:
        return None
    if best is None:
        return ParsedItemContext(
            item_id=effective_item_id,
            url=reminder_url,
            source="reminder_url" if reminder_item_id else "message",
        )
    if not best.url and reminder_url:
        best.url = reminder_url
    return best


def _parse_dict_node(node: dict[str, Any]) -> ParsedMessageCard | None:
    if not _looks_like_item_card(node) and not _looks_like_order_card(node):
        return None
    item_id = _first_value(node, ITEM_ID_KEYS)
    order_id = _first_value(node, ORDER_ID_KEYS)
    title = _first_value(node, TITLE_KEYS)
    price = _first_value(node, PRICE_KEYS)
    status = _first_value(node, STATUS_KEYS)
    image_url = _first_image(node)
    url = _first_value(node, URL_KEYS)

    if order_id:
        return ParsedMessageCard(
            card_type="order",
            item_id=item_id,
            order_id=order_id,
            title=title,
            price=price,
            status=status,
            image_url=image_url,
            url=url,
            raw_summary=_summary(node),
        )

    product_signal_count = sum(bool(value) for value in (item_id, title, price, image_url))
    if item_id and product_signal_count >= 2:
        return ParsedMessageCard(
            card_type="product",
            item_id=item_id,
            title=title,
            price=price,
            status=status,
            image_url=image_url,
            url=url,
            raw_summary=_summary(node),
        )

    return None


def _walk_payload(value: Any, depth: int = 0) -> Iterable[Any]:
    if depth > 8:
        return
    value = _decode_embedded_value(value)
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_payload(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_payload(child, depth + 1)


def _maybe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _decode_embedded_value(value: Any) -> Any:
    parsed = _maybe_json(value)
    if parsed is not value:
        return parsed
    if not isinstance(value, str):
        return value
    text = value.strip()
    if len(text) < 8 or len(text) > 2_000_000:
        return value
    try:
        padding = "=" * (-len(text) % 4)
        decoded = base64.b64decode(text + padding, validate=True).decode("utf-8")
        decoded = decoded.strip()
        if decoded.startswith(("{", "[")):
            return json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return value


def _looks_like_item_card(node: dict[str, Any]) -> bool:
    keys = {str(key).lower() for key in node}
    return bool(
        keys.intersection({"itemcard", "itemid", "item_id", "auctionid"})
        and keys.intersection({"title", "itemtitle", "price", "mainpic", "picurl", "imageurl"})
    )


def _looks_like_order_card(node: dict[str, Any]) -> bool:
    keys = {str(key).lower() for key in node}
    return bool(keys.intersection({key.lower() for key in ORDER_ID_KEYS}))


def _context_score(context: ParsedItemContext) -> int:
    return sum(bool(value) for value in (context.title, context.price, context.image_url, context.url))


def _numeric_item_id(value: Any) -> str | None:
    normalized = _normalize_scalar(value)
    if not normalized or not normalized.isdigit():
        return None
    return normalized


def _is_goofish_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    normalized = hostname.rstrip(".").lower()
    return normalized == "goofish.com" or normalized.endswith(".goofish.com")


def _find_custom(payload: dict[str, Any]) -> dict[str, Any]:
    for node in _walk_payload(payload):
        if not isinstance(node, dict):
            continue
        custom = node.get("custom")
        if isinstance(custom, dict) and custom.get("data"):
            return custom
    return {}


def _decode_custom_data(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    text = value.strip()
    parsed = _maybe_json(text)
    if isinstance(parsed, dict):
        return parsed
    try:
        padding = "=" * (-len(text) % 4)
        decoded = base64.b64decode(text + padding).decode("utf-8")
        result = json.loads(decoded)
        return result if isinstance(result, dict) else {}
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _nested_dict(value: Any, *keys: str) -> dict[str, Any]:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return current if isinstance(current, dict) else {}


def _nested_scalar(value: Any, *keys: str) -> str | None:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _normalize_scalar(current)


def _first_dict(value: Any, key: str) -> dict[str, Any] | None:
    for node in _walk_payload(value):
        if not isinstance(node, dict):
            continue
        candidate = node.get(key)
        if isinstance(candidate, dict):
            return candidate
    return None


def _find_message_extension(value: Any) -> dict[str, Any]:
    fallback: dict[str, Any] = {}
    for node in _walk_payload(value):
        if not isinstance(node, dict):
            continue
        candidate = node.get("extension")
        if not isinstance(candidate, dict):
            continue
        if not fallback and candidate:
            fallback = candidate
        if any(key in candidate for key in ("reminderUrl", "bizTag", "reminderContent")):
            return candidate
    return fallback


def _parse_url_query(value: str | None) -> dict[str, list[str]]:
    if not value:
        return {}
    try:
        return parse_qs(urlparse(value).query)
    except ValueError:
        return {}


def _query_value(query: dict[str, list[str]], *keys: str) -> str | None:
    lowered = {key.lower(): value for key, value in query.items()}
    for key in keys:
        values = lowered.get(key.lower())
        if values and values[0].strip():
            return values[0].strip()
    return None


def _normalize_order_state(value: str) -> tuple[str, str]:
    normalized = value.strip().lower()
    for keywords, event_type, status in ORDER_STATE_RULES:
        if any(keyword.lower() in normalized for keyword in keywords):
            return event_type, status
    return "updated", "unknown"


def _is_trade_tip(value: str) -> bool:
    normalized = value.strip().lower()
    return any(
        keyword in normalized
        for keyword in (
            "订单",
            "交易成功",
            "确认收货",
            "卖家已发货",
            "等待你发货",
            "待付款",
            "已付款",
            "完成了评价",
        )
    )


def _extract_price(value: str) -> str | None:
    matched = re.search(r"(?:¥|￥)\s*([0-9]+(?:\.[0-9]{1,2})?)", value)
    return matched.group(1) if matched else None


def _find_http_value(value: Any) -> str | None:
    for node in _walk_payload(value):
        if isinstance(node, str) and node.startswith(("http://", "https://")):
            return node
    return None


def _first_value(node: dict[str, Any], keys: set[str]) -> str | None:
    lowered = {str(key).lower(): key for key in node.keys()}
    for key in keys:
        actual_key = lowered.get(key.lower())
        if actual_key is None:
            continue
        value = node.get(actual_key)
        normalized = _normalize_scalar(value)
        if normalized:
            return normalized
    return None


def _first_image(node: dict[str, Any]) -> str | None:
    value = _first_value(node, IMAGE_KEYS)
    if value and value.startswith(("http://", "https://")):
        return value
    for child in node.values():
        if isinstance(child, dict):
            image = _first_image(child)
            if image:
                return image
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    image = _first_image(item)
                    if image:
                        return image
                else:
                    normalized = _normalize_scalar(item)
                    if normalized and normalized.startswith(("http://", "https://")):
                        return normalized
    return None


def _normalize_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _extract_title_from_content(content: str) -> str | None:
    text = content.strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    return text[:80]


def _summary(node: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in node.items():
        if len(result) >= 20:
            break
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[str(key)] = value
    return result
