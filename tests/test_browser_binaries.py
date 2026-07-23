import io
import json
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from apps.api.xianyu_admin_api.browser_binaries import (
    BrowserBinaryError,
    BrowserBinaryManager,
)


class BrowserBinaryManagerTests(unittest.TestCase):
    @staticmethod
    def _standard_zip(version: str) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as bundle:
            bundle.writestr(
                "chrome-linux64/chrome",
                f"#!/bin/sh\necho 'Google Chrome for Testing {version}'\n",
            )
        return output.getvalue()

    def test_upload_install_is_versioned_validated_and_activated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            payload = base / "payload"
            payload.mkdir()
            executable = payload / "chrome"
            executable.write_text(
                "#!/bin/sh\necho 'Chromium 136.0.7103.49'\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            archive = base / "fingerprint-chromium.tar.xz"
            with tarfile.open(archive, "w:xz") as bundle:
                bundle.add(executable, arcname="fingerprint-chromium/chrome")

            manager = BrowserBinaryManager(base / "third_party")
            installed = manager.install_archive(archive, source="upload")

            self.assertEqual(installed.version, "136.0.7103.49")
            self.assertTrue(installed.valid)
            self.assertEqual(manager.active_version(), "136.0.7103.49")
            self.assertEqual(
                manager.resolve_fingerprint_executable("136.0.7103.49"),
                installed.executable_path,
            )
            self.assertTrue(os.access(installed.executable_path, os.X_OK))

    def test_archive_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive = base / "malicious.tar.xz"
            with tarfile.open(archive, "w:xz") as bundle:
                member = tarfile.TarInfo("../escape")
                contents = b"do not extract"
                member.size = len(contents)
                bundle.addfile(member, io.BytesIO(contents))

            manager = BrowserBinaryManager(base / "third_party")
            with self.assertRaises(BrowserBinaryError):
                manager.install_archive(archive, source="upload")
            self.assertFalse((base / "escape").exists())

    def test_standard_chrome_zip_is_validated_versioned_and_can_return_to_system(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive = base / "chrome-linux64.zip"
            archive.write_bytes(self._standard_zip("150.0.7871.124"))
            manager = BrowserBinaryManager(
                base / "standard",
                browser_kind="standard",
            )

            installed = manager.install_archive(archive, source="upload")

            self.assertEqual(installed.version, "150.0.7871.124")
            self.assertEqual(manager.active_version(), "150.0.7871.124")
            self.assertEqual(
                manager.resolve_executable("150.0.7871.124"),
                installed.executable_path,
            )
            manager.clear_active()
            self.assertIsNone(manager.active_version())

    def test_standard_chrome_rejects_non_zip_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive = base / "chrome.tar.xz"
            with tarfile.open(archive, "w:xz"):
                pass
            manager = BrowserBinaryManager(
                base / "standard",
                browser_kind="standard",
            )

            with self.assertRaisesRegex(BrowserBinaryError, "仅支持"):
                manager.install_archive(archive, source="upload")

    def test_standard_latest_uses_official_stable_linux_download(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            manager = BrowserBinaryManager(
                base / "standard",
                browser_kind="standard",
            )
            url = (
                "https://storage.googleapis.com/chrome-for-testing-public/"
                "150.0.7871.124/linux64/chrome-linux64.zip"
            )
            release = {
                "channels": {
                    "Stable": {
                        "downloads": {
                            "chrome": [{"platform": "linux64", "url": url}]
                        }
                    }
                }
            }
            responses = [
                io.BytesIO(json.dumps(release).encode()),
                io.BytesIO(self._standard_zip("150.0.7871.124")),
            ]

            with patch(
                "apps.api.xianyu_admin_api.browser_binaries.urllib.request.urlopen",
                side_effect=responses,
            ) as urlopen:
                installed = manager.download_latest()

            self.assertEqual(installed.version, "150.0.7871.124")
            self.assertEqual(installed.source, "download")
            self.assertEqual(urlopen.call_count, 2)

    def test_standard_latest_rejects_untrusted_download_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manager = BrowserBinaryManager(
                Path(temporary) / "standard",
                browser_kind="standard",
            )
            release = {
                "channels": {
                    "Stable": {
                        "downloads": {
                            "chrome": [
                                {
                                    "platform": "linux64",
                                    "url": "https://example.com/chrome-linux64.zip",
                                }
                            ]
                        }
                    }
                }
            }
            with (
                patch(
                    "apps.api.xianyu_admin_api.browser_binaries.urllib.request.urlopen",
                    return_value=io.BytesIO(json.dumps(release).encode()),
                ),
                self.assertRaisesRegex(BrowserBinaryError, "不受信任"),
            ):
                manager.download_latest()

    def test_new_account_can_pin_standard_default_without_changing_legacy_system_mode(self) -> None:
        from apps.api.xianyu_admin_api.main import _normalize_browser_identity_for_save
        from apps.api.xianyu_admin_api.schemas import AccountBrowserIdentityPayload

        identity = AccountBrowserIdentityPayload(browser_engine="system_chromium")
        with (
            patch(
                "apps.api.xianyu_admin_api.main.standard_browser_binary_manager.active_version",
                return_value="150.0.7871.124",
            ),
            patch(
                "apps.api.xianyu_admin_api.main.standard_browser_binary_manager.resolve_executable",
                return_value=Path("/managed/chrome"),
            ),
        ):
            legacy = _normalize_browser_identity_for_save(identity)
            created = _normalize_browser_identity_for_save(
                identity,
                apply_standard_default=True,
            )

        self.assertIsNone(legacy.browser_version)
        self.assertEqual(created.browser_version, "150.0.7871.124")


if __name__ == "__main__":
    unittest.main()
