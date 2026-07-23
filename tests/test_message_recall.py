import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from apps.api.xianyu_admin_api.runtime import AccountRuntimeManager
from apps.api.xianyu_admin_api.schemas import MessagePayload
from apps.api.xianyu_admin_api.store import AccountRecord
from integrations.xianyu_core.models import SendMessageResult


def _message(**overrides: object) -> MessagePayload:
    values = {
        "message_pk": "message-pk-1",
        "account_id": "account-1",
        "conversation_id": "conversation-1",
        "message_id": "platform-message-1",
        "direction": "outbound",
        "message_type": "text",
        "content": "hello",
        "send_success": True,
        "send_status": "sent",
        "attachments": [],
        "created_at": datetime.now(UTC) - timedelta(seconds=30),
    }
    values.update(overrides)
    return MessagePayload(**values)


class MessageRecallTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_message_is_recalled_and_persisted_after_platform_ack(self) -> None:
        message = _message()
        recalled = _message(recalled_at=datetime.now(UTC))
        store = AsyncMock()
        store.get_message.return_value = message
        store.mark_message_recalled.return_value = recalled
        core = AsyncMock()
        core.recall_message.return_value = SendMessageResult(
            success=True,
            account_id="account-1",
            conversation_id="conversation-1",
            message_id="platform-message-1",
        )
        manager = AccountRuntimeManager(store)
        manager._core = core
        manager._after_message_persisted = AsyncMock()

        result = await manager.recall_message(
            AccountRecord(account_id="account-1", account_name="seller"),
            "conversation-1",
            "message-pk-1",
        )

        self.assertTrue(result.success)
        self.assertIsNotNone(result.message.recalled_at)
        core.recall_message.assert_awaited_once_with(
            "account-1",
            "conversation-1",
            "platform-message-1",
        )
        store.mark_message_recalled.assert_awaited_once()

    async def test_expired_message_is_rejected_before_platform_call(self) -> None:
        store = AsyncMock()
        store.get_message.return_value = _message(
            created_at=datetime.now(UTC) - timedelta(seconds=121)
        )
        core = AsyncMock()
        manager = AccountRuntimeManager(store)
        manager._core = core

        result = await manager.recall_message(
            AccountRecord(account_id="account-1", account_name="seller"),
            "conversation-1",
            "message-pk-1",
        )

        self.assertFalse(result.success)
        self.assertIn("two-minute", result.error or "")
        core.recall_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
