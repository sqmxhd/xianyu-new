import asyncio
import json
import unittest

from integrations.xianyu_core.client import XianyuAccountSession
from integrations.xianyu_core.models import AccountConfig


class _DummyApi:
    def __init__(self, *_: object) -> None:
        self.session = type("Session", (), {"proxies": {}})()


class _Upstream:
    XianyuApis = _DummyApi

    @staticmethod
    def trans_cookies(_: str) -> dict[str, str]:
        return {"unb": "seller-id"}

    @staticmethod
    def generate_device_id(_: str) -> str:
        return "device-id"

    @staticmethod
    def generate_mid() -> str:
        return "mid-1"

    @staticmethod
    def generate_uuid() -> str:
        return "uuid-1"


class _AcknowledgingWebSocket:
    def __init__(self, session: XianyuAccountSession, code: int, message: str | None = None) -> None:
        self.session = session
        self.code = code
        self.message = message

    async def send(self, raw_frame: str) -> None:
        request = json.loads(raw_frame)
        if "lwp" not in request:
            return
        response = {"code": self.code, "headers": {"mid": request["headers"]["mid"]}}
        if self.message:
            response["message"] = self.message
        await self.session._handle_raw_message(json.dumps(response))


class CoreAcknowledgementTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self, code: int, message: str | None = None) -> XianyuAccountSession:
        session = XianyuAccountSession(AccountConfig("account-1", "unb=seller-id"), _Upstream())
        session.websocket = _AcknowledgingWebSocket(session, code, message)
        session._online_event.set()
        return session

    async def test_send_is_successful_only_after_platform_ack(self) -> None:
        result = await self.make_session(200).send_text("conversation-1", "buyer-1", "hello")

        self.assertTrue(result.success)
        self.assertEqual(result.message_id, "mid-1")
        self.assertEqual(result.raw_payload["response"]["code"], 200)

    async def test_platform_rejection_is_returned_as_failure(self) -> None:
        result = await self.make_session(403, "denied").send_text(
            "conversation-1", "buyer-1", "hello"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "denied")
        self.assertEqual(result.raw_payload["response"]["code"], 403)

    async def test_recall_waits_for_platform_ack(self) -> None:
        session = self.make_session(200)

        result = await session.recall_message("conversation-1", "platform-message-1")

        self.assertTrue(result.success)
        self.assertEqual(result.message_id, "platform-message-1")
        self.assertEqual(
            result.raw_payload["request"]["lwp"],
            "/r/MessageManager/recallMessage",
        )
        self.assertEqual(result.raw_payload["request"]["body"], ["platform-message-1"])

    async def test_recall_rejection_is_returned_as_failure(self) -> None:
        result = await self.make_session(409, "recall window expired").recall_message(
            "conversation-1",
            "platform-message-1",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "recall window expired")


if __name__ == "__main__":
    unittest.main()
