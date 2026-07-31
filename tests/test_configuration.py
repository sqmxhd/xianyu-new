from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.container_entry import (
    initialize_runtime_secrets,
    load_runtime_environment,
)
from tools.init_local_env import initialize_local_environment


class RuntimeSecretTests(unittest.TestCase):
    def test_runtime_secrets_are_generated_once_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            environment = {
                "XIANYU_RUNTIME_SECRET_DIR": str(secret_dir),
                "XIANYU_GENERATED_SECRETS": (
                    "jwt-secret,mysql-root-password,mysql-password,redis-password"
                ),
            }
            with patch.dict(os.environ, environment, clear=True):
                initialize_runtime_secrets()
                first = {
                    path.name: path.read_text(encoding="utf-8")
                    for path in secret_dir.iterdir()
                }
                initialize_runtime_secrets()
                second = {
                    path.name: path.read_text(encoding="utf-8")
                    for path in secret_dir.iterdir()
                }

            self.assertEqual(first, second)
            self.assertEqual(
                set(first),
                {
                    "jwt-secret",
                    "mysql-root-password",
                    "mysql-password",
                    "redis-password",
                },
            )
            self.assertTrue(all(len(value.strip()) >= 32 for value in first.values()))

    def test_missing_secret_is_not_regenerated_over_existing_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "mysql"
            data.mkdir()
            (data / "ibdata1").write_text("existing", encoding="utf-8")
            environment = {
                "XIANYU_RUNTIME_SECRET_DIR": str(root / "secrets"),
                "XIANYU_GENERATED_SECRETS": "mysql-password",
                "XIANYU_SECRET_GUARD_DIRS": str(data),
            }
            with patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(RuntimeError, "existing persistent data"):
                    initialize_runtime_secrets()

    def test_existing_deployment_can_seed_original_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "mysql"
            data.mkdir()
            (data / "ibdata1").write_text("existing", encoding="utf-8")
            environment = {
                "XIANYU_RUNTIME_SECRET_DIR": str(root / "secrets"),
                "XIANYU_GENERATED_SECRETS": "mysql-password",
                "XIANYU_SECRET_GUARD_DIRS": str(data),
                "MYSQL_PASSWORD": "original-database-password",
            }
            with patch.dict(os.environ, environment, clear=True):
                initialize_runtime_secrets()

            self.assertEqual(
                (root / "secrets" / "mysql-password")
                .read_text(encoding="utf-8")
                .strip(),
                "original-database-password",
            )

    def test_runtime_environment_is_built_from_secret_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary)
            (secret_dir / "jwt-secret").write_text("jwt-value\n", encoding="utf-8")
            (secret_dir / "mysql-password").write_text("mysql/value\n", encoding="utf-8")
            (secret_dir / "redis-password").write_text("redis:value\n", encoding="utf-8")
            environment = {
                "XIANYU_RUNTIME_SECRET_DIR": str(secret_dir),
                "XIANYU_DATABASE_HOST": "mysql",
                "XIANYU_REDIS_HOST": "redis",
            }
            with patch.dict(os.environ, environment, clear=True):
                load_runtime_environment()
                self.assertEqual(os.environ["XIANYU_JWT_SECRET"], "jwt-value")
                self.assertIn("mysql%2Fvalue@mysql:3306", os.environ["XIANYU_DATABASE_URL"])
                self.assertIn("redis%3Avalue@redis:6379/0", os.environ["XIANYU_REDIS_URL"])


class LocalEnvironmentTests(unittest.TestCase):
    def test_source_template_exposes_only_two_manual_values(self) -> None:
        template = Path(__file__).resolve().parents[1] / ".env.example"
        active = [
            line.split("=", 1)[0]
            for line in template.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and "=" in line
        ]
        self.assertEqual(active, ["XIANYU_DATABASE_URL", "XIANYU_REDIS_URL"])

    def test_local_initializer_preserves_manual_values_and_generates_jwt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / ".env.local"
            target.write_text(
                "XIANYU_DATABASE_URL=mysql+pymysql://db\n"
                "XIANYU_REDIS_URL=redis://cache\n"
                "# XIANYU_JWT_SECRET=\n",
                encoding="utf-8",
            )
            changed, missing = initialize_local_environment(target)
            first = target.read_text(encoding="utf-8")
            changed_again, missing_again = initialize_local_environment(target)

            self.assertTrue(changed)
            self.assertFalse(changed_again)
            self.assertEqual(missing, ())
            self.assertEqual(missing_again, ())
            self.assertEqual(first, target.read_text(encoding="utf-8"))
            self.assertIn("XIANYU_JWT_SECRET=", first)
            self.assertNotIn("# XIANYU_JWT_SECRET=", first)


if __name__ == "__main__":
    unittest.main()
