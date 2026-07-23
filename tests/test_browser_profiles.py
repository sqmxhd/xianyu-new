import tempfile
import unittest
import json
from pathlib import Path

from apps.api.xianyu_admin_api.browser_profiles import BrowserProfileStorage


class BrowserProfileStorageTests(unittest.TestCase):
    def test_delete_is_account_scoped_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = BrowserProfileStorage(root)
            account = Path(root) / "account-1"
            sibling = Path(root) / "account-2"
            qr_profile = Path(root) / "_qr" / "session-1"
            account.mkdir()
            sibling.mkdir()
            qr_profile.mkdir(parents=True)
            (account / "Cache").write_text("cache")
            (sibling / "keep").write_text("keep")
            (qr_profile / "keep").write_text("keep")

            self.assertTrue(storage.delete_account("account-1"))
            self.assertFalse(account.exists())
            self.assertTrue((sibling / "keep").is_file())
            self.assertTrue((qr_profile / "keep").is_file())
            self.assertFalse(storage.delete_account("account-1"))

    def test_invalid_account_id_cannot_escape_root(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = BrowserProfileStorage(root)
            with self.assertRaisesRegex(ValueError, "invalid account ID"):
                storage.delete_account("../outside")

    def test_symlink_is_unlinked_without_deleting_target(self) -> None:
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as outside,
        ):
            storage = BrowserProfileStorage(root)
            target = Path(outside) / "important"
            target.mkdir()
            (target / "keep").write_text("keep")
            link = Path(root) / "account-1"
            link.symlink_to(target, target_is_directory=True)

            self.assertTrue(storage.delete_account("account-1"))
            self.assertFalse(link.exists())
            self.assertTrue((target / "keep").is_file())

    def test_prepared_profile_is_listed_with_account_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = BrowserProfileStorage(root)
            profile = storage.prepare_account("account-1", "主账号")
            (profile / "Cache").mkdir()
            (profile / "Cache" / "data").write_bytes(b"1234")

            records = storage.list_profiles()

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].profile_key, "account:account-1")
            self.assertEqual(records[0].owner_account_id, "account-1")
            self.assertEqual(records[0].owner_account_name, "主账号")
            self.assertGreaterEqual(records[0].size_bytes, 4)

    def test_profile_manifest_tracks_browser_identity_revision(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = BrowserProfileStorage(root)
            storage.prepare_account(
                "account-1",
                "主账号",
                browser_engine="fingerprint_chromium",
                config_revision=3,
            )

            record = storage.list_profiles()[0]

            self.assertEqual(record.browser_engine, "fingerprint_chromium")
            self.assertEqual(record.config_revision, 3)

    def test_existing_chromium_preferences_are_set_to_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = BrowserProfileStorage(root)
            profile = storage.account_path("account-1")
            (profile / "Default").mkdir(parents=True)
            (profile / "Default" / "Preferences").write_text(
                json.dumps({"intl": {"accept_languages": "en-US"}}),
                encoding="utf-8",
            )
            (profile / "Local State").write_text("{}", encoding="utf-8")

            storage.prepare_account("account-1", "主账号")

            preferences = json.loads(
                (profile / "Default" / "Preferences").read_text(encoding="utf-8")
            )
            local_state = json.loads((profile / "Local State").read_text(encoding="utf-8"))
            self.assertEqual(preferences["intl"]["accept_languages"], "zh-CN,zh,en-US,en")
            self.assertEqual(local_state["intl"]["app_locale"], "zh-CN")

    def test_qr_profile_can_be_managed_by_opaque_key(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            storage = BrowserProfileStorage(root)
            profile = storage.prepare_qr("session-1", "待登录账号")
            self.assertTrue(profile.is_dir())
            self.assertEqual(storage.list_profiles()[0].profile_key, "qr:session-1")
            self.assertTrue(storage.delete_profile("qr:session-1"))
            self.assertFalse(profile.exists())


if __name__ == "__main__":
    unittest.main()
