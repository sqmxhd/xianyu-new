import os
import tempfile
import unittest

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.schemas import WebNotificationConfigUpdatePayload
from apps.api.xianyu_admin_api.web_notifications import (
    MAX_WEB_NOTIFICATION_SOUND_BYTES,
    WebNotificationRepository,
    WebNotificationSoundError,
    WebNotificationSoundStorage,
)


def wav_bytes(payload: bytes = b"\x00\x00\x00\x00") -> bytes:
    return b"RIFF" + (len(payload) + 4).to_bytes(4, "little") + b"WAVE" + payload


class WebNotificationSoundStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.storage = WebNotificationSoundStorage(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_sound_is_detected_named_and_stored_by_content_hash(self) -> None:
        stored = self.storage.save(wav_bytes(), "../客户提醒.wav")

        self.assertEqual(stored.mime_type, "audio/wav")
        self.assertEqual(stored.original_filename, "客户提醒.wav")
        self.assertEqual(stored.size_bytes, len(wav_bytes()))
        self.assertTrue(self.storage.path(stored.key).is_file())
        self.assertEqual(self.storage.path(stored.key).read_bytes(), wav_bytes())

    def test_invalid_and_oversized_files_are_rejected(self) -> None:
        with self.assertRaisesRegex(WebNotificationSoundError, "仅支持"):
            self.storage.save(b"not audio", "sound.mp3")
        with self.assertRaisesRegex(WebNotificationSoundError, "5 MB"):
            self.storage.save(
                b"ID3" + b"\0" * MAX_WEB_NOTIFICATION_SOUND_BYTES,
                "sound.mp3",
            )
        with self.assertRaises(WebNotificationSoundError):
            self.storage.path("../../outside.mp3")


class WebNotificationRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
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
        self.repository = WebNotificationRepository(self.session_factory)
        self.temporary = tempfile.TemporaryDirectory()
        self.storage = WebNotificationSoundStorage(self.temporary.name)

    async def asyncTearDown(self) -> None:
        self.engine.dispose()
        self.temporary.cleanup()

    async def test_default_toggle_upload_and_reset_are_platform_wide(self) -> None:
        initial = await self.repository.get_config()
        self.assertTrue(initial.enabled)
        self.assertFalse(initial.has_custom_sound)
        self.assertIsNone(initial.sound_url)

        disabled = await self.repository.update_config(
            WebNotificationConfigUpdatePayload(enabled=False)
        )
        self.assertFalse(disabled.enabled)

        sound = self.storage.save(wav_bytes(b"ding"), "ding.wav")
        uploaded, previous_key = await self.repository.set_sound(sound)
        self.assertIsNone(previous_key)
        self.assertTrue(uploaded.has_custom_sound)
        self.assertEqual(uploaded.sound_filename, "ding.wav")
        self.assertIn(sound.sha256[:12], uploaded.sound_url or "")
        self.assertEqual(
            await self.repository.get_sound_record(),
            (sound.key, "audio/wav", "ding.wav"),
        )

        reset, removed_key = await self.repository.clear_sound()
        self.assertEqual(removed_key, sound.key)
        self.assertFalse(reset.has_custom_sound)
        self.assertIsNone(await self.repository.get_sound_record())


if __name__ == "__main__":
    unittest.main()
