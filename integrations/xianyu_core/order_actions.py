"""Account-scoped seller order detail and write operations over MTOP HTTP."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import requests

from .models import AccountConfig
from .order_models import OrderActionError, OrderActionResult, OrderDetailSnapshot
from .product_models import ProductPublishError
from .product_publisher import MtopProductPublisher


DETAIL_API = "mtop.idle.web.trade.order.detail"
HEADINFO_API = "mtop.idle.trade.pc.message.headinfo"
SHIPPING_RENDER_API = "mtop.taobao.idle.logistic.consign.render"
REFUND_DETAIL_API = "mtop.taobao.idle.refund.detail"
REFUND_REFUSE_RENDER_API = "mtop.taobao.idle.refund.refuse.render"
ACTION_SPECS: dict[str, tuple[str, str]] = {
    "confirm_shipping": ("mtop.taobao.idle.logistic.consign.dummy", "1.0"),
    "offline_shipping": ("mtop.taobao.idle.logistic.consign.offline", "1.0"),
    "free_shipping": ("mtop.idle.groupon.activity.seller.freeshipping", "1.0"),
    "close_order": ("mtop.taobao.idle.trade.close.by.seller", "2.0"),
    "rate_buyer": ("mtop.taobao.idle.rate.create", "4.0"),
    "refuse_refund": ("mtop.taobao.idle.refund.refuse", "1.0"),
}
STATUS_TEXT_MAP = (
    ("退款成功", "refunded"),
    ("已退款", "refunded"),
    ("退款中", "refunding"),
    ("退款申请", "refunding"),
    ("交易关闭", "closed"),
    ("已关闭", "closed"),
    ("交易成功", "completed"),
    ("已完成", "completed"),
    ("已发货", "shipped"),
    ("待发货", "paid_waiting_delivery"),
    ("等待卖家发货", "paid_waiting_delivery"),
    ("待付款", "pending_payment"),
)


class MtopOrderActions(MtopProductPublisher):
    """Perform one explicitly requested order action without blind write retries."""

    def __init__(self, account: AccountConfig, **kwargs: Any) -> None:
        try:
            super().__init__(account, **kwargs)
        except ProductPublishError as exc:
            raise OrderActionError(
                exc.kind,
                str(exc).replace("发布", "订单操作"),
                uncertain=exc.uncertain,
                cookie_updates=exc.cookie_updates,
                raw_response=exc.raw_response,
            ) from exc

    def get_order_detail(self, order_id: str) -> OrderDetailSnapshot:
        clean_order_id = self._required(order_id, "订单号")
        try:
            response = self._post_mtop(
                DETAIL_API,
                "1.0",
                {"tid": clean_order_id},
                spm_pre="",
                spm_cnt="a21ybx.order-detail.0.0",
                extra_headers={
                    "Referer": (
                        "https://www.goofish.com/order-detail?"
                        f"orderId={clean_order_id}&role=seller"
                    )
                },
                tracking_log_prefix=None,
            )
            self._ensure_success(response, operation="查询订单详情")
            return self._parse_detail(clean_order_id, response)
        except OrderActionError:
            raise
        except ProductPublishError as exc:
            raise self._from_publish_error(exc, "查询订单详情") from exc
        except requests.RequestException as exc:
            raise OrderActionError(
                "network",
                f"查询订单详情网络请求失败（{exc.__class__.__name__}）",
                cookie_updates=self.cookie_updates(),
            ) from exc

    def get_order_headinfo(self, item_id: str, conversation_id: str) -> dict[str, Any]:
        clean_item_id = self._required(item_id, "商品 ID")
        clean_conversation_id = self._required(conversation_id, "会话 ID")
        session_id: int | str = (
            int(clean_conversation_id)
            if clean_conversation_id.isdigit()
            else clean_conversation_id
        )
        try:
            response = self._post_mtop(
                HEADINFO_API,
                "1.0",
                {"itemId": clean_item_id, "sessionId": session_id},
                spm_pre="",
                spm_cnt="a21ybx.im.0.0",
                extra_headers={"Referer": "https://www.goofish.com/"},
                tracking_log_prefix=None,
            )
            self._ensure_success(response, operation="查询会话订单信息")
            data = response.get("data")
            return dict(data) if isinstance(data, Mapping) else {}
        except OrderActionError:
            raise
        except ProductPublishError as exc:
            raise self._from_publish_error(exc, "查询会话订单信息") from exc
        except requests.RequestException as exc:
            raise OrderActionError(
                "network",
                f"查询会话订单信息网络请求失败（{exc.__class__.__name__}）",
                cookie_updates=self.cookie_updates(),
            ) from exc

    def get_shipping_options(self, order_id: str) -> dict[str, Any]:
        clean_order_id = self._required(order_id, "订单号")
        try:
            response = self._post_mtop(
                SHIPPING_RENDER_API,
                "1.0",
                {"orderId": clean_order_id, "pageSource": "idleDelivery"},
                spm_pre="",
                spm_cnt="a2170.30051450.0.0",
                extra_headers={
                    "Origin": "https://h5.m.goofish.com",
                    "Referer": (
                        "https://h5.m.goofish.com/wow/moyu/moyu-project/"
                        "idle-logistics/pages/idleDeliver?kun=true"
                    ),
                },
                tracking_log_prefix=None,
            )
            self._ensure_success(response, operation="查询可用发货方式")
            return self._response_data(response)
        except ProductPublishError as exc:
            raise self._from_publish_error(exc, "查询可用发货方式") from exc
        except requests.RequestException as exc:
            raise OrderActionError(
                "network",
                f"查询可用发货方式网络请求失败（{exc.__class__.__name__}）",
                cookie_updates=self.cookie_updates(),
            ) from exc

    def get_refund_detail(self, order_id: str) -> dict[str, Any]:
        clean_order_id = self._required(order_id, "订单号")
        try:
            response = self._post_mtop(
                REFUND_DETAIL_API,
                "1.0",
                {"orderId": clean_order_id},
                spm_pre="",
                spm_cnt="a2170.refunddetail.0.0",
                extra_headers={
                    "Origin": "https://h5.m.goofish.com",
                    "Referer": (
                        "https://h5.m.goofish.com/wow/moyu/moyu-project/"
                        "idle-reverse/pages/refundDetail?kun=true"
                    ),
                },
                tracking_log_prefix=None,
            )
            self._ensure_success(response, operation="查询退款详情")
            return self._response_data(response)
        except ProductPublishError as exc:
            raise self._from_publish_error(exc, "查询退款详情") from exc
        except requests.RequestException as exc:
            raise OrderActionError(
                "network",
                f"查询退款详情网络请求失败（{exc.__class__.__name__}）",
                cookie_updates=self.cookie_updates(),
            ) from exc

    def get_refuse_refund_options(
        self, refund_id: str, reason_id: str = ""
    ) -> dict[str, Any]:
        clean_refund_id = self._required(refund_id, "退款单号")
        payload: dict[str, Any] = {"refundId": clean_refund_id}
        if reason_id:
            payload["refuseReasonId"] = reason_id
        try:
            response = self._post_mtop(
                REFUND_REFUSE_RENDER_API,
                "1.0",
                payload,
                spm_pre="",
                spm_cnt="a2170.refund_refuse_reason_float.0.0",
                extra_headers={
                    "Origin": "https://h5.m.goofish.com",
                    "Referer": (
                        "https://h5.m.goofish.com/wow/moyu/moyu-project/"
                        "idle-reverse/pages/rejectReason?kun=true"
                    ),
                },
                tracking_log_prefix=None,
            )
            self._ensure_success(response, operation="查询拒绝退款选项")
            return self._response_data(response)
        except ProductPublishError as exc:
            raise self._from_publish_error(exc, "查询拒绝退款选项") from exc
        except requests.RequestException as exc:
            raise OrderActionError(
                "network",
                f"查询拒绝退款选项网络请求失败（{exc.__class__.__name__}）",
                cookie_updates=self.cookie_updates(),
            ) from exc

    def execute(
        self,
        action: str,
        order_id: str,
        *,
        item_id: str = "",
        buyer_id: str = "",
        feedback: str = "不错的买家，期待再次交易",
        close_reason: str = "其他原因",
        tracking_no: str = "",
        carrier_code: str = "",
        carrier_brand_code: str = "",
        sender_address_id: str = "",
        refund_id: str = "",
        refund_reason_id: str = "",
        refund_proof: Mapping[str, Any] | None = None,
        refund_logistic_info: Mapping[str, Any] | None = None,
        refund_negotiation_apply: Mapping[str, Any] | None = None,
    ) -> OrderActionResult:
        clean_action = str(action or "").strip()
        clean_order_id = self._required(order_id, "订单号")
        if clean_action not in ACTION_SPECS:
            raise OrderActionError("validation", f"不支持的订单操作: {clean_action or '-'}")

        if clean_action == "confirm_shipping":
            payload: dict[str, Any] = {
                "orderId": clean_order_id,
                "tradeText": "",
                "picList": "[]",
                "newUnconsign": True,
                "source": "normal",
            }
        elif clean_action == "offline_shipping":
            payload = {
                "orderId": clean_order_id,
                "mailNo": self._required(tracking_no, "快递单号"),
                "cpCode": self._required(carrier_code, "快递公司编码"),
                "addressId": str(sender_address_id or "").strip() or None,
                "brandCode": str(carrier_brand_code or "").strip() or None,
            }
        elif clean_action == "free_shipping":
            payload = {
                "bizOrderId": clean_order_id,
                "itemId": self._required(item_id, "商品 ID"),
                "buyerId": self._required(buyer_id, "买家 ID"),
            }
        elif clean_action == "close_order":
            payload = {
                "tid": clean_order_id,
                "bizOrderId": clean_order_id,
                "closeReason": self._required(close_reason, "关闭原因"),
            }
        elif clean_action == "rate_buyer":
            payload = {
                "tradeId": clean_order_id,
                "rate": 1,
                "feedback": self._required(feedback, "评价内容")[:500],
                "createOrAppend": 0,
            }
        else:
            payload = {
                "refundId": self._required(refund_id, "退款单号"),
                "refuseReasonId": self._required(refund_reason_id, "拒绝原因"),
            }
            if refund_proof:
                payload["refuseProof"] = json.dumps(
                    dict(refund_proof), ensure_ascii=False, separators=(",", ":")
                )
            if refund_logistic_info:
                payload["logisticInfo"] = json.dumps(
                    dict(refund_logistic_info), ensure_ascii=False, separators=(",", ":")
                )
            if refund_negotiation_apply:
                payload["negotiationApply"] = json.dumps(
                    dict(refund_negotiation_apply),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

        api_name, version = ACTION_SPECS[clean_action]
        try:
            response = self._post_mtop(
                api_name,
                version,
                payload,
                spm_pre=("a21107h.44911108.0.0" if clean_action == "close_order" else ""),
                spm_cnt=("a21107h.44911108.0.0" if clean_action == "close_order" else ""),
                extra_headers=self._action_headers(clean_action),
                tracking_log_prefix=None,
            )
            self._ensure_success(response, operation=self._action_label(clean_action))
        except ProductPublishError as exc:
            raw_response = exc.raw_response
            if clean_action in {
                "confirm_shipping",
                "offline_shipping",
                "free_shipping",
            } and self._contains_marker(
                raw_response, ("ORDER_ALREADY_DELIVERY", "已发货成功")
            ):
                return OrderActionResult(
                    clean_action,
                    clean_order_id,
                    True,
                    "订单已经发货，无需重复操作",
                    platform_code=self._response_code(raw_response),
                    already_applied=True,
                    raw_response=raw_response,
                )
            raise self._from_publish_error(exc, self._action_label(clean_action), write=True) from exc
        except requests.RequestException as exc:
            raise OrderActionError(
                "result_unknown",
                f"{self._action_label(clean_action)}请求已发出但未收到明确结果，禁止直接重试",
                uncertain=True,
                cookie_updates=self.cookie_updates(),
            ) from exc

        return OrderActionResult(
            clean_action,
            clean_order_id,
            True,
            f"{self._action_label(clean_action)}成功",
            platform_code=self._response_code(response),
            raw_response=response,
        )

    @staticmethod
    def _required(value: Any, label: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise OrderActionError("validation", f"{label}不能为空")
        return text

    @staticmethod
    def _action_label(action: str) -> str:
        return {
            "confirm_shipping": "确认无物流发货",
            "offline_shipping": "自行寄件发货",
            "free_shipping": "确认免拼发货",
            "close_order": "关闭订单",
            "rate_buyer": "评价买家",
            "refuse_refund": "拒绝退款",
        }[action]

    @staticmethod
    def _action_headers(action: str) -> dict[str, str]:
        if action == "close_order":
            return {
                "Origin": "https://seller.goofish.com",
                "Referer": "https://seller.goofish.com/?site=COMMONPRO",
                "idle_site_biz_code": "COMMONPRO",
                "idle_user_group_member_id": "",
            }
        if action in {"confirm_shipping", "offline_shipping"}:
            return {
                "Origin": "https://h5.m.goofish.com",
                "Referer": (
                    "https://h5.m.goofish.com/wow/moyu/moyu-project/"
                    "idle-logistics/pages/idleDeliver?kun=true"
                ),
            }
        if action == "refuse_refund":
            return {
                "Origin": "https://h5.m.goofish.com",
                "Referer": (
                    "https://h5.m.goofish.com/wow/moyu/moyu-project/"
                    "idle-reverse/pages/rejectApply?kun=true"
                ),
            }
        return {"Referer": "https://www.goofish.com/"}

    @staticmethod
    def _response_data(response: Mapping[str, Any]) -> dict[str, Any]:
        data = response.get("data")
        if not isinstance(data, Mapping):
            return {}
        nested = data.get("data")
        return dict(nested) if isinstance(nested, Mapping) else dict(data)

    def _from_publish_error(
        self,
        exc: ProductPublishError,
        operation: str,
        *,
        write: bool = False,
    ) -> OrderActionError:
        uncertain = bool(
            write
            and (
                exc.uncertain
                or exc.kind
                not in {"auth", "platform_rejected", "risk_control", "validation"}
            )
        )
        return OrderActionError(
            "result_unknown" if uncertain else exc.kind,
            (
                f"{operation}请求结果无法确认，禁止直接重试"
                if uncertain
                else str(exc).replace("发布", operation)
            ),
            uncertain=uncertain,
            verification_required=exc.kind == "risk_control",
            cookie_updates=self.cookie_updates(),
            raw_response=exc.raw_response,
        )

    @staticmethod
    def _response_code(response: Mapping[str, Any]) -> str:
        ret = response.get("ret") if isinstance(response, Mapping) else None
        if isinstance(ret, list) and ret:
            return str(ret[0]).split("::", 1)[0]
        return "UNKNOWN"

    @classmethod
    def _parse_detail(
        cls, order_id: str, response: Mapping[str, Any]
    ) -> OrderDetailSnapshot:
        data = response.get("data") if isinstance(response.get("data"), Mapping) else {}
        components = data.get("components") if isinstance(data, Mapping) else []
        components = components if isinstance(components, list) else []
        item_id = str(data.get("itemId") or "").strip() if isinstance(data, Mapping) else ""
        buyer_id = str(data.get("peerUserId") or "").strip() if isinstance(data, Mapping) else ""
        price = ""
        quantity = 1
        receiver_name = ""
        receiver_phone = ""
        receiver_address = ""
        status_text = ""
        is_bargain = False

        for component in components:
            if not isinstance(component, Mapping):
                continue
            render = str(component.get("render") or "")
            value = component.get("data") if isinstance(component.get("data"), Mapping) else {}
            if render == "orderInfoVO":
                item_info = value.get("itemInfo") if isinstance(value.get("itemInfo"), Mapping) else {}
                item_id = str(item_info.get("itemId") or value.get("itemId") or item_id).strip()
                buyer_id = str(value.get("buyerUserId") or value.get("buyerId") or buyer_id).strip()
                price = str(item_info.get("price") or price).strip()
                try:
                    quantity = max(1, int(item_info.get("buyAmount") or quantity))
                except (TypeError, ValueError):
                    pass
            elif render == "addressInfoVO":
                receiver_name = str(value.get("name") or "").strip()
                receiver_phone = str(value.get("phoneNumber") or "").strip()
                receiver_address = str(value.get("address") or "").strip()
            elif render == "orderStatusVO":
                status_info = value.get("orderStatusInfo")
                if isinstance(status_info, Mapping):
                    status_text = str(status_info.get("title") or "").strip()
                nodes = value.get("orderStatusNodeList")
                if isinstance(nodes, list):
                    node_titles = [
                        str(node.get("title") or "").strip()
                        for node in nodes
                        if isinstance(node, Mapping)
                    ]
                    is_bargain = any(title in {"已刀成", "待刀成"} for title in node_titles)
                    if not status_text:
                        status_text = " ".join(title for title in node_titles if title)

        if not status_text:
            status_text = cls._find_status_text(data)
        status = cls._normalize_status(status_text)
        return OrderDetailSnapshot(
            order_id=order_id,
            item_id=item_id,
            buyer_id=buyer_id,
            price=price,
            quantity=quantity,
            status=status,
            status_text=status_text,
            platform_status=status_text,
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            receiver_address=receiver_address,
            is_bargain=is_bargain,
            raw_response=response,
        )

    @staticmethod
    def _find_status_text(value: Any) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(value or "")
        for marker, _status in STATUS_TEXT_MAP:
            if marker in text:
                return marker
        return ""

    @staticmethod
    def _normalize_status(text: str) -> str:
        for marker, status in STATUS_TEXT_MAP:
            if marker in text:
                return status
        return "unknown"
