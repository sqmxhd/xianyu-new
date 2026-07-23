import asyncio
import base64
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.card_parser import (
    normalize_item_url,
    parse_item_context,
    parse_message_cards,
    parse_order_event,
)
from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.order_management_service import OrderManagementRepository
from apps.api.xianyu_admin_api.runtime import AccountRuntimeManager
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    DeliveryPreparePayload,
    DeliveryTemplateCreatePayload,
    OrderDeliveryPreviewRequest,
)
from apps.api.xianyu_admin_api.store import AccountStore
from integrations.xianyu_core import SellerOrder


def order_payload(order_id: str = "order-1") -> dict:
    card = {
        "dxCard": {
            "item": {
                "main": {
                    "targetUrl": f"fleamarket://order_detail?id={order_id}&role=Buyer",
                    "exContent": {
                        "title": "我已付款，等待你发货",
                        "desc": "测试商品 ￥12.50",
                        "picUrl": "https://example.test/item.jpg",
                    },
                },
                "extension": {
                    "extJson": {"updateKey": "TRADE_PAID_DONE_BUYER"},
                    "bizTag": {"taskName": "trade_paid"},
                },
            }
        }
    }
    encoded = base64.b64encode(json.dumps(card).encode()).decode()
    return {
        "message": {"content": {"custom": {"data": encoded}}},
        "extension": {
            "reminderUrl": "fleamarket://chat?itemId=item-1&userId=buyer-1"
        },
    }


def product_card_payload() -> dict:
    card = {
        "contentType": 7,
        "itemCard": {
            "itemId": "item-card-1",
            "title": "卡片商品",
            "price": "19.90",
            "mainPic": "https://example.test/product.jpg",
            "targetUrl": "fleamarket://item?id=item-card-1",
        },
    }
    encoded = base64.b64encode(json.dumps(card).encode()).decode()
    return {
        "message": {"content": {"custom": {"data": encoded}}},
        "extension": {
            "reminderUrl": "fleamarket://chat?itemId=item-card-1&userId=buyer-1"
        },
    }


class OrderParserTests(unittest.TestCase):
    def test_item_deep_link_is_converted_to_browser_url(self) -> None:
        self.assertEqual(
            normalize_item_url(
                "fleamarket://item?id=1055756055551&fmdirect=true",
                "1055756055551",
            ),
            "https://h5.m.goofish.com/item?id=1055756055551",
        )

    def test_numeric_item_id_provides_url_when_platform_url_is_missing(self) -> None:
        self.assertEqual(
            normalize_item_url(None, "1055756055551"),
            "https://h5.m.goofish.com/item?id=1055756055551",
        )

    def test_untrusted_or_mismatched_item_url_cannot_change_item_id(self) -> None:
        expected = "https://h5.m.goofish.com/item?id=1055756055551"
        self.assertEqual(
            normalize_item_url("javascript:alert(1)", "1055756055551"),
            expected,
        )
        self.assertEqual(
            normalize_item_url(
                "https://h5.m.goofish.com/item?id=9999999999999",
                "1055756055551",
            ),
            expected,
        )

    def test_valid_goofish_https_url_is_preserved(self) -> None:
        item_url = "https://www.goofish.com/item?id=1055756055551"
        self.assertEqual(normalize_item_url(item_url, "1055756055551"), item_url)

    def test_goofish_non_item_page_is_not_used_as_item_url(self) -> None:
        self.assertEqual(
            normalize_item_url(
                "https://h5.m.goofish.com/wow/message-head-c2c/index.html",
                "1055756055551",
            ),
            "https://h5.m.goofish.com/item?id=1055756055551",
        )

    def test_dx_card_is_decoded_into_normalized_order_event(self) -> None:
        parsed = parse_order_event(order_payload(), content="我已付款，等待你发货")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.order_id, "order-1")
        self.assertEqual(parsed.item_id, "item-1")
        self.assertEqual(parsed.peer_user_id, "buyer-1")
        self.assertEqual(parsed.status, "paid_waiting_delivery")
        self.assertEqual(parsed.price, "12.50")
        self.assertEqual(parsed.trade_role, "buyer")

    def test_product_card_and_item_context_are_decoded_from_base64(self) -> None:
        context = parse_item_context(product_card_payload())
        cards = parse_message_cards(product_card_payload(), content="分享商品")

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.item_id, "item-card-1")
        self.assertEqual(context.title, "卡片商品")
        self.assertEqual(context.image_url, "https://example.test/product.jpg")
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].card_type, "product")
        self.assertEqual(cards[0].price, "19.90")

    def test_plain_message_with_fallback_item_does_not_create_card(self) -> None:
        cards = parse_message_cards({}, content="普通消息", fallback_item_id="item-1")
        self.assertEqual(cards, [])


class OrderStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.store = AccountStore(session_factory=self.factory, initialize=False)
        self.repository = OrderManagementRepository(self.factory)
        self.account = await self.store.create_account(
            AccountCreatePayload(account_name="order-account", enabled=False)
        )

    async def asyncTearDown(self) -> None:
        self.engine.dispose()

    async def test_delivery_send_claim_is_atomic_across_store_instances(self) -> None:
        record = await self.store.prepare_delivery_record(
            self.account.account_id,
            "conversation-claim",
            DeliveryPreparePayload(
                receiver_user_id="buyer-claim",
                content="claim once",
            ),
        )
        assert record is not None
        second_store = AccountStore(session_factory=self.factory, initialize=False)

        first, second = await asyncio.gather(
            self.store.claim_delivery_record_for_send(
                account_id=self.account.account_id,
                record_id=record.record_id,
            ),
            second_store.claim_delivery_record_for_send(
                account_id=self.account.account_id,
                record_id=record.record_id,
            ),
        )
        self.assertEqual(sum(item is not None for item in (first, second)), 1)
        current = await self.store.get_delivery_record(
            self.account.account_id,
            record.record_id,
        )
        assert current is not None
        self.assertEqual(current.status, "sending")

    async def test_unacknowledged_delivery_is_uncertain_and_not_resent(self) -> None:
        record = await self.store.prepare_delivery_record(
            self.account.account_id,
            "conversation-uncertain",
            DeliveryPreparePayload(
                receiver_user_id="buyer-uncertain",
                content="send once",
            ),
        )
        assert record is not None
        send_text = AsyncMock(
            return_value=SimpleNamespace(
                success=False,
                message_id="message-uncertain",
                error="timed out waiting for platform acknowledgement",
                raw_payload={"request": {"lwp": "/r/MessageSend/sendByReceiverScope"}},
            )
        )
        runtime = AccountRuntimeManager(self.store)
        runtime._core = SimpleNamespace(send_text=send_text)

        first = await runtime.send_delivery_record(self.account, record.record_id)
        second = await runtime.send_delivery_record(self.account, record.record_id)

        assert first is not None and second is not None
        self.assertFalse(first.success)
        self.assertEqual(first.record.status, "uncertain")
        self.assertFalse(second.success)
        self.assertEqual(second.record.status, "uncertain")
        self.assertEqual(send_text.await_count, 1)

    async def test_order_upsert_tip_correlation_and_delivery_derivation(self) -> None:
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="card",
            content="我已付款，等待你发货",
            message_id="message-1",
            peer_user_id="buyer-1",
            peer_name="测试买家",
            item_id="item-1",
            raw_payload=order_payload(),
            created_at_ms=1_700_000_000_000,
        )
        orders = await self.store.list_orders(account_id=self.account.account_id)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].status, "paid_waiting_delivery")

        template = await self.store.create_delivery_template(
            self.account.account_id,
            DeliveryTemplateCreatePayload(
                name="资料",
                content="订单 {order_id} / 商品 {item_id} / 买家 {peer_name}",
            ),
        )
        assert template is not None
        preview = await self.store.preview_order_delivery(
            orders[0].order_pk,
            OrderDeliveryPreviewRequest(template_id=template.template_id),
        )
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertFalse(preview.eligible)
        self.assertTrue(any("已售订单接口确认" in reason for reason in preview.reasons))

        await self.repository.apply_orders(
            self.account.account_id,
            (
                SellerOrder(
                    order_id="order-1",
                    item_id="item-1",
                    buyer_id="buyer-1",
                    buyer_name="测试买家",
                    price="12.50",
                    status="paid_waiting_delivery",
                    status_text="待发货",
                    platform_status="待发货",
                ),
            ),
            mode="full",
        )
        orders = await self.store.list_orders(account_id=self.account.account_id)
        preview = await self.store.preview_order_delivery(
            orders[0].order_pk,
            OrderDeliveryPreviewRequest(template_id=template.template_id),
        )
        assert preview is not None
        self.assertTrue(preview.eligible)
        self.assertIn("order-1", preview.content)
        self.assertIn("测试买家", preview.content)

        record = await self.store.prepare_order_delivery(
            orders[0].order_pk,
            OrderDeliveryPreviewRequest(template_id=template.template_id),
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.receiver_user_id, "buyer-1")
        self.assertEqual(record.order_id, "order-1")
        self.assertEqual(record.order_pk, orders[0].order_pk)

        duplicate = await self.store.preview_order_delivery(
            orders[0].order_pk,
            OrderDeliveryPreviewRequest(template_id=template.template_id),
        )
        assert duplicate is not None
        self.assertFalse(duplicate.eligible)
        self.assertTrue(any("已有" in reason for reason in duplicate.reasons))

        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="system",
            content="卖家已发货",
            message_id="message-2",
            peer_user_id="buyer-1",
            item_id="item-1",
            raw_payload={},
            created_at_ms=1_700_000_001_000,
        )
        updated = await self.store.get_order(orders[0].order_pk)
        assert updated is not None
        self.assertEqual(updated.status, "paid_waiting_delivery")
        self.assertEqual(len(updated.events), 2)

        live = await self.store.apply_order_headinfo(
            orders[0].order_pk,
            {
                "commonData": {"data": {"orderId": "order-1", "itemId": "item-1"}},
                "left": {"data": {"picUrl": "https://example.test/live.jpg"}},
                "middle": {"data": {"title": "测试商品", "price": "12.50"}},
                "right": {"data": {"btnList": [{"action": "RATE"}]}},
            },
        )
        assert live is not None
        self.assertEqual(live.status, "paid_waiting_delivery")
        self.assertEqual(live.title, "测试商品")
        self.assertIsNotNone(live.last_synced_at)

    async def test_product_context_and_cards_are_persisted_idempotently(self) -> None:
        payload = product_card_payload()
        first = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-product",
            direction="inbound",
            message_type="card",
            content="分享商品",
            message_id="product-message-1",
            peer_user_id="buyer-1",
            raw_payload=payload,
            created_at_ms=1_700_000_002_000,
        )
        duplicate = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-product",
            direction="inbound",
            message_type="card",
            content="分享商品",
            message_id="product-message-1",
            peer_user_id="buyer-1",
            raw_payload=payload,
            created_at_ms=1_700_000_002_000,
        )

        self.assertIsNotNone(first)
        self.assertIsNone(duplicate)
        conversation = await self.store.get_conversation(
            self.account.account_id,
            "conversation-product",
        )
        assert conversation is not None
        self.assertEqual(conversation.item_id, "item-card-1")
        self.assertEqual(conversation.item_title, "卡片商品")
        messages = await self.store.list_messages(
            self.account.account_id,
            "conversation-product",
        )
        self.assertEqual(len(messages), 1)
        self.assertEqual(len(messages[0].cards), 1)
        self.assertEqual(messages[0].cards[0].item_id, "item-card-1")
        await self.store.backfill_message_contexts()
        second_backfill = await self.store.backfill_message_contexts()
        cards = await self.store.list_message_cards(
            self.account.account_id,
            "conversation-product",
        )
        self.assertEqual(len(cards), 1)
        self.assertEqual(second_backfill, 0)


if __name__ == "__main__":
    unittest.main()
