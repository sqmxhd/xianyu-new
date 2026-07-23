import unittest

import requests

from apps.api.xianyu_admin_api.face_verification import (
    FACE_CHECK_URL,
    FaceVerificationError,
    poll_face_verification,
    prepare_face_verification,
)


class _FakeResponse:
    def __init__(self, *, payload=None, text="", url="https://passport.goofish.com/"):
        self._payload = payload or {}
        self.text = text
        self.url = url

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.cookies = requests.cookies.RequestsCookieJar()

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected GET: {url}")
        return self.responses.pop(0)


class FaceVerificationTests(unittest.TestCase):
    def test_prepare_extracts_htoken_modes_url_and_qr_content(self) -> None:
        http = _FakeHttp(
            [
                _FakeResponse(
                    text=(
                        'htoken=token_123; window.location.href = '
                        '"https://passport.goofish.com/iv/mini/verify_modes.htm?htoken=token_123&amp;_umidfg=";'
                    ),
                    url="https://passport.goofish.com/iv/mini/normal_validate.htm",
                ),
                _FakeResponse(
                    text='new Qrcode({ text: "https:\\/\\/passport.goofish.com\\/face?id=1" });',
                    url="https://passport.goofish.com/iv/mini/identity_verify.htm?htoken=token_123",
                ),
            ]
        )

        challenge = prepare_face_verification(
            http,
            "https://passport.goofish.com/iv/start",
            {"User-Agent": "test"},
        )

        self.assertEqual(challenge.htoken, "token_123")
        self.assertEqual(challenge.code_content, "https://passport.goofish.com/face?id=1")
        self.assertTrue(http.calls[1][0].endswith("_umidfg=1"))

    def test_poll_waits_then_follows_completion_url(self) -> None:
        http = _FakeHttp(
            [
                _FakeResponse(payload={"content": {"code": 0}}),
                _FakeResponse(
                    payload={
                        "content": {
                            "code": 3,
                            "url": "https://passport.goofish.com/iv/ivCheckLogin.htm?token=done",
                        }
                    }
                ),
                _FakeResponse(url="https://passport.goofish.com/iv/ivCheckLogin.htm?token=done"),
            ]
        )
        challenge = prepare_challenge()

        self.assertFalse(poll_face_verification(http, challenge, {}))
        self.assertTrue(poll_face_verification(http, challenge, {}))
        self.assertEqual(http.calls[0][0], FACE_CHECK_URL)
        self.assertEqual(http.calls[2][0], "https://passport.goofish.com/iv/ivCheckLogin.htm?token=done")

    def test_rejects_non_passport_redirects(self) -> None:
        with self.assertRaises(FaceVerificationError):
            prepare_face_verification(_FakeHttp([]), "https://example.com/iv/start", {})


def prepare_challenge():
    from apps.api.xianyu_admin_api.face_verification import FaceVerificationChallenge

    return FaceVerificationChallenge(
        htoken="token_123",
        code_content="face-content",
        referer="https://passport.goofish.com/iv/mini/identity_verify.htm?htoken=token_123",
    )


if __name__ == "__main__":
    unittest.main()
