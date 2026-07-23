import asyncio
import os
import unittest

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.orm import ConversationORM, ProductItemORM
from apps.api.xianyu_admin_api.runtime import AccountRuntimeManager
from apps.api.xianyu_admin_api.schemas import AccountCreatePayload
from apps.api.xianyu_admin_api.store import AccountStore
from integrations.xianyu_core.models import ConversationPage, ConversationSummary


class ConversationBatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.factory = factory
        self.store = AccountStore(session_factory=factory, initialize=False)
        self.account = await self.store.create_account(
            AccountCreatePayload(account_name="batch-account", enabled=False)
        )

    async def asyncTearDown(self) -> None:
        self.engine.dispose()

    async def test_batch_only_reports_changed_conversations(self) -> None:
        row = {
            "conversation_id": "conversation-1",
            "peer_user_id": "buyer-1",
            "peer_name": "buyer",
            "last_message_content": "hello",
            "last_message_type": "text",
            "last_message_direction": "inbound",
            "last_message_at_ms": 1_700_000_000_000,
            "unread_count": 1,
        }

        first, first_changed = await self.store.upsert_conversations(
            self.account.account_id, [row]
        )
        second, second_changed = await self.store.upsert_conversations(
            self.account.account_id, [row]
        )
        updated, updated_changed = await self.store.upsert_conversations(
            self.account.account_id, [{**row, "peer_name": "new buyer"}]
        )

        self.assertEqual(len(first), 1)
        self.assertEqual(len(first_changed), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(second_changed, [])
        self.assertEqual(updated[0].peer_name, "new buyer")
        self.assertEqual(len(updated_changed), 1)

    async def test_item_url_falls_back_for_cached_rows_and_headinfo_deep_links(self) -> None:
        item_id = "1055756055551"
        expected_url = f"https://h5.m.goofish.com/item?id={item_id}"
        rows, _ = await self.store.upsert_conversations(
            self.account.account_id,
            [
                {
                    "conversation_id": "conversation-item-link",
                    "peer_user_id": "buyer-1",
                    "item_id": item_id,
                    "last_message_content": "咨询商品",
                    "last_message_type": "text",
                    "last_message_direction": "inbound",
                    "last_message_at_ms": 1_700_000_000_000,
                    "unread_count": 0,
                }
            ],
        )
        self.assertEqual(rows[0].item_url, expected_url)

        with self.factory() as session:
            conversation = session.query(ConversationORM).filter_by(
                account_id=self.account.account_id,
                conversation_id="conversation-item-link",
            ).one()
            conversation.item_url = None
            session.commit()

        cached = await self.store.get_conversation(
            self.account.account_id,
            "conversation-item-link",
        )
        assert cached is not None
        self.assertEqual(cached.item_url, expected_url)

        updated = await self.store.apply_conversation_headinfo(
            self.account.account_id,
            "conversation-item-link",
            {
                "commonData": {"data": {"itemId": item_id}},
                "left": {
                    "data": {
                        "jumpUrl": f"fleamarket://item?id={item_id}&fmdirect=true"
                    }
                },
                "middle": {"data": {}},
            },
        )
        assert updated is not None
        self.assertEqual(updated.item_url, expected_url)

    async def test_notice_title_does_not_replace_valid_peer_name(self) -> None:
        row = {
            "conversation_id": "conversation-1",
            "peer_user_id": "buyer-1",
            "peer_name": "共享AI",
            "last_message_content": "hello",
            "last_message_type": "text",
            "last_message_direction": "inbound",
            "last_message_at_ms": 1_700_000_000_000,
            "unread_count": 1,
        }
        await self.store.upsert_conversations(self.account.account_id, [row])

        updated, changed = await self.store.upsert_conversations(
            self.account.account_id,
            [{**row, "peer_name": "你有一条新消息"}],
        )

        self.assertEqual(updated[0].peer_name, "共享AI")
        self.assertEqual(changed, [])

    async def test_authoritative_message_time_can_correct_future_summary(self) -> None:
        row = {
            "conversation_id": "conversation-future",
            "peer_user_id": "buyer-1",
            "peer_name": "buyer",
            "last_message_content": "same message",
            "last_message_type": "text",
            "last_message_direction": "inbound",
            "last_message_at_ms": 1_800_000_000_000,
            "unread_count": 0,
        }
        await self.store.upsert_conversations(self.account.account_id, [row])
        corrected, changed = await self.store.upsert_conversations(
            self.account.account_id,
            [{**row, "last_message_at_ms": 1_600_000_000_000}],
        )

        self.assertEqual(len(changed), 1)
        self.assertEqual(corrected[0].last_message_at.timestamp(), 1_600_000_000)
        self.assertEqual(corrected[0].last_activity_at.timestamp(), 1_600_000_000)
        assert corrected[0].last_inbound_at is not None
        self.assertEqual(corrected[0].last_inbound_at.timestamp(), 1_600_000_000)

    async def test_first_platform_timestamp_replaces_ingestion_activity(self) -> None:
        base = {
            "conversation_id": "conversation-late-timestamp",
            "peer_user_id": "buyer-1",
            "peer_name": "buyer",
            "last_message_content": "hello",
            "last_message_type": "text",
            "last_message_direction": "inbound",
            "unread_count": 0,
        }
        await self.store.upsert_conversations(self.account.account_id, [base])
        updated, _ = await self.store.upsert_conversations(
            self.account.account_id,
            [{**base, "last_message_at_ms": 1_600_000_000_000}],
        )

        self.assertEqual(updated[0].last_message_at.timestamp(), 1_600_000_000)
        self.assertEqual(updated[0].last_activity_at.timestamp(), 1_600_000_000)

    async def test_cached_history_reconciles_incorrect_conversation_time(self) -> None:
        await self.store.upsert_conversations(
            self.account.account_id,
            [
                {
                    "conversation_id": "conversation-history",
                    "peer_user_id": "buyer-1",
                    "peer_name": "buyer",
                    "last_message_content": "same message",
                    "last_message_type": "text",
                    "last_message_direction": "inbound",
                    "last_message_at_ms": 1_800_000_000_000,
                    "unread_count": 0,
                }
            ],
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-history",
            direction="inbound",
            message_type="text",
            content="same message",
            message_id="message-history",
            created_at_ms=1_600_000_000_000,
            count_unread=False,
        )

        changed = await self.store.reconcile_conversation_summaries(
            self.account.account_id,
            "conversation-history",
        )
        conversations = await self.store.list_conversations(self.account.account_id)

        self.assertEqual(len(changed), 1)
        self.assertEqual(conversations[0].last_message_at.timestamp(), 1_600_000_000)
        self.assertEqual(conversations[0].last_activity_at.timestamp(), 1_600_000_000)
        assert conversations[0].last_inbound_at is not None
        self.assertEqual(conversations[0].last_inbound_at.timestamp(), 1_600_000_000)

    async def test_peer_profile_is_persisted_and_returned_with_conversation(self) -> None:
        await self.store.upsert_conversations(
            self.account.account_id,
            [
                {
                    "conversation_id": "conversation-profile",
                    "peer_user_id": "buyer-profile",
                    "peer_name": "旧昵称",
                    "last_message_content": "咨询",
                    "last_message_type": "text",
                    "last_message_direction": "inbound",
                    "last_message_at_ms": 1_700_000_000_000,
                }
            ],
        )

        updated = await self.store.apply_conversation_peer_profile(
            self.account.account_id,
            "conversation-profile",
            "buyer-profile",
            display_name="平台昵称",
            avatar_url="https://example.test/avatar.jpg",
        )
        listed = await self.store.list_conversations(self.account.account_id)

        assert updated is not None
        self.assertEqual(updated.peer_name, "平台昵称")
        self.assertEqual(updated.peer_avatar_url, "https://example.test/avatar.jpg")
        self.assertEqual(listed[0].peer_avatar_url, "https://example.test/avatar.jpg")

    async def test_product_cache_backfills_all_conversations_for_the_same_item(self) -> None:
        item_id = "item-cached"
        await self.store.upsert_conversations(
            self.account.account_id,
            [
                {"conversation_id": "conversation-product-a", "item_id": item_id},
                {"conversation_id": "conversation-product-b", "item_id": item_id},
            ],
        )
        with self.factory() as session:
            session.add(
                ProductItemORM(
                    account_id=self.account.account_id,
                    item_id=item_id,
                    title="缓存商品",
                    price="19.90",
                    cover_url="https://example.test/item.jpg",
                    detail_url=f"https://h5.m.goofish.com/item?id={item_id}",
                )
            )
            session.commit()

        updated = await self.store.backfill_conversation_item_from_product(
            self.account.account_id,
            "conversation-product-a",
        )
        listed = await self.store.list_conversations(self.account.account_id)

        assert updated is not None
        self.assertEqual(updated.item_image_url, "https://example.test/item.jpg")
        self.assertEqual(
            {item.item_image_url for item in listed},
            {"https://example.test/item.jpg"},
        )

    async def test_account_identity_must_match_cookie_owner(self) -> None:
        account = await self.store.create_account(
            AccountCreatePayload(
                account_name="identity-account",
                cookie="unb=seller-100; _m_h5_tk=token_1",
                enabled=False,
            )
        )

        with self.assertRaisesRegex(ValueError, "different account"):
            await self.store.update_account_platform_identity(
                account.account_id,
                platform_user_id="seller-200",
                display_name="错误用户",
                avatar_url=None,
            )

        updated = await self.store.update_account_platform_identity(
            account.account_id,
            platform_user_id="seller-100",
            display_name="平台卖家",
            avatar_url="https://example.test/seller.jpg",
        )
        assert updated is not None
        self.assertEqual(updated.platform_display_name, "平台卖家")
        self.assertEqual(updated.platform_user_id, "seller-100")


class _SyncCore:
    def __init__(self) -> None:
        self.calls = 0

    def is_account_online(self, _account_id: str) -> bool:
        return True

    def account_connection_health(self, _account_id: str):  # type: ignore[no-untyped-def]
        return {
            "running": True,
            "online": True,
            "rpc_healthy": True,
        }

    async def list_conversations(
        self, _account_id: str, *, cursor: int | None, limit: int
    ) -> ConversationPage:
        self.calls += 1
        await asyncio.sleep(0.02)
        return ConversationPage(
            items=[
                ConversationSummary(
                    account_id="account-1",
                    conversation_id="conversation-1",
                )
            ],
            has_more=False,
            next_cursor=None,
        )


class _SyncStore:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def upsert_conversations(self, _account_id: str, rows):  # type: ignore[no-untyped-def]
        self.rows.extend(rows)
        return rows, []

    async def count_conversations(self, _account_id: str) -> int:
        return len(self.rows)


class _PagedSyncCore(_SyncCore):
    def __init__(self) -> None:
        super().__init__()
        self.cursors: list[int | None] = []

    async def list_conversations(
        self, _account_id: str, *, cursor: int | None, limit: int
    ) -> ConversationPage:
        self.calls += 1
        self.cursors.append(cursor)
        page_number = len(self.cursors)
        return ConversationPage(
            items=[
                ConversationSummary(
                    account_id="account-1",
                    conversation_id=f"conversation-{page_number}",
                )
            ],
            has_more=page_number == 1,
            next_cursor=100 if page_number == 1 else None,
        )


class ConversationSingleFlightTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_refreshes_share_one_platform_request(self) -> None:
        runtime = AccountRuntimeManager(_SyncStore())  # type: ignore[arg-type]
        core = _SyncCore()
        runtime._core = core

        left, right = await asyncio.gather(
            runtime.sync_conversations("account-1", limit=100),
            runtime.sync_conversations("account-1", limit=100),
        )

        self.assertEqual(core.calls, 1)
        self.assertEqual(left, right)

    async def test_initial_warm_sync_follows_platform_cursor(self) -> None:
        store = _SyncStore()
        runtime = AccountRuntimeManager(store)  # type: ignore[arg-type]
        core = _PagedSyncCore()
        runtime._core = core

        await runtime._warm_conversations("account-1")
        status = await runtime.conversation_sync_status("account-1")

        self.assertEqual(core.cursors, [None, 100])
        self.assertEqual(len(store.rows), 2)
        self.assertEqual(status.state, "healthy")
        self.assertEqual(status.conversation_count, 2)
        self.assertIn("account-1", runtime._conversation_full_sync_completed)


if __name__ == "__main__":
    unittest.main()
