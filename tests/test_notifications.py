import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from apps.api.xianyu_admin_api.notifications import BarkNotifier


class _NotificationStore:
    async def get_bark_config(self):  # type: ignore[no-untyped-def]
        raise AssertionError("system messages must not load notification configuration")


class NotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_system_message_is_not_sent_as_customer_notification(self) -> None:
        notifier = BarkNotifier(_NotificationStore())  # type: ignore[arg-type]
        account = SimpleNamespace(account_id="account-1", account_name="测试账户")
        message = SimpleNamespace(
            direction="inbound",
            message_type="system",
            content="平台安全提醒",
        )

        await notifier.notify_inbound_message(account, message)  # type: ignore[arg-type]
