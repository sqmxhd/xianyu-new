import base64
import json
import os
import unittest

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.orm import ConversationORM, MessageORM, PeerIdentityORM
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    QuickPhraseCreatePayload,
    QuickPhraseUpdatePayload,
    UserCreatePayload,
)
from apps.api.xianyu_admin_api.store import AccountStore


class MessageDedupeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.session_factory = factory
        self.store = AccountStore(session_factory=factory, initialize=False)
        self.account = await self.store.create_account(
            AccountCreatePayload(account_name="dedupe-account", enabled=False)
        )

    async def asyncTearDown(self) -> None:
        self.engine.dispose()

    async def test_platform_message_id_is_idempotent(self) -> None:
        first = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="同一条消息",
            message_id="message-1",
            created_at_ms=1_700_000_000_000,
        )
        duplicate = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="同一条消息",
            message_id="message-1",
            created_at_ms=1_700_000_000_000,
        )

        messages = await self.store.list_messages(
            self.account.account_id, "conversation-1", limit=20
        )
        conversations = await self.store.list_conversations(self.account.account_id, limit=20)

        self.assertIsNotNone(first)
        self.assertIsNone(duplicate)
        self.assertEqual(len(messages), 1)
        self.assertEqual(conversations[0].message_count, 1)

    async def test_unknown_text_card_backfill_repairs_message_and_work_state(self) -> None:
        text_card_data = json.dumps(
            {
                "contentType": 6,
                "textCard": {
                    "title": "<strong>平台安全提醒</strong>",
                    "content": "请在闲鱼内完成沟通及交易",
                },
            },
            ensure_ascii=False,
        )
        raw_payload = {
            "message": {
                "content": {
                    "contentType": 101,
                    "custom": {
                        "summary": "[平台安全提醒]",
                        "data": base64.b64encode(text_card_data.encode()).decode(),
                    }
                },
            }
        }
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-text-card",
            direction="inbound",
            message_type="unknown",
            content="[未知消息类型:6]",
            message_id="message-text-card",
            raw_payload=raw_payload,
            created_at_ms=1_700_000_000_000,
        )

        repaired = await self.store.backfill_unknown_text_cards()
        reconciled = await self.store.reconcile_conversation_summaries(
            self.account.account_id,
            "conversation-text-card",
        )
        repaired_again = await self.store.backfill_unknown_text_cards()
        messages = await self.store.list_messages(
            self.account.account_id,
            "conversation-text-card",
            limit=20,
        )
        conversations = await self.store.list_conversations(
            self.account.account_id,
            limit=20,
        )

        self.assertEqual(repaired, 1)
        self.assertEqual(repaired_again, 0)
        self.assertEqual(len(reconciled), 1)
        self.assertEqual(messages[0].message_type, "system")
        self.assertEqual(messages[0].content, "平台安全提醒\n请在闲鱼内完成沟通及交易")
        self.assertEqual(conversations[0].last_activity_type, "system")
        self.assertFalse(conversations[0].needs_reply)
        self.assertIsNone(conversations[0].last_inbound_at)
        self.assertEqual(conversations[0].unread_count, 1)

    async def test_duplicate_can_upgrade_an_unknown_message(self) -> None:
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-upgrade",
            direction="inbound",
            message_type="unknown",
            content="[未知消息类型:6]",
            message_id="message-upgrade",
        )

        duplicate = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-upgrade",
            direction="inbound",
            message_type="system",
            content="平台通知",
            message_id="message-upgrade",
        )
        messages = await self.store.list_messages(
            self.account.account_id,
            "conversation-upgrade",
            limit=20,
        )

        self.assertIsNone(duplicate)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_type, "system")
        self.assertEqual(messages[0].content, "平台通知")

    async def test_degraded_voice_placeholder_is_upgraded_with_attachment(self) -> None:
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-audio-upgrade",
            direction="inbound",
            message_type="text",
            content="[语音]",
            message_id="message-audio-upgrade",
        )

        upgraded = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-audio-upgrade",
            direction="inbound",
            message_type="audio",
            content="[语音 2秒]",
            message_id="message-audio-upgrade",
            attachments=[
                {
                    "attachment_type": "audio",
                    "remote_url": "https://media.aliyuncs.com/voice.amr",
                    "mime_type": "audio/amr",
                    "size_bytes": 4070,
                }
            ],
        )
        messages = await self.store.list_messages(
            self.account.account_id,
            "conversation-audio-upgrade",
            limit=20,
        )

        self.assertIsNotNone(upgraded)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_type, "audio")
        self.assertEqual(messages[0].content, "[语音 2秒]")
        self.assertEqual(messages[0].attachments[0].attachment_type, "audio")

    async def test_second_precision_platform_timestamp_is_normalized(self) -> None:
        message = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-seconds",
            direction="inbound",
            message_type="text",
            content="second precision timestamp",
            message_id="message-seconds",
            created_at_ms=1_700_000_000,
        )

        self.assertEqual(message.created_at_ms, 1_700_000_000_000)
        self.assertEqual(message.created_at.timestamp(), 1_700_000_000)

    async def test_local_message_gets_canonical_millisecond_timestamps(self) -> None:
        message = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-local-time",
            direction="outbound",
            message_type="text",
            content="local timestamp",
            send_success=False,
        )

        self.assertIsNotNone(message.created_at_ms)
        self.assertIsNone(message.received_at_ms)
        self.assertEqual(
            message.created_at_ms,
            int(message.created_at.timestamp() * 1000),
        )
        self.assertEqual(message.created_at.microsecond % 1000, 0)

    async def test_messages_are_sorted_by_platform_milliseconds(self) -> None:
        for message_id, timestamp in (
            ("same-second-later", 1_700_000_000_999),
            ("same-second-earlier", 1_700_000_000_001),
        ):
            await self.store.record_message(
                account_id=self.account.account_id,
                conversation_id="conversation-millisecond-order",
                direction="inbound",
                message_type="text",
                content=message_id,
                message_id=message_id,
                created_at_ms=timestamp,
            )

        messages = await self.store.list_messages(
            self.account.account_id,
            "conversation-millisecond-order",
            limit=20,
        )

        self.assertEqual(
            [message.message_id for message in messages],
            ["same-second-earlier", "same-second-later"],
        )
        self.assertTrue(all(message.received_at_ms is not None for message in messages))

    async def test_outbound_image_request_is_idempotent_and_persists_media(self) -> None:
        await self.store.upsert_conversation(
            account_id=self.account.account_id,
            conversation_id="conversation-image",
            peer_user_id="buyer-1",
        )

        pending, created = await self.store.begin_outbound_image(
            account_id=self.account.account_id,
            conversation_id="conversation-image",
            client_request_id="request-image-1",
            peer_user_id="buyer-1",
        )
        duplicate, duplicate_created = await self.store.begin_outbound_image(
            account_id=self.account.account_id,
            conversation_id="conversation-image",
            client_request_id="request-image-1",
            peer_user_id="buyer-1",
        )
        completed = await self.store.complete_outbound_image(
            account_id=self.account.account_id,
            client_request_id="request-image-1",
            success=True,
            message_id="platform-image-1",
            error=None,
            raw_payload={"response": {"code": 200}},
            media={
                "url": "https://cdn.example/image.jpg",
                "mime_type": "image/jpeg",
                "width": 800,
                "height": 600,
                "size_bytes": 12345,
                "sha256": "abc123",
            },
        )

        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertIsNotNone(pending)
        self.assertEqual(duplicate.message_pk, pending.message_pk)
        self.assertEqual(completed.send_status, "sent")
        self.assertEqual(completed.content, "https://cdn.example/image.jpg")
        self.assertEqual(completed.attachments[0].width, 800)
        messages = await self.store.list_messages(
            self.account.account_id, "conversation-image", limit=20
        )
        conversations = await self.store.list_conversations(self.account.account_id, limit=20)
        self.assertEqual(len(messages), 1)
        image_conversation = next(
            item for item in conversations if item.conversation_id == "conversation-image"
        )
        self.assertEqual(image_conversation.last_message_type, "image")
        self.assertEqual(image_conversation.last_message_direction, "outbound")

    async def test_outbound_text_send_status_is_persisted_for_timeline_events(self) -> None:
        failed = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-text-status",
            direction="outbound",
            message_type="text",
            content="没有发出去的文本",
            send_success=False,
            send_error="account session is not running",
        )
        sent = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-text-status",
            direction="outbound",
            message_type="text",
            content="已经发出的文本",
            message_id="sent-text-1",
            send_success=True,
        )

        messages = await self.store.list_messages(
            self.account.account_id, "conversation-text-status", limit=20
        )

        self.assertIsNotNone(failed)
        self.assertIsNotNone(sent)
        self.assertEqual(failed.send_status, "failed")
        self.assertEqual(sent.send_status, "sent")
        self.assertEqual([message.send_status for message in messages], ["failed", "sent"])

    async def test_recalled_message_state_is_persisted(self) -> None:
        sent = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-recall",
            direction="outbound",
            message_type="text",
            content="需要撤回",
            message_id="platform-recall-1",
            send_success=True,
        )

        recalled = await self.store.mark_message_recalled(
            self.account.account_id,
            "conversation-recall",
            sent.message_pk,
        )
        loaded = await self.store.get_message(
            self.account.account_id,
            "conversation-recall",
            sent.message_pk,
        )

        self.assertIsNotNone(recalled.recalled_at)
        self.assertEqual(loaded.recalled_at, recalled.recalled_at)

    async def test_quick_phrases_are_user_scoped_and_track_recent_use(self) -> None:
        first_user = await self.store.create_user(
            UserCreatePayload(username="phrase-user-one", password="12345678")
        )
        second_user = await self.store.create_user(
            UserCreatePayload(username="phrase-user-two", password="12345678")
        )
        created = await self.store.create_quick_phrase(
            first_user.user_id,
            QuickPhraseCreatePayload(
                title="问候",
                content="您好，请问有什么可以帮您？",
                group_name="售前",
                sort_order=10,
            ),
        )

        self.assertEqual(await self.store.list_quick_phrases(second_user.user_id), [])
        used = await self.store.touch_quick_phrase(first_user.user_id, created.phrase_id)
        updated = await self.store.update_quick_phrase(
            first_user.user_id,
            created.phrase_id,
            QuickPhraseUpdatePayload(
                title="问候语",
                content=created.content,
                group_name="通用",
                sort_order=0,
            ),
        )

        self.assertIsNotNone(used.last_used_at)
        self.assertEqual(updated.group_name, "通用")
        self.assertFalse(
            await self.store.delete_quick_phrase(second_user.user_id, created.phrase_id)
        )
        self.assertTrue(
            await self.store.delete_quick_phrase(first_user.user_id, created.phrase_id)
        )

    async def test_notice_name_does_not_degrade_conversation(self) -> None:
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="你好",
            message_id="message-1",
            peer_user_id="buyer-1",
            peer_name="共享AI",
        )
        notice = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="价格多少",
            message_id="message-2",
            peer_user_id="buyer-1",
            peer_name="你有一条新消息",
        )

        conversations = await self.store.list_conversations(self.account.account_id, limit=20)
        messages = await self.store.list_messages(
            self.account.account_id, "conversation-1", limit=20
        )

        self.assertIsNotNone(notice)
        self.assertEqual(notice.peer_name, "共享AI")
        self.assertEqual(conversations[0].peer_name, "共享AI")
        self.assertEqual({message.peer_name for message in messages}, {"共享AI"})

    async def test_identity_is_shared_across_conversations(self) -> None:
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="你好",
            message_id="message-1",
            peer_user_id="buyer-1",
            peer_name="共享AI",
            created_at_ms=1_700_000_000_000,
        )

        conversations, _ = await self.store.upsert_conversations(
            self.account.account_id,
            [
                {
                    "conversation_id": "conversation-2",
                    "peer_user_id": "buyer-1",
                    "peer_name": None,
                    "last_message_content": "另一个商品",
                    "last_message_type": "text",
                    "last_message_direction": "inbound",
                    "last_message_at_ms": 1_700_000_001_000,
                    "unread_count": 0,
                }
            ],
        )

        with self.session_factory() as session:
            identities = session.query(PeerIdentityORM).all()

        self.assertEqual(conversations[0].peer_name, "共享AI")
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0].display_name, "共享AI")

    async def test_older_message_cannot_replace_newer_identity(self) -> None:
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="新消息",
            message_id="message-new",
            peer_user_id="buyer-1",
            peer_name="新昵称",
            created_at_ms=1_700_000_001_000,
        )
        older = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="补拉的旧消息",
            message_id="message-old",
            peer_user_id="buyer-1",
            peer_name="旧昵称",
            created_at_ms=1_700_000_000_000,
        )

        messages = await self.store.list_messages(
            self.account.account_id, "conversation-1", limit=20
        )

        self.assertIsNotNone(older)
        self.assertEqual(older.peer_name, "新昵称")
        self.assertEqual({message.peer_name for message in messages}, {"新昵称"})

    async def test_backfill_recovers_name_and_is_idempotent(self) -> None:
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="你好",
            message_id="message-1",
            peer_user_id="buyer-1",
            peer_name="共享AI",
        )
        with self.session_factory() as session:
            conversation = session.query(ConversationORM).one()
            conversation.peer_name = "你有一条新消息"
            legacy_message = MessageORM(
                message_pk="legacy-message",
                account_id=self.account.account_id,
                conversation_id="conversation-1",
                message_id="message-2",
                direction="inbound",
                message_type="text",
                content="价格多少",
                peer_user_id="buyer-1",
                peer_name="你有一条新消息",
                created_at_ms=1_700_000_002_000,
            )
            session.add(legacy_message)
            session.commit()

        repaired = await self.store.backfill_peer_names()
        second_repair = await self.store.backfill_peer_names()
        conversations = await self.store.list_conversations(self.account.account_id, limit=20)
        messages = await self.store.list_messages(
            self.account.account_id, "conversation-1", limit=20
        )

        self.assertEqual(repaired, 2)
        self.assertEqual(second_repair, 0)
        self.assertEqual(conversations[0].peer_name, "共享AI")
        self.assertEqual(
            next(item for item in messages if item.message_id == "message-2").peer_name,
            "共享AI",
        )


if __name__ == "__main__":
    unittest.main()
