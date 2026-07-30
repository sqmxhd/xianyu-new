"""Platform-wide browser notification sound settings and storage."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .executors import run_db_blocking
from .orm import WebNotificationConfigORM, utcnow
from .schemas import (
    WebNotificationConfigPayload,
    WebNotificationConfigUpdatePayload,
)
from .settings import settings


WEB_NOTIFICATION_CONFIG_ID = "default"
MAX_WEB_NOTIFICATION_SOUND_BYTES = 5 * 1024 * 1024
SOUND_URL_PATH = "/api/web-notification/sound"
SAFE_SOUND_KEY = re.compile(r"^[a-f0-9]{64}\.(?:mp3|wav|ogg|m4a)$")


class WebNotificationSoundError(ValueError):
    """Raised when an uploaded browser notification sound is invalid."""


@dataclass(slots=True, frozen=True)
class PreparedNotificationSound:
    key: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str


def _detect_audio(raw: bytes) -> tuple[str, str] | None:
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        return "wav", "audio/wav"
    if raw.startswith(b"OggS"):
        return "ogg", "audio/ogg"
    if raw.startswith(b"ID3") or (
        len(raw) >= 2 and raw[0] == 0xFF and raw[1] & 0xE0 == 0xE0
    ):
        return "mp3", "audio/mpeg"
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        return "m4a", "audio/mp4"
    return None


class WebNotificationSoundStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.web_notification_sound_dir).resolve()

    def save(self, raw: bytes, filename: str | None) -> PreparedNotificationSound:
        if not raw:
            raise WebNotificationSoundError("铃声文件为空")
        if len(raw) > MAX_WEB_NOTIFICATION_SOUND_BYTES:
            raise WebNotificationSoundError("铃声文件不能超过 5 MB")
        detected = _detect_audio(raw)
        if detected is None:
            raise WebNotificationSoundError("仅支持 MP3、WAV、OGG 或 M4A 铃声文件")
        extension, mime_type = detected
        digest = hashlib.sha256(raw).hexdigest()
        key = f"{digest}.{extension}"
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(raw)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        safe_filename = Path(filename or f"notification.{extension}").name.strip()
        if not safe_filename:
            safe_filename = f"notification.{extension}"
        return PreparedNotificationSound(
            key=key,
            original_filename=safe_filename[:255],
            mime_type=mime_type,
            size_bytes=len(raw),
            sha256=digest,
        )

    def path(self, key: str) -> Path:
        if not SAFE_SOUND_KEY.fullmatch(key):
            raise WebNotificationSoundError("无效的铃声文件标识")
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise WebNotificationSoundError("铃声文件路径越界")
        return target

    def delete(self, key: str | None) -> None:
        if not key:
            return
        self.path(key).unlink(missing_ok=True)


class WebNotificationRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    async def get_config(self) -> WebNotificationConfigPayload:
        return await run_db_blocking(self._get_config_sync)

    async def update_config(
        self,
        payload: WebNotificationConfigUpdatePayload,
    ) -> WebNotificationConfigPayload:
        return await run_db_blocking(self._update_config_sync, payload)

    async def set_sound(
        self,
        sound: PreparedNotificationSound,
    ) -> tuple[WebNotificationConfigPayload, str | None]:
        return await run_db_blocking(self._set_sound_sync, sound)

    async def clear_sound(self) -> tuple[WebNotificationConfigPayload, str | None]:
        return await run_db_blocking(self._clear_sound_sync)

    async def get_sound_record(self) -> tuple[str, str, str] | None:
        return await run_db_blocking(self._get_sound_record_sync)

    @staticmethod
    def _payload(row: WebNotificationConfigORM) -> WebNotificationConfigPayload:
        has_custom_sound = bool(row.sound_key and row.sound_sha256)
        return WebNotificationConfigPayload(
            config_id=row.config_id,
            enabled=row.enabled,
            has_custom_sound=has_custom_sound,
            sound_filename=row.sound_filename if has_custom_sound else None,
            sound_mime_type=row.sound_mime_type if has_custom_sound else None,
            sound_size_bytes=row.sound_size_bytes if has_custom_sound else None,
            sound_sha256=row.sound_sha256 if has_custom_sound else None,
            sound_url=(
                f"{SOUND_URL_PATH}?v={row.sound_sha256[:12]}"
                if has_custom_sound and row.sound_sha256
                else None
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _get_or_create(self, session: Session) -> WebNotificationConfigORM:
        row = session.get(WebNotificationConfigORM, WEB_NOTIFICATION_CONFIG_ID)
        if row is None:
            row = WebNotificationConfigORM(
                config_id=WEB_NOTIFICATION_CONFIG_ID,
                enabled=True,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                row = session.get(WebNotificationConfigORM, WEB_NOTIFICATION_CONFIG_ID)
                if row is None:
                    raise
        return row

    def _get_config_sync(self) -> WebNotificationConfigPayload:
        with self._session_factory() as session:
            return self._payload(self._get_or_create(session))

    def _update_config_sync(
        self,
        payload: WebNotificationConfigUpdatePayload,
    ) -> WebNotificationConfigPayload:
        with self._session_factory() as session:
            row = self._get_or_create(session)
            row.enabled = payload.enabled
            row.updated_at = utcnow()
            session.commit()
            return self._payload(row)

    def _set_sound_sync(
        self,
        sound: PreparedNotificationSound,
    ) -> tuple[WebNotificationConfigPayload, str | None]:
        with self._session_factory() as session:
            row = self._get_or_create(session)
            previous_key = row.sound_key
            row.sound_key = sound.key
            row.sound_filename = sound.original_filename
            row.sound_mime_type = sound.mime_type
            row.sound_size_bytes = sound.size_bytes
            row.sound_sha256 = sound.sha256
            row.updated_at = utcnow()
            session.commit()
            return self._payload(row), previous_key

    def _clear_sound_sync(self) -> tuple[WebNotificationConfigPayload, str | None]:
        with self._session_factory() as session:
            row = self._get_or_create(session)
            previous_key = row.sound_key
            row.sound_key = None
            row.sound_filename = None
            row.sound_mime_type = None
            row.sound_size_bytes = None
            row.sound_sha256 = None
            row.updated_at = utcnow()
            session.commit()
            return self._payload(row), previous_key

    def _get_sound_record_sync(self) -> tuple[str, str, str] | None:
        with self._session_factory() as session:
            row = session.get(WebNotificationConfigORM, WEB_NOTIFICATION_CONFIG_ID)
            if not row or not row.sound_key or not row.sound_mime_type:
                return None
            return (
                row.sound_key,
                row.sound_mime_type,
                row.sound_filename or "notification-sound",
            )


web_notification_sound_storage = WebNotificationSoundStorage()
