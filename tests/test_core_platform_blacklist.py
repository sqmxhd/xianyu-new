import unittest
from unittest.mock import Mock

import requests

from integrations.xianyu_core.client import XianyuAccountSession
from integrations.xianyu_core.models import AccountConfig


class _DummyApi:
    def __init__(self, *_: object) -> None:
        self.session = requests.Session()


class _Upstream:
    XianyuApis = _DummyApi

    @staticmethod
    def trans_cookies(_: str) -> dict[str, str]:
        return {"unb": "seller-id", "_m_h5_tk": "token_value_123"}

    @staticmethod
    def get_session_cookies_str(_: requests.Session) -> str:
        return "unb=seller-id; _m_h5_tk=token_value_123"

    @staticmethod
    def generate_sign(timestamp: str, token: str, data: str) -> str:
        return f"{timestamp}:{token}:{data}"


class CorePlatformBlacklistTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self, data: dict) -> tuple[XianyuAccountSession, Mock]:
        session = XianyuAccountSession(
            AccountConfig("account-1", "unb=seller-id; _m_h5_tk=token_value_123"),
            _Upstream(),
        )
        response = Mock()
        response.raise_for_status.return_value = None
        response.cookies.get_dict.return_value = {}
        response.json.return_value = {"ret": ["SUCCESS::调用成功"], "data": data}
        post = Mock(return_value=response)
        session.xianyu.session.post = post
        return session, post

    async def test_query_uses_official_api_and_returns_authoritative_state(self) -> None:
        session, post = self.make_session({"isInBlack": True})

        result = await session.platform_blacklist("conversation-1", "query")

        self.assertTrue(result.success)
        self.assertTrue(result.blocked)
        request = post.call_args
        self.assertIn("idlemessage.pc.blacklist.query", request.args[0])
        self.assertEqual(request.kwargs["data"]["data"], '{"sessionId":"conversation-1"}')

    async def test_add_returns_blocked_state(self) -> None:
        session, post = self.make_session({})

        result = await session.platform_blacklist("conversation-1", "add")

        self.assertTrue(result.success)
        self.assertTrue(result.blocked)
        self.assertIn("idlemessage.pc.blacklist.add", post.call_args.args[0])

    async def test_expired_mtop_token_is_resigned_and_retried(self) -> None:
        session, post = self.make_session({"isInBlack": False})
        expired = Mock()
        expired.raise_for_status.return_value = None
        expired.cookies.get_dict.return_value = {
            "_m_h5_tk": "refreshed-token",
            "_m_h5_tk_enc": "refreshed-token-enc",
        }
        expired.json.return_value = {
            "ret": ["FAIL_SYS_TOKEN_EXOIRED::令牌过期"],
            "data": {},
        }
        succeeded = Mock()
        succeeded.raise_for_status.return_value = None
        succeeded.cookies.get_dict.return_value = {}
        succeeded.json.return_value = {
            "ret": ["SUCCESS::调用成功"],
            "data": {"isInBlack": False},
        }
        post.side_effect = [expired, succeeded]

        result = await session.platform_blacklist("conversation-1", "query")

        self.assertTrue(result.success)
        self.assertFalse(result.blocked)
        self.assertEqual(post.call_count, 2)

    async def test_user_profile_uses_pc_user_query_and_normalizes_avatar(self) -> None:
        session, post = self.make_session(
            {
                "userInfo": {
                    "fishNick": "客户昵称",
                    "logo": "//gw.alicdn.com/avatar.jpg",
                }
            }
        )

        result = await session.get_user_profile("conversation-1")

        self.assertEqual(result["display_name"], "客户昵称")
        self.assertEqual(result["avatar_url"], "https://gw.alicdn.com/avatar.jpg")
        self.assertIn("idlemessage.pc.user.query", post.call_args.args[0])
        self.assertEqual(
            post.call_args.kwargs["data"]["data"],
            '{"type":0,"sessionType":1,"sessionId":"conversation-1","isOwner":false}',
        )

    async def test_account_identity_uses_platform_navigation_profile(self) -> None:
        session, post = self.make_session(
            {
                "module": {
                    "base": {
                        "displayName": "平台卖家",
                        "avatar": "http://example.test/seller.jpg",
                    }
                }
            }
        )

        result = await session.get_account_identity()

        self.assertEqual(result["platform_user_id"], "seller-id")
        self.assertEqual(result["display_name"], "平台卖家")
        self.assertEqual(result["avatar_url"], "https://example.test/seller.jpg")
        self.assertIn("idle.web.user.page.nav", post.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
