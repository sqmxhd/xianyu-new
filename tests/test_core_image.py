import base64
import io
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image
import requests

from integrations.xianyu_core.client import XianyuAccountSession
from integrations.xianyu_core.images import PreparedImage, UploadedImage, prepare_image
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
    def generate_mid() -> str:
        return "mid-image"

    @staticmethod
    def generate_uuid() -> str:
        return "uuid-image"


class _AcknowledgingWebSocket:
    def __init__(self, session: XianyuAccountSession) -> None:
        self.session = session
        self.request: dict | None = None

    async def send(self, raw_frame: str) -> None:
        request = json.loads(raw_frame)
        if "lwp" not in request:
            return
        self.request = request
        await self.session._handle_raw_message(
            json.dumps({"code": 200, "headers": {"mid": request["headers"]["mid"]}})
        )


def _png_bytes(width: int = 40, height: int = 20) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (width, height), (255, 0, 0, 128)).save(output, "PNG")
    return output.getvalue()


class CoreImageTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self) -> tuple[XianyuAccountSession, _AcknowledgingWebSocket]:
        session = XianyuAccountSession(AccountConfig("account-1", "unb=seller-id"), _Upstream())
        websocket = _AcknowledgingWebSocket(session)
        session.websocket = websocket
        session._online_event.set()
        return session, websocket

    def test_prepare_image_normalizes_to_jpeg(self) -> None:
        prepared = prepare_image(_png_bytes())

        self.assertEqual(prepared.mime_type, "image/jpeg")
        self.assertEqual((prepared.width, prepared.height), (40, 20))
        self.assertLessEqual(prepared.size_bytes, 5 * 1024 * 1024)
        with Image.open(io.BytesIO(prepared.data)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.mode, "RGB")

    async def test_send_image_uses_xianyu_image_payload_and_ack(self) -> None:
        session, websocket = self.make_session()
        uploaded = UploadedImage(
            url="https://cdn.example/image.jpg",
            width=40,
            height=20,
            mime_type="image/jpeg",
            size_bytes=123,
            sha256="hash",
        )

        with patch.object(session, "_upload_image", AsyncMock(return_value=uploaded)):
            result = await session.send_image("conversation-1", "buyer-1", _png_bytes())

        self.assertTrue(result.success)
        self.assertIsNotNone(websocket.request)
        frame = websocket.request or {}
        custom = frame["body"][0]["content"]["custom"]
        payload = json.loads(base64.b64decode(custom["data"]).decode("utf-8"))
        self.assertEqual(custom["type"], 1)
        self.assertEqual(payload["contentType"], 2)
        self.assertEqual(
            payload["image"]["pics"][0],
            {
                "type": 0,
                "url": "https://cdn.example/image.jpg",
                "width": 40,
                "height": 20,
            },
        )
        self.assertEqual(
            frame["body"][1]["actualReceivers"],
            ["buyer-1@goofish", "seller-id@goofish"],
        )
        self.assertEqual(result.raw_payload["media"]["url"], uploaded.url)

    async def test_invalid_image_fails_before_upload(self) -> None:
        session, websocket = self.make_session()
        uploader = AsyncMock()

        with patch.object(session, "_upload_image", uploader):
            result = await session.send_image("conversation-1", "buyer-1", b"not-an-image")

        self.assertFalse(result.success)
        self.assertIn("有效图片", result.error or "")
        uploader.assert_not_awaited()
        self.assertIsNone(websocket.request)

    def test_upload_retries_transient_tls_failures(self) -> None:
        session, _ = self.make_session()
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"object":{"url":"https://cdn.example/retried.jpg"}}'
        post = Mock(
            side_effect=[
                requests.exceptions.SSLError("tls eof"),
                requests.exceptions.SSLError("tls eof"),
                response,
            ]
        )
        session.xianyu.session.post = post
        prepared = PreparedImage(
            data=b"jpeg",
            filename="image.jpg",
            mime_type="image/jpeg",
            width=2,
            height=2,
            size_bytes=4,
            sha256="hash",
        )

        url = session._upload_image_sync(prepared)

        self.assertEqual(url, "https://cdn.example/retried.jpg")
        self.assertEqual(post.call_count, 3)


if __name__ == "__main__":
    unittest.main()
