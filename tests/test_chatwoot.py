import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch


os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.chatwoot import (
    CHATWOOT_ACCOUNT_ALERT_TASK,
    CHATWOOT_OUTBOUND_AUDIO_UNSUPPORTED_MESSAGE,
    ChatwootIntegrationError,
    ChatwootRepository,
    _account_alert_content,
    _account_label_title,
    _chatwoot_inbound_content,
    _contact_identity_payload,
    _ensure_account_alert_conversation,
    _ensure_managed_account_inbox,
    _ensure_remote_conversation,
    _has_audio_attachment,
    _managed_inbox_name,
    _create_private_recall_snapshot,
    _recall_snapshot_payload,
    _visible_contact_name,
    _chatwoot_request,
    _download_image,
    _download_xianyu_audio,
    _extract_xianyu_audio_url,
    accept_chatwoot_webhook,
    enqueue_account_alert_sync,
    execute_account_alert_task,
    execute_local_message_task,
    execute_account_metadata_task,
    execute_webhook_task,
    reconcile_chatwoot_read_states,
    save_chatwoot_config,
    verify_chatwoot_signature,
)
from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.orm import (
    ChatwootConfigORM,
    ChatwootConversationORM,
    ConversationORM,
)
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    AccountWorkspaceVisibilityUpdatePayload,
    ChatwootConfigUpdatePayload,
    UserCreatePayload,
)
from apps.api.xianyu_admin_api.store import AccountStore


def _image_response(
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
    chunks: list[bytes] | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.iter_content.return_value = chunks or []
    return response


class ChatwootImageDownloadTests(unittest.TestCase):
    @staticmethod
    def _session(client: MagicMock) -> MagicMock:
        session = MagicMock()
        session.return_value.__enter__.return_value = client
        return session

    def test_download_uses_chatwoot_ca_and_follows_same_origin_redirect(self) -> None:
        redirect = _image_response(
            302,
            headers={"location": "/rails/active_storage/disk/image-token"},
        )
        image = _image_response(
            200,
            headers={"content-type": "image/jpeg"},
            chunks=[b"image-", b"bytes"],
        )
        client = MagicMock()
        client.get.side_effect = [redirect, image]

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot.requests.Session",
                self._session(client),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._host_is_private",
                return_value=True,
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_tls_verify",
                return_value="/etc/xianyu/tls/chatwoot-ca.pem",
            ),
        ):
            data, mime_type, filename = _download_image(
                "https://192.168.201.2/rails/active_storage/blobs/redirect/photo.jpg",
                allowed_private_origin="https://192.168.201.2",
            )

        self.assertEqual(data, b"image-bytes")
        self.assertEqual(mime_type, "image/jpeg")
        self.assertTrue(filename.endswith(".jpg"))
        self.assertEqual(client.get.call_count, 2)
        for call in client.get.call_args_list:
            self.assertEqual(
                call.kwargs["verify"],
                "/etc/xianyu/tls/chatwoot-ca.pem",
            )
            self.assertFalse(call.kwargs["allow_redirects"])
        redirect.close.assert_called_once()
        image.close.assert_called_once()

    def test_download_rejects_redirect_to_unapproved_private_origin(self) -> None:
        redirect = _image_response(
            302,
            headers={"location": "http://127.0.0.1/internal"},
        )
        client = MagicMock()
        client.get.return_value = redirect

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot.requests.Session",
                self._session(client),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._host_is_private",
                side_effect=lambda hostname: hostname == "127.0.0.1",
            ),
            self.assertRaisesRegex(
                ChatwootIntegrationError,
                "指向内网",
            ),
        ):
            _download_image("https://images.example/photo.jpg")

        self.assertEqual(client.get.call_count, 1)
        redirect.close.assert_called_once()

    def test_download_rejects_https_downgrade(self) -> None:
        redirect = _image_response(
            302,
            headers={"location": "http://cdn.example/photo.jpg"},
        )
        client = MagicMock()
        client.get.return_value = redirect

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot.requests.Session",
                self._session(client),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._host_is_private",
                return_value=False,
            ),
            self.assertRaisesRegex(
                ChatwootIntegrationError,
                "禁止降级",
            ),
        ):
            _download_image("https://images.example/photo.jpg")

        self.assertEqual(client.get.call_count, 1)
        redirect.close.assert_called_once()

    def test_public_image_uses_default_ca_verification(self) -> None:
        image = _image_response(
            200,
            headers={"content-type": "image/png"},
            chunks=[b"png-data"],
        )
        client = MagicMock()
        client.get.return_value = image

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot.requests.Session",
                self._session(client),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._host_is_private",
                return_value=False,
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_tls_verify"
            ) as tls_verify,
        ):
            data, mime_type, _ = _download_image(
                "https://images.example/photo.png"
            )

        self.assertEqual(data, b"png-data")
        self.assertEqual(mime_type, "image/png")
        self.assertIs(client.get.call_args.kwargs["verify"], True)
        tls_verify.assert_not_called()


class ChatwootAudioTests(unittest.TestCase):
    def test_detects_audio_by_chatwoot_type_mime_or_filename(self) -> None:
        self.assertTrue(
            _has_audio_attachment({"attachments": [{"file_type": "audio"}]})
        )
        self.assertTrue(
            _has_audio_attachment(
                {"attachments": [{"content_type": "audio/x-wav"}]}
            )
        )
        self.assertTrue(
            _has_audio_attachment(
                {
                    "attachments": [
                        {
                            "file_type": "file",
                            "data_url": "https://chatwoot.test/file/voice.AMR?download=1",
                        }
                    ]
                }
            )
        )
        self.assertFalse(
            _has_audio_attachment(
                {
                    "attachments": [
                        {
                            "file_type": "image",
                            "content_type": "image/webp",
                            "data_url": "https://chatwoot.test/file/image.webp",
                        }
                    ]
                }
            )
        )

    @staticmethod
    def _session(client: MagicMock) -> MagicMock:
        session = MagicMock()
        session.return_value.__enter__.return_value = client
        return session

    def test_audio_download_upgrades_trusted_xianyu_url_to_https(self) -> None:
        audio = _image_response(206, chunks=[b"#!AMR\n", b"voice-bytes"])
        client = MagicMock()
        client.get.return_value = audio

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot.requests.Session",
                self._session(client),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._host_is_private",
                return_value=False,
            ),
        ):
            data, mime_type, filename = _download_xianyu_audio(
                "http://voice.oss-cn-hangzhou.aliyuncs.com/message.amr"
            )

        self.assertEqual(data, b"#!AMR\nvoice-bytes")
        self.assertEqual(mime_type, "audio/amr")
        self.assertTrue(filename.endswith(".amr"))
        self.assertTrue(client.get.call_args.args[0].startswith("https://"))
        self.assertTrue(client.get.call_args.kwargs["verify"])

    def test_audio_download_rejects_untrusted_host(self) -> None:
        with self.assertRaisesRegex(
            ChatwootIntegrationError,
            "不在受信任",
        ):
            _download_xianyu_audio("https://example.test/message.amr")

    def test_audio_url_is_recovered_from_legacy_base64_payload(self) -> None:
        payload = {
            "content": {
                "custom": {
                    "data": (
                        "eyJjb250ZW50VHlwZSI6IDMsICJhdWRpbyI6IHsidXJsIjog"
                        "Imh0dHBzOi8vbWVkaWEuYWxpeXVuY3MuY29tL3ZvaWNlLmFtciJ9fQ=="
                    )
                }
            }
        }

        self.assertEqual(
            _extract_xianyu_audio_url(payload),
            "https://media.aliyuncs.com/voice.amr",
        )


class ChatwootAccountIdentityTests(unittest.TestCase):
    def test_contact_name_is_visible_and_idempotent(self) -> None:
        self.assertEqual(
            _visible_contact_name("闲鱼客户", "主账号"),
            "闲鱼｜主账号",
        )
        self.assertEqual(
            _visible_contact_name("闲鱼客户｜主账号", "主账号"),
            "闲鱼｜主账号",
        )
        self.assertEqual(
            _visible_contact_name("[闲鱼｜主账号] 闲鱼客户", "主账号"),
            "闲鱼｜主账号",
        )

    def test_inbound_preview_leads_with_full_customer_name(self) -> None:
        context = {
            "peer_name": "奔波霸和霸波奔",
            "peer_user_id": "buyer-1",
        }
        self.assertEqual(
            _chatwoot_inbound_content(
                context,
                "你好，请问还在吗？",
                has_images=False,
                has_audio=False,
            ),
            "奔波霸和霸波奔：你好，请问还在吗？",
        )
        self.assertEqual(
            _chatwoot_inbound_content(
                context,
                "",
                has_images=True,
                has_audio=False,
            ),
            "奔波霸和霸波奔：[图片]",
        )

    def test_account_label_is_readable_stable_and_sanitized(self) -> None:
        self.assertEqual(
            _account_label_title("测试 账号/一号", "ABCDEF123456"),
            "闲鱼-测试-账号-一号-abcd",
        )

    def test_platform_account_customer_identity_is_globally_unambiguous(self) -> None:
        first = _contact_identity_payload(
            account_id="account-a",
            account_name="账号甲",
            peer_user_id="same-customer",
            peer_name="同一客户",
        )
        second = _contact_identity_payload(
            account_id="account-b",
            account_name="账号乙",
            peer_user_id="same-customer",
            peer_name="同一客户",
        )

        self.assertEqual(
            first["identifier"],
            "xianyu:account-a:same-customer",
        )
        self.assertNotEqual(first["identifier"], second["identifier"])
        self.assertEqual(first["name"], "闲鱼｜账号甲")
        self.assertEqual(
            first["custom_attributes"]["source_customer_id"],
            "same-customer",
        )
        self.assertEqual(
            first["custom_attributes"]["source_customer_name"],
            "同一客户",
        )

    def test_managed_inbox_name_exposes_platform_account_and_state(self) -> None:
        self.assertEqual(
            _managed_inbox_name(
                platform="xianyu",
                account_name="主账号",
                state="online",
            ),
            "🟢 [闲鱼] 主账号",
        )
        self.assertEqual(
            _managed_inbox_name(
                platform="xianyu",
                account_name="主账号",
                state="reconnecting",
            ),
            "🟡 [闲鱼] 主账号",
        )


class ChatwootBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
        self.store = AccountStore(
            session_factory=self.session_factory,
            initialize=False,
        )
        self.repository = ChatwootRepository(self.session_factory)
        original_upsert_config = self.repository.upsert_config

        async def upsert_test_config(
            payload: ChatwootConfigUpdatePayload,
            *,
            chatwoot_account_id: int = 3,
        ):
            if not payload.api_access_token:
                payload = payload.model_copy(
                    update={"api_access_token": "test-service-account-token"}
                )
            return await original_upsert_config(
                payload,
                chatwoot_account_id=chatwoot_account_id,
            )

        self.repository.upsert_config = upsert_test_config
        self.account = await self.store.create_account(
            AccountCreatePayload(
                enabled=True,
                chat_enabled=True,
            )
        )
        self.account = await self.store.update_account_platform_identity(
            self.account.account_id,
            platform_user_id="seller-chatwoot-test",
            display_name="chatwoot-test",
            avatar_url=None,
        )
        assert self.account is not None

    async def asyncTearDown(self) -> None:
        self.engine.dispose()

    def test_signed_webhook_accepts_timestamp_body_hmac_and_rejects_stale(self) -> None:
        body = b'{"event":"message_created"}'
        timestamp = str(int(time.time()))
        signature = "sha256=" + hmac.new(
            b"webhook-secret",
            f"{timestamp}.".encode() + body,
            hashlib.sha256,
        ).hexdigest()

        self.assertTrue(
            verify_chatwoot_signature(
                secret="webhook-secret",
                raw_body=body,
                signature=signature,
                timestamp=timestamp,
            )
        )
        self.assertFalse(
            verify_chatwoot_signature(
                secret="webhook-secret",
                raw_body=body,
                signature=signature,
                timestamp=timestamp,
                now=int(timestamp) + 301,
            )
        )

    def test_recall_snapshot_contains_original_text_image_and_result(self) -> None:
        content, image_urls = _recall_snapshot_payload(
            [
                {
                    "message_pk": "text-piece",
                    "created_at_ms": 1_800_000_000_000,
                    "created_at": "2027-01-15T08:00:00+00:00",
                    "message_type": "text",
                    "content": "原始文字",
                    "attachments": [],
                },
                {
                    "message_pk": "image-piece",
                    "created_at_ms": 1_800_000_000_001,
                    "created_at": "2027-01-15T08:00:00.001000+00:00",
                    "message_type": "image",
                    "content": "https://cdn.example/original.jpg",
                    "attachments": [
                        {
                            "attachment_type": "image",
                            "remote_url": "https://cdn.example/original.jpg",
                        }
                    ],
                },
            ],
            succeeded=True,
            error=None,
        )

        self.assertIn("原消息（2027-01-15 16:00:00 上海时间）", content)
        self.assertIn("原始文字", content)
        self.assertIn("↩ 闲鱼消息已撤回", content)
        self.assertNotIn("https://cdn.example/original.jpg", content)
        self.assertEqual(image_urls, ["https://cdn.example/original.jpg"])

    async def test_private_recall_snapshot_uploads_images_as_private_note(
        self,
    ) -> None:
        config = {
            "base_url": "https://chatwoot.internal",
            "chatwoot_account_id": 3,
            "api_access_token": "service-token",
        }
        request_mock = MagicMock(return_value=(200, {"id": 900}))
        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._download_image",
                new=MagicMock(
                    return_value=(b"jpeg-data", "image/jpeg", "original.jpg")
                ),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
                new=request_mock,
            ),
        ):
            created = await _create_private_recall_snapshot(
                config,
                chatwoot_conversation_id="88",
                chatwoot_message_id="99",
                contexts=[
                    {
                        "message_pk": "image-piece",
                        "message_type": "image",
                        "content": "https://cdn.example/original.jpg",
                        "attachments": [
                            {
                                "attachment_type": "image",
                                "remote_url": "https://cdn.example/original.jpg",
                            }
                        ],
                    }
                ],
                succeeded=True,
                error=None,
            )

        self.assertTrue(created)
        request_mock.assert_called_once()
        call = request_mock.call_args
        self.assertEqual(call.args[0], "POST")
        self.assertEqual(call.kwargs["data"]["private"], "true")
        self.assertEqual(
            call.kwargs["data"][
                "content_attributes[xianyu_deleted_source_message_id]"
            ],
            "99",
        )
        self.assertEqual(call.kwargs["files"][0][1][0], "original.jpg")

    async def test_service_account_token_is_encrypted_and_exposed_to_admin(self) -> None:
        config = await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                account_alerts_enabled=True,
                offline_alert_delay_seconds=180,
                base_url="http://chatwoot.internal:3000/",
                api_access_token="service-account-token",
            )
        )

        self.assertTrue(config.has_api_access_token)
        self.assertTrue(config.full_outbound_sync_enabled)
        self.assertTrue(config.account_alerts_enabled)
        self.assertEqual(config.offline_alert_delay_seconds, 180)
        self.assertFalse(config.account_grouping_enabled)
        self.assertEqual(config.api_access_token, "service-account-token")
        with self.session_factory() as session:
            row = session.scalar(select(ChatwootConfigORM))
            assert row is not None
            self.assertNotEqual(row.api_access_token_encrypted, "service-account-token")

    async def test_component_health_is_aggregated_without_last_writer_loss(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
                api_access_token="service-account-token",
            )
        )
        await self.repository.set_component_health(
            component="label",
            status="error",
            error="标签接口异常",
        )
        await self.repository.set_component_health(
            component="credential",
            status="ready",
            error=None,
        )

        degraded = await self.repository.get_config_payload()
        assert degraded is not None
        self.assertEqual(degraded.status, "degraded")
        self.assertEqual(degraded.label_status, "error")
        self.assertEqual(degraded.last_error, "标签接口异常")

        await self.repository.set_component_health(
            component="label",
            status="ready",
            error=None,
        )
        ready = await self.repository.get_config_payload()
        assert ready is not None
        self.assertEqual(ready.status, "ready")
        self.assertIsNone(ready.last_error)

    async def test_save_config_detects_administrator_account(self) -> None:
        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            return_value=(
                200,
                {
                    "id": 21,
                    "accounts": [
                        {"id": 7, "name": "服务平台", "role": "administrator"}
                    ],
                },
            ),
        ) as request:
            saved = await save_chatwoot_config(
                self.repository,
                ChatwootConfigUpdatePayload(
                    enabled=True,
                    base_url="https://chatwoot.internal/",
                    api_access_token="service-account-token",
                ),
            )

        self.assertEqual(saved.chatwoot_account_id, 7)
        self.assertEqual(saved.base_url, "https://chatwoot.internal")
        self.assertEqual(request.call_args.kwargs["token"], "service-account-token")

    async def test_save_config_rejects_non_administrator(self) -> None:
        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            return_value=(
                200,
                {"id": 21, "accounts": [{"id": 7, "role": "agent"}]},
            ),
        ):
            with self.assertRaisesRegex(
                ChatwootIntegrationError,
                "administrator",
            ):
                await save_chatwoot_config(
                    self.repository,
                    ChatwootConfigUpdatePayload(
                        enabled=True,
                        base_url="https://chatwoot.internal",
                        api_access_token="service-account-token",
                    ),
                )

    async def test_offline_alert_is_delayed_and_enqueued_once(self) -> None:
        queued_task = SimpleNamespace(task_id="task-alert", status="pending")
        store = SimpleNamespace(
            session_factory=self.session_factory,
            create_background_task=AsyncMock(return_value=queued_task),
            mark_background_task_queued=AsyncMock(),
        )
        with (
            patch.object(
                ChatwootRepository,
                "get_config",
                AsyncMock(
                    return_value={
                        "enabled": True,
                        "account_alerts_enabled": True,
                        "offline_alert_delay_seconds": 180,
                    }
                ),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot.enqueue_background_task",
                AsyncMock(return_value=SimpleNamespace(queued=True)),
            ),
        ):
            before = datetime.now(UTC)
            await enqueue_account_alert_sync(
                store,
                account_id=self.account.account_id,
                state="offline",
                message="连接中断",
            )

        payload = store.create_background_task.await_args.args[0]
        self.assertEqual(payload.task_type, CHATWOOT_ACCOUNT_ALERT_TASK)
        self.assertEqual(payload.payload["expected_state"], "offline")
        self.assertIsNotNone(payload.run_after)
        assert payload.run_after is not None
        delay = (payload.run_after - before).total_seconds()
        self.assertGreaterEqual(delay, 179)
        self.assertLessEqual(delay, 181)
        store.mark_background_task_queued.assert_awaited_once_with("task-alert")

    async def test_delayed_alert_is_skipped_after_account_recovers(self) -> None:
        with patch.object(
            ChatwootRepository,
            "get_config",
            AsyncMock(
                return_value={
                    "enabled": True,
                    "account_alerts_enabled": True,
                    "account_state": "online",
                }
            ),
        ), patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request"
        ) as request:
            result = await execute_account_alert_task(
                self.store,
                account_id=self.account.account_id,
                state="offline",
                message="连接中断",
                expected_state="offline",
            )

        self.assertTrue(result["skipped"])
        self.assertEqual(result["current_state"], "online")
        request.assert_not_called()

    async def test_account_alert_uses_dedicated_incoming_event_conversation(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                account_alerts_enabled=True,
                base_url="https://chatwoot.internal",
                api_access_token="service-token",
            )
        )
        await self.repository.upsert_inbox_binding(
            account_id=self.account.account_id,
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
            webhook_secret="managed-secret",
            label_id=None,
            label_title=None,
        )

        def fake_request(method: str, url: str, **kwargs: object):
            if url.endswith("/toggle_status"):
                return 200, {}
            if url.endswith("/messages"):
                return 200, {"id": 901}
            raise AssertionError(f"unexpected request: {method} {url}")

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._ensure_account_alert_conversation",
                AsyncMock(return_value=("alert-source", "77")),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
                side_effect=fake_request,
            ) as request,
        ):
            failed = await execute_account_alert_task(
                self.store,
                account_id=self.account.account_id,
                state="offline",
                message="连接持续中断",
            )
            duplicate = await execute_account_alert_task(
                self.store,
                account_id=self.account.account_id,
                state="offline",
                message="连接持续中断",
            )
            recovered = await execute_account_alert_task(
                self.store,
                account_id=self.account.account_id,
                state="online",
                message="连接已恢复",
            )

        self.assertEqual(failed["chatwoot_message_id"], "901")
        self.assertTrue(duplicate["skipped"])
        self.assertEqual(recovered["previous_state"], "offline")
        message_calls = [
            call
            for call in request.call_args_list
            if call.args[1].endswith("/messages")
        ]
        self.assertEqual(len(message_calls), 2)
        self.assertIn(
            "/public/api/v1/inboxes/managed-inbox/contacts/"
            "alert-source/conversations/77/messages",
            message_calls[0].args[1],
        )
        self.assertIn("上海时间", message_calls[0].kwargs["json_body"]["content"])

    async def test_account_alert_channel_is_persisted_per_managed_inbox(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
                api_access_token="service-token",
            )
        )
        await self.repository.upsert_inbox_binding(
            account_id=self.account.account_id,
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
            webhook_secret="managed-secret",
            label_id=None,
            label_title=None,
        )
        config = await self.repository.get_config(account_id=self.account.account_id)
        assert config is not None

        def fake_request(method: str, url: str, **kwargs: object):
            if method == "POST" and url.endswith("/contacts"):
                return 200, {"id": 51}
            if method == "PATCH" and "/contacts/" in url:
                return 200, {}
            if method == "POST" and url.endswith("/conversations"):
                return 200, {"id": 77}
            raise AssertionError(f"unexpected request: {method} {url}")

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._ensure_managed_account_inbox",
                AsyncMock(return_value=config),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
                side_effect=fake_request,
            ),
        ):
            source_id, conversation_id = await _ensure_account_alert_conversation(
                self.repository,
                config,
            )

        binding = await self.repository.get_inbox_binding(self.account.account_id)
        assert binding is not None
        self.assertEqual(conversation_id, "77")
        self.assertEqual(binding["alert_source_id"], source_id)
        self.assertEqual(binding["alert_contact_id"], "51")
        self.assertEqual(binding["alert_conversation_id"], "77")

    def test_account_alert_content_uses_shanghai_time(self) -> None:
        content = _account_alert_content(
            {
                "platform": "xianyu",
                "platform_name": "闲鱼",
                "account_id": "account-1",
                "account_name": "账号甲",
            },
            state="test",
            message=None,
        )
        self.assertIn("平台：闲鱼", content)
        self.assertIn("账户：账号甲", content)
        self.assertIn("上海时间", content)

    async def test_managed_inbox_secret_is_scoped_by_remote_inbox_id(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
            )
        )
        binding = await self.repository.upsert_inbox_binding(
            account_id=self.account.account_id,
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
            webhook_secret="managed-webhook-secret",
            label_id=17,
            label_title="闲鱼-chatwoot-test-1234",
        )

        self.assertEqual(binding["chatwoot_inbox_id"], 9)
        self.assertIsNone(await self.repository.get_config_secret(1))
        self.assertEqual(
            await self.repository.get_config_secret(9),
            "managed-webhook-secret",
        )
        self.assertIsNone(await self.repository.get_config_secret(99))
        payload = await self.repository.get_config_payload()
        assert payload is not None
        self.assertEqual(payload.managed_inbox_count, 1)
        self.assertTrue(payload.account_grouping_enabled)

    async def test_legacy_conversation_is_remapped_to_managed_account_inbox(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
                api_access_token="service-account-token",
            )
        )
        await self.repository.upsert_inbox_binding(
            account_id=self.account.account_id,
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
            webhook_secret="managed-webhook-secret",
            label_id=None,
            label_title=None,
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-migrate",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-migrate",
            peer_name="迁移客户",
        )
        contact = await self.repository.ensure_contact_map(
            account_id=self.account.account_id,
            peer_user_id="buyer-migrate",
            display_name="迁移客户",
            avatar_url=None,
            chatwoot_contact_id="44",
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-migrate",
            peer_user_id="buyer-migrate",
            source_id=str(contact["source_id"]),
            chatwoot_conversation_id="108",
            chatwoot_inbox_id=1,
            inbox_identifier="legacy-inbox",
        )
        config = await self.repository.get_config(
            account_id=self.account.account_id
        )
        context = await self.repository.get_local_conversation_context(
            self.account.account_id,
            "conversation-migrate",
        )
        assert config is not None
        assert context is not None

        def fake_request(
            method: str,
            url: str,
            **kwargs: object,
        ) -> tuple[int, object]:
            if method == "POST" and url.endswith("/contacts/44/contact_inboxes"):
                self.assertEqual(
                    kwargs["json_body"],
                    {
                        "inbox_id": 9,
                        "source_id": contact["source_id"],
                    },
                )
                return 200, {"source_id": contact["source_id"]}
            if method == "PATCH" and "/public/api/v1/inboxes/managed-inbox/" in url:
                return 200, {}
            if method == "GET" and url.endswith("/conversations"):
                return 200, {"payload": []}
            if method == "POST" and url.endswith("/api/v1/accounts/3/conversations"):
                body = kwargs["json_body"]
                self.assertEqual(body["inbox_id"], 9)
                self.assertEqual(body["contact_id"], 44)
                self.assertEqual(
                    body["custom_attributes"]["source_platform_name"],
                    "闲鱼",
                )
                self.assertEqual(
                    body["custom_attributes"]["source_account_state"],
                    "stopped",
                )
                return 200, {"id": 208}
            if method == "POST" and url.endswith("/conversations/208/custom_attributes"):
                return 200, {}
            if method == "POST" and url.endswith("/conversations/208/messages"):
                return 200, {"id": 209}
            if method == "POST" and url.endswith("/conversations/108/toggle_status"):
                return 200, {"status": "resolved"}
            raise AssertionError(f"unexpected request: {method} {url}")

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            side_effect=fake_request,
        ):
            migrated = await _ensure_remote_conversation(
                self.repository,
                config,
                context,
            )

        self.assertTrue(migrated["migrated"])
        self.assertEqual(migrated["chatwoot_conversation_id"], "208")
        self.assertEqual(migrated["chatwoot_inbox_id"], 9)
        self.assertEqual(migrated["inbox_identifier"], "managed-inbox")

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request"
        ) as request:
            unchanged = await _ensure_remote_conversation(
                self.repository,
                config,
                context,
            )
        request.assert_not_called()
        self.assertEqual(unchanged["chatwoot_conversation_id"], "208")

    async def test_same_contact_new_xianyu_conversation_gets_distinct_remote(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
                api_access_token="service-account-token",
            )
        )
        await self.repository.upsert_inbox_binding(
            account_id=self.account.account_id,
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
            webhook_secret="managed-webhook-secret",
            label_id=None,
            label_title=None,
        )
        contact = await self.repository.ensure_contact_map(
            account_id=self.account.account_id,
            peer_user_id="buyer-shared",
            display_name="同一买家",
            avatar_url=None,
            chatwoot_contact_id="44",
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-old",
            peer_user_id="buyer-shared",
            source_id=str(contact["source_id"]),
            chatwoot_conversation_id="20",
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-new",
            direction="inbound",
            message_type="text",
            content="new conversation",
            peer_user_id="buyer-shared",
            peer_name="同一买家",
        )
        config = await self.repository.get_config(
            account_id=self.account.account_id
        )
        context = await self.repository.get_local_conversation_context(
            self.account.account_id,
            "conversation-new",
        )
        assert config is not None
        assert context is not None

        def fake_request(
            method: str,
            url: str,
            **kwargs: object,
        ) -> tuple[int, object]:
            if method == "POST" and url.endswith("/contacts"):
                return 409, {}
            if method == "PATCH" and "/contacts/" in url:
                return 200, {}
            if method == "GET" and url.endswith("/conversations"):
                return 200, {
                    "payload": [
                        {
                            "id": 20,
                            "custom_attributes": {
                                "source_conversation_id": "conversation-old",
                            },
                        }
                    ]
                }
            if method == "POST" and url.endswith(
                "/api/v1/accounts/3/conversations"
            ):
                body = kwargs["json_body"]
                self.assertEqual(body["source_id"], contact["source_id"])
                self.assertEqual(body["contact_id"], 44)
                self.assertEqual(
                    body["custom_attributes"]["source_conversation_id"],
                    "conversation-new",
                )
                return 200, {"id": 21}
            if method == "POST" and url.endswith(
                "/conversations/21/custom_attributes"
            ):
                return 200, {}
            raise AssertionError(f"unexpected request: {method} {url}")

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            side_effect=fake_request,
        ):
            mapping = await _ensure_remote_conversation(
                self.repository,
                config,
                context,
            )

        self.assertEqual(mapping["chatwoot_conversation_id"], "21")
        self.assertEqual(mapping["source_id"], contact["source_id"])
        old_mapping = await self.repository.get_conversation_map(
            self.account.account_id,
            "conversation-old",
        )
        assert old_mapping is not None
        self.assertEqual(old_mapping["chatwoot_conversation_id"], "20")

    async def test_remote_conversation_cannot_bind_two_xianyu_conversations(
        self,
    ) -> None:
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-old",
            peer_user_id="buyer-shared",
            source_id="source-shared",
            chatwoot_conversation_id="20",
        )

        with self.assertRaisesRegex(
            ChatwootIntegrationError,
            "Chatwoot 会话 20 已绑定闲鱼会话 conversation-old",
        ):
            await self.repository.create_conversation_map(
                account_id=self.account.account_id,
                conversation_id="conversation-new",
                peer_user_id="buyer-shared",
                source_id="source-shared",
                chatwoot_conversation_id="20",
            )

    async def test_managed_inbox_and_account_label_are_created_once(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
                api_access_token="service-account-token",
            )
        )
        config = await self.repository.get_config(
            account_id=self.account.account_id
        )
        assert config is not None
        remote_label: dict[str, object] | None = None
        remote_inbox: dict[str, object] | None = None

        def fake_request(
            method: str,
            url: str,
            **kwargs: object,
        ) -> tuple[int, object]:
            nonlocal remote_inbox, remote_label
            if method == "GET" and url.endswith("/profile"):
                return 200, {"id": 21}
            if method == "GET" and "/inbox_members/" in url:
                return 200, {"payload": [{"id": 21}]}
            if method == "GET" and url.endswith("/inboxes"):
                return 200, [remote_inbox] if remote_inbox else []
            if method == "POST" and url.endswith("/inboxes"):
                self.assertFalse(
                    kwargs["json_body"]["lock_to_single_conversation"]
                )
                remote_inbox = {
                    "id": 9,
                    "name": "🔴 [闲鱼] chatwoot-test",
                    "channel_type": "Channel::Api",
                    "inbox_identifier": "managed-inbox",
                    "secret": "managed-webhook-secret",
                    "lock_to_single_conversation": False,
                }
                return 200, remote_inbox
            if method == "PATCH" and url.endswith("/inboxes/9"):
                self.assertFalse(kwargs["json_body"]["channel"]["hmac_mandatory"])
                self.assertEqual(
                    kwargs["json_body"]["channel"]["webhook_url"],
                    "/api/integrations/chatwoot/webhook",
                )
                return 200, {}
            if method == "GET" and url.endswith("/labels"):
                return 200, {"payload": [remote_label] if remote_label else []}
            if method == "POST" and url.endswith("/labels"):
                request_body = kwargs["json_body"]
                self.assertEqual(set(request_body), {"label"})
                label_body = request_body["label"]
                remote_label = {
                    "id": 17,
                    **label_body,
                }
                return 200, remote_label
            if method == "PATCH" and url.endswith("/labels/17"):
                request_body = kwargs["json_body"]
                self.assertEqual(set(request_body), {"label"})
                remote_label = {"id": 17, **request_body["label"]}
                return 200, remote_label
            raise AssertionError(f"unexpected request: {method} {url}")

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            side_effect=fake_request,
        ) as request:
            resolved = await _ensure_managed_account_inbox(
                self.repository,
                config,
            )
            assert remote_label is not None
            remote_label["title"] = "stale-account-label"
            again = await _ensure_managed_account_inbox(
                self.repository,
                resolved,
                refresh_display_name=True,
            )

        self.assertTrue(resolved["managed_inbox"])
        self.assertEqual(resolved["inbox_identifier"], "managed-inbox")
        self.assertEqual(resolved["label_id"], 17)
        self.assertEqual(resolved["default_assignee_id"], 21)
        self.assertEqual(again["chatwoot_inbox_id"], 9)
        self.assertEqual(
            sum(
                1
                for call in request.call_args_list
                if call.args[0] == "POST" and call.args[1].endswith("/inboxes")
            ),
            1,
        )
        self.assertEqual(
            sum(
                1
                for call in request.call_args_list
                if call.args[0] == "PATCH"
                and call.args[1].endswith("/inboxes/9")
            ),
            2,
        )
        self.assertEqual(
            sum(
                1
                for call in request.call_args_list
                if call.args[0] == "POST" and call.args[1].endswith("/labels")
            ),
            1,
        )
        self.assertEqual(
            sum(
                1
                for call in request.call_args_list
                if call.args[0] == "PATCH" and call.args[1].endswith("/labels/17")
            ),
            1,
        )
        payload = await self.repository.get_config_payload()
        assert payload is not None
        self.assertTrue(payload.account_grouping_enabled)

    async def test_managed_inbox_remains_usable_when_label_api_is_broken(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
                api_access_token="service-account-token",
            )
        )
        config = await self.repository.get_config(
            account_id=self.account.account_id
        )
        assert config is not None

        def fake_request(
            method: str,
            url: str,
            **kwargs: object,
        ) -> tuple[int, object]:
            if method == "GET" and url.endswith("/profile"):
                return 200, {"id": 21}
            if method == "GET" and "/inbox_members/" in url:
                return 200, {"payload": []}
            if method == "POST" and url.endswith("/inbox_members"):
                return 200, {"payload": [{"id": 21}]}
            if method == "GET" and url.endswith("/inboxes"):
                return 200, []
            if method == "POST" and url.endswith("/inboxes"):
                self.assertFalse(
                    kwargs["json_body"]["lock_to_single_conversation"]
                )
                return 200, {
                    "id": 9,
                    "name": "🔴 [闲鱼] chatwoot-test",
                    "channel_type": "Channel::Api",
                    "inbox_identifier": "managed-inbox",
                    "secret": "managed-webhook-secret",
                    "lock_to_single_conversation": False,
                }
            if method == "PATCH" and url.endswith("/inboxes/9"):
                return 200, {}
            if url.endswith("/labels"):
                raise ChatwootIntegrationError("Chatwoot API HTTP 500")
            raise AssertionError(f"unexpected request: {method} {url}")

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            side_effect=fake_request,
        ) as request:
            resolved = await _ensure_managed_account_inbox(
                self.repository,
                config,
            )

        self.assertTrue(resolved["managed_inbox"])
        self.assertEqual(resolved["chatwoot_inbox_id"], 9)
        self.assertIn("HTTP 500", resolved["label_error"])
        self.assertFalse(
            any(
                call.args[0] == "POST" and call.args[1].endswith("/labels")
                for call in request.call_args_list
            )
        )
        payload = await self.repository.get_config_payload()
        assert payload is not None
        self.assertTrue(payload.account_grouping_enabled)

    async def test_metadata_backfill_updates_visible_contact_with_managed_inbox(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
            )
        )
        contact = await self.repository.ensure_contact_map(
            account_id=self.account.account_id,
            peer_user_id="buyer-visible",
            display_name="买家甲",
            avatar_url=None,
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-visible",
            peer_user_id="buyer-visible",
            source_id=str(contact["source_id"]),
            chatwoot_conversation_id="108",
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
        )
        await self.repository.upsert_inbox_binding(
            account_id=self.account.account_id,
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
            webhook_secret="managed-webhook-secret",
            label_id=None,
            label_title=None,
        )
        config = await self.repository.get_config(account_id=self.account.account_id)
        assert config is not None

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._ensure_custom_attribute_definitions",
                new=AsyncMock(return_value=0),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._ensure_managed_account_inbox",
                new=AsyncMock(return_value=config),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
                return_value=(200, {}),
            ) as request,
        ):
            result = await execute_account_metadata_task(
                self.store,
                account_id=self.account.account_id,
                reason="test",
            )

        self.assertTrue(result["token_ready"])
        self.assertEqual(result["contact_updates"], 1)
        identity_call = next(
            call
            for call in request.call_args_list
            if call.args[0] == "PATCH" and "/public/api/v1/inboxes/" in call.args[1]
        )
        payload = identity_call.kwargs["json_body"]
        self.assertEqual(payload["name"], "闲鱼｜chatwoot-test")
        self.assertEqual(
            payload["custom_attributes"]["xianyu_account_name"],
            "chatwoot-test",
        )
        config_payload = await self.repository.get_config_payload()
        assert config_payload is not None
        self.assertEqual(config_payload.status, "ready")

    async def test_metadata_backfill_keeps_historic_disabled_account_identifiable(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
            )
        )
        contact = await self.repository.ensure_contact_map(
            account_id=self.account.account_id,
            peer_user_id="buyer-history",
            display_name="历史买家",
            avatar_url=None,
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-history",
            peer_user_id="buyer-history",
            source_id=str(contact["source_id"]),
            chatwoot_conversation_id="109",
            chatwoot_inbox_id=1,
            inbox_identifier="legacy-inbox",
        )
        await self.store.update_account_workspace_visibility(
            self.account.account_id,
            AccountWorkspaceVisibilityUpdatePayload(chat_enabled=False),
        )

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            return_value=(200, {}),
        ) as request:
            result = await execute_account_metadata_task(
                self.store,
                account_id=self.account.account_id,
                reason="historic-backfill",
            )

        self.assertFalse(result["account_chat_enabled"])
        self.assertEqual(result["contact_updates"], 1)
        self.assertEqual(
            request.call_args.kwargs["json_body"]["name"],
            "闲鱼｜chatwoot-test",
        )

    async def test_base_url_upgrade_preserves_existing_mappings(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
            )
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-https",
            peer_user_id="buyer-https",
            source_id="source-https",
            chatwoot_conversation_id="108",
        )

        updated = await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="https://chatwoot.internal",
            )
        )

        mapping = await self.repository.get_conversation_map(
            self.account.account_id,
            "conversation-https",
        )
        self.assertEqual(updated.base_url, "https://chatwoot.internal")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["chatwoot_conversation_id"], "108")

    async def test_config_exposes_canonical_https_callback_url(self) -> None:
        with patch(
            "apps.api.xianyu_admin_api.chatwoot.settings",
            SimpleNamespace(
                public_base_url="https://192.168.2.3",
                chatwoot_ca_bundle="",
            ),
        ):
            config = await self.repository.upsert_config(
                ChatwootConfigUpdatePayload(
                    enabled=True,
                    base_url="https://192.168.201.2",
                )
            )

        self.assertEqual(
            config.callback_url,
            "https://192.168.2.3/api/integrations/chatwoot/webhook",
        )

    async def test_config_callback_is_always_derived_from_public_url(self) -> None:
        with patch(
            "apps.api.xianyu_admin_api.chatwoot.settings",
            SimpleNamespace(
                public_base_url="https://xianyu.example.test",
                chatwoot_ca_bundle="",
            ),
        ):
            config = await self.repository.upsert_config(
                ChatwootConfigUpdatePayload(
                    enabled=True,
                    base_url="https://chatwoot.internal",
                    api_access_token="service-account-token",
                )
            )

        self.assertEqual(
            config.callback_url,
            "https://xianyu.example.test/api/integrations/chatwoot/webhook",
        )

    def test_chatwoot_request_uses_configured_ca_bundle(self) -> None:
        response = SimpleNamespace(
            status_code=200,
            json=lambda: {"ok": True},
            text="",
        )
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.request.return_value = response
        with tempfile.NamedTemporaryFile() as ca_file, patch(
            "apps.api.xianyu_admin_api.chatwoot.settings",
            SimpleNamespace(
                public_base_url="",
                chatwoot_ca_bundle=ca_file.name,
            ),
        ), patch(
            "apps.api.xianyu_admin_api.chatwoot.requests.Session",
            return_value=client,
        ):
            status, body = _chatwoot_request(
                "GET",
                "https://chatwoot.internal/health",
            )

        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})
        self.assertEqual(client.request.call_args.kwargs["verify"], ca_file.name)
        self.assertEqual(
            client.request.call_args.kwargs["headers"],
            {},
        )

    def test_chatwoot_request_uses_nginx_safe_access_token_header(self) -> None:
        response = SimpleNamespace(
            status_code=200,
            json=lambda: {"ok": True},
            text="",
        )
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.request.return_value = response
        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_tls_verify",
                return_value=True,
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot.requests.Session",
                return_value=client,
            ),
        ):
            _chatwoot_request(
                "GET",
                "https://chatwoot.internal/api/v1/profile",
                token="service-token",
            )

        self.assertEqual(
            client.request.call_args.kwargs["headers"],
            {"api-access-token": "service-token"},
        )

    async def test_verified_webhook_is_durable_and_delivery_id_is_idempotent(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
            )
        )
        await self.repository.upsert_inbox_binding(
            account_id=self.account.account_id,
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
            webhook_secret="webhook-secret-value",
            label_id=None,
            label_title=None,
        )
        body = json.dumps(
            {
                "event": "message_created",
                "id": 42,
                "account": {"id": 3},
                "inbox": {"id": 9},
            },
            separators=(",", ":"),
        ).encode()
        timestamp = str(int(time.time()))
        signature = "sha256=" + hmac.new(
            b"webhook-secret-value",
            f"{timestamp}.".encode() + body,
            hashlib.sha256,
        ).hexdigest()

        with patch(
            "apps.api.xianyu_admin_api.chatwoot.enqueue_background_task",
            new=AsyncMock(return_value=SimpleNamespace(queued=True)),
        ):
            first = await accept_chatwoot_webhook(
                self.store,
                self.repository,
                raw_body=body,
                signature=signature,
                timestamp=timestamp,
                delivery_header="delivery-42",
            )
            second = await accept_chatwoot_webhook(
                self.store,
                self.repository,
                raw_body=body,
                signature=signature,
                timestamp=timestamp,
                delivery_header="delivery-42",
            )

        self.assertTrue(first.accepted)
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        tasks = await self.store.list_background_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_type, "chatwoot.process_webhook")
        config = await self.repository.get_config_payload()
        assert config is not None
        self.assertEqual(config.chatwoot_account_id, 3)

    async def test_outbound_text_client_request_is_idempotent(self) -> None:
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-1",
        )
        first, created = await self.store.begin_outbound_text(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            client_request_id="cw-message-42-text",
            peer_user_id="buyer-1",
            text="reply",
        )
        duplicate, duplicate_created = await self.store.begin_outbound_text(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            client_request_id="cw-message-42-text",
            peer_user_id="buyer-1",
            text="reply",
        )

        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertIsNotNone(first)
        self.assertEqual(first.message_pk, duplicate.message_pk)

    async def test_account_chat_switch_gates_platform_config(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
            )
        )
        enabled = await self.repository.get_config(account_id=self.account.account_id)
        self.assertIsNotNone(enabled)
        self.assertTrue(enabled["enabled"])

        await self.store.update_account_workspace_visibility(
            self.account.account_id,
            AccountWorkspaceVisibilityUpdatePayload(chat_enabled=False),
        )
        disabled = await self.repository.get_config(account_id=self.account.account_id)
        self.assertIsNotNone(disabled)
        self.assertFalse(disabled["enabled"])

    async def test_agent_text_and_image_are_forwarded_and_mapped(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
            )
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-1",
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            peer_user_id="buyer-1",
            source_id="source-1",
            chatwoot_conversation_id="88",
        )
        webhook_payload = {
            "event": "message_created",
            "id": 99,
            "message_type": "outgoing",
            "private": False,
            "content": "客服回复",
            "conversation": {"id": 88},
            "attachments": [
                {
                    "file_type": "image",
                    "data_url": "http://chatwoot.internal:3000/rails/image.jpg",
                }
            ],
        }
        raw = json.dumps(webhook_payload).encode()
        await self.repository.record_webhook(
            delivery_id="delivery-agent-message",
            event_name="message_created",
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_payload=raw,
        )

        async def runtime_command(action, _account_id, _payload):
            suffix = "text" if action == "text" else "image"
            return {
                "success": True,
                "message": {"message_pk": f"local-{suffix}"},
            }

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._download_image",
            return_value=(b"image-bytes", "image/jpeg", "image.jpg"),
        ):
            result = await execute_webhook_task(
                self.store,
                delivery_id="delivery-agent-message",
                runtime_command=runtime_command,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["pieces"], 2)
        mappings = await self.repository.find_message_maps_by_remote(
            self.account.account_id,
            "99",
        )
        self.assertEqual(
            {item["message_pk"] for item in mappings},
            {"local-text", "local-image"},
        )

    async def test_agent_audio_is_blocked_with_private_note(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
                api_access_token="service-token",
            )
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-audio",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-audio",
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-audio",
            peer_user_id="buyer-audio",
            source_id="source-audio",
            chatwoot_conversation_id="188",
        )
        webhook_payload = {
            "event": "message_created",
            "id": 199,
            "message_type": "outgoing",
            "private": False,
            "conversation": {"id": 188},
            "attachments": [
                {
                    "file_type": "audio",
                    "data_url": "http://chatwoot.internal/audio.mp3",
                }
            ],
        }
        raw = json.dumps(webhook_payload).encode()
        await self.repository.record_webhook(
            delivery_id="delivery-agent-audio",
            event_name="message_created",
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_payload=raw,
        )
        runtime_command = AsyncMock()

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._create_private_delivery_note",
            new=AsyncMock(return_value=True),
        ) as create_note:
            result = await execute_webhook_task(
                self.store,
                delivery_id="delivery-agent-audio",
                runtime_command=runtime_command,
            )

        self.assertTrue(result["skipped"])
        self.assertTrue(result["private_note_created"])
        self.assertEqual(
            result["reason"],
            CHATWOOT_OUTBOUND_AUDIO_UNSUPPORTED_MESSAGE,
        )
        runtime_command.assert_not_awaited()
        create_note.assert_awaited_once()
        mappings = await self.repository.find_message_maps_by_remote(
            self.account.account_id,
            "199",
        )
        self.assertEqual(mappings[0]["state"], "audio_unsupported")

    async def test_local_audio_is_uploaded_to_chatwoot_without_transcoding(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
            )
        )
        message = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-local-audio",
            direction="inbound",
            message_type="audio",
            content="[语音 2秒]",
            peer_user_id="buyer-local-audio",
            attachments=[
                {
                    "attachment_type": "audio",
                    "remote_url": (
                        "http://voice.oss-cn-hangzhou.aliyuncs.com/message.amr"
                    ),
                    "mime_type": "audio/amr",
                    "size_bytes": 4070,
                }
            ],
        )
        self.assertIsNotNone(message)
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-local-audio",
            peer_user_id="buyer-local-audio",
            source_id="source-local-audio",
            chatwoot_conversation_id="288",
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
        )
        await self.repository.upsert_inbox_binding(
            account_id=self.account.account_id,
            chatwoot_inbox_id=9,
            inbox_identifier="managed-inbox",
            webhook_secret="managed-webhook-secret",
            label_id=None,
            label_title=None,
        )
        config = await self.repository.get_config(account_id=self.account.account_id)
        assert config is not None

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._ensure_managed_account_inbox",
                new=AsyncMock(return_value=config),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._download_xianyu_audio",
                return_value=(b"#!AMR\nvoice-bytes", "audio/amr", "voice.amr"),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
                return_value=(200, {"id": 299}),
            ) as request,
        ):
            result = await execute_local_message_task(
                self.store,
                account_id=self.account.account_id,
                message_pk=message.message_pk,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["attachments"], 1)
        files = request.call_args.kwargs["files"]
        self.assertEqual(files[0][1], ("voice.amr", b"#!AMR\nvoice-bytes", "audio/amr"))
        self.assertEqual(
            request.call_args.kwargs["data"]["content"],
            "buyer-local-audio：[语音 2秒]",
        )

    async def test_local_recall_creates_official_chatwoot_private_snapshot(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
                api_access_token="service-token",
            )
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-recall-note",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-recall-note",
        )
        message = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-recall-note",
            direction="outbound",
            message_type="text",
            content="reply",
            message_id="platform-recall-note",
            peer_user_id="buyer-recall-note",
            send_success=True,
        )
        self.assertIsNotNone(message)
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-recall-note",
            peer_user_id="buyer-recall-note",
            source_id="source-recall-note",
            chatwoot_conversation_id="388",
        )
        await self.repository.record_message_map(
            account_id=self.account.account_id,
            message_pk=message.message_pk,
            chatwoot_message_id="399",
            chatwoot_conversation_id="388",
            origin="xianyu",
            state="synced",
        )
        await self.store.mark_message_recalled(
            self.account.account_id,
            "conversation-recall-note",
            message.message_pk,
        )

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_recall_snapshot_exists",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._create_private_recall_snapshot",
                new=AsyncMock(return_value=True),
            ) as create_snapshot,
        ):
            result = await execute_local_message_task(
                self.store,
                account_id=self.account.account_id,
                message_pk=message.message_pk,
            )

        self.assertEqual(result["action"], "recalled")
        self.assertEqual(result["representation"], "private_snapshot")
        self.assertTrue(result["private_snapshot_created"])
        create_snapshot.assert_awaited_once_with(
            ANY,
            chatwoot_conversation_id="388",
            chatwoot_message_id="399",
            contexts=[ANY],
            succeeded=True,
            error=None,
        )

    async def test_webhook_routes_to_the_account_owned_by_the_conversation(self) -> None:
        second_account = await self.store.create_account(
            AccountCreatePayload(enabled=True,
                chat_enabled=True,
            )
        )
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
            )
        )
        await self.store.record_message(
            account_id=second_account.account_id,
            conversation_id="conversation-2",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-2",
        )
        await self.repository.create_conversation_map(
            account_id=second_account.account_id,
            conversation_id="conversation-2",
            peer_user_id="buyer-2",
            source_id="source-2",
            chatwoot_conversation_id="89",
        )
        webhook_payload = {
            "event": "message_created",
            "id": 100,
            "message_type": "outgoing",
            "private": False,
            "content": "第二个账户的回复",
            "conversation": {"id": 89},
        }
        raw = json.dumps(webhook_payload).encode()
        await self.repository.record_webhook(
            delivery_id="delivery-second-account",
            event_name="message_created",
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_payload=raw,
        )
        runtime_command = AsyncMock(
            return_value={"success": True, "message": {"message_pk": "local-second"}}
        )

        result = await execute_webhook_task(
            self.store,
            delivery_id="delivery-second-account",
            runtime_command=runtime_command,
        )

        self.assertTrue(result["ok"])
        runtime_command.assert_awaited_once()
        self.assertEqual(runtime_command.await_args.args[1], second_account.account_id)

    async def test_read_reconciliation_clears_viewer_state_but_keeps_platform_baseline(
        self,
    ) -> None:
        first_user = await self.store.create_user(
            UserCreatePayload(username="chatwoot-reader-one", password="12345678")
        )
        second_user = await self.store.create_user(
            UserCreatePayload(username="chatwoot-reader-two", password="12345678")
        )
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
                api_access_token="service-token",
            )
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-read-sync",
            direction="inbound",
            message_type="text",
            content="需要查看",
            message_id="read-sync-message-1",
            peer_user_id="buyer-read-sync",
            created_at_ms=1_800_000_000_123,
        )
        late_user = await self.store.create_user(
            UserCreatePayload(username="chatwoot-reader-late", password="12345678")
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-read-sync",
            peer_user_id="buyer-read-sync",
            source_id="source-read-sync",
            chatwoot_conversation_id="501",
        )

        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            return_value=(
                200,
                {
                    "id": 501,
                    "unread_count": 0,
                    "agent_last_seen_at": 1_800_000_001,
                },
            ),
        ) as request:
            result = await reconcile_chatwoot_read_states(self.store)

        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["read_synced_users"], 3)
        self.assertEqual(
            {event["user_id"] for event in result["events"]},
            {first_user.user_id, second_user.user_id, late_user.user_id},
        )
        request.assert_called_once()

        first_items, _, _ = await self.store.list_conversations_for_user(
            first_user.user_id,
            status="all",
        )
        second_items, _, _ = await self.store.list_conversations_for_user(
            second_user.user_id,
            status="all",
        )
        late_items, _, _ = await self.store.list_conversations_for_user(
            late_user.user_id,
            status="all",
        )
        self.assertEqual(first_items[0].viewer_unread_count, 0)
        self.assertEqual(second_items[0].viewer_unread_count, 0)
        self.assertEqual(late_items[0].viewer_unread_count, 0)
        with self.session_factory() as session:
            conversation = session.scalar(
                select(ConversationORM).where(
                    ConversationORM.account_id == self.account.account_id,
                    ConversationORM.conversation_id == "conversation-read-sync",
                )
            )
            mapping = session.scalar(
                select(ChatwootConversationORM).where(
                    ChatwootConversationORM.chatwoot_conversation_id == "501"
                )
            )
            self.assertIsNotNone(conversation)
            self.assertEqual(conversation.unread_count, 1)
            self.assertTrue(conversation.needs_reply)
            self.assertIsNotNone(mapping.remote_agent_last_seen_at)
            self.assertIsNotNone(mapping.read_synced_at)

        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-read-sync",
            direction="inbound",
            message_type="text",
            content="查看之后的新消息",
            message_id="read-sync-message-2",
            peer_user_id="buyer-read-sync",
            created_at_ms=1_800_000_002_123,
        )
        with patch(
            "apps.api.xianyu_admin_api.chatwoot._chatwoot_request",
            return_value=(
                200,
                {
                    "id": 501,
                    "unread_count": 0,
                    "agent_last_seen_at": 1_800_000_001,
                },
            ),
        ):
            stale_result = await reconcile_chatwoot_read_states(self.store)
        self.assertEqual(stale_result["read_synced_users"], 0)
        first_items, _, _ = await self.store.list_conversations_for_user(
            first_user.user_id,
            status="all",
        )
        self.assertEqual(first_items[0].viewer_unread_count, 1)

    async def test_webhook_snapshot_fast_path_publishes_shared_read_events(self) -> None:
        user = await self.store.create_user(
            UserCreatePayload(username="chatwoot-webhook-reader", password="12345678")
        )
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
            )
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-webhook-read",
            direction="inbound",
            message_type="text",
            content="Webhook 查看",
            message_id="webhook-read-message",
            peer_user_id="buyer-webhook-read",
            created_at_ms=1_800_000_010_123,
        )
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-webhook-read",
            peer_user_id="buyer-webhook-read",
            source_id="source-webhook-read",
            chatwoot_conversation_id="502",
        )
        webhook_payload = {
            "event": "conversation_updated",
            "id": 502,
            "status": "open",
            "unread_count": 0,
            "agent_last_seen_at": 1_800_000_011,
        }
        raw = json.dumps(webhook_payload).encode()
        await self.repository.record_webhook(
            delivery_id="delivery-read-fast-path",
            event_name="conversation_updated",
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_payload=raw,
        )
        notifier = AsyncMock()

        result = await execute_webhook_task(
            self.store,
            delivery_id="delivery-read-fast-path",
            runtime_command=AsyncMock(),
            read_notifier=notifier,
        )

        self.assertEqual(result["read_synced_users"], 1)
        notifier.assert_awaited_once()
        self.assertEqual(notifier.await_args.args[0]["user_id"], user.user_id)
        items, _, _ = await self.store.list_conversations_for_user(
            user.user_id,
            status="all",
        )
        self.assertEqual(items[0].viewer_unread_count, 0)

    async def test_deleted_agent_message_calls_platform_recall_and_reports_result(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
                api_access_token="service-token",
            )
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-1",
        )
        outbound = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="outbound",
            message_type="text",
            content="reply",
            message_id="platform-message-1",
            peer_user_id="buyer-1",
            send_success=True,
        )
        assert outbound is not None
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            peer_user_id="buyer-1",
            source_id="source-1",
            chatwoot_conversation_id="88",
        )
        await self.repository.record_message_map(
            account_id=self.account.account_id,
            message_pk=outbound.message_pk,
            chatwoot_message_id="99",
            chatwoot_conversation_id="88",
            origin="chatwoot",
            state="synced",
        )
        webhook_payload = {
            "event": "message_updated",
            "id": 99,
            "message_type": "outgoing",
            "content_attributes": {"deleted": True},
            "conversation": {"id": 88},
        }
        raw = json.dumps(webhook_payload).encode()
        await self.repository.record_webhook(
            delivery_id="delivery-recall",
            event_name="message_updated",
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_payload=raw,
        )
        runtime_command = AsyncMock(
            return_value={
                "success": True,
                "message_pk": outbound.message_pk,
            }
        )

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_recall_snapshot_exists",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._create_private_recall_snapshot",
                new=AsyncMock(return_value=True),
            ) as create_snapshot,
        ):
            result = await execute_webhook_task(
                self.store,
                delivery_id="delivery-recall",
                runtime_command=runtime_command,
            )
            await self.repository.record_webhook(
                delivery_id="delivery-recall-duplicate",
                event_name="message_updated",
                payload_sha256=hashlib.sha256(raw).hexdigest(),
                raw_payload=raw,
            )
            duplicate_result = await execute_webhook_task(
                self.store,
                delivery_id="delivery-recall-duplicate",
                runtime_command=runtime_command,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["platform_recall"])
        self.assertEqual(result["remote_deleted"], 1)
        self.assertEqual(result["recalled_messages"], 1)
        self.assertTrue(duplicate_result["ok"])
        self.assertEqual(duplicate_result["recalled_messages"], 1)
        runtime_command.assert_awaited_once_with(
            "recall",
            self.account.account_id,
            {
                "conversation_id": "conversation-1",
                "message_pk": outbound.message_pk,
            },
        )
        create_snapshot.assert_awaited_once()
        snapshot_kwargs = create_snapshot.await_args.kwargs
        self.assertEqual(snapshot_kwargs["chatwoot_conversation_id"], "88")
        self.assertEqual(snapshot_kwargs["chatwoot_message_id"], "99")
        self.assertTrue(snapshot_kwargs["succeeded"])
        self.assertIsNone(snapshot_kwargs["error"])
        self.assertEqual(snapshot_kwargs["contexts"][0]["content"], "reply")
        self.assertEqual(
            snapshot_kwargs["contexts"][0]["message_pk"],
            outbound.message_pk,
        )
        self.assertTrue(result["private_snapshot_created"])
        self.assertFalse(duplicate_result["private_snapshot_created"])
        create_snapshot.assert_awaited_once_with(
            ANY,
            chatwoot_conversation_id="88",
            chatwoot_message_id="99",
            contexts=ANY,
            succeeded=True,
            error=None,
        )
        mappings = await self.repository.find_message_maps_by_remote(
            self.account.account_id,
            "99",
        )
        self.assertEqual(mappings[0]["state"], "recalled")

    async def test_deleted_message_retries_snapshot_without_recalling_again(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
                api_access_token="service-token",
            )
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-snapshot-retry",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-snapshot-retry",
        )
        outbound = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-snapshot-retry",
            direction="outbound",
            message_type="text",
            content="需要恢复的原消息",
            message_id="platform-snapshot-retry",
            peer_user_id="buyer-snapshot-retry",
            send_success=True,
        )
        assert outbound is not None
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-snapshot-retry",
            peer_user_id="buyer-snapshot-retry",
            source_id="source-snapshot-retry",
            chatwoot_conversation_id="388",
        )
        await self.repository.record_message_map(
            account_id=self.account.account_id,
            message_pk=outbound.message_pk,
            chatwoot_message_id="399",
            chatwoot_conversation_id="388",
            origin="chatwoot",
            state="synced",
        )
        webhook_payload = {
            "event": "message_updated",
            "id": 399,
            "message_type": "outgoing",
            "content_attributes": {"deleted": True},
            "conversation": {"id": 388},
        }
        raw = json.dumps(webhook_payload).encode()
        await self.repository.record_webhook(
            delivery_id="delivery-snapshot-retry",
            event_name="message_updated",
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_payload=raw,
        )
        runtime_command = AsyncMock(
            return_value={
                "success": True,
                "message_pk": outbound.message_pk,
            }
        )
        create_snapshot = AsyncMock(
            side_effect=[RuntimeError("Chatwoot temporarily unavailable"), True]
        )

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_recall_snapshot_exists",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._create_private_recall_snapshot",
                new=create_snapshot,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "temporarily unavailable"):
                await execute_webhook_task(
                    self.store,
                    delivery_id="delivery-snapshot-retry",
                    runtime_command=runtime_command,
                )
            pending = await self.repository.find_message_maps_by_remote(
                self.account.account_id,
                "399",
            )
            self.assertEqual(pending[0]["state"], "recall_snapshot_pending")

            result = await execute_webhook_task(
                self.store,
                delivery_id="delivery-snapshot-retry",
                runtime_command=runtime_command,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["private_snapshot_created"])
        runtime_command.assert_awaited_once()
        self.assertEqual(create_snapshot.await_count, 2)
        mappings = await self.repository.find_message_maps_by_remote(
            self.account.account_id,
            "399",
        )
        self.assertEqual(mappings[0]["state"], "recalled")

    async def test_deleted_agent_message_reports_platform_recall_failure(
        self,
    ) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
                api_access_token="service-token",
            )
        )
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-delete-failed",
            direction="inbound",
            message_type="text",
            content="hello",
            peer_user_id="buyer-delete-failed",
        )
        outbound = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-delete-failed",
            direction="outbound",
            message_type="text",
            content="reply",
            message_id="platform-delete-failed",
            peer_user_id="buyer-delete-failed",
            send_success=True,
        )
        assert outbound is not None
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-delete-failed",
            peer_user_id="buyer-delete-failed",
            source_id="source-delete-failed",
            chatwoot_conversation_id="188",
        )
        await self.repository.record_message_map(
            account_id=self.account.account_id,
            message_pk=outbound.message_pk,
            chatwoot_message_id="199",
            chatwoot_conversation_id="188",
            origin="chatwoot",
            state="synced",
        )
        webhook_payload = {
            "event": "message_updated",
            "id": 199,
            "message_type": "outgoing",
            "content_attributes": {"deleted": True},
            "conversation": {"id": 188},
        }
        raw = json.dumps(webhook_payload).encode()
        await self.repository.record_webhook(
            delivery_id="delivery-delete-failed",
            event_name="message_updated",
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_payload=raw,
        )
        runtime_command = AsyncMock(
            return_value={
                "success": False,
                "error": "消息已超过两分钟撤回时限",
            }
        )

        with (
            patch(
                "apps.api.xianyu_admin_api.chatwoot._chatwoot_recall_snapshot_exists",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "apps.api.xianyu_admin_api.chatwoot._create_private_recall_snapshot",
                new=AsyncMock(return_value=True),
            ) as create_snapshot,
        ):
            result = await execute_webhook_task(
                self.store,
                delivery_id="delivery-delete-failed",
                runtime_command=runtime_command,
            )

        self.assertFalse(result["ok"])
        self.assertTrue(result["platform_recall"])
        self.assertEqual(result["failed_messages"], 1)
        create_snapshot.assert_awaited_once()
        self.assertIn(
            "消息已超过两分钟撤回时限",
            create_snapshot.await_args.kwargs["error"],
        )
        self.assertEqual(
            create_snapshot.await_args.kwargs["contexts"][0]["content"],
            "reply",
        )
        mappings = await self.repository.find_message_maps_by_remote(
            self.account.account_id,
            "199",
        )
        self.assertEqual(mappings[0]["state"], "recall_failed")
        self.assertEqual(mappings[0]["error"], "消息已超过两分钟撤回时限")

    async def test_deleted_incoming_message_remains_chatwoot_only(self) -> None:
        await self.repository.upsert_config(
            ChatwootConfigUpdatePayload(
                enabled=True,
                base_url="http://chatwoot.internal:3000",
            )
        )
        inbound = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-incoming-delete",
            direction="inbound",
            message_type="text",
            content="hello",
            message_id="platform-incoming-delete",
            peer_user_id="buyer-incoming-delete",
        )
        assert inbound is not None
        await self.repository.create_conversation_map(
            account_id=self.account.account_id,
            conversation_id="conversation-incoming-delete",
            peer_user_id="buyer-incoming-delete",
            source_id="source-incoming-delete",
            chatwoot_conversation_id="288",
        )
        await self.repository.record_message_map(
            account_id=self.account.account_id,
            message_pk=inbound.message_pk,
            chatwoot_message_id="299",
            chatwoot_conversation_id="288",
            origin="xianyu",
            state="synced",
        )
        webhook_payload = {
            "event": "message_updated",
            "id": 299,
            "message_type": "incoming",
            "content_attributes": {"deleted": True},
            "conversation": {"id": 288},
        }
        raw = json.dumps(webhook_payload).encode()
        await self.repository.record_webhook(
            delivery_id="delivery-incoming-delete",
            event_name="message_updated",
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_payload=raw,
        )
        runtime_command = AsyncMock()

        result = await execute_webhook_task(
            self.store,
            delivery_id="delivery-incoming-delete",
            runtime_command=runtime_command,
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["platform_recall"])
        runtime_command.assert_not_awaited()
        mappings = await self.repository.find_message_maps_by_remote(
            self.account.account_id,
            "299",
        )
        self.assertEqual(mappings[0]["state"], "remote_deleted")

if __name__ == "__main__":
    unittest.main()
