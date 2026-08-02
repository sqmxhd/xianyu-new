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
    def test_pipeline_delivers_registry_and_downloadable_images(self) -> None:
        root = Path(__file__).resolve().parents[1]
        pipeline = (root / ".gitlab-ci.yml").read_text(encoding="utf-8")
        common_jobs = (root / ".gitlab" / "ci" / "common.yml").read_text(
            encoding="utf-8"
        )
        docker_jobs = (root / ".gitlab" / "ci" / "docker.yml").read_text(
            encoding="utf-8"
        )
        test_jobs = (root / ".gitlab" / "ci" / "test.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("stages:\n  - test\n  - docker", pipeline)
        self.assertNotIn(".gitlab/ci/binary.yml", pipeline)
        self.assertFalse((root / ".gitlab" / "ci" / "binary.yml").exists())
        self.assertIn("image-amd64:", docker_jobs)
        self.assertIn("archive-amd64:", docker_jobs)
        self.assertIn("backend:", test_jobs)
        self.assertIn("\nfrontend:", test_jobs)
        self.assertIn("\nportability:", test_jobs)
        self.assertNotIn("\nverify:", test_jobs)
        self.assertEqual(docker_jobs.count("- job: backend"), 2)
        self.assertEqual(docker_jobs.count("- job: frontend"), 2)
        self.assertEqual(docker_jobs.count("- job: portability"), 2)
        self.assertNotIn("chatwoot-source-amd64:", docker_jobs)
        self.assertNotIn("chatwoot-image-amd64:", docker_jobs)
        self.assertIn(".container-delivery:", common_jobs)
        self.assertIn('$CI_COMMIT_BRANCH == "main"', common_jobs)
        self.assertNotIn('$CI_COMMIT_BRANCH == "tg"', common_jobs)
        self.assertNotIn("when: manual", common_jobs)
        self.assertNotIn("$CI_COMMIT_TAG", common_jobs)
        self.assertNotIn("$CI_DEFAULT_BRANCH", common_jobs)
        self.assertIn("$CI_REGISTRY_IMAGE:latest", docker_jobs)
        self.assertIn('RELEASE_SERIES: "1.0"', pipeline)
        self.assertEqual(
            docker_jobs.count('version="${RELEASE_SERIES}.${CI_PIPELINE_IID}"'),
            2,
        )
        self.assertNotIn("$CI_REGISTRY_IMAGE:edge", docker_jobs)
        self.assertIn(
            '--output "type=image,\\"name=$names\\",push=true"',
            docker_jobs,
        )
        self.assertNotIn("BundleImage.Dockerfile", docker_jobs)
        self.assertNotIn("assemble_offline_bundle.sh", docker_jobs)
        self.assertNotIn("chatwoot", docker_jobs.lower())
        self.assertEqual(docker_jobs.count("--opt platform=linux/amd64"), 2)
        self.assertIn("gzip -9", docker_jobs)
        self.assertIn("expire_in: 14 days", docker_jobs)
        self.assertIn(
            "xianyu-admin-*-linux-amd64.docker.tar.gz",
            docker_jobs,
        )
        self.assertIn("- 开始部署.sh", docker_jobs)
        self.assertIn("- compose.all.yml", docker_jobs)

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
            'VOLUME ["/data/product-images", "/data/contact-avatars", '
            '"/data/web-notification-sounds", '
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
        self.assertIn('Path("/data/contact-avatars")', entrypoint)
        self.assertIn('if role == "app"', entrypoint)
        self.assertIn("run_application_stack", entrypoint)

    def test_container_deployment_has_no_fixed_public_origin(self) -> None:
        root = Path(__file__).resolve().parents[1]
        compose = (root / "compose.yml").read_text(encoding="utf-8")
        compose_all = (root / "compose.all.yml").read_text(encoding="utf-8")
        external = (root / ".env.docker.example").read_text(encoding="utf-8")
        self.assertFalse((root / ".env.docker.all.example").exists())

        self.assertFalse((root / ".env.docker.external.example").exists())
        for contents in (compose, compose_all, external):
            self.assertNotIn("https://192.168.2.3", contents)
        self.assertIn(
            '"${XIANYU_BIND_IP:-0.0.0.0}:${XIANYU_HTTPS_PORT:-6161}:8443"',
            compose,
        )
        self.assertIn(
            '"${XIANYU_BIND_IP:-0.0.0.0}:${XIANYU_HTTPS_PORT:-6161}:8443"',
            compose_all,
        )
        for contents in (compose, compose_all):
            self.assertNotIn("\n    build:", contents)
            self.assertIn("max-size: \"20m\"", contents)
            self.assertIn("max-file: \"5\"", contents)

        self.assertEqual(compose.count("pull_policy: always"), 1)
        self.assertEqual(compose.count("platform: linux/amd64"), 1)
        self.assertIn(
            "web-notification-sounds:/data/web-notification-sounds", compose
        )
        self.assertIn("runtime-secrets:/run/xianyu-secrets", compose)
        self.assertIn("./config/tls:/run/secrets/xianyu-tls:ro", compose)
        self.assertIn("container_name: xianyu-app", compose)
        self.assertNotIn("\n  worker:", compose)
        self.assertNotIn("\n  gateway:", compose)

        self.assertNotIn("pull_policy: always", compose_all)
        self.assertEqual(compose_all.count("pull_policy: never"), 4)
        self.assertIn("${DEPLOY_ROOT:?DEPLOY_ROOT 未配置}", compose_all)
        self.assertIn("/contact-avatars:/data/contact-avatars", compose_all)
        self.assertIn("/postgres:/var/lib/postgresql/data", compose_all)
        self.assertIn("certificates/xianyu", compose_all)
        self.assertIn("certificates/chatwoot", compose_all)
        self.assertIn("container_name: xianyu-app", compose_all)
        self.assertIn("container_name: xianyu-database", compose_all)
        self.assertIn("container_name: xianyu-redis", compose_all)
        self.assertIn("container_name: xianyu-chatwoot", compose_all)
        self.assertIn("container_name: xianyu-chatwoot-worker", compose_all)
        self.assertIn("name: xianyu_internal", compose_all)
        self.assertIn("\n  chatwoot-rails:", compose_all)
        self.assertIn("\n  chatwoot-sidekiq:", compose_all)
        self.assertNotIn("\n  chatwoot-gateway:", compose_all)
        self.assertNotIn("\n  init-config:", compose_all)
        self.assertNotIn("\n  chatwoot-prepare:", compose_all)

        self.assertNotIn("\n  mysql:", compose)
        self.assertNotIn("\n  redis:", compose)
        self.assertNotIn("\n  mysql:", compose_all)
        self.assertIn("\n  postgres:", compose_all)
        self.assertIn("\n  redis:", compose_all)
        self.assertIn("POSTGRES_PASSWORD_FILE:", compose_all)
        self.assertIn(
            "command: [postgres, -c, shared_preload_libraries=pg_stat_statements]",
            compose_all,
        )
        self.assertNotIn("REDIS_URL: redis://chatwoot-redis:6379", compose_all)
        self.assertIn("XIANYU_REDIS_DATABASE: \"0\"", compose_all)
        self.assertIn("POSTGRES_DATABASE: chatwoot", compose_all)
        services_block = compose_all.split("services:\n", 1)[1].split(
            "\nnetworks:\n", 1
        )[0]
        self.assertEqual(
            {
                line.strip().removesuffix(":")
                for line in services_block.splitlines()
                if line.startswith("  ")
                and not line.startswith("    ")
                and line.strip().endswith(":")
            },
            {
                "postgres",
                "redis",
                "xianyu-app",
                "chatwoot-rails",
                "chatwoot-sidekiq",
            },
        )
        self.assertEqual(
            [
                line.split("=", 1)[0]
                for line in external.splitlines()
                if line and not line.startswith("#") and "=" in line
            ],
            ["XIANYU_DATABASE_URL", "XIANYU_REDIS_URL"],
        )

    def test_deployment_imports_project_and_prepares_official_dependencies(self) -> None:
        root = Path(__file__).resolve().parents[1]
        deploy = (root / "开始部署.sh").read_text(encoding="utf-8")

        self.assertIn("xianyu-admin-*-linux-amd64.docker.tar.gz", deploy)
        self.assertIn('DEPLOY_ROOT="$SCRIPT_DIR/XIANYU_DATA"', deploy)
        self.assertIn("docker load", deploy)
        self.assertIn("docker pull", deploy)
        self.assertIn("在线拉取官方镜像", deploy)
        self.assertIn("导入本地官方镜像包", deploy)
        self.assertIn("chatwoot/chatwoot:v4.16.0", deploy)
        self.assertNotIn("mysql:8.4", deploy)
        self.assertIn("redis:7.4-alpine", deploy)
        self.assertIn("pgvector/pgvector:pg16", deploy)
        self.assertIn("REDIS_URL=redis://:%s@redis:6379/1", deploy)
        self.assertIn("initialize_shared_databases", deploy)
        self.assertIn("guard_legacy_mysql_data", deploy)
        self.assertIn("旧数据未被修改", deploy)
        self.assertIn("bundle exec rails db:chatwoot_prepare", deploy)
        for extension in ("pg_stat_statements", "pg_trgm", "pgcrypto", "vector"):
            self.assertIn(
                f"CREATE EXTENSION IF NOT EXISTS {extension};",
                deploy,
            )
        self.assertIn("for attempt in 1 2 3", deploy)
        self.assertIn("deployment-complete.env", deploy)
        self.assertIn("检测到未完成的部署", deploy)
        self.assertIn('certificates/xianyu/privkey.pem"', deploy)
        self.assertIn('[ ! -e "$path" ] || chmod 600 "$path"', deploy)
        self.assertNotIn(
            '[ -z "$(current_version)" ] || fail "已经存在部署',
            deploy,
        )
        self.assertIn("证书管理", deploy)
        self.assertIn("99991231235959Z", deploy)
        self.assertIn("CHATWOOT_HTTPS_PORT", deploy)
        self.assertIn("现有数据、配置、证书和密钥不会被修改", deploy)
        self.assertFalse(
            (root / "tools" / "package" / "assemble_offline_bundle.sh").exists()
        )
        self.assertFalse(
            (root / "tools" / "package" / "BundleImage.Dockerfile").exists()
        )

    def test_postgresql_runtime_is_packaged_for_the_shared_database(self) -> None:
        root = Path(__file__).resolve().parents[1]
        requirements = (root / "apps" / "api" / "requirements.txt").read_text(
            encoding="utf-8"
        )
        spec = (root / "tools" / "package" / "xianyu.spec").read_text(
            encoding="utf-8"
        )
        database = (
            root / "apps" / "api" / "xianyu_admin_api" / "database.py"
        ).read_text(encoding="utf-8")
        self.assertIn("psycopg[binary]>=3.2,<4", requirements)
        self.assertIn('"sqlalchemy.dialects.postgresql.psycopg"', spec)
        self.assertNotIn("`trigger`", database)

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
