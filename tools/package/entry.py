"""Portable command entrypoint used by the frozen binary distribution."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from apps.runtime_paths import (
    configure_bundled_runtime,
    resource_path,
    runtime_path,
)


def _build_info() -> dict[str, str]:
    for candidate in (
        runtime_path("build-info.json"),
        resource_path("build-info.json"),
    ):
        try:
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(loaded, dict):
            return {str(key): str(value) for key, value in loaded.items()}
    return {"name": "xianyu-admin", "version": "unknown"}


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from apps.api.xianyu_admin_api.main import app

    options: dict[str, object] = {
        "host": args.host,
        "port": args.port,
        "log_level": args.log_level,
        "proxy_headers": False,
    }
    if args.ssl_certfile or args.ssl_keyfile:
        if not args.ssl_certfile or not args.ssl_keyfile:
            raise SystemExit("--ssl-certfile and --ssl-keyfile must be used together")
        options["ssl_certfile"] = args.ssl_certfile
        options["ssl_keyfile"] = args.ssl_keyfile
    uvicorn.run(app, **options)
    return 0


def _worker(args: argparse.Namespace) -> int:
    from apps.api.xianyu_admin_api.worker import run_worker

    asyncio.run(
        run_worker(
            once=args.once,
            idle_sleep_seconds=args.idle_sleep,
        )
    )
    return 0


def _verify() -> int:
    os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
    os.environ.setdefault(
        "XIANYU_JWT_SECRET",
        "packaging-verification-secret-with-sufficient-length",
    )
    os.environ.setdefault("XIANYU_IM_VERIFICATION_BROWSER_ENABLED", "false")

    from apps.api.xianyu_admin_api.main import app
    from apps.api.xianyu_admin_api.worker import run_worker
    from integrations.xianyu_core.upstream import DEFAULT_UPSTREAM_ROOT

    required = (
        resource_path(
            "apps", "api", "xianyu_admin_api", "data", "ip2region_v4.xdb"
        ),
        resource_path("apps", "api", "xianyu_admin_api", "data", "geoip.db"),
        resource_path(
            "apps", "api", "xianyu_admin_api", "product_regions.json"
        ),
        resource_path("apps", "admin", "dist", "index.html"),
        DEFAULT_UPSTREAM_ROOT / "static" / "goofish_js_version_2.js",
        resource_path(
            "integrations", "xianyu_core", "protocol_decrypt_worker.cjs"
        ),
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"packaged resources are missing: {', '.join(missing)}")

    node = shutil.which("node.exe" if os.name == "nt" else "node")
    if not node:
        raise RuntimeError("bundled Node runtime is missing")
    completed = subprocess.run(
        [node, "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    result = {
        "app": app.title,
        "worker": callable(run_worker),
        "node": completed.stdout.strip(),
        "upstream": str(DEFAULT_UPSTREAM_ROOT),
        "status": "ok",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xianyu")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="run the API and bundled web UI")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--log-level", default="info")
    serve.add_argument("--ssl-certfile")
    serve.add_argument("--ssl-keyfile")

    worker = subparsers.add_parser("worker", help="run the background queue worker")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--idle-sleep", type=float, default=2.0)

    subparsers.add_parser("version", help="print build version")
    subparsers.add_parser("verify", help="verify packaged runtime resources")
    return parser


def main() -> int:
    configure_bundled_runtime()
    parser = _parser()
    arguments = sys.argv[1:] or ["serve"]
    args = parser.parse_args(arguments)
    command = args.command
    if command == "serve":
        return _serve(args)
    if command == "worker":
        return _worker(args)
    if command == "version":
        info = _build_info()
        print(f"{info.get('name', 'xianyu-admin')} {info.get('version', 'unknown')}")
        return 0
    if command == "verify":
        return _verify()
    parser.error(f"unsupported command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
