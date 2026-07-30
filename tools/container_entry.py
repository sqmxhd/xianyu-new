"""Role-based Docker entrypoint for API, worker, and HTTPS gateway containers."""

from __future__ import annotations

import os
import pwd
import shutil
import sys
from pathlib import Path


APP_USER = "xianyu"
WRITABLE_DIRECTORIES = (
    Path("/data/product-images"),
    Path("/data/web-notification-sounds"),
    Path("/data/browser-profiles"),
    Path("/data/fingerprint-chromium"),
    Path("/data/standard-chromium"),
)


def prepare_writable_directories() -> None:
    account = pwd.getpwnam(APP_USER)
    for directory in WRITABLE_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)
        if os.geteuid() == 0:
            os.chown(directory, account.pw_uid, account.pw_gid)


def drop_privileges() -> None:
    if os.geteuid() != 0:
        return
    account = pwd.getpwnam(APP_USER)
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ["HOME"] = account.pw_dir


def exec_command(arguments: list[str]) -> None:
    os.execvp(arguments[0], arguments)


def main() -> int:
    role = sys.argv[1] if len(sys.argv) > 1 else "api"
    if role in {"api", "worker"}:
        prepare_writable_directories()
        drop_privileges()

    if role == "api":
        exec_command(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "apps.api.xianyu_admin_api.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--no-proxy-headers",
            ]
        )
    if role == "worker":
        exec_command(
            [
                sys.executable,
                "-m",
                "apps.api.xianyu_admin_api.worker",
                *sys.argv[2:],
            ]
        )
    if role == "gateway":
        nginx = shutil.which("nginx")
        if not nginx:
            raise RuntimeError("nginx is not installed")
        exec_command(
            [
                nginx,
                "-c",
                "/app/deploy/nginx/xianyu-container.conf",
                "-g",
                "daemon off;",
            ]
        )
    raise SystemExit(f"unsupported container role: {role}")


if __name__ == "__main__":
    raise SystemExit(main())
