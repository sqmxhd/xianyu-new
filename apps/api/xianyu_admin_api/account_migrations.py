"""Encrypted account migration archives and safe browser-profile transport."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Literal

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .browser_profiles import BrowserProfileStorage, PROFILE_MANIFEST
from .schemas import AccountBrowserIdentityPayload
from .store import AccountRecord


ARCHIVE_FORMAT = "xianyu-account-migration"
ARCHIVE_SCHEMA_VERSION = 1
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_FILES = 50_000
SESSION_TTL_SECONDS = 15 * 60
KDF_N = 2**15
KDF_R = 8
KDF_P = 1

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9\u4e00-\u9fff._-]+")
_EXCLUDED_DIRECTORY_NAMES = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "Crashpad",
    "ShaderCache",
    "component_crx_cache",
}
_EXCLUDED_FILE_NAMES = {
    PROFILE_MANIFEST,
    "SingletonCookie",
    "SingletonLock",
    "SingletonSocket",
    "chrome_debug.log",
}


class AccountMigrationError(RuntimeError):
    pass


class MigratedProxy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    scheme: Literal["socks5", "socks5h"] = "socks5h"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)


class MigratedAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_account_id: str = Field(min_length=1, max_length=64)
    platform: Literal["xianyu"] = "xianyu"
    platform_user_id: str | None = Field(default=None, max_length=128)
    platform_display_name: str | None = Field(default=None, max_length=255)
    platform_avatar_url: str | None = Field(default=None, max_length=1000)
    remark: str | None = Field(default=None, max_length=500)
    cookie: str = Field(default="", max_length=10000)
    desired_enabled: bool = True
    conversation_visible: bool = True
    desired_chat_enabled: bool = False
    order_management_visible: bool = True
    product_management_visible: bool = True
    browser_identity: AccountBrowserIdentityPayload
    source_fingerprint_snapshot: dict[str, Any] | None = None
    proxy: MigratedProxy | None = None
    profile_present: bool = False
    exported_at: datetime

    @field_validator("cookie", mode="before")
    @classmethod
    def normalize_cookie(cls, value: object) -> str:
        return str(value or "").strip()

    @property
    def cookie_user_id(self) -> str | None:
        for part in self.cookie.split(";"):
            name, separator, value = part.strip().partition("=")
            if separator and name == "unb" and value.strip():
                return value.strip()
        return None


@dataclass(frozen=True, slots=True)
class MigrationPackage:
    path: Path
    filename: str


@dataclass(slots=True)
class StagedAccountMigration:
    session_id: str
    root: Path
    account: MigratedAccount
    profile_path: Path | None
    profile_size_bytes: int
    profile_file_count: int
    archive_size_bytes: int
    expires_at: datetime


class AccountMigrationArchiveService:
    def __init__(
        self,
        profile_storage: BrowserProfileStorage,
        *,
        staging_root: str | Path | None = None,
        max_archive_bytes: int = MAX_ARCHIVE_BYTES,
        max_extracted_bytes: int = MAX_EXTRACTED_BYTES,
        max_files: int = MAX_ARCHIVE_FILES,
    ) -> None:
        self.profile_storage = profile_storage
        # Keep transient archives beside, rather than inside, the profile root.
        # Otherwise BrowserProfileStorage would expose this directory as an orphan
        # browser profile while an export/import is in progress.
        self.staging_root = Path(
            staging_root or (profile_storage.root.parent / ".account-migrations")
        ).resolve()
        self.max_archive_bytes = max_archive_bytes
        self.max_extracted_bytes = max_extracted_bytes
        self.max_files = max_files
        self._sessions: dict[str, StagedAccountMigration] = {}
        self._session_timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def create_package(self, account: AccountRecord, password: str) -> MigrationPackage:
        self._validate_password(password)
        self._prepare_root()
        work_root = Path(tempfile.mkdtemp(prefix="export-", dir=self.staging_root))
        try:
            profile = self.profile_storage.account_path(account.account_id)
            profile_present = profile.is_dir() and not profile.is_symlink()
            migrated = self._migrated_account(account, profile_present=profile_present)
            compressed_payload = work_root / "payload.tar.gz"
            self._write_compressed_payload(compressed_payload, migrated, profile if profile_present else None)
            if compressed_payload.stat().st_size > self.max_archive_bytes:
                raise AccountMigrationError("账户迁移包超过 512 MiB，请先清理浏览器缓存后重试")

            encrypted_payload = work_root / "payload.enc"
            salt = os.urandom(16)
            nonce = os.urandom(12)
            tag, ciphertext_sha256 = self._encrypt_file(
                compressed_payload,
                encrypted_payload,
                password,
                salt,
                nonce,
            )
            manifest = {
                "format": ARCHIVE_FORMAT,
                "schema_version": ARCHIVE_SCHEMA_VERSION,
                "encryption": "AES-256-GCM",
                "kdf": {
                    "name": "scrypt",
                    "n": KDF_N,
                    "r": KDF_R,
                    "p": KDF_P,
                    "salt": self._b64(salt),
                },
                "nonce": self._b64(nonce),
                "tag": self._b64(tag),
                "ciphertext_sha256": ciphertext_sha256,
                "created_at": datetime.now(UTC).isoformat(),
            }
            filename = self._package_filename(account)
            archive = work_root / filename
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
                bundle.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
                )
                bundle.write(encrypted_payload, "payload.enc")
            if archive.stat().st_size > self.max_archive_bytes:
                raise AccountMigrationError("账户迁移包超过 512 MiB，请先清理浏览器缓存后重试")
            compressed_payload.unlink(missing_ok=True)
            encrypted_payload.unlink(missing_ok=True)
            return MigrationPackage(path=archive, filename=filename)
        except Exception:
            shutil.rmtree(work_root, ignore_errors=True)
            raise

    def inspect_package(
        self,
        stream: BinaryIO,
        filename: str,
        password: str,
    ) -> StagedAccountMigration:
        self._validate_password(password)
        if not str(filename or "").lower().endswith(".zip"):
            raise AccountMigrationError("请选择 .xianyu.zip 账户迁移包")
        self._prepare_root()
        self.cleanup_expired()
        session_id = uuid.uuid4().hex
        stage_root = Path(tempfile.mkdtemp(prefix=f"import-{session_id}-", dir=self.staging_root))
        archive = stage_root / "upload.zip"
        try:
            archive_size = self._copy_limited(stream, archive, self.max_archive_bytes)
            manifest, encrypted_info = self._read_outer_archive(archive)
            decrypted = stage_root / "payload.tar.gz"
            self._decrypt_file_from_zip(
                archive,
                encrypted_info,
                decrypted,
                password,
                manifest,
            )
            extracted = stage_root / "extracted"
            account, profile_path, profile_size, profile_files = self._extract_payload(
                decrypted,
                extracted,
            )
            decrypted.unlink(missing_ok=True)
            archive.unlink(missing_ok=True)
            expires_at = datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS)
            staged = StagedAccountMigration(
                session_id=session_id,
                root=stage_root,
                account=account,
                profile_path=profile_path,
                profile_size_bytes=profile_size,
                profile_file_count=profile_files,
                archive_size_bytes=archive_size,
                expires_at=expires_at,
            )
            expiration = threading.Timer(
                SESSION_TTL_SECONDS,
                self.complete_session,
                args=(session_id,),
            )
            expiration.daemon = True
            with self._lock:
                self._sessions[session_id] = staged
                self._session_timers[session_id] = expiration
            expiration.start()
            return staged
        except Exception:
            shutil.rmtree(stage_root, ignore_errors=True)
            raise

    def get_session(self, session_id: str) -> StagedAccountMigration:
        self.cleanup_expired()
        with self._lock:
            staged = self._sessions.get(str(session_id or ""))
        if staged is None:
            raise AccountMigrationError("账户迁移预检已过期，请重新上传迁移包")
        return staged

    def complete_session(self, session_id: str) -> None:
        with self._lock:
            staged = self._sessions.pop(session_id, None)
            timer = self._session_timers.pop(session_id, None)
        if timer is not None:
            timer.cancel()
        if staged is not None:
            shutil.rmtree(staged.root, ignore_errors=True)

    def cleanup_expired(self) -> None:
        now = datetime.now(UTC)
        expired: list[StagedAccountMigration] = []
        timers: list[threading.Timer] = []
        with self._lock:
            for session_id, staged in tuple(self._sessions.items()):
                if staged.expires_at <= now:
                    expired.append(self._sessions.pop(session_id))
                    timer = self._session_timers.pop(session_id, None)
                    if timer is not None:
                        timers.append(timer)
        for timer in timers:
            timer.cancel()
        for staged in expired:
            shutil.rmtree(staged.root, ignore_errors=True)
        if not self.staging_root.exists():
            return
        cutoff = time.time() - SESSION_TTL_SECONDS * 2
        for child in self.staging_root.iterdir():
            try:
                if child.is_dir() and child.stat().st_mtime < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
            except OSError:
                continue

    def install_profile(self, staged: StagedAccountMigration, account: AccountRecord) -> bool:
        if staged.profile_path is None or not staged.profile_path.is_dir():
            return False
        target = self.profile_storage.account_path(account.account_id)
        if target.exists() or target.is_symlink():
            raise AccountMigrationError("目标账户浏览器 Profile 已存在，无法覆盖")
        temporary = target.with_name(f".{target.name}.importing-{uuid.uuid4().hex}")
        try:
            shutil.copytree(staged.profile_path, temporary, symlinks=False)
            temporary.chmod(0o700)
            temporary.replace(target)
            self.profile_storage.prepare_account(
                account.account_id,
                account.display_name,
                account.browser_identity.browser_engine,
                account.browser_identity.config_revision,
            )
            return True
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            if target.exists() and not target.is_symlink():
                shutil.rmtree(target, ignore_errors=True)
            raise

    def remove_export(self, package: MigrationPackage) -> None:
        shutil.rmtree(package.path.parent, ignore_errors=True)

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password or "") < 8:
            raise AccountMigrationError("迁移密码至少需要 8 位")

    def _prepare_root(self) -> None:
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.staging_root.chmod(0o700)

    @staticmethod
    def _migrated_account(account: AccountRecord, *, profile_present: bool) -> MigratedAccount:
        snapshot = account.browser_identity.fingerprint_snapshot
        proxy = None
        if account.proxy_id and account.proxy.host and account.proxy.port:
            proxy = MigratedProxy(
                name=account.proxy_name or "导入代理",
                enabled=account.proxy.enabled,
                scheme=account.proxy.scheme,
                host=account.proxy.host,
                port=account.proxy.port,
                username=account.proxy.username,
                password=account.proxy.password,
            )
        return MigratedAccount(
            source_account_id=account.account_id,
            platform_user_id=account.platform_user_id,
            platform_display_name=account.platform_display_name,
            platform_avatar_url=account.platform_avatar_url,
            remark=account.remark,
            cookie=account.cookie,
            desired_enabled=account.enabled,
            conversation_visible=account.conversation_visible,
            desired_chat_enabled=account.chat_enabled,
            order_management_visible=account.order_management_visible,
            product_management_visible=account.product_management_visible,
            browser_identity=account.browser_identity.writable_copy(),
            source_fingerprint_snapshot=(
                snapshot.model_dump(mode="json") if snapshot is not None else None
            ),
            proxy=proxy,
            profile_present=profile_present,
            exported_at=datetime.now(UTC),
        )

    def _write_compressed_payload(
        self,
        destination: Path,
        account: MigratedAccount,
        profile: Path | None,
    ) -> None:
        file_count = 1
        total_bytes = 0
        with tarfile.open(destination, "w:gz", format=tarfile.PAX_FORMAT) as bundle:
            encoded = account.model_dump_json(exclude_none=False).encode("utf-8")
            info = tarfile.TarInfo("account.json")
            info.size = len(encoded)
            info.mode = 0o600
            info.mtime = int(time.time())
            bundle.addfile(info, io.BytesIO(encoded))
            total_bytes += len(encoded)
            if profile is None:
                return
            profile_info = tarfile.TarInfo("profile")
            profile_info.type = tarfile.DIRTYPE
            profile_info.mode = 0o700
            profile_info.mtime = int(time.time())
            bundle.addfile(profile_info)
            for root, directories, files in os.walk(profile, followlinks=False):
                root_path = Path(root)
                directories[:] = [
                    name
                    for name in directories
                    if name not in _EXCLUDED_DIRECTORY_NAMES
                    and not (root_path / name).is_symlink()
                ]
                for name in files:
                    source = root_path / name
                    if name in _EXCLUDED_FILE_NAMES or source.is_symlink():
                        continue
                    try:
                        metadata = source.lstat()
                    except OSError as exc:
                        raise AccountMigrationError(f"读取浏览器 Profile 失败：{exc}") from exc
                    if not stat.S_ISREG(metadata.st_mode):
                        continue
                    size = metadata.st_size
                    total_bytes += size
                    file_count += 1
                    if total_bytes > self.max_extracted_bytes:
                        raise AccountMigrationError("浏览器 Profile 解压后超过 2 GiB")
                    if file_count > self.max_files:
                        raise AccountMigrationError("浏览器 Profile 文件数量超过限制")
                    relative = source.relative_to(profile)
                    archive_name = PurePosixPath("profile", *relative.parts).as_posix()
                    info = tarfile.TarInfo(archive_name)
                    info.size = size
                    info.mode = 0o600
                    info.mtime = int(metadata.st_mtime)
                    with source.open("rb") as handle:
                        bundle.addfile(info, handle)

    def _encrypt_file(
        self,
        source: Path,
        destination: Path,
        password: str,
        salt: bytes,
        nonce: bytes,
    ) -> tuple[bytes, str]:
        key = self._derive_key(password, salt)
        encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        digest = hashlib.sha256()
        with source.open("rb") as reader, destination.open("wb") as writer:
            while chunk := reader.read(1024 * 1024):
                encrypted = encryptor.update(chunk)
                writer.write(encrypted)
                digest.update(encrypted)
            final = encryptor.finalize()
            writer.write(final)
            digest.update(final)
        return encryptor.tag, digest.hexdigest()

    def _read_outer_archive(
        self,
        archive: Path,
    ) -> tuple[dict[str, Any], zipfile.ZipInfo]:
        try:
            with zipfile.ZipFile(archive) as bundle:
                infos = bundle.infolist()
                names = {item.filename for item in infos}
                if len(infos) != 2 or names != {"manifest.json", "payload.enc"}:
                    raise AccountMigrationError("账户迁移包目录结构不正确")
                manifest_info = bundle.getinfo("manifest.json")
                encrypted_info = bundle.getinfo("payload.enc")
                if (
                    manifest_info.compress_type != zipfile.ZIP_STORED
                    or encrypted_info.compress_type != zipfile.ZIP_STORED
                ):
                    raise AccountMigrationError("账户迁移包压缩格式不受支持")
                if manifest_info.file_size > 64 * 1024:
                    raise AccountMigrationError("账户迁移包清单异常")
                if encrypted_info.file_size > self.max_archive_bytes:
                    raise AccountMigrationError("账户迁移包超过 512 MiB")
                manifest = json.loads(bundle.read(manifest_info).decode("utf-8"))
        except AccountMigrationError:
            raise
        except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AccountMigrationError("账户迁移包损坏或格式不正确") from exc
        if manifest.get("format") != ARCHIVE_FORMAT:
            raise AccountMigrationError("不是闲鱼账户迁移包")
        if manifest.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
            raise AccountMigrationError("账户迁移包版本不受当前平台支持")
        kdf = manifest.get("kdf")
        if not isinstance(kdf, dict) or (
            kdf.get("name"), kdf.get("n"), kdf.get("r"), kdf.get("p")
        ) != ("scrypt", KDF_N, KDF_R, KDF_P):
            raise AccountMigrationError("账户迁移包密钥参数不受支持")
        return manifest, encrypted_info

    def _decrypt_file_from_zip(
        self,
        archive: Path,
        encrypted_info: zipfile.ZipInfo,
        destination: Path,
        password: str,
        manifest: dict[str, Any],
    ) -> None:
        try:
            salt = self._unb64(str(manifest["kdf"]["salt"]))
            nonce = self._unb64(str(manifest["nonce"]))
            tag = self._unb64(str(manifest["tag"]))
            if len(salt) != 16 or len(nonce) != 12 or len(tag) != 16:
                raise ValueError("invalid encryption metadata")
            key = self._derive_key(password, salt)
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            digest = hashlib.sha256()
            written = 0
            with zipfile.ZipFile(archive) as bundle, bundle.open(encrypted_info) as reader, destination.open("wb") as writer:
                while chunk := reader.read(1024 * 1024):
                    digest.update(chunk)
                    decrypted = decryptor.update(chunk)
                    written += len(decrypted)
                    if written > self.max_archive_bytes:
                        raise AccountMigrationError("账户迁移包解密后超过大小限制")
                    writer.write(decrypted)
                writer.write(decryptor.finalize())
            if digest.hexdigest() != str(manifest.get("ciphertext_sha256") or ""):
                raise AccountMigrationError("账户迁移包完整性校验失败")
        except AccountMigrationError:
            raise
        except (InvalidTag, ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
            destination.unlink(missing_ok=True)
            raise AccountMigrationError("迁移密码错误或账户迁移包已被篡改") from exc

    def _extract_payload(
        self,
        source: Path,
        destination: Path,
    ) -> tuple[MigratedAccount, Path | None, int, int]:
        destination.mkdir(mode=0o700)
        total_bytes = 0
        file_count = 0
        account_bytes: bytes | None = None
        try:
            with tarfile.open(source, "r:gz") as bundle:
                for member in bundle:
                    path = PurePosixPath(member.name)
                    if path.is_absolute() or ".." in path.parts or not path.parts:
                        raise AccountMigrationError("账户迁移包包含不安全路径")
                    if member.isdir():
                        if path.as_posix() != "profile":
                            raise AccountMigrationError("账户迁移包包含未知目录")
                        (destination / "profile").mkdir(mode=0o700, exist_ok=True)
                        continue
                    if not member.isfile():
                        raise AccountMigrationError("账户迁移包包含不安全的链接或设备文件")
                    if path.as_posix() != "account.json" and path.parts[0] != "profile":
                        raise AccountMigrationError("账户迁移包包含未知文件")
                    file_count += 1
                    total_bytes += member.size
                    if file_count > self.max_files:
                        raise AccountMigrationError("账户迁移包文件数量超过限制")
                    if total_bytes > self.max_extracted_bytes:
                        raise AccountMigrationError("账户迁移包解压后超过 2 GiB")
                    reader = bundle.extractfile(member)
                    if reader is None:
                        raise AccountMigrationError("账户迁移包文件读取失败")
                    if path.as_posix() == "account.json":
                        if account_bytes is not None or member.size > 1024 * 1024:
                            raise AccountMigrationError("账户迁移包账户清单异常")
                        account_bytes = reader.read(member.size + 1)
                        continue
                    target = destination.joinpath(*path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with target.open("wb") as writer:
                        shutil.copyfileobj(reader, writer, length=1024 * 1024)
                    target.chmod(0o600)
        except AccountMigrationError:
            raise
        except (OSError, tarfile.TarError) as exc:
            raise AccountMigrationError("账户迁移包压缩数据损坏") from exc
        if account_bytes is None:
            raise AccountMigrationError("账户迁移包缺少账户清单")
        try:
            account = MigratedAccount.model_validate_json(account_bytes)
        except Exception as exc:
            raise AccountMigrationError("账户迁移包账户数据无效") from exc
        if account.cookie_user_id and account.platform_user_id and account.cookie_user_id != account.platform_user_id:
            raise AccountMigrationError("迁移包 Cookie 与平台账户身份不一致")
        profile_path = destination / "profile"
        if account.profile_present != profile_path.is_dir():
            raise AccountMigrationError("迁移包浏览器 Profile 状态不一致")
        profile_files = max(0, file_count - 1)
        profile_size = max(0, total_bytes - len(account_bytes))
        return account, profile_path if profile_path.is_dir() else None, profile_size, profile_files

    @staticmethod
    def _copy_limited(stream: BinaryIO, destination: Path, limit: int) -> int:
        total = 0
        with destination.open("wb") as writer:
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise AccountMigrationError("账户迁移包超过 512 MiB")
                writer.write(chunk)
        return total

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        return Scrypt(
            salt=salt,
            length=32,
            n=KDF_N,
            r=KDF_R,
            p=KDF_P,
        ).derive(password.encode("utf-8"))

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii")

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value.encode("ascii"))

    @staticmethod
    def _package_filename(account: AccountRecord) -> str:
        name = account.platform_display_name or account.platform_user_id or account.account_id[:8]
        safe_name = _SAFE_FILENAME.sub("-", name).strip("-._")[:48] or "account"
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        return f"xianyu-account-{safe_name}-{timestamp}.xianyu.zip"
