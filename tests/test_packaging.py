from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from apps.runtime_paths import resource_path, runtime_path
from integrations.xianyu_core.protocol_worker import _NodeDecryptWorker
from tools.package.build import resolve_version


class PackagingContractTests(unittest.TestCase):
    def test_container_deployment_has_no_fixed_public_origin(self) -> None:
        root = Path(__file__).resolve().parents[1]
        compose = (root / "compose.yml").read_text(encoding="utf-8")
        bundled = (root / ".env.docker.example").read_text(encoding="utf-8")
        external = (root / ".env.docker.external.example").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("https://192.168.2.3", compose)
        self.assertNotIn("https://192.168.2.3", bundled)
        self.assertNotIn("https://192.168.2.3", external)
        self.assertIn('profiles:\n      - bundled', compose)
        self.assertIn('required: false', compose)
        self.assertIn(
            '"${XIANYU_BIND_IP:-0.0.0.0}:${XIANYU_HTTPS_PORT:-6161}:8443"',
            compose,
        )
        self.assertIn("COMPOSE_PROFILES=bundled", bundled)
        self.assertIn("COMPOSE_PROFILES=", external)

    def test_source_runtime_and_resource_roots_are_stable(self) -> None:
        self.assertEqual(
            resource_path("apps", "admin", "package.json"),
            Path(__file__).resolve().parents[1] / "apps" / "admin" / "package.json",
        )
        self.assertEqual(
            runtime_path("data", "product-images"),
            Path(__file__).resolve().parents[1] / "data" / "product-images",
        )

    def test_package_version_is_sanitized(self) -> None:
        self.assertEqual(resolve_version("v1.2.3"), "1.2.3")
        self.assertEqual(resolve_version("feature/package test"), "feature-package-test")

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_protocol_worker_uses_portable_pipe_reader(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "decoder.js"
            source.write_text(
                'function decrypt(data) { return "decoded:" + data; }\n',
                encoding="utf-8",
            )
            worker = _NodeDecryptWorker(source, timeout=5)
            try:
                self.assertEqual(worker.decrypt("hello"), "decoded:hello")
            finally:
                worker.close()


if __name__ == "__main__":
    unittest.main()
