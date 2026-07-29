import asyncio
import json
import os
import unittest
from datetime import UTC, datetime

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.order_management_service import OrderManagementRepository
from apps.api.xianyu_admin_api.orm import OrderORM
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    AccountWorkspaceVisibilityUpdatePayload,
)
from apps.api.xianyu_admin_api.store import AccountStore
from integrations.xianyu_core import (
    AccountConfig,
    BuyerOrder,
    MtopBuyerOrderOperations,
    MtopOrderOperations,
    ProxyConfig,
    SellerOrder,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.cookies = requests.cookies.RequestsCookieJar()
        self.headers = {}
        self.proxies = {}
        self.trust_env = True
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self):
        return None


def sold_order(order_id, status="待发货", *, item_id="item-1"):
    return {
        "commonData": {
            "orderId": order_id,
            "itemId": item_id,
            "orderStatus": status,
            "createTime": "2026-07-15 12:30:00",
            "paySuccessTime": "2026-07-15 12:31:00",
            "inRefund": "false",
        },
        "buyerInfoVO": {
            "buyerId": "buyer-1",
            "userNick": "测试买家",
            "name": "张三",
            "phone": "13800000000",
            "address": "测试地址",
        },
        "priceVO": {"totalPrice": "19.90", "buyNum": "2"},
        "rightVO": {"btnList": []},
    }


def success_page(items, next_page, total_count):
    return FakeResponse(
        {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "module": {
                    "items": items,
                    "nextPage": "true" if next_page else "false",
                    "totalCount": str(total_count),
                }
            },
        }
    )


def bought_order(order_id, status="wait_seller_send_goods"):
    return {
        "commonData": {
            "orderId": order_id,
            "itemId": f"item-{order_id}",
            "peerUserId": "seller-1",
            "tradeStatusEnum": status,
        },
        "head": {
            "data": {
                "createTime": "2026-07-15 13:30:00",
                "statusViewMsg": "等待卖家发货",
                "userInfo": {"userId": "seller-1", "userNick": "测试卖家"},
            }
        },
        "content": {
            "data": {
                "detailInfo": {
                    "auctionTitle": "测试商品",
                    "auctionPic": "//example.test/item.jpg",
                },
                "priceInfo": {"price": "29.90", "buyAmount": "2"},
            }
        },
        "tail": {"data": {"btnList": []}},
    }


def bought_success_page(items, *, next_page, last_end_row=None, total_count=0):
    return FakeResponse(
        {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "items": items,
                "nextPage": next_page,
                "lastEndRow": last_end_row,
                "totalCount": total_count,
            },
        }
    )


class OrderOperationAdapterTests(unittest.TestCase):
    def test_buyer_orders_follow_last_end_row_cursor_and_parse_seller(self):
        session = FakeSession(
            [
                bought_success_page(
                    [bought_order("buyer-order-1")],
                    next_page=True,
                    last_end_row="cursor-1",
                ),
                bought_success_page(
                    [bought_order("buyer-order-2", "trade_success")],
                    next_page=False,
                ),
            ]
        )
        sleeps = []
        client = MtopBuyerOrderOperations(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=token_1"),
            session_factory=lambda: session,
            sign_handler=lambda *_args: "signature",
            sleep_handler=sleeps.append,
            page_delay_seconds=0.25,
        )

        result = client.list_bought_orders()
        client.close()

        self.assertTrue(result.complete)
        self.assertEqual([item.order_id for item in result.items], ["buyer-order-1", "buyer-order-2"])
        self.assertEqual(result.items[0].seller_name, "测试卖家")
        self.assertEqual(result.items[0].status, "waiting_seller_delivery")
        self.assertEqual(result.items[0].quantity, 2)
        self.assertEqual(result.items[1].status, "completed")
        payloads = [json.loads(call[1]["data"]["data"]) for call in session.calls]
        self.assertNotIn("offsetRow", payloads[0])
        self.assertEqual(payloads[1]["offsetRow"], "cursor-1")
        self.assertEqual(sleeps, [0.25])

    def test_buyer_order_sync_stops_on_repeated_cursor(self):
        session = FakeSession(
            [
                bought_success_page(
                    [bought_order("buyer-order-1")],
                    next_page=True,
                    last_end_row="cursor-1",
                ),
                bought_success_page(
                    [bought_order("buyer-order-2")],
                    next_page=True,
                    last_end_row="cursor-1",
                ),
            ]
        )
        client = MtopBuyerOrderOperations(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=token_1"),
            session_factory=lambda: session,
            sign_handler=lambda *_args: "signature",
            sleep_handler=lambda _value: None,
        )

        result = client.list_bought_orders()
        client.close()

        self.assertFalse(result.complete)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(len(session.calls), 2)

    def test_seller_orders_use_bound_proxy_and_parse_all_pages(self):
        session = FakeSession(
            [
                success_page([sold_order("order-1")], True, 2),
                success_page([sold_order("order-2", "交易成功")], False, 2),
            ]
        )
        sleeps = []
        client = MtopOrderOperations(
            AccountConfig(
                account_id="account-1",
                cookie="unb=10001; _m_h5_tk=token_1",
                proxy=ProxyConfig(
                    enabled=True,
                    required=True,
                    scheme="socks5h",
                    host="127.0.0.1",
                    port=1080,
                ),
            ),
            session_factory=lambda: session,
            sign_handler=lambda *_args: "signature",
            sleep_handler=sleeps.append,
            page_delay_seconds=0.25,
        )

        result = client.list_sold_orders()
        client.close()

        self.assertTrue(result.complete)
        self.assertEqual(result.total_count, 2)
        self.assertEqual([item.order_id for item in result.items], ["order-1", "order-2"])
        self.assertEqual(result.items[0].status, "paid_waiting_delivery")
        self.assertEqual(result.items[0].buyer_name, "测试买家")
        self.assertEqual(result.items[0].quantity, 2)
        self.assertEqual(result.items[1].status, "completed")
        self.assertEqual(sleeps, [0.25])
        self.assertEqual(
            session.proxies,
            {
                "http": "socks5h://127.0.0.1:1080",
                "https": "socks5h://127.0.0.1:1080",
            },
        )
        payloads = [json.loads(call[1]["data"]["data"]) for call in session.calls]
        self.assertEqual([payload["pageNumber"] for payload in payloads], [1, 2])
        self.assertTrue(all(payload["queryCode"] == "ALL" for payload in payloads))
        self.assertEqual(session.calls[0][1]["headers"]["idle_site_biz_code"], "COMMONPRO")

    def test_pending_sync_stops_after_one_page(self):
        session = FakeSession([success_page([sold_order("order-1")], True, 20)])
        client = MtopOrderOperations(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=token_1"),
            session_factory=lambda: session,
            sign_handler=lambda *_args: "signature",
            sleep_handler=lambda _value: None,
        )

        result = client.list_sold_orders(query_code="NOT_SHIP", max_pages=1)
        client.close()

        self.assertFalse(result.complete)
        payload = json.loads(session.calls[0][1]["data"]["data"])
        self.assertEqual(payload["queryCode"], "NOT_SHIP")
        self.assertEqual(len(session.calls), 1)

    def test_transient_ssl_failure_retries_on_the_same_route(self):
        session = FakeSession(
            [requests.exceptions.SSLError("temporary eof"), success_page([], False, 0)]
        )
        sleeps = []
        client = MtopOrderOperations(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=token_1"),
            session_factory=lambda: session,
            sign_handler=lambda *_args: "signature",
            sleep_handler=sleeps.append,
        )

        result = client.list_sold_orders()
        client.close()

        self.assertTrue(result.complete)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(sleeps, [0.5])


class OrderManagementRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
        self.store = AccountStore(self.sessions, initialize=False)
        self.repository = OrderManagementRepository(self.sessions)
        self.account = asyncio.run(
            self.store.create_account(
                AccountCreatePayload(cookie="unb=10001; _m_h5_tk=token_1",
                    enabled=True,
                )
            )
        )

    def tearDown(self):
        self.engine.dispose()

    def test_hidden_account_is_excluded_only_from_order_management_views(self):
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.add(
                OrderORM(
                    order_pk="visibility-order",
                    account_id=self.account.account_id,
                    platform_order_id="visibility-order-1",
                    trade_role="seller",
                    data_source="seller_sold",
                    conversation_id="visibility-conversation",
                    status="waiting_seller_delivery",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

        visible_before = asyncio.run(
            self.store.list_orders(management_visible_only=True)
        )
        self.assertEqual(len(visible_before), 1)
        asyncio.run(
            self.store.update_account_workspace_visibility(
                self.account.account_id,
                AccountWorkspaceVisibilityUpdatePayload(order_management_visible=False),
            )
        )

        summaries = asyncio.run(self.repository.list_account_summaries())
        visible_after = asyncio.run(
            self.store.list_orders(management_visible_only=True)
        )
        unfiltered = asyncio.run(self.store.list_orders())
        self.assertEqual(summaries, [])
        self.assertEqual(visible_after, [])
        self.assertEqual(len(unfiltered), 1)

    def test_only_confirmed_seller_orders_are_counted_and_listed(self):
        with self.sessions() as session:
            now = datetime.now(UTC)
            session.add(
                OrderORM(
                    order_pk="buyer-order",
                    account_id=self.account.account_id,
                    platform_order_id="buyer-1",
                    trade_role="buyer",
                    data_source="message",
                    conversation_id="conversation-1",
                    status="paid_waiting_delivery",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

        inserted, updated, skipped = asyncio.run(
            self.repository.apply_orders(
                self.account.account_id,
                (
                    SellerOrder(
                        order_id="seller-1",
                        item_id="item-1",
                        buyer_id="buyer-2",
                        buyer_name="平台买家",
                        price="39.80",
                        quantity=2,
                        status="paid_waiting_delivery",
                        status_text="待发货",
                        platform_status="待发货",
                        platform_created_at=datetime(2026, 7, 15, 4, 30, tzinfo=UTC),
                    ),
                ),
                mode="full",
            )
        )

        self.assertEqual((inserted, updated, skipped), (1, 0, 0))
        summary = asyncio.run(self.repository.list_account_summaries())[0]
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.pending_count, 1)
        listed = asyncio.run(
            self.store.list_orders(
                account_id=self.account.account_id,
                trade_role="seller",
                data_source="seller_sold",
            )
        )
        self.assertEqual([order.platform_order_id for order in listed], ["seller-1"])
        self.assertEqual(listed[0].buyer_name, "平台买家")
        self.assertEqual(listed[0].quantity, 2)

    def test_non_retryable_failure_pauses_automatic_sync(self):
        asyncio.run(self.repository.ensure_account_settings([self.account.account_id]))

        asyncio.run(
            self.repository.fail_sync(
                self.account.account_id,
                "账号暂无卖家中心订单列表权限",
                pause=True,
            )
        )

        setting = asyncio.run(self.repository.get_setting(self.account.account_id))
        assert setting is not None
        self.assertFalse(setting.sync_enabled)
        self.assertEqual(setting.last_sync_status, "failed")

    def test_bought_sync_reconciles_message_order_and_keeps_sold_state_isolated(self):
        with self.sessions() as session:
            now = datetime.now(UTC)
            session.add(
                OrderORM(
                    order_pk="message-order",
                    account_id=self.account.account_id,
                    platform_order_id="bought-1",
                    trade_role="unknown",
                    data_source="message",
                    conversation_id="conversation-1",
                    peer_name="旧会话名称",
                    status="unknown",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

        counts = asyncio.run(
            self.repository.apply_buyer_orders(
                self.account.account_id,
                (
                    BuyerOrder(
                        order_id="bought-1",
                        item_id="item-1",
                        title="买入商品",
                        seller_id="seller-1",
                        seller_name="平台卖家",
                        price="18.00",
                        status="waiting_seller_delivery",
                        status_text="待卖家发货",
                    ),
                ),
                mode="full",
            )
        )

        self.assertEqual(counts, (0, 1, 0))
        bought_summary = asyncio.run(
            self.repository.list_account_summaries("bought")
        )[0]
        sold_summary = asyncio.run(self.repository.list_account_summaries("sold"))[0]
        self.assertEqual(bought_summary.total_count, 1)
        self.assertEqual(bought_summary.pending_count, 1)
        self.assertEqual(sold_summary.total_count, 0)
        with self.sessions() as session:
            row = session.get(OrderORM, "message-order")
            assert row is not None
            self.assertEqual(row.conversation_id, "conversation-1")
            self.assertEqual(row.trade_role, "buyer")
            self.assertEqual(row.data_source, "buyer_bought")
            self.assertEqual(row.peer_name, "平台卖家")


if __name__ == "__main__":
    unittest.main()
