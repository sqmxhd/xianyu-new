import asyncio
import base64
import json
import threading
import time
import unittest
from unittest.mock import patch

from integrations.xianyu_core.client import XianyuAccountSession
from integrations.xianyu_core.models import AccountConfig, Direction, MessageType
from integrations.xianyu_core.peer_names import normalize_peer_name


class _DummyApi:
    def __init__(self, *_: object) -> None:
        self.session = type("Session", (), {"proxies": {}})()


class _Upstream:
    XianyuApis = _DummyApi
    counter = 0

    @staticmethod
    def trans_cookies(_: str) -> dict[str, str]:
        return {"unb": "seller-1"}

    @staticmethod
    def generate_device_id(_: str) -> str:
        return "device-1"

    @classmethod
    def generate_mid(cls) -> str:
        cls.counter += 1
        return f"mid-{cls.counter}"

    @staticmethod
    def decrypt(value: str) -> str:
        return value


class _RpcWebSocket:
    def __init__(self, session: XianyuAccountSession) -> None:
        self.session = session
        self.requests: list[dict] = []
        self.acks: list[dict] = []

    async def send(self, raw: str) -> None:
        request = json.loads(raw)
        if "lwp" not in request:
            self.acks.append(request)
            return
        self.requests.append(request)
        if request["lwp"] == "/r/Conversation/listNewestPagination":
            body = {
                "hasMore": True,
                "nextCursor": 123,
                "userConvs": [
                    {
                        "singleChatUserConversation": {
                            "singleChatConversation": {
                                "cid": "conversation-1@goofish",
                                "pairFirst": "seller-1@goofish",
                                "pairSecond": "buyer-1@goofish",
                                "extension": {
                                    "itemId": "item-1",
                                    "itemTitle": "会话商品",
                                    "itemPrice": "9.90",
                                    "itemPic": "https://example.test/item.jpg",
                                },
                            },
                            "lastMessage": {
                                "message": {
                                    "createAt": 1_600_000_000_000,
                                    "content": {"custom": {"summary": "最近消息"}},
                                    "extension": {
                                        "senderUserId": "buyer-1@goofish",
                                        "reminderTitle": "买家",
                                    },
                                }
                            },
                            "modifyTime": 1_700_000_000_000,
                            "redPoint": 2,
                        }
                    }
                ],
            }
        else:
            body = {
                "hasMore": False,
                "userMessageModels": [
                    {
                        "message": {
                            "messageId": "message-1",
                            "createAt": 1_700_000_000_001,
                            "extension": {
                                "senderUserId": "buyer-1@goofish",
                                "reminderTitle": "买家",
                                "reminderUrl": "fleamarket://chat?itemId=item-history-1",
                            },
                            "content": {"custom": {"summary": "历史消息"}},
                        }
                    }
                ],
            }
        await self.session._handle_raw_message(
            json.dumps({"headers": {"mid": request["headers"]["mid"]}, "body": body})
        )


class _AckWebSocket:
    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def send(self, raw: str) -> None:
        self.frames.append(json.loads(raw))


class _BlockingWebSocket:
    def __aiter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __anext__(self):  # type: ignore[no-untyped-def]
        await asyncio.Event().wait()
        raise StopAsyncIteration

    async def send(self, _raw: str) -> None:
        return None

    async def close(self) -> None:
        return None


class _WebSocketContext:
    def __init__(self, websocket: _BlockingWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> _BlockingWebSocket:
        return self.websocket

    async def __aexit__(self, *_args) -> None:  # type: ignore[no-untyped-def]
        return None


class CoreHistoryTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self) -> XianyuAccountSession:
        return XianyuAccountSession(AccountConfig("account-1", "unb=seller-1"), _Upstream())

    async def test_conversation_and_history_rpcs_are_normalized(self) -> None:
        session = self.make_session()
        websocket = _RpcWebSocket(session)
        session.websocket = websocket

        conversations = await session.list_conversations(limit=20)
        messages = await session.list_messages("conversation-1", limit=20)

        self.assertEqual(websocket.requests[0]["lwp"], "/r/Conversation/listNewestPagination")
        self.assertEqual(websocket.requests[1]["lwp"], "/r/MessageManager/listUserMessages")
        self.assertEqual(len(websocket.acks), 2)
        self.assertEqual(websocket.acks[0]["code"], 200)
        self.assertEqual(conversations.items[0].peer_user_id, "buyer-1")
        self.assertEqual(conversations.items[0].item_id, "item-1")
        self.assertEqual(conversations.items[0].item_title, "会话商品")
        self.assertEqual(conversations.items[0].item_price, "9.90")
        self.assertEqual(conversations.items[0].last_message_at_ms, 1_600_000_000_000)
        self.assertTrue(conversations.has_more)
        self.assertEqual(messages.items[0].message_id, "message-1")
        self.assertEqual(messages.items[0].direction, Direction.INBOUND)
        self.assertEqual(messages.items[0].item_id, "item-history-1")

    async def test_cached_im_token_is_reused(self) -> None:
        session = XianyuAccountSession(
            AccountConfig(
                "account-1",
                "unb=seller-1",
                im_token="cached-token",
                im_token_expires_at_ms=int(time.time() * 1000) + 120_000,
            ),
            _Upstream(),
        )

        self.assertEqual(await session._get_im_token(), "cached-token")

    def test_websocket_protocol_ping_is_enabled(self) -> None:
        session = self.make_session()
        captured: dict[str, object] = {}

        def fake_connect(
            url: str,
            *,
            additional_headers: dict[str, str] | None = None,
            ping_interval: int | None = None,
            ping_timeout: int | None = None,
            open_timeout: int | None = None,
            close_timeout: int | None = None,
            proxy: str | None = None,
        ) -> dict[str, object]:
            captured.update(
                url=url,
                additional_headers=additional_headers,
                ping_interval=ping_interval,
                ping_timeout=ping_timeout,
                open_timeout=open_timeout,
                close_timeout=close_timeout,
                proxy=proxy,
            )
            return captured

        with patch("websockets.connect", fake_connect):
            result = session._connect({"Cookie": "unb=seller-1"})

        self.assertIs(result, captured)
        self.assertEqual(captured["ping_interval"], 20)
        self.assertEqual(captured["ping_timeout"], 15)

    def test_all_push_entries_are_parsed_with_correct_identity(self) -> None:
        session = self.make_session()
        frame = {
            "body": {
                "syncPushPackage": {
                    "data": [
                        {
                            "data": {
                                "1": {
                                    "2": "conversation-1@goofish",
                                    "3": "message-1",
                                    "5": 1_700_000_000_001,
                                    "10": {
                                        "senderUserId": "buyer-1@goofish",
                                        "reminderTitle": "买家",
                                        "reminderContent": "你好",
                                    },
                                }
                            }
                        },
                        {
                            "data": {
                                "1": {
                                    "2": "conversation-1@goofish",
                                    "3": "message-2",
                                    "5": 1_700_000_000_002,
                                    "10": {
                                        "senderUserId": "seller-1@goofish",
                                        "reminderContent": "已回复",
                                    },
                                }
                            }
                        },
                    ]
                }
            }
        }

        events = session._parse_chat_events(frame)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].message_id, "message-1")
        self.assertEqual(events[0].created_at_ms, 1_700_000_000_001)
        self.assertEqual(events[0].message_type, MessageType.TEXT)
        self.assertEqual(events[1].direction, Direction.OUTBOUND)

    def test_text_card_push_is_normalized_as_system_message(self) -> None:
        session = self.make_session()
        payload = {
            "1": {
                "2": "conversation-text-card@goofish",
                "3": "message-text-card",
                "5": 1_700_000_000_003,
                "6": {
                    "3": {
                        "2": "[请不要脱离闲鱼沟通及交易]",
                        "4": 6,
                        "5": json.dumps(
                            {
                                "contentType": 6,
                                "textCard": {
                                    "title": "<strong>请不要脱离闲鱼沟通及交易</strong>",
                                    "content": (
                                        "<strong>脱离闲鱼可能面临被骗或者信息泄露的风险，"
                                        "请务必在闲鱼内完成所有沟通及交易！</strong> "
                                        '<a href="https://h5.m.goofish.com/safety">'
                                        "了解更多交易安全指南</a>"
                                    ),
                                },
                            },
                            ensure_ascii=False,
                        ),
                    }
                },
                "10": {
                    "senderUserId": "buyer-1@goofish",
                    "reminderTitle": "买家",
                    "reminderContent": "[请不要脱离闲鱼沟通及交易]",
                },
            }
        }

        event = session._parse_push_payload(payload)

        self.assertIsNotNone(event)
        self.assertEqual(event.message_type, MessageType.SYSTEM)
        self.assertEqual(
            event.content,
            "请不要脱离闲鱼沟通及交易\n"
            "脱离闲鱼可能面临被骗或者信息泄露的风险，"
            "请务必在闲鱼内完成所有沟通及交易！ 了解更多交易安全指南",
        )

    def test_unknown_push_uses_readable_protocol_summary(self) -> None:
        session = self.make_session()
        message_type, content = session._parse_push_content(
            {
                "6": {
                    "3": {
                        "2": "[暂不支持的消息]",
                        "5": json.dumps({"contentType": 999}),
                    }
                }
            },
            {"reminderContent": "平台摘要"},
        )

        self.assertEqual(message_type, MessageType.UNKNOWN)
        self.assertEqual(content, "[暂不支持的消息]")

    def test_voice_push_is_normalized_with_audio_metadata(self) -> None:
        session = self.make_session()
        audio_url = (
            "http://wantu-xm4-xianyu-video-hz.oss-cn-hangzhou.aliyuncs.com/"
            "voice.amr"
        )
        payload = {
            "1": {
                "2": "conversation-audio@goofish",
                "3": "message-audio",
                "6": {
                    "3": {
                        "2": "[语音]",
                        "5": json.dumps(
                            {
                                "contentType": 3,
                                "audio": {
                                    "duration": 2,
                                    "sizeBytes": 4070,
                                    "url": audio_url,
                                },
                            }
                        ),
                    }
                },
                "10": {
                    "senderUserId": "buyer-audio@goofish",
                    "reminderContent": "[语音]",
                },
            }
        }

        event = session._parse_push_payload(payload)

        self.assertIsNotNone(event)
        self.assertEqual(event.message_type, MessageType.AUDIO)
        self.assertEqual(event.content, "[语音 2秒]")
        self.assertEqual(len(event.attachments), 1)
        self.assertEqual(event.attachments[0].attachment_type, "audio")
        self.assertEqual(event.attachments[0].remote_url, audio_url)
        self.assertEqual(event.attachments[0].mime_type, "audio/amr")
        self.assertEqual(event.attachments[0].size_bytes, 4070)
        self.assertEqual(event.attachments[0].duration_seconds, 2)

    def test_voice_history_is_normalized_with_audio_metadata(self) -> None:
        session = self.make_session()
        decoded = {
            "contentType": 3,
            "audio": {
                "duration": 3,
                "sizeBytes": 5000,
                "url": "https://media.aliyuncs.com/voice.amr",
            },
        }
        model = {
            "message": {
                "messageId": "history-audio",
                "extension": {"senderUserId": "buyer-audio@goofish"},
                "content": {
                    "custom": {
                        "data": base64.b64encode(
                            json.dumps(decoded).encode()
                        ).decode()
                    }
                },
            }
        }

        event = session._parse_history_message(model, "conversation-audio")

        self.assertIsNotNone(event)
        self.assertEqual(event.message_type, MessageType.AUDIO)
        self.assertEqual(event.content, "[语音 3秒]")
        self.assertEqual(event.attachments[0].size_bytes, 5000)

    def test_base64_json_sync_entry_skips_binary_decryptor(self) -> None:
        session = self.make_session()
        payload = {
            "1": {
                "2": "conversation-base64@goofish",
                "3": "message-base64",
                "10": {
                    "senderUserId": "buyer-base64@goofish",
                    "reminderContent": "base64 message",
                },
            }
        }
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()

        with patch.object(session.upstream, "decrypt") as decrypt:
            events = session._parse_chat_events(
                {
                    "body": {
                        "syncPushPackage": {
                            "data": [{"data": encoded}],
                        }
                    }
                }
            )

        decrypt.assert_not_called()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].message_id, "message-base64")

    def test_notice_title_is_not_used_as_peer_name(self) -> None:
        session = self.make_session()
        payload = {
            "1": {
                "2": "conversation-1@goofish",
                "3": "message-1",
                "10": {
                    "senderUserId": "buyer-1@goofish",
                    "reminderTitle": "你有一条新消息",
                    "reminderContent": "价格多少",
                },
            }
        }

        event = session._parse_push_payload(payload)

        self.assertIsNotNone(event)
        self.assertIsNone(event.peer_name)

    def test_transaction_notice_titles_are_not_peer_names(self) -> None:
        titles = (
            "卖家人不错？送Ta闲鱼小红花",
            "可以送Ta闲鱼小红花吗～",
            "买家已拍下，待付款",
            "等待您发货",
            "等待你发货",
            "我发起了退款申请",
            "我将「退货退款」修改为「退款」",
            "闲鱼游戏交易安全提醒",
        )

        for title in titles:
            with self.subTest(title=title):
                self.assertIsNone(normalize_peer_name(title, peer_user_id="buyer-1"))

    def test_sender_nickname_has_priority_over_notice_title(self) -> None:
        session = self.make_session()
        payload = {
            "1": {
                "2": "conversation-1@goofish",
                "3": "message-1",
                "10": {
                    "senderUserId": "buyer-1@goofish",
                    "senderNick": "共享AI",
                    "reminderTitle": "你有一条新消息",
                    "reminderContent": "价格多少",
                },
            }
        }

        event = session._parse_push_payload(payload)

        self.assertIsNotNone(event)
        self.assertEqual(event.peer_name, "共享AI")

    async def test_business_callback_failure_does_not_break_receiver(self) -> None:
        session = self.make_session()
        websocket = _AckWebSocket()
        session.websocket = websocket
        handled: list[str] = []

        async def failing_handler(event) -> None:  # type: ignore[no-untyped-def]
            handled.append(event.message_id)
            raise RuntimeError("database unavailable")

        session._on_message = failing_handler
        await session._handle_raw_message(
            json.dumps(
                {
                    "headers": {"mid": "push-1", "sid": "sync"},
                    "body": {
                        "syncPushPackage": {
                            "data": [
                                {
                                    "data": {
                                        "1": {
                                            "2": "conversation-1@goofish",
                                            "3": "message-1",
                                            "5": 1_700_000_000_001,
                                            "10": {
                                                "senderUserId": "buyer-1@goofish",
                                                "reminderContent": "hello",
                                            },
                                        }
                                    }
                                }
                            ]
                        }
                    },
                }
            )
        )

        self.assertEqual(handled, ["message-1"])
        self.assertEqual(websocket.frames[0]["code"], 200)

    async def test_slow_push_decode_does_not_block_rpc_response(self) -> None:
        session = self.make_session()
        websocket = _RpcWebSocket(session)
        session.websocket = websocket
        decode_started = threading.Event()
        release_decode = threading.Event()

        def slow_decode(_frame):  # type: ignore[no-untyped-def]
            decode_started.set()
            release_decode.wait(timeout=2)
            return []

        async def on_message(_event) -> None:  # type: ignore[no-untyped-def]
            return None

        session._parse_chat_events = slow_decode  # type: ignore[method-assign]
        session._on_message = on_message
        session._push_task = asyncio.create_task(session._push_loop())
        try:
            await session._handle_raw_message(
                json.dumps(
                    {
                        "headers": {"mid": "push-slow", "sid": "sync"},
                        "body": {"syncPushPackage": {"data": [{"data": "encrypted"}]}},
                    }
                )
            )
            started = await asyncio.to_thread(decode_started.wait, 0.5)
            self.assertTrue(started)

            conversations = await asyncio.wait_for(
                session.list_conversations(limit=20),
                timeout=0.5,
            )

            self.assertEqual(len(conversations.items), 1)
            self.assertEqual(websocket.requests[-1]["lwp"], "/r/Conversation/listNewestPagination")
        finally:
            release_decode.set()
            session._push_task.cancel()
            await asyncio.gather(session._push_task, return_exceptions=True)
            session._push_task = None

    async def test_heartbeat_failure_is_supervised_as_connection_failure(self) -> None:
        session = self.make_session()
        states: list[str] = []

        async def on_message(_event) -> None:  # type: ignore[no-untyped-def]
            return None

        async def on_state(_account_id, state, _message) -> None:  # type: ignore[no-untyped-def]
            states.append(state.value)
            if len(states) >= 3:
                session._stop_event.set()

        async def init_session() -> None:
            return None

        async def failed_heartbeat() -> None:
            raise RuntimeError("heartbeat failed")

        session._on_message = on_message
        session._on_state = on_state
        session._init_session = init_session  # type: ignore[method-assign]
        session._heartbeat_loop = failed_heartbeat  # type: ignore[method-assign]
        session._build_ws_headers = lambda: {}  # type: ignore[method-assign]
        session._connect = lambda _headers: _WebSocketContext(_BlockingWebSocket())  # type: ignore[method-assign]

        await session._run()

        self.assertEqual(states[:3], ["connecting", "online", "offline"])


if __name__ == "__main__":
    unittest.main()
