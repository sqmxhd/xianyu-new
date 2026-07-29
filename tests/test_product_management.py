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
from apps.api.xianyu_admin_api.orm import (
    ProductItemORM,
    ProductOperationItemORM,
    ProductPublishTaskORM,
)
from apps.api.xianyu_admin_api.product_management_service import (
    ProductLocalCleanupConflict,
    ProductManagementRepository,
)
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    AccountWorkspaceVisibilityUpdatePayload,
)
from apps.api.xianyu_admin_api.store import AccountStore
from integrations.xianyu_core import (
    AccountConfig,
    ManagedProduct,
    MtopProductOperations,
    ProductOperationError,
    ProxyConfig,
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


def success(data):
    return FakeResponse({"ret": ["SUCCESS::调用成功"], "data": data})


def product_card(item_id, title, *, want_text=None):
    card_data = {
        "id": item_id,
        "title": title,
        "categoryId": "100",
        "priceInfo": {"preText": "¥", "price": "19.90"},
        "picInfo": {"picUrl": "//img.alicdn.com/item.jpg"},
        "itemStatus": "0",
    }
    if want_text is not None:
        card_data["itemLabelDataVO"] = {
            "labelData": {
                "r3": {
                    "tagList": [
                        {"data": {"labelId": "9", "content": want_text}}
                    ]
                }
            }
        }
    return {
        "cardData": {
            **card_data,
        }
    }


class ProductOperationAdapterTests(unittest.TestCase):
    def make_client(self, session, sleeps=None):
        return MtopProductOperations(
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
            sleep_handler=(sleeps.append if sleeps is not None else lambda _value: None),
        )

    def test_catalog_pagination_parsing_and_bound_proxy(self):
        session = FakeSession(
            [
                success({"cardList": [product_card("1", "商品一"), product_card("2", "商品二")]}),
                success({"cardList": [product_card("3", "商品三")]}),
            ]
        )
        sleeps = []
        client = self.make_client(session, sleeps)

        result = client.list_selling_items(page_size=2, page_delay=(0, 0))

        self.assertTrue(result.complete)
        self.assertEqual(result.pages, 2)
        self.assertEqual([item.item_id for item in result.items], ["1", "2", "3"])
        self.assertEqual(result.items[0].cover_url, "https://img.alicdn.com/item.jpg")
        self.assertEqual(sleeps, [0])
        self.assertEqual(
            session.proxies,
            {
                "http": "socks5h://127.0.0.1:1080",
                "https": "socks5h://127.0.0.1:1080",
            },
        )
        pages = [json.loads(call[1]["data"]["data"])["pageNumber"] for call in session.calls]
        self.assertEqual(pages, [1, 2])

    def test_catalog_parses_optional_want_label(self):
        session = FakeSession(
            [success({"cardList": [product_card("1", "商品一", want_text="1.2万+人想要")]})]
        )
        client = self.make_client(session)

        result = client.list_selling_items(page_size=20)

        self.assertEqual(result.items[0].want_count, 12_000)
        self.assertEqual(result.items[0].want_text, "1.2万+人想要")

    def test_offline_uses_seller_endpoint_and_reports_each_item(self):
        session = FakeSession(
            [
                success(
                    {
                        "code": "success",
                        "data": {
                            "itemProcessResultList": [
                                {"itemId": "1", "success": True},
                                {"itemId": "2", "success": False},
                            ]
                        },
                    }
                )
            ]
        )
        client = self.make_client(session)

        result = client.offline_items(["1", "2"])

        self.assertEqual([item.success for item in result.items], [True, False])
        url, kwargs = session.calls[0]
        self.assertIn("mtop.alibaba.idle.seller.pc.item.batch.offline", url)
        self.assertEqual(json.loads(kwargs["data"]["data"]), {"itemIds": "1,2"})
        self.assertEqual(kwargs["headers"]["idle_site_biz_code"], "COMMONPRO")

    def test_seller_offline_requires_an_explicit_item_result(self):
        session = FakeSession([success({"code": "success", "data": {"sucCount": 1}})])
        client = self.make_client(session)

        result = client.offline_items(["1"])

        self.assertFalse(result.items[0].success)
        self.assertIn("未返回", result.items[0].message)

    def test_personal_offline_sends_only_the_item_page_write_request(self):
        session = FakeSession([success({})])
        client = self.make_client(session)

        result = client.offline_personal_item("1")

        self.assertTrue(result.success)
        self.assertFalse(result.verified)
        self.assertEqual(result.channel, "personal_web")
        self.assertEqual(len(session.calls), 1)
        action_url, action_kwargs = session.calls[0]
        self.assertIn("mtop.taobao.idle.item.downshelf/2.0", action_url)
        self.assertEqual(json.loads(action_kwargs["data"]["data"]), {"itemId": "1"})
        self.assertEqual(
            action_kwargs["headers"]["Referer"],
            "https://www.goofish.com/item?id=1",
        )

    def test_personal_delete_sends_only_the_item_page_write_request(self):
        session = FakeSession([success({})])
        client = self.make_client(session)

        result = client.delete_personal_item("1")

        self.assertTrue(result.success)
        self.assertFalse(result.verified)
        self.assertEqual(len(session.calls), 1)
        self.assertIn("com.taobao.idle.item.delete/1.1", session.calls[0][0])
        self.assertEqual(json.loads(session.calls[0][1]["data"]["data"]), {"itemId": "1"})

    def test_personal_delete_not_found_is_an_idempotent_success(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "ret": ["FAIL_BIZ_ITEM_DEL_NOT_FOUND::宝贝不存在"],
                        "data": {},
                    }
                )
            ]
        )
        client = self.make_client(session)

        result = client.delete_personal_item("1")

        self.assertTrue(result.success)
        self.assertTrue(result.skipped)
        self.assertTrue(result.verified)
        self.assertEqual(len(session.calls), 1)

    def test_personal_action_risk_control_requires_verification(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "ret": [
                            "FAIL_SYS_USER_VALIDATE",
                            "RGV587_ERROR::需要安全验证",
                        ],
                        "data": {"url": "https://example.invalid/verify"},
                    }
                )
            ]
        )
        client = self.make_client(session)

        with self.assertRaises(ProductOperationError) as raised:
            client.offline_personal_item("1")

        self.assertEqual(raised.exception.kind, "risk_control")
        self.assertTrue(raised.exception.verification_required)
        self.assertFalse(raised.exception.uncertain)
        self.assertEqual(len(session.calls), 1)

    def test_personal_action_network_failure_is_uncertain_and_not_retried(self):
        session = FakeSession([requests.ConnectionError("connection lost")])
        client = self.make_client(session)

        with self.assertRaises(ProductOperationError) as raised:
            client.offline_personal_item("1")

        self.assertEqual(raised.exception.kind, "result_unknown")
        self.assertTrue(raised.exception.uncertain)
        self.assertEqual(len(session.calls), 1)

    def test_delete_network_failure_is_uncertain_and_not_retried(self):
        session = FakeSession([requests.ConnectionError("connection lost")])
        client = self.make_client(session)

        with self.assertRaises(ProductOperationError) as raised:
            client.delete_item("1")

        self.assertTrue(raised.exception.uncertain)
        self.assertEqual(raised.exception.kind, "result_unknown")
        self.assertEqual(len(session.calls), 1)

    def test_already_polished_is_a_successful_skip(self):
        session = FakeSession(
            [FakeResponse({"ret": ["FAIL_SYS::一天只能擦亮一次"], "data": {}})]
        )
        client = self.make_client(session)

        result = client.polish_item("1")

        self.assertTrue(result.success)
        self.assertTrue(result.skipped)


class ProductManagementRepositoryTests(unittest.TestCase):
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
        self.repository = ProductManagementRepository(self.sessions)
        self.account = asyncio.run(
            self.store.create_account(
                AccountCreatePayload(cookie="unb=10001; _m_h5_tk=token_1",
                    enabled=True,
                )
            )
        )

    def tearDown(self):
        self.engine.dispose()

    def test_hidden_account_is_excluded_only_from_product_management_summary(self):
        before = asyncio.run(self.repository.list_account_summaries())
        self.assertEqual(len(before), 1)

        updated = asyncio.run(
            self.store.update_account_workspace_visibility(
                self.account.account_id,
                AccountWorkspaceVisibilityUpdatePayload(product_management_visible=False),
            )
        )
        self.assertIsNotNone(updated)
        summaries = asyncio.run(self.repository.list_account_summaries())
        self.assertEqual(summaries, [])

    def test_full_sync_requires_two_misses_before_not_selling(self):
        product_a = ManagedProduct(item_id="1", title="商品一", price="¥19.90")
        product_b = ManagedProduct(item_id="2", title="商品二", price="¥29.90")

        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id, (product_a, product_b), full=True, complete=True
            )
        )
        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id, (product_a,), full=True, complete=True
            )
        )
        first_missing = asyncio.run(
            self.repository.list_items(self.account.account_id, keyword="商品二")
        )[0]
        self.assertEqual(first_missing.platform_status, "selling")
        self.assertEqual(first_missing.sync_state, "pending_confirmation")

        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id, (product_a,), full=True, complete=True
            )
        )
        confirmed_missing = asyncio.run(
            self.repository.list_items(self.account.account_id, keyword="商品二")
        )[0]
        self.assertEqual(confirmed_missing.platform_status, "not_selling")
        self.assertEqual(confirmed_missing.missing_sync_count, 2)

    def test_full_sync_reconciles_pending_action_status_without_item_detail(self):
        product = ManagedProduct(item_id="1", title="商品一", price="¥19.90")
        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id, (product,), full=True, complete=True
            )
        )
        asyncio.run(
            self.repository.mark_item_status(
                self.account.account_id,
                "1",
                "offline",
                pending_confirmation=True,
            )
        )

        pending = asyncio.run(self.repository.list_items(self.account.account_id))[0]
        self.assertEqual(pending.platform_status, "offline")
        self.assertEqual(pending.sync_state, "pending_confirmation")

        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id, (), full=True, complete=True
            )
        )
        confirmed = asyncio.run(self.repository.list_items(self.account.account_id))[0]
        self.assertEqual(confirmed.platform_status, "offline")
        self.assertEqual(confirmed.sync_state, "current")

        asyncio.run(
            self.repository.mark_item_status(
                self.account.account_id,
                "1",
                "offline",
                pending_confirmation=True,
            )
        )
        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id, (product,), full=True, complete=True
            )
        )
        reverted = asyncio.run(self.repository.list_items(self.account.account_id))[0]
        self.assertEqual(reverted.platform_status, "selling")
        self.assertEqual(reverted.sync_state, "current")

    def test_sync_persists_and_clears_want_metric(self):
        product = ManagedProduct(item_id="1", want_count=24, want_text="24人想要")
        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id, (product,), full=False, complete=True
            )
        )

        synced = asyncio.run(self.repository.list_items(self.account.account_id))[0]
        self.assertEqual(synced.want_count, 24)
        self.assertEqual(synced.want_text, "24人想要")

        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id,
                (ManagedProduct(item_id="1"),),
                full=False,
                complete=True,
            )
        )
        refreshed = asyncio.run(self.repository.list_items(self.account.account_id))[0]
        self.assertIsNone(refreshed.want_count)
        self.assertIsNone(refreshed.want_text)

    def test_sync_confirms_publish_task_when_platform_item_appears(self):
        published_at = datetime(2026, 7, 18, 10, 30, tzinfo=UTC)
        with self.sessions() as session:
            session.add(
                ProductPublishTaskORM(
                    task_id="publish-task-1",
                    account_id=self.account.account_id,
                    draft_id="",
                    mode="platform_api",
                    status="verification_required",
                    phase="verification_required",
                    item_id="published-item-1",
                    result_certainty="published_unconfirmed",
                    finished_at=published_at,
                )
            )
            session.commit()

        asyncio.run(
            self.repository.apply_sync(
                self.account.account_id,
                (ManagedProduct(item_id="published-item-1", title="新商品", price="¥19.90"),),
                full=False,
                complete=True,
            )
        )

        with self.sessions() as session:
            task = session.get(ProductPublishTaskORM, "publish-task-1")
            self.assertIsNotNone(task)
            self.assertEqual(task.status, "success")
            self.assertEqual(task.phase, "completed")
            self.assertEqual(task.result_certainty, "confirmed_success")
            self.assertFalse(task.retryable)
            item = session.get(
                ProductItemORM,
                {"account_id": self.account.account_id, "item_id": "published-item-1"},
            )
            assert item is not None
            self.assertEqual(item.published_at, published_at)
            self.assertEqual(item.published_at_source, "publish_task")

    def test_local_cleanup_requires_confirmed_deleted_state(self):
        with self.sessions() as session:
            session.add_all(
                [
                    ProductItemORM(
                        account_id=self.account.account_id,
                        item_id="selling-item",
                        title="在售商品",
                        platform_status="selling",
                        sync_state="current",
                    ),
                    ProductItemORM(
                        account_id=self.account.account_id,
                        item_id="pending-delete-item",
                        title="待核检商品",
                        platform_status="deleted",
                        sync_state="pending_confirmation",
                    ),
                ]
            )
            session.commit()

        with self.assertRaisesRegex(ProductLocalCleanupConflict, "仅已从闲鱼平台删除"):
            asyncio.run(
                self.repository.delete_local_item(self.account.account_id, "selling-item")
            )
        with self.assertRaisesRegex(ProductLocalCleanupConflict, "尚未核检"):
            asyncio.run(
                self.repository.delete_local_item(
                    self.account.account_id, "pending-delete-item"
                )
            )

        self.assertEqual(
            len(asyncio.run(self.repository.list_items(self.account.account_id))),
            2,
        )

    def test_local_cleanup_removes_snapshot_and_hides_publish_task_but_keeps_history(self):
        with self.sessions() as session:
            session.add(
                ProductItemORM(
                    account_id=self.account.account_id,
                    item_id="deleted-item",
                    title="已删除商品",
                    platform_status="deleted",
                    sync_state="current",
                )
            )
            session.add(
                ProductPublishTaskORM(
                    task_id="publish-task-deleted",
                    account_id=self.account.account_id,
                    draft_id="",
                    mode="platform_api",
                    status="success",
                    phase="completed",
                    item_id="deleted-item",
                )
            )
            session.commit()

        run = asyncio.run(
            self.repository.create_run(
                self.account.account_id,
                "delete",
                "manual",
                item_ids=["deleted-item"],
            )
        )
        asyncio.run(
            self.repository.add_run_item(
                run.run_id,
                "deleted-item",
                "success",
                "平台已删除",
                "personal_web:SUCCESS",
            )
        )

        result = asyncio.run(
            self.repository.delete_local_item(self.account.account_id, "deleted-item")
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.deleted)
        self.assertEqual(result.hidden_publish_task_count, 1)
        self.assertEqual(asyncio.run(self.repository.list_items(self.account.account_id)), [])
        self.assertEqual(asyncio.run(self.store.list_product_publish_tasks(self.account.account_id)), [])
        with self.sessions() as session:
            self.assertIsNone(
                session.get(
                    ProductItemORM,
                    {"account_id": self.account.account_id, "item_id": "deleted-item"},
                )
            )
            publish_task = session.get(ProductPublishTaskORM, "publish-task-deleted")
            self.assertIsNotNone(publish_task)
            self.assertIsNotNone(publish_task.catalog_hidden_at)
            operation_items = session.query(ProductOperationItemORM).filter_by(
                run_id=run.run_id,
                item_id="deleted-item",
            ).all()
            self.assertEqual(len(operation_items), 1)

    def test_items_sort_by_published_time_descending_with_unknown_last(self):
        with self.sessions() as session:
            session.add_all(
                [
                    ProductItemORM(
                        account_id=self.account.account_id,
                        item_id="newer",
                        title="较晚发布",
                        published_at=datetime(2026, 7, 18, 12, 0, tzinfo=UTC),
                        published_at_source="publish_task",
                    ),
                    ProductItemORM(
                        account_id=self.account.account_id,
                        item_id="unknown",
                        title="发布时间未知",
                    ),
                    ProductItemORM(
                        account_id=self.account.account_id,
                        item_id="older",
                        title="较早发布",
                        published_at=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
                        published_at_source="publish_task",
                    ),
                ]
            )
            session.commit()

        items = asyncio.run(self.repository.list_items(self.account.account_id))
        self.assertEqual([item.item_id for item in items], ["newer", "older", "unknown"])

    def test_manual_requests_dedupe_only_when_targets_match(self):
        first = asyncio.run(
            self.repository.create_run(
                self.account.account_id, "polish", "manual", item_ids=["1"]
            )
        )
        second = asyncio.run(
            self.repository.create_run(
                self.account.account_id, "polish", "manual", item_ids=["2"]
            )
        )
        duplicate = asyncio.run(
            self.repository.create_run(
                self.account.account_id, "polish", "manual", item_ids=["2"]
            )
        )

        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(second.run_id, duplicate.run_id)

    def test_publish_verification_gets_a_fresh_sync_run(self):
        scheduled = asyncio.run(
            self.repository.create_run(
                self.account.account_id, "sync", "scheduled", full_sync=False
            )
        )
        publish_verification = asyncio.run(
            self.repository.create_run(
                self.account.account_id, "sync", "publish", full_sync=False
            )
        )

        self.assertNotEqual(scheduled.run_id, publish_verification.run_id)

    def test_polish_completion_updates_schedule_state(self):
        asyncio.run(self.repository.ensure_account_settings([self.account.account_id]))
        when = datetime.now(UTC)

        asyncio.run(self.repository.complete_polish(self.account.account_id, when))

        setting = asyncio.run(self.repository.get_setting(self.account.account_id))
        self.assertIsNotNone(setting)
        self.assertIsNotNone(setting.last_polish_at)


if __name__ == "__main__":
    unittest.main()
