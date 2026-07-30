from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from apps.runtime_paths import resource_path, runtime_path
from integrations.xianyu_core.protocol_worker import _NodeDecryptWorker
from tools.package.build import resolve_version


class PackagingContractTests(unittest.TestCase):
    def test_pipeline_publishes_only_the_registry_image_from_tg_or_tags(self) -> None:
        root = Path(__file__).resolve().parents[1]
        pipeline = (root / ".gitlab-ci.yml").read_text(encoding="utf-8")
        common_jobs = (root / ".gitlab" / "ci" / "common.yml").read_text(
            encoding="utf-8"
        )
        docker_jobs = (root / ".gitlab" / "ci" / "docker.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("stages:\n  - test\n  - docker", pipeline)
        self.assertNotIn(".gitlab/ci/binary.yml", pipeline)
        self.assertFalse((root / ".gitlab" / "ci" / "binary.yml").exists())
        self.assertIn("image-amd64:", docker_jobs)
        self.assertNotIn("archive-amd64:", docker_jobs)
        self.assertIn(".container-release:", common_jobs)
        self.assertIn('$CI_COMMIT_BRANCH == "tg"', common_jobs)
        self.assertNotIn("$CI_DEFAULT_BRANCH", common_jobs)
        self.assertIn("$CI_REGISTRY_IMAGE:latest", docker_jobs)
        self.assertNotIn("$CI_REGISTRY_IMAGE:edge", docker_jobs)
        self.assertIn(
            '--output "type=image,\\"name=$names\\",push=true"',
            docker_jobs,
        )

    def test_container_geoip_resources_are_complete(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = {
            "geoip.db": (
                24_189_340,
                "44fc8373bf2c86a429dd4d6d240283a3768c4ca187db8811fcd9cb65c1d7cb3e",
            ),
            "ip2region_v4.xdb": (
                10_641_896,
                "59d4ce4ffd9dfcab94ff08dd0fa842e3cc7f19684f16a12396e80a0226a5d3a7",
            ),
        }
        resource_root = root / "apps" / "api" / "xianyu_admin_api" / "data"
        for name, (size, digest) in expected.items():
            with self.subTest(name=name):
                path = resource_root / name
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_size, size)
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    digest,
                )

        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("python -m tools.package.entry verify", dockerfile)
        self.assertIn(
            'VOLUME ["/data/product-images", "/data/web-notification-sounds", '
            '"/data/browser-profiles", '
            '"/data/fingerprint-chromium", "/data/standard-chromium"]',
            dockerfile,
        )
        dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("!apps/api/xianyu_admin_api/data/**", dockerignore)
        entrypoint = (root / "tools" / "container_entry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('Path("/data/web-notification-sounds")', entrypoint)

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
        self.assertNotIn("\n    build:", compose)
        self.assertEqual(compose.count("pull_policy: always"), 3)
        self.assertEqual(compose.count("platform: linux/amd64"), 3)
        self.assertEqual(
            compose.count(
                '${XIANYU_IMAGE:-192.168.2.5:5050/bug/xianyu:latest}'
            ),
            3,
        )
        self.assertIn(
            "web-notification-sounds:/data/web-notification-sounds",
            compose,
        )
        self.assertIn(
            'XIANYU_FINGERPRINT_BROWSER_MAX_ARCHIVE_BYTES: "536870912"',
            compose,
        )
        self.assertIn("max-size: \"20m\"", compose)
        self.assertIn("max-file: \"5\"", compose)
        self.assertNotIn("BASE_IMAGE_PREFIX=", bundled)
        self.assertNotIn("BASE_IMAGE_PREFIX=", external)

    def test_gateway_limits_browser_archives_without_widening_general_api(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        configs = (
            root / "deploy" / "nginx" / "xianyu-container.conf",
            root / "deploy" / "nginx" / "xianyu-admin.conf",
            root / "deploy" / "nginx" / "xianyu-admin-https.conf",
        )

        for config in configs:
            with self.subTest(config=config.name):
                contents = config.read_text(encoding="utf-8")
                self.assertIn(
                    "location = /api/settings/browser-runtime/standard/upload",
                    contents,
                )
                self.assertIn(
                    "location = /api/settings/browser-runtime/fingerprint/upload",
                    contents,
                )
                self.assertEqual(contents.count("client_max_body_size 520m;"), 2)
                self.assertEqual(contents.count("client_max_body_size 64m;"), 1)
                self.assertEqual(contents.count("proxy_request_buffering off;"), 2)
                self.assertGreaterEqual(contents.count("access_log off;"), 2)

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
