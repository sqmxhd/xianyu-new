"""Versioned fingerprint-chromium binary installation and discovery."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .schemas import (
    BrowserBinaryPayload,
    BrowserRuntimeSettingPayload,
    SystemBrowserPayload,
)
from .platform_runtime import is_root_process, system_browser_candidates
from .settings import settings


OFFICIAL_REPOSITORY = "https://github.com/adryfish/fingerprint-chromium"
LATEST_RELEASE_API = (
    "https://api.github.com/repos/adryfish/fingerprint-chromium/releases/latest"
)
STANDARD_OFFICIAL_REPOSITORY = (
    "https://github.com/GoogleChromeLabs/chrome-for-testing"
)
STANDARD_LATEST_RELEASE_API = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)
STANDARD_DOWNLOAD_PREFIX = (
    "https://storage.googleapis.com/chrome-for-testing-public/"
)
MANIFEST_NAME = ".xianyu-browser.json"
ACTIVE_NAME = "active.json"
VERSION_PATTERN = re.compile(r"(\d+\.\d+\.\d+\.\d+)")


class BrowserBinaryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InstalledBrowser:
    version: str
    executable_path: Path
    source: str
    sha256: str | None
    size_bytes: int
    installed_at: datetime | None
    active: bool
    valid: bool = True
    validation_message: str | None = None

    def to_payload(self) -> BrowserBinaryPayload:
        return BrowserBinaryPayload(
            version=self.version,
            executable_path=str(self.executable_path),
            source=self.source,  # type: ignore[arg-type]
            sha256=self.sha256,
            size_bytes=self.size_bytes,
            installed_at=self.installed_at,
            active=self.active,
            valid=self.valid,
            validation_message=self.validation_message,
        )


class BrowserBinaryManager:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        browser_kind: str = "fingerprint",
    ) -> None:
        if browser_kind not in {"fingerprint", "standard"}:
            raise ValueError("unsupported browser kind")
        self.browser_kind = browser_kind
        default_root = (
            settings.fingerprint_browser_root
            if browser_kind == "fingerprint"
            else settings.standard_browser_root
        )
        self.root = Path(root or default_root).resolve()
        self.releases = self.root / "releases"
        self.downloads = self.root / "downloads"
        self._lock = threading.RLock()
        self._system_cache: tuple[float, SystemBrowserPayload] | None = None

    @property
    def display_name(self) -> str:
        return "Fingerprint Chromium" if self.browser_kind == "fingerprint" else "标准 Chrome"

    def ensure_layout(self) -> None:
        self.releases.mkdir(parents=True, exist_ok=True)
        self.downloads.mkdir(parents=True, exist_ok=True)
        self.root.chmod(0o755)

    def system_browser(self) -> SystemBrowserPayload:
        now = datetime.now(UTC).timestamp()
        if self._system_cache is not None and now - self._system_cache[0] < 30:
            return self._system_cache[1]
        configured = settings.im_verification_browser_path.strip()
        path = configured or next(iter(system_browser_candidates()), None)
        if not path:
            result = SystemBrowserPayload(
                available=False,
                validation_message="未检测到系统 Chromium/Chrome",
            )
        else:
            try:
                version = self._read_version(Path(path))
                result = SystemBrowserPayload(
                    executable_path=str(Path(path).resolve()),
                    version=version,
                    available=True,
                )
            except BrowserBinaryError as exc:
                result = SystemBrowserPayload(
                    executable_path=str(Path(path).resolve()),
                    available=False,
                    validation_message=str(exc),
                )
        self._system_cache = (now, result)
        return result

    def active_version(self) -> str | None:
        try:
            data = json.loads((self.root / ACTIVE_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        value = str(data.get("version") or "").strip() if isinstance(data, dict) else ""
        return value or None

    def activate(self, version: str) -> InstalledBrowser:
        with self._lock:
            installed = self.get_installed(version)
            if installed is None:
                raise BrowserBinaryError(f"{self.display_name} 版本不存在")
            if not installed.valid:
                raise BrowserBinaryError(installed.validation_message or "浏览器版本校验失败")
            self.ensure_layout()
            target = self.root / ACTIVE_NAME
            temporary = target.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {"version": installed.version, "updated_at": datetime.now(UTC).isoformat()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            os.replace(temporary, target)
            return self.get_installed(version) or installed

    def clear_active(self) -> None:
        with self._lock:
            (self.root / ACTIVE_NAME).unlink(missing_ok=True)

    def resolve_fingerprint_executable(self, version: str | None = None) -> Path:
        return self.resolve_executable(version)

    def resolve_executable(self, version: str | None = None) -> Path:
        requested = str(version or self.active_version() or "").strip()
        if not requested:
            raise BrowserBinaryError(f"尚未安装并启用 {self.display_name}")
        installed = self.get_installed(requested)
        if installed is None or not installed.valid:
            raise BrowserBinaryError(
                installed.validation_message if installed else f"指定的 {self.display_name} 不存在"
            )
        return installed.executable_path

    def effective_version(self, engine: str, pinned_version: str | None) -> str | None:
        if engine == "fingerprint_chromium":
            requested = str(pinned_version or self.active_version() or "").strip()
            return requested or None
        if pinned_version:
            return str(pinned_version).strip() or None
        return self.system_browser().version

    def list_installed(self) -> list[InstalledBrowser]:
        self.ensure_layout()
        active = self.active_version()
        result: list[InstalledBrowser] = []
        for directory in sorted(self.releases.iterdir(), reverse=True):
            if not directory.is_dir() or directory.is_symlink():
                continue
            manifest = self._read_manifest(directory)
            version = str(manifest.get("version") or directory.name)
            source = str(manifest.get("source") or "unknown")
            if source not in {"upload", "download", "bundled", "unknown"}:
                source = "unknown"
            executable = directory / str(manifest.get("executable") or "chrome")
            valid = executable.is_file() and os.access(executable, os.X_OK)
            message = None if valid else "chrome 可执行文件不存在或不可执行"
            installed_at = self._parse_datetime(manifest.get("installed_at"))
            result.append(
                InstalledBrowser(
                    version=version,
                    executable_path=executable,
                    source=source,
                    sha256=str(manifest.get("sha256") or "") or None,
                    size_bytes=self._directory_size(directory),
                    installed_at=installed_at,
                    active=version == active,
                    valid=valid,
                    validation_message=message,
                )
            )
        return result

    def get_installed(self, version: str) -> InstalledBrowser | None:
        return next((item for item in self.list_installed() if item.version == version), None)

    def install_archive(
        self,
        archive_path: str | Path,
        *,
        source: str,
        expected_sha256: str | None = None,
    ) -> InstalledBrowser:
        archive = Path(archive_path).resolve()
        if not archive.is_file():
            raise BrowserBinaryError("浏览器压缩包不存在")
        if self.browser_kind == "standard" and not archive.name.lower().endswith(".zip"):
            raise BrowserBinaryError("标准 Chrome 仅支持官方 Linux ZIP 压缩包")
        if archive.stat().st_size > settings.fingerprint_browser_max_archive_bytes:
            raise BrowserBinaryError("浏览器压缩包超过允许大小")
        actual_sha256 = self._sha256(archive)
        if expected_sha256 and actual_sha256.lower() != expected_sha256.lower():
            raise BrowserBinaryError("浏览器压缩包 SHA256 校验失败")

        with self._lock:
            self.ensure_layout()
            extraction = Path(tempfile.mkdtemp(prefix="extract-", dir=self.downloads))
            try:
                self._extract_securely(archive, extraction)
                executable = self._find_executable(extraction)
                executable.chmod(executable.stat().st_mode | 0o111)
                version = self._read_version(executable)
                if self.browser_kind == "standard":
                    self._smoke_test(executable)
                target = self.releases / version
                if target.exists():
                    existing = self.get_installed(version)
                    if existing and existing.sha256 == actual_sha256:
                        return existing
                    raise BrowserBinaryError(f"版本 {version} 已存在，请先使用或清理现有版本")
                payload_root = executable.parent
                staged = self.releases / f".{version}.installing"
                if staged.exists():
                    shutil.rmtree(staged)
                shutil.move(str(payload_root), staged)
                installed_executable = staged / executable.name
                installed_executable.chmod(installed_executable.stat().st_mode | 0o111)
                manifest = {
                    "version": version,
                    "executable": executable.name,
                    "source": source,
                    "sha256": actual_sha256,
                    "archive_size_bytes": archive.stat().st_size,
                    "installed_at": datetime.now(UTC).isoformat(),
                    "upstream": (
                        OFFICIAL_REPOSITORY
                        if self.browser_kind == "fingerprint"
                        else STANDARD_OFFICIAL_REPOSITORY
                    ),
                }
                (staged / MANIFEST_NAME).write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                os.replace(staged, target)
                if self.active_version() is None:
                    self.activate(version)
                installed = self.get_installed(version)
                if installed is None:
                    raise BrowserBinaryError("浏览器安装完成后未能读取版本")
                return installed
            finally:
                shutil.rmtree(extraction, ignore_errors=True)

    def install_upload(self, stream: Any, filename: str) -> InstalledBrowser:
        self.ensure_layout()
        safe_name = Path(str(filename or "browser.tar.xz")).name
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="upload-",
            suffix=f"-{safe_name}",
            dir=self.downloads,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            total = 0
            with temporary.open("wb") as output:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > settings.fingerprint_browser_max_archive_bytes:
                        raise BrowserBinaryError("浏览器压缩包超过允许大小")
                    output.write(chunk)
            return self.install_archive(temporary, source="upload")
        finally:
            temporary.unlink(missing_ok=True)

    def download_latest(self) -> InstalledBrowser:
        self.ensure_layout()
        if self.browser_kind == "standard":
            return self._download_latest_standard()
        request = urllib.request.Request(
            LATEST_RELEASE_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "xianyu-admin/1.0"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=settings.fingerprint_browser_download_timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise BrowserBinaryError(f"读取官方版本信息失败：{exc}") from exc
        assets = payload.get("assets") if isinstance(payload, dict) else None
        if not isinstance(assets, list):
            raise BrowserBinaryError("官方版本信息中没有可下载文件")
        platform_suffix = (
            "_windows_x64.zip" if os.name == "nt" else "x86_64_linux.tar.xz"
        )
        asset = next(
            (
                item
                for item in assets
                if isinstance(item, dict)
                and str(item.get("name") or "").endswith(platform_suffix)
            ),
            None,
        )
        if asset is None:
            raise BrowserBinaryError(
                "官方最新版没有当前平台可用的 Fingerprint Chromium 压缩包"
            )
        url = str(asset.get("browser_download_url") or "")
        if not url.startswith("https://github.com/adryfish/fingerprint-chromium/releases/download/"):
            raise BrowserBinaryError("官方浏览器下载地址不受信任")
        digest = str(asset.get("digest") or "")
        expected = digest.removeprefix("sha256:") if digest.startswith("sha256:") else None
        default_name = (
            "fingerprint-chromium-windows-x64.zip"
            if os.name == "nt"
            else "fingerprint-chromium-linux-x64.tar.xz"
        )
        name = Path(str(asset.get("name") or default_name)).name
        descriptor, temporary_name = tempfile.mkstemp(prefix="download-", suffix=f"-{name}", dir=self.downloads)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            download_request = urllib.request.Request(url, headers={"User-Agent": "xianyu-admin/1.0"})
            with (
                urllib.request.urlopen(
                    download_request,
                    timeout=settings.fingerprint_browser_download_timeout_seconds,
                ) as response,
                temporary.open("wb") as output,
            ):
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > settings.fingerprint_browser_max_archive_bytes:
                        raise BrowserBinaryError("下载的浏览器压缩包超过允许大小")
                    output.write(chunk)
            return self.install_archive(
                temporary,
                source="download",
                expected_sha256=expected,
            )
        except BrowserBinaryError:
            raise
        except Exception as exc:
            raise BrowserBinaryError(f"浏览器下载失败：{exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _download_latest_standard(self) -> InstalledBrowser:
        request = urllib.request.Request(
            STANDARD_LATEST_RELEASE_API,
            headers={"Accept": "application/json", "User-Agent": "xianyu-admin/1.0"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=settings.fingerprint_browser_download_timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise BrowserBinaryError(f"读取 Chrome for Testing 版本信息失败：{exc}") from exc
        channels = payload.get("channels") if isinstance(payload, dict) else None
        stable = channels.get("Stable") if isinstance(channels, dict) else None
        downloads = stable.get("downloads") if isinstance(stable, dict) else None
        chrome_assets = downloads.get("chrome") if isinstance(downloads, dict) else None
        target_platform = "win64" if os.name == "nt" else "linux64"
        asset = next(
            (
                item
                for item in chrome_assets or []
                if isinstance(item, dict) and item.get("platform") == target_platform
            ),
            None,
        )
        if asset is None:
            raise BrowserBinaryError(
                "Chrome for Testing Stable 没有当前平台的 x64 下载文件"
            )
        url = str(asset.get("url") or "")
        if not url.startswith(STANDARD_DOWNLOAD_PREFIX):
            raise BrowserBinaryError("Chrome for Testing 下载地址不受信任")
        name = Path(
            url.rsplit("/", 1)[-1]
            or ("chrome-win64.zip" if os.name == "nt" else "chrome-linux64.zip")
        ).name
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="download-",
            suffix=f"-{name}",
            dir=self.downloads,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            download_request = urllib.request.Request(
                url,
                headers={"User-Agent": "xianyu-admin/1.0"},
            )
            with (
                urllib.request.urlopen(
                    download_request,
                    timeout=settings.fingerprint_browser_download_timeout_seconds,
                ) as response,
                temporary.open("wb") as output,
            ):
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > settings.fingerprint_browser_max_archive_bytes:
                        raise BrowserBinaryError("下载的浏览器压缩包超过允许大小")
                    output.write(chunk)
            return self.install_archive(temporary, source="download")
        except BrowserBinaryError:
            raise
        except Exception as exc:
            raise BrowserBinaryError(f"Chrome for Testing 下载失败：{exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _extract_securely(self, archive: Path, target: Path) -> None:
        suffix = archive.name.lower()
        if suffix.endswith((".tar.xz", ".txz")):
            with tarfile.open(archive, mode="r:xz") as bundle:
                members = bundle.getmembers()
                total = sum(max(0, member.size) for member in members)
                if total > settings.fingerprint_browser_max_extracted_bytes:
                    raise BrowserBinaryError("浏览器压缩包解压后超过允许大小")
                for member in members:
                    self._validate_archive_name(member.name)
                    if member.issym() or member.islnk() or member.isdev():
                        raise BrowserBinaryError("浏览器压缩包包含不安全的链接或设备文件")
                bundle.extractall(target, members=members, filter="data")
            return
        if suffix.endswith(".zip"):
            with zipfile.ZipFile(archive) as bundle:
                infos = bundle.infolist()
                if sum(max(0, item.file_size) for item in infos) > settings.fingerprint_browser_max_extracted_bytes:
                    raise BrowserBinaryError("浏览器压缩包解压后超过允许大小")
                for item in infos:
                    self._validate_archive_name(item.filename)
                    if (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise BrowserBinaryError("浏览器压缩包包含不安全的软链接")
                bundle.extractall(target)
            return
        raise BrowserBinaryError("仅支持 Linux TAR.XZ 或 ZIP 浏览器压缩包")

    @staticmethod
    def _validate_archive_name(name: str) -> None:
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise BrowserBinaryError("浏览器压缩包包含越界路径")

    @staticmethod
    def _find_executable(root: Path) -> Path:
        candidates = [
            path
            for executable_name in ("chrome", "chrome.exe")
            for path in root.rglob(executable_name)
            if path.is_file() and not path.is_symlink()
        ]
        if not candidates:
            raise BrowserBinaryError("压缩包中未找到 chrome 可执行文件")
        return min(candidates, key=lambda item: len(item.parts))

    @staticmethod
    def _read_version(executable: Path) -> str:
        try:
            completed = subprocess.run(
                [str(executable), "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
                env=dict(os.environ),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BrowserBinaryError(f"浏览器版本检测失败：{exc}") from exc
        output = f"{completed.stdout} {completed.stderr}".strip()
        matched = VERSION_PATTERN.search(output)
        if completed.returncode != 0 or not matched:
            raise BrowserBinaryError(f"浏览器版本检测失败：{output or '无输出'}")
        return matched.group(1)

    @staticmethod
    def _smoke_test(executable: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="browser-smoke-") as profile:
            command = [
                str(executable),
                "--headless=new",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                f"--user-data-dir={profile}",
                "--dump-dom",
            ]
            if is_root_process():
                command.append("--no-sandbox")
            command.append("about:blank")
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=dict(os.environ),
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise BrowserBinaryError(f"浏览器启动校验失败：{exc}") from exc
            if completed.returncode != 0:
                output = f"{completed.stdout} {completed.stderr}".strip()
                raise BrowserBinaryError(
                    f"浏览器启动校验失败：{output or f'退出码 {completed.returncode}'}"
                )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _directory_size(path: Path) -> int:
        total = 0
        for child in path.rglob("*"):
            if child.is_file() and not child.is_symlink():
                try:
                    total += child.stat().st_size
                except OSError:
                    pass
        return total

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    @staticmethod
    def _read_manifest(directory: Path) -> dict[str, Any]:
        try:
            payload = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return payload if isinstance(payload, dict) else {}


browser_binary_manager = BrowserBinaryManager()
standard_browser_binary_manager = BrowserBinaryManager(
    settings.standard_browser_root,
    browser_kind="standard",
)


def browser_runtime_payload(
    *,
    active_vnc_account_id: str | None = None,
    active_vnc_account_ids: list[str] | None = None,
    max_vnc_session_count: int = 1,
    vnc_idle_timeout_seconds: int = 1800,
    vnc_max_session_seconds: int = 28800,
) -> BrowserRuntimeSettingPayload:
    active_ids = list(dict.fromkeys(active_vnc_account_ids or []))
    if active_vnc_account_id and active_vnc_account_id not in active_ids:
        active_ids.insert(0, active_vnc_account_id)
    return BrowserRuntimeSettingPayload(
        root_directory=str(browser_binary_manager.root),
        standard_root_directory=str(standard_browser_binary_manager.root),
        system_browser=browser_binary_manager.system_browser(),
        standard_browsers=[
            item.to_payload() for item in standard_browser_binary_manager.list_installed()
        ],
        active_standard_version=standard_browser_binary_manager.active_version(),
        fingerprint_browsers=[
            item.to_payload() for item in browser_binary_manager.list_installed()
        ],
        active_fingerprint_version=browser_binary_manager.active_version(),
        official_project_url=OFFICIAL_REPOSITORY,
        official_standard_project_url=STANDARD_OFFICIAL_REPOSITORY,
        active_vnc_account_id=active_ids[0] if active_ids else active_vnc_account_id,
        active_vnc_account_ids=active_ids,
        active_vnc_session_count=len(active_ids),
        max_vnc_session_count=max(1, max_vnc_session_count),
        vnc_idle_timeout_seconds=max(60, vnc_idle_timeout_seconds),
        vnc_max_session_seconds=max(
            max(60, vnc_idle_timeout_seconds),
            vnc_max_session_seconds,
        ),
    )
