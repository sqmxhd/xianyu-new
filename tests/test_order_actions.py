import asyncio
import json
import os
import unittest
from datetime import UTC, datetime

import requests

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base, _backfill_headinfo_order_metadata
from apps.api.xianyu_admin_api.card_parser import ParsedOrderEvent
from apps.api.xianyu_admin_api.order_action_policy import order_action_availability
from apps.api.xianyu_admin_api.order_action_service import (
    OrderActionConflict,
    OrderActionRepository,
    OrderActionService,
)
from apps.api.xianyu_admin_api.orm import MessageORM, OrderOperationORM, OrderORM
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    OrderOperationExecuteRequest,
)
from apps.api.xianyu_admin_api.store import AccountStore
from integrations.xianyu_core import (
    AccountConfig,
    MtopOrderActions,
    OrderActionError,
    OrderActionResult,
    OrderDetailSnapshot,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.trust_env = True
        self.headers = {}
        self.proxies = {}
        self.cookies = requests.cookies.RequestsCookieJar()
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self):
        return None


class OrderActionAdapterTests(unittest.TestCase):
    def make_client(self, responses):
        session = FakeSession(responses)
        client = MtopOrderActions(
            AccountConfig(
                account_id="account-1",
                cookie="unb=10001; _m_h5_tk=token_1",
            ),
            session_factory=lambda: session,
            sign_handler=lambda *_args: "sign",
        )
        return client, session

    def test_detail_is_normalized_for_preflight(self):
        response = FakeResponse(
            {
                "ret": ["SUCCESS::调用成功"],
                "data": {
                    "itemId": "item-1",
                    "peerUserId": "buyer-1",
                    "components": [
                        {
                            "render": "orderInfoVO",
                            "data": {
                                "buyerUserId": "buyer-1",
                                "itemInfo": {
                                    "itemId": "item-1",
                                    "price": "18.80",
                                    "buyAmount": 2,
                                },
                            },
                        },
                        {
                            "render": "addressInfoVO",
                            "data": {
                                "name": "张三",
                                "phoneNumber": "13800000000",
                                "address": "浙江省杭州市",
                            },
                        },
                        {
                            "render": "orderStatusVO",
                            "data": {
                                "orderStatusInfo": {"title": "待发货"},
                                "orderStatusNodeList": [{"title": "已刀成"}],
                            },
                        },
                    ],
                },
            }
        )
        client, _session = self.make_client([response])
        try:
            detail = client.get_order_detail("order-1")
        finally:
            client.close()
        self.assertEqual(detail.status, "paid_waiting_delivery")
        self.assertEqual(detail.item_id, "item-1")
        self.assertEqual(detail.buyer_id, "buyer-1")
        self.assertEqual(detail.quantity, 2)
        self.assertTrue(detail.is_bargain)
        self.assertEqual(detail.receiver_name, "张三")

    def test_headinfo_returns_dynamic_platform_capabilities(self):
        client, session = self.make_client(
            [
                FakeResponse(
                    {
                        "ret": ["SUCCESS::调用成功"],
                        "data": {
                            "commonData": {"orderId": "order-1"},
                            "right": {
                                "data": {
                                    "btnList": [
                                        {"name": "去发货", "tradeAction": "LOGISTICS_SEND"}
                                    ]
                                }
                            },
                        },
                    }
                )
            ]
        )
        try:
            result = client.get_order_headinfo("item-1", "123456")
        finally:
            client.close()
        self.assertEqual(result["commonData"]["orderId"], "order-1")
        url, call = session.calls[0]
        self.assertIn("mtop.idle.trade.pc.message.headinfo", url)
        self.assertEqual(json.loads(call["data"]["data"])["sessionId"], 123456)

    def test_action_payloads_follow_upstream_contracts(self):
        for action, expected_api, expected_payload in (
            (
                "confirm_shipping",
                "mtop.taobao.idle.logistic.consign.dummy",
                {
                    "orderId": "order-1",
                    "tradeText": "",
                    "picList": "[]",
                    "newUnconsign": True,
                    "source": "normal",
                },
            ),
            (
                "offline_shipping",
                "mtop.taobao.idle.logistic.consign.offline",
                {
                    "orderId": "order-1",
                    "mailNo": "YT123456",
                    "cpCode": "YTO",
                    "addressId": "sender-1",
                    "brandCode": "YTO",
                },
            ),
            (
                "free_shipping",
                "mtop.idle.groupon.activity.seller.freeshipping",
                {"bizOrderId": "order-1", "itemId": "item-1", "buyerId": "buyer-1"},
            ),
            (
                "close_order",
                "mtop.taobao.idle.trade.close.by.seller",
                {"tid": "order-1", "closeReason": "其他原因"},
            ),
            (
                "rate_buyer",
                "mtop.taobao.idle.rate.create",
                {"tradeId": "order-1", "rate": 1, "feedback": "合作愉快"},
            ),
        ):
            with self.subTest(action=action):
                client, session = self.make_client(
                    [FakeResponse({"ret": ["SUCCESS::调用成功"], "data": {}})]
                )
                try:
                    result = client.execute(
                        action,
                        "order-1",
                        item_id="item-1",
                        buyer_id="buyer-1",
                        feedback="合作愉快",
                        tracking_no="YT123456",
                        carrier_code="YTO",
                        carrier_brand_code="YTO",
                        sender_address_id="sender-1",
                    )
                finally:
                    client.close()
                self.assertTrue(result.success)
                url, call = session.calls[0]
                self.assertIn(expected_api, url)
                payload = json.loads(call["data"]["data"])
                for key, value in expected_payload.items():
                    self.assertEqual(payload[key], value)

    def test_refuse_refund_payload_follows_h5_contract(self):
        client, session = self.make_client(
            [FakeResponse({"ret": ["SUCCESS::调用成功"], "data": {}})]
        )
        try:
            result = client.execute(
                "refuse_refund",
                "order-1",
                refund_id="refund-1",
                refund_reason_id="reason-1",
            )
        finally:
            client.close()
        self.assertTrue(result.success)
        url, call = session.calls[0]
        self.assertIn("mtop.taobao.idle.refund.refuse", url)
        self.assertEqual(
            json.loads(call["data"]["data"]),
            {"refundId": "refund-1", "refuseReasonId": "reason-1"},
        )

    def test_dynamic_shipping_and_refund_render_endpoints(self):
        client, session = self.make_client(
            [
                FakeResponse(
                    {
                        "ret": ["SUCCESS::调用成功"],
                        "data": {"idleLogisticTypes": ["DUMMY_CONSIGN"]},
                    }
                ),
                FakeResponse(
                    {
                        "ret": ["SUCCESS::调用成功"],
                        "data": {"refundId": "refund-1"},
                    }
                ),
                FakeResponse(
                    {
                        "ret": ["SUCCESS::调用成功"],
                        "data": {"refuseReasonList": []},
                    }
                ),
            ]
        )
        try:
            shipping = client.get_shipping_options("order-1")
            refund = client.get_refund_detail("order-1")
            refusal = client.get_refuse_refund_options("refund-1")
        finally:
            client.close()
        self.assertEqual(shipping["idleLogisticTypes"], ["DUMMY_CONSIGN"])
        self.assertEqual(refund["refundId"], "refund-1")
        self.assertEqual(refusal["refuseReasonList"], [])
        self.assertIn("mtop.taobao.idle.logistic.consign.render", session.calls[0][0])
        self.assertIn("mtop.taobao.idle.refund.detail", session.calls[1][0])
        self.assertIn("mtop.taobao.idle.refund.refuse.render", session.calls[2][0])

    def test_network_failure_after_write_is_marked_uncertain(self):
        client, _session = self.make_client([requests.Timeout("timeout")])
        try:
            with self.assertRaises(OrderActionError) as raised:
                client.execute("confirm_shipping", "order-1")
        finally:
            client.close()
        self.assertEqual(raised.exception.kind, "result_unknown")
        self.assertTrue(raised.exception.uncertain)


class FakeOrderActions:
    execute_count = 0
    headinfo_actions = ["LOGISTICS_SEND"]
    refund_rejected = False

    def __init__(self, _account):
        self.closed = False

    def get_order_detail(self, order_id):
        return OrderDetailSnapshot(
            order_id=order_id,
            item_id="item-1",
            buyer_id="buyer-1",
            status="paid_waiting_delivery",
            status_text="待发货",
            platform_status="待发货",
        )

    def get_order_headinfo(self, item_id, conversation_id):
        buttons = []
        for action in type(self).headinfo_actions:
            button = {"name": action, "tradeAction": action}
            if action == "DEAL_REFUND":
                button["clickEvent"] = {
                    "type": "openPage",
                    "data": {
                        "url": (
                            "https://h5.m.goofish.com/wow/refundDetail?"
                            "orderId=order-1"
                        )
                    },
                }
            buttons.append(button)
        return {
            "commonData": {
                "orderId": "order-1",
                "itemId": item_id,
                "supportPCTrade": True,
            },
            "middle": {"subTitle": "含运费0.00元"},
            "right": {"data": {"btnList": buttons}},
        }

    def get_shipping_options(self, order_id):
        return {
            "idleLogisticTypes": ["DUMMY_CONSIGN", "OFFLINE_CONSIGN"],
            "senderAddressInfo": {"addressId": "sender-1"},
        }

    def get_refund_detail(self, order_id):
        if type(self).refund_rejected:
            return {
                "refundId": "refund-1",
                "statusDesc": "已拒绝退款",
                "components": [],
            }
        return {
            "refundId": "refund-1",
            "refundStatus": "1",
            "components": [
                {
                    "data": {
                        "buttons": [
                            {"name": "同意退款", "code": "agreeRefundApply"},
                            {"name": "拒绝退款", "code": "rejectApply"},
                        ]
                    }
                }
            ],
        }

    def get_refuse_refund_options(self, refund_id, reason_id=""):
        return {
            "refuseReasonList": [
                {"refuseReasonId": "reason-1", "reasonName": "商品已经发出"}
            ],
            "refuseProof": {"mustProof": False},
        }

    def execute(self, action, order_id, **_kwargs):
        type(self).execute_count += 1
        if action == "refuse_refund":
            type(self).refund_rejected = True
        return OrderActionResult(
            action=action,
            order_id=order_id,
            success=True,
            message="确认无物流发货成功",
            platform_code="SUCCESS",
            raw_response={"ret": ["SUCCESS::调用成功"]},
        )

    def cookie_updates(self):
        return {}

    def close(self):
        self.closed = True


class OrderActionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.store = AccountStore(session_factory=self.factory, initialize=False)
        self.account = await self.store.create_account(
            AccountCreatePayload(cookie="unb=10001; _m_h5_tk=token_1",
                enabled=False,
            )
        )
        now = datetime.now(UTC)
        with self.factory() as session:
            session.add(
                OrderORM(
                    order_pk="order-pk-1",
                    account_id=self.account.account_id,
                    platform_order_id="order-1",
                    trade_role="seller",
                    data_source="seller_sold",
                    first_seen_source="seller_sold",
                    platform_confirmed=True,
                    sync_state="confirmed",
                    conversation_id="conversation-1",
                    peer_user_id="buyer-1",
                    buyer_user_id="buyer-1",
                    item_id="item-1",
                    title="测试商品",
                    status="paid_waiting_delivery",
                    status_text="待发货",
                    platform_status="待发货",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        FakeOrderActions.execute_count = 0
        FakeOrderActions.headinfo_actions = ["LOGISTICS_SEND"]
        FakeOrderActions.refund_rejected = False
        self.repository = OrderActionRepository(self.factory)
        self.service = OrderActionService(
            self.store,
            self.repository,
            operations_factory=FakeOrderActions,
        )

    async def asyncTearDown(self):
        self.engine.dispose()

    async def test_policy_blocks_unconfirmed_message_orders(self):
        actions = order_action_availability(
            {
                "trade_role": "seller",
                "data_source": "message",
                "platform_confirmed": False,
                "platform_order_id": "order-2",
                "status": "paid_waiting_delivery",
            }
        )
        self.assertTrue(all(not action.enabled for action in actions))

    async def test_headinfo_confirmation_is_sufficient_but_capability_is_per_action(self):
        actions = order_action_availability(
            {
                "trade_role": "seller",
                "data_source": "headinfo",
                "platform_confirmed": True,
                "platform_order_id": "order-2",
                "status": "paid_waiting_delivery",
                "headinfo_confirmed_at": datetime.now(UTC),
                "platform_capabilities": json.dumps(["LOGISTICS_SEND"]),
                "platform_shipping_methods": json.dumps(["DUMMY_CONSIGN"]),
            }
        )
        by_action = {item.action: item for item in actions}
        self.assertTrue(by_action["confirm_shipping"].enabled)
        self.assertFalse(by_action["close_order"].enabled)
        self.assertIn("平台当前未提供", by_action["close_order"].reason)

    async def test_message_replay_preserves_headinfo_confirmation_and_refund_status(self):
        now = datetime.now(UTC)
        with self.factory() as session:
            order = session.get(OrderORM, "order-pk-1")
            order.data_source = "headinfo"
            order.headinfo_confirmed_at = now
            order.platform_capabilities = json.dumps(
                ["DEAL_REFUND", "LOGISTICS_SEND"]
            )
            order.status = "paid_waiting_delivery"
            order.refund_status = "pending"
            order.raw_summary = json.dumps({"source": "headinfo"})
            message = MessageORM(
                message_pk="message-replay-1",
                account_id=self.account.account_id,
                conversation_id="conversation-1",
                message_id="message-replay-platform-1",
                direction="in",
                message_type="dx_card",
                content="我已付款，等待你发货",
                created_at_ms=int(now.timestamp() * 1000),
                created_at=now,
            )
            session.add(message)
            session.flush()
            self.store._upsert_order_event(
                session,
                message=message,
                parsed=ParsedOrderEvent(
                    event_type="paid",
                    status="paid_waiting_delivery",
                    status_text="我已付款，等待你发货",
                    order_id="order-1",
                    item_id="item-1",
                    trade_role="seller",
                    raw_summary={"source": "dx_card"},
                ),
            )
            session.commit()
        current = await self.store.get_order("order-pk-1")
        self.assertEqual(current.data_source, "headinfo")
        self.assertEqual(current.status, "paid_waiting_delivery")
        self.assertEqual(current.refund_status, "pending")
        self.assertEqual(current.raw_summary.get("source"), "headinfo")

    async def test_refund_headinfo_allows_shipping_when_render_allows_it(self):
        with self.factory() as session:
            order = session.get(OrderORM, "order-pk-1")
            order.data_source = "headinfo"
            order.first_seen_source = "dx_card"
            order.headinfo_confirmed_at = datetime.now(UTC)
            order.platform_capabilities = json.dumps(["LOGISTICS_SEND"])
            session.commit()
        FakeOrderActions.headinfo_actions = ["DEAL_REFUND", "LOGISTICS_SEND"]
        request = OrderOperationExecuteRequest(
            action="confirm_shipping",
            idempotency_key="operation-key-refund",
        )
        result = await self.service.execute(
            "order-pk-1", request, requested_by="admin"
        )
        self.assertEqual(result.operation.status, "succeeded")
        self.assertEqual(FakeOrderActions.execute_count, 1)
        current = await self.store.get_order("order-pk-1")
        self.assertEqual(current.status, "shipped")
        self.assertEqual(current.refund_status, "pending")
        self.assertIn("DEAL_REFUND", current.platform_capabilities)
        self.assertIn("DEAL_REFUND", current.platform_action_links)
        self.assertIn("DUMMY_CONSIGN", current.platform_shipping_methods)
        self.assertIn("REFUSE_REFUND", current.platform_refund_actions)

    async def test_legacy_headinfo_rows_are_backfilled_as_confirmed_refunds(self):
        now = datetime.now(UTC)
        with self.factory() as session:
            session.add(
                OrderORM(
                    order_pk="legacy-headinfo-order",
                    account_id=self.account.account_id,
                    platform_order_id="legacy-order-1",
                    trade_role="seller",
                    data_source="headinfo",
                    first_seen_source="dx_card",
                    platform_confirmed=False,
                    sync_state="provisional",
                    conversation_id="conversation-legacy",
                    item_id="item-legacy",
                    status="paid_waiting_delivery",
                    raw_summary=json.dumps(
                        {
                            "source": "headinfo",
                            "commonData": {"orderId": "legacy-order-1"},
                            "right": {
                                "btnList": [
                                    {
                                        "tradeAction": "DEAL_REFUND",
                                        "clickEvent": {
                                            "data": {
                                                "url": "https://h5.m.goofish.com/refund?id=1"
                                            }
                                        },
                                    }
                                ]
                            },
                        }
                    ),
                    last_synced_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        _backfill_headinfo_order_metadata(self.engine)
        current = await self.store.get_order("legacy-headinfo-order")
        self.assertTrue(current.platform_confirmed)
        self.assertEqual(current.sync_state, "confirmed")
        self.assertEqual(current.status, "paid_waiting_delivery")
        self.assertEqual(current.refund_status, "pending")
        listed = await self.store.list_orders(
            trade_role="seller", confirmed_only=True
        )
        self.assertIn("legacy-order-1", [item.platform_order_id for item in listed])

    async def test_persisted_headinfo_evidence_is_repaired_after_message_replay(self):
        now = datetime.now(UTC)
        with self.factory() as session:
            session.add(
                OrderORM(
                    order_pk="replayed-headinfo-order",
                    account_id=self.account.account_id,
                    platform_order_id="replayed-order-1",
                    trade_role="seller",
                    data_source="dx_card",
                    first_seen_source="dx_card",
                    platform_confirmed=True,
                    sync_state="confirmed",
                    conversation_id="conversation-replayed",
                    item_id="item-replayed",
                    status="paid_waiting_delivery",
                    headinfo_confirmed_at=now,
                    platform_capabilities=json.dumps(
                        ["DEAL_REFUND", "LOGISTICS_SEND"]
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        _backfill_headinfo_order_metadata(self.engine)
        current = await self.store.get_order("replayed-headinfo-order")
        self.assertEqual(current.data_source, "headinfo")
        self.assertEqual(current.status, "paid_waiting_delivery")
        self.assertEqual(current.refund_status, "pending")

    async def test_refuse_refund_uses_dynamic_reason_and_updates_refund_state(self):
        with self.factory() as session:
            order = session.get(OrderORM, "order-pk-1")
            order.data_source = "headinfo"
            order.headinfo_confirmed_at = datetime.now(UTC)
            session.commit()
        FakeOrderActions.headinfo_actions = ["DEAL_REFUND", "LOGISTICS_SEND"]
        preview = await self.service.preview("order-pk-1", "refuse_refund")
        self.assertTrue(preview.eligible)
        self.assertEqual(preview.order.refund_id, "refund-1")
        self.assertEqual(preview.order.refund_refuse_options[0]["id"], "reason-1")

        result = await self.service.execute(
            "order-pk-1",
            OrderOperationExecuteRequest(
                action="refuse_refund",
                idempotency_key="operation-key-refuse",
                refund_reason_id="reason-1",
            ),
            requested_by="admin",
        )
        self.assertEqual(result.operation.status, "succeeded")
        self.assertEqual(result.order.status, "paid_waiting_delivery")
        self.assertEqual(result.order.refund_status, "rejected")

    async def test_execute_is_durable_and_idempotent(self):
        request = OrderOperationExecuteRequest(
            action="confirm_shipping",
            idempotency_key="operation-key-0001",
        )
        first = await self.service.execute("order-pk-1", request, requested_by="admin")
        second = await self.service.execute("order-pk-1", request, requested_by="admin")

        self.assertEqual(first.operation.status, "succeeded")
        self.assertEqual(second.operation.operation_id, first.operation.operation_id)
        self.assertEqual(second.order.status, "shipped")
        self.assertEqual(FakeOrderActions.execute_count, 1)
        with self.factory() as session:
            count = session.scalar(select(func.count()).select_from(OrderOperationORM))
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
