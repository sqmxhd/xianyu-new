"""Safe storage operations for persistent Chromium profiles."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .settings import settings


SAFE_ACCOUNT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SAFE_DIRECTORY_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
PROFILE_MANIFEST = ".xianyu-profile.json"


class BrowserProfileBusyError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BrowserProfileDirectory:
    profile_key: str
    directory_name: str
    profile_type: str
    owner_account_id: str | None
    owner_account_name: str | None
    size_bytes: int
    created_at: datetime
    updated_at: datetime
    in_use: bool
    manageable: bool
    browser_engine: str | None = None
    config_revision: int | None = None


class BrowserProfileStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.im_verification_profile_dir).resolve()

    @staticmethod
    def account_profile_key(directory_name: str) -> str:
        return f"account:{directory_name}"

    @staticmethod
    def qr_profile_key(directory_name: str) -> str:
        return f"qr:{directory_name}"

    def account_path(self, account_id: str) -> Path:
        if not SAFE_ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("invalid account ID")
        return self._direct_child(self.root, account_id)

    def qr_path(self, session_id: str) -> Path:
        if not SAFE_ACCOUNT_ID.fullmatch(session_id):
            raise ValueError("invalid QR session ID")
        qr_root = self._direct_child(self.root, "_qr")
        return self._direct_child(qr_root, session_id)

    def prepare_account(
        self,
        account_id: str,
        account_name: str,
        browser_engine: str | None = None,
        config_revision: int | None = None,
    ) -> Path:
        directory = self.account_path(account_id)
        self._prepare_profile(
            directory,
            profile_type="account",
            account_id=account_id,
            account_name=account_name,
            browser_engine=browser_engine,
            config_revision=config_revision,
        )
        self._apply_chinese_preferences(directory)
        return directory

    def prepare_qr(
        self,
        session_id: str,
        account_name: str | None,
    ) -> Path:
        directory = self.qr_path(session_id)
        self._prepare_profile(
            directory,
            profile_type="qr",
            account_id=None,
            account_name=account_name,
        )
        return directory

    def list_profiles(self) -> list[BrowserProfileDirectory]:
        if not self.root.exists():
            return []
        profiles: list[BrowserProfileDirectory] = []
        for child in sorted(self.root.iterdir(), key=lambda item: item.name):
            if child.name == "_qr":
                if child.is_dir() and not child.is_symlink():
                    for qr_child in sorted(child.iterdir(), key=lambda item: item.name):
                        if qr_child.is_dir() or qr_child.is_symlink():
                            profiles.append(self._profile_record(qr_child, "qr"))
                continue
            if child.is_dir() or child.is_symlink():
                profiles.append(self._profile_record(child, "account"))
        return profiles

    def delete_account(self, account_id: str) -> bool:
        return self._delete_directory(self.account_path(account_id))

    def delete_profile(self, profile_key: str) -> bool:
        return self._delete_directory(self.profile_path(profile_key))

    def profile_in_use(self, profile_key: str) -> bool:
        return bool(self._profile_processes(self.profile_path(profile_key)))

    def stop_profile_processes(self, profile_key: str) -> bool:
        directory = self.profile_path(profile_key)
        processes = self._profile_processes(directory)
        if not processes:
            return False
        for pid in processes:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not self._profile_processes(directory):
                self._remove_profile_locks(directory)
                return True
            time.sleep(0.1)
        for pid in self._profile_processes(directory):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self._remove_profile_locks(directory)
        return True

    def profile_path(self, profile_key: str) -> Path:
        profile_type, separator, directory_name = profile_key.partition(":")
        if not separator or not SAFE_DIRECTORY_NAME.fullmatch(directory_name):
            raise ValueError("invalid browser profile key")
        if profile_type == "account":
            return self._direct_child(self.root, directory_name)
        if profile_type == "qr":
            return self._direct_child(self._direct_child(self.root, "_qr"), directory_name)
        raise ValueError("invalid browser profile type")

    @staticmethod
    def _direct_child(parent: Path, name: str) -> Path:
        if name in {"", ".", ".."} or "/" in name or "\\" in name or "\0" in name:
            raise ValueError("invalid browser profile directory")
        directory = parent / name
        if directory.parent != parent:
            raise ValueError("browser profile path escapes storage root")
        return directory

    def _prepare_profile(
        self,
        directory: Path,
        *,
        profile_type: str,
        account_id: str | None,
        account_name: str | None,
        browser_engine: str | None = None,
        config_revision: int | None = None,
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)
        manifest_path = directory / PROFILE_MANIFEST
        previous = self._read_manifest(manifest_path)
        now = datetime.now(UTC).isoformat()
        manifest = {
            "version": 1,
            "profile_type": profile_type,
            "account_id": account_id,
            "account_name": account_name,
            "created_at": previous.get("created_at") or now,
            "updated_at": now,
            "browser_engine": browser_engine or previous.get("browser_engine"),
            "config_revision": config_revision or previous.get("config_revision"),
        }
        temporary = directory / f"{PROFILE_MANIFEST}.tmp"
        temporary.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(manifest_path)

    def _profile_record(self, directory: Path, default_type: str) -> BrowserProfileDirectory:
        manifest = (
            {}
            if directory.is_symlink()
            else self._read_manifest(directory / PROFILE_MANIFEST)
        )
        stat = directory.lstat()
        created_at = self._parse_datetime(manifest.get("created_at")) or datetime.fromtimestamp(
            stat.st_ctime, UTC
        )
        updated_at = datetime.fromtimestamp(stat.st_mtime, UTC)
        profile_type = str(manifest.get("profile_type") or default_type)
        key_factory = self.qr_profile_key if default_type == "qr" else self.account_profile_key
        manageable = bool(SAFE_DIRECTORY_NAME.fullmatch(directory.name))
        return BrowserProfileDirectory(
            profile_key=key_factory(directory.name),
            directory_name=directory.name,
            profile_type=profile_type,
            owner_account_id=self._optional_string(manifest.get("account_id")),
            owner_account_name=self._optional_string(manifest.get("account_name")),
            size_bytes=self._directory_size(directory),
            created_at=created_at,
            updated_at=updated_at,
            in_use=self._path_in_use(directory),
            manageable=manageable,
            browser_engine=self._optional_string(manifest.get("browser_engine")),
            config_revision=(
                int(manifest["config_revision"])
                if str(manifest.get("config_revision") or "").isdigit()
                else None
            ),
        )

    def _delete_directory(self, directory: Path) -> bool:
        if directory.is_symlink():
            directory.unlink()
            return True
        if not directory.exists():
            return False
        if not directory.is_dir():
            raise ValueError("browser profile is not a directory")
        if self._path_in_use(directory):
            raise BrowserProfileBusyError("browser profile is in use")
        shutil.rmtree(directory)
        return True

    def _path_in_use(self, directory: Path) -> bool:
        return bool(self._profile_processes(directory))

    @staticmethod
    def _profile_processes(directory: Path) -> list[int]:
        if directory.is_symlink():
            return []
        profile_text = str(directory.resolve())
        matches: list[int] = []
        for process_dir in Path("/proc").glob("[0-9]*"):
            try:
                arguments = [
                    item.decode("utf-8", "ignore")
                    for item in (process_dir / "cmdline").read_bytes().split(b"\0")
                    if item
                ]
            except (OSError, PermissionError):
                continue
            if profile_text in arguments or f"--user-data-dir={profile_text}" in arguments:
                matches.append(int(process_dir.name))
        return matches

    @staticmethod
    def _remove_profile_locks(directory: Path) -> None:
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            try:
                (directory / name).unlink()
            except (FileNotFoundError, OSError):
                pass

    @staticmethod
    def _directory_size(directory: Path) -> int:
        if directory.is_symlink():
            return 0
        total = 0
        for root, directories, files in os.walk(directory, followlinks=False):
            directories[:] = [
                name for name in directories if not (Path(root) / name).is_symlink()
            ]
            for name in files:
                try:
                    path = Path(root) / name
                    if not path.is_symlink():
                        total += path.stat().st_size
                except (FileNotFoundError, PermissionError, OSError):
                    continue
        return total

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any]:
        try:
            if path.stat().st_size > 16_384:
                return {}
            loaded = json.loads(path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except (FileNotFoundError, PermissionError, OSError, ValueError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    @classmethod
    def _apply_chinese_preferences(cls, directory: Path) -> None:
        cls._update_json_file(
            directory / "Default" / "Preferences",
            {
                "intl.accept_languages": "zh-CN,zh,en-US,en",
                "intl.selected_languages": "zh-CN,zh,en-US,en",
            },
        )
        cls._update_json_file(
            directory / "Local State",
            {"intl.app_locale": "zh-CN"},
        )

    @classmethod
    def _update_json_file(cls, path: Path, updates: dict[str, str]) -> None:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                return
        except (FileNotFoundError, PermissionError, OSError, ValueError, json.JSONDecodeError):
            return
        for dotted_key, value in updates.items():
            target = loaded
            parts = dotted_key.split(".")
            for part in parts[:-1]:
                nested = target.get(part)
                if not isinstance(nested, dict):
                    nested = {}
                    target[part] = nested
                target = nested
            target[parts[-1]] = value
        temporary = path.with_name(f"{path.name}.xianyu-tmp")
        temporary.write_text(json.dumps(loaded, ensure_ascii=False), encoding="utf-8")
        temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)


browser_profile_storage = BrowserProfileStorage()
