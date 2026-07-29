import os
import time
import unittest

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    AccountUpdatePayload,
    AccountWorkspaceVisibilityUpdatePayload,
    UserCreatePayload,
)
from apps.api.xianyu_admin_api.store import AccountStore


class AggregateConversationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.store = AccountStore(session_factory=factory, initialize=False)
        self.user = await self.store.create_user(
            UserCreatePayload(username="operator-one", password="12345678")
        )
        self.other_user = await self.store.create_user(
            UserCreatePayload(username="operator-two", password="12345678")
        )
        self.first_account = await self.store.create_account(
            AccountCreatePayload(enabled=True)
        )
        self.second_account = await self.store.create_account(
            AccountCreatePayload(enabled=True)
        )
        self.first_account = await self.store.update_account_platform_identity(
            self.first_account.account_id,
            platform_user_id="seller-first",
            display_name="first-account",
            avatar_url=None,
        )
        self.second_account = await self.store.update_account_platform_identity(
            self.second_account.account_id,
            platform_user_id="seller-second",
            display_name="second-account",
            avatar_url=None,
        )
        assert self.first_account is not None
        assert self.second_account is not None

    async def asyncTearDown(self) -> None:
        self.engine.dispose()

    async def test_aggregate_keeps_same_conversation_id_separate_by_account(self) -> None:
        for account in (self.first_account, self.second_account):
            await self.store.record_message(
                account_id=account.account_id,
                conversation_id="shared-conversation-id",
                direction="inbound",
                message_type="text",
                content=f"message from {account.display_name}",
            )

        items, has_more, next_cursor = await self.store.list_conversations_for_user(
            self.user.user_id,
            limit=100,
        )

        self.assertFalse(has_more)
        self.assertIsNone(next_cursor)
        self.assertEqual(len(items), 2)
        self.assertEqual(len({item.conversation_key for item in items}), 2)
        self.assertEqual({item.account_name for item in items}, {"first-account", "second-account"})
        self.assertTrue(all(item.platform == "xianyu" for item in items))

    async def test_read_state_is_per_user_and_does_not_clear_needs_reply(self) -> None:
        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="still available?",
        )

        marked = await self.store.mark_conversation_read(
            self.user.user_id,
            self.first_account.account_id,
            "conversation-1",
        )
        current_items, _, _ = await self.store.list_conversations_for_user(
            self.user.user_id,
            status="unread",
        )
        other_items, _, _ = await self.store.list_conversations_for_user(
            self.other_user.user_id,
            status="unread",
        )

        self.assertIsNotNone(marked)
        self.assertEqual(marked.viewer_unread_count, 0)
        self.assertTrue(marked.needs_reply)
        self.assertEqual(current_items, [])
        self.assertEqual(len(other_items), 1)

    async def test_disabled_account_is_hidden_without_deleting_cached_history(self) -> None:
        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-hidden-while-disabled",
            direction="inbound",
            message_type="text",
            content="cached history",
        )

        await self.store.update_account(
            self.first_account.account_id,
            AccountUpdatePayload(enabled=False),
        )
        hidden, _, _ = await self.store.list_conversations_for_user(self.user.user_id)
        self.assertEqual(hidden, [])

        await self.store.update_account(
            self.first_account.account_id,
            AccountUpdatePayload(enabled=True),
        )
        restored, _, _ = await self.store.list_conversations_for_user(self.user.user_id)
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].conversation_id, "conversation-hidden-while-disabled")

    async def test_workspace_visibility_hides_conversation_without_disabling_account(self) -> None:
        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-hidden-from-workspace",
            direction="inbound",
            message_type="text",
            content="keep this cached",
        )
        self.assertTrue(self.first_account.conversation_visible)
        self.assertTrue(self.first_account.order_management_visible)
        self.assertTrue(self.first_account.product_management_visible)

        hidden_account = await self.store.update_account_workspace_visibility(
            self.first_account.account_id,
            AccountWorkspaceVisibilityUpdatePayload(conversation_visible=False),
        )
        assert hidden_account is not None
        self.assertTrue(hidden_account.enabled)
        self.assertFalse(hidden_account.conversation_visible)
        hidden, _, _ = await self.store.list_conversations_for_user(self.user.user_id)
        self.assertEqual(hidden, [])

        restored_account = await self.store.update_account_workspace_visibility(
            self.first_account.account_id,
            AccountWorkspaceVisibilityUpdatePayload(conversation_visible=True),
        )
        assert restored_account is not None
        restored, _, _ = await self.store.list_conversations_for_user(self.user.user_id)
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].conversation_id, "conversation-hidden-from-workspace")

    async def test_only_successful_outbound_clears_needs_reply(self) -> None:
        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-2",
            direction="inbound",
            message_type="text",
            content="hello",
        )
        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-2",
            direction="outbound",
            message_type="text",
            content="failed reply",
            send_success=False,
        )
        pending, _, _ = await self.store.list_conversations_for_user(
            self.user.user_id,
            status="needs_reply",
        )
        self.assertEqual(len(pending), 1)

        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-2",
            direction="outbound",
            message_type="text",
            content="successful reply",
            send_success=True,
        )
        pending, _, _ = await self.store.list_conversations_for_user(
            self.user.user_id,
            status="needs_reply",
        )
        self.assertEqual(pending, [])

    async def test_out_of_order_live_message_is_unread_and_promotes_conversation(self) -> None:
        now_ms = int(time.time() * 1000)
        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-delayed",
            direction="inbound",
            message_type="text",
            content="previous delayed conversation message",
            message_id="delayed-previous",
            created_at_ms=now_ms - 60_000,
        )
        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-recent",
            direction="inbound",
            message_type="text",
            content="recent conversation message",
            message_id="recent-message",
            created_at_ms=now_ms - 30_000,
        )
        for conversation_id in ("conversation-delayed", "conversation-recent"):
            await self.store.mark_conversation_read(
                self.user.user_id,
                self.first_account.account_id,
                conversation_id,
            )

        before, _, _ = await self.store.list_conversations_for_user(self.user.user_id)
        delayed_before = next(
            item for item in before if item.conversation_id == "conversation-delayed"
        )
        self.assertEqual(before[0].conversation_id, "conversation-recent")

        delayed_message = await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-delayed",
            direction="inbound",
            message_type="text",
            content="newly received with an older platform timestamp",
            message_id="delayed-new",
            created_at_ms=now_ms - 120_000,
        )
        after, _, _ = await self.store.list_conversations_for_user(self.user.user_id)
        delayed_after = after[0]
        messages = await self.store.list_messages(
            self.first_account.account_id,
            "conversation-delayed",
            limit=20,
        )

        self.assertEqual(delayed_after.conversation_id, "conversation-delayed")
        self.assertEqual(delayed_after.viewer_unread_count, 1)
        self.assertEqual(delayed_after.last_message_at, delayed_before.last_message_at)
        self.assertGreater(delayed_after.last_activity_at, delayed_before.last_activity_at)
        self.assertEqual(
            delayed_after.last_activity_content,
            "newly received with an older platform timestamp",
        )
        self.assertIsNotNone(delayed_message.received_at)
        self.assertIsNotNone(delayed_message.received_at_ms)
        self.assertEqual(messages[0].message_id, "delayed-new")
        self.assertEqual(messages[-1].message_id, "delayed-previous")

    async def test_history_backfill_does_not_promote_conversation(self) -> None:
        now_ms = int(time.time() * 1000)
        await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-history",
            direction="inbound",
            message_type="text",
            content="live message",
            message_id="history-live",
            created_at_ms=now_ms,
        )
        before = await self.store.get_conversation(
            self.first_account.account_id,
            "conversation-history",
        )

        history_message = await self.store.record_message(
            account_id=self.first_account.account_id,
            conversation_id="conversation-history",
            direction="inbound",
            message_type="text",
            content="backfilled message",
            message_id="history-backfill",
            created_at_ms=now_ms - 86_400_000,
            count_unread=False,
        )
        after = await self.store.get_conversation(
            self.first_account.account_id,
            "conversation-history",
        )

        self.assertEqual(after.last_activity_at, before.last_activity_at)
        self.assertIsNone(history_message.received_at)

    async def test_keyset_cursor_returns_each_conversation_once(self) -> None:
        for index in range(5):
            conversation_id = f"conversation-page-{index}"
            await self.store.record_message(
                account_id=self.first_account.account_id,
                conversation_id=conversation_id,
                direction="inbound",
                message_type="text",
                content=f"page message {index}",
                message_id=f"page-message-{index}",
            )
            if index % 2:
                await self.store.mark_conversation_read(
                    self.user.user_id,
                    self.first_account.account_id,
                    conversation_id,
                )

        cursor = None
        collected = []
        while True:
            page, has_more, cursor = await self.store.list_conversations_for_user(
                self.user.user_id,
                limit=2,
                cursor=cursor,
            )
            collected.extend(page)
            if not has_more:
                break
            self.assertIsInstance(cursor, str)

        self.assertEqual(len(collected), 5)
        self.assertEqual(len({item.conversation_id for item in collected}), 5)
        activity_times = [
            item.last_activity_at or item.last_message_at or item.created_at
            for item in collected
        ]
        self.assertEqual(activity_times, sorted(activity_times, reverse=True))


if __name__ == "__main__":
    unittest.main()
