"""Role-based Docker entrypoint for API, worker, and HTTPS gateways."""

from __future__ import annotations

import os
import pwd
import secrets
import shutil
import sys
from pathlib import Path
from urllib.parse import quote


APP_USER = "xianyu"
SECRET_ENVIRONMENT = {
    "jwt-secret": "XIANYU_JWT_SECRET",
    "mysql-root-password": "MYSQL_ROOT_PASSWORD",
    "mysql-password": "MYSQL_PASSWORD",
    "redis-password": "REDIS_PASSWORD",
}
WRITABLE_DIRECTORIES = (
    Path("/data/product-images"),
    Path("/data/contact-avatars"),
    Path("/data/web-notification-sounds"),
    Path("/data/browser-profiles"),
    Path("/data/fingerprint-chromium"),
    Path("/data/standard-chromium"),
)


def _secret_directory() -> Path:
    value = os.getenv("XIANYU_RUNTIME_SECRET_DIR", "").strip()
    if not value:
        raise RuntimeError("XIANYU_RUNTIME_SECRET_DIR is required")
    return Path(value)


def _read_secret(name: str) -> str:
    path = _secret_directory() / name
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"runtime secret is unavailable: {name}") from exc
    if not value:
        raise RuntimeError(f"runtime secret is empty: {name}")
    return value


def _secret_has_value(path: Path) -> bool:
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def _directory_has_data(path: Path) -> bool:
    try:
        return any(path.iterdir())
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RuntimeError(f"cannot inspect secret guard directory: {path}") from exc


def initialize_runtime_secrets() -> None:
    requested = tuple(
        dict.fromkeys(
            item.strip()
            for item in os.getenv(
                "XIANYU_GENERATED_SECRETS", "jwt-secret"
            ).split(",")
            if item.strip()
        )
    )
    unknown = sorted(set(requested) - set(SECRET_ENVIRONMENT))
    if unknown:
        raise RuntimeError(f"unsupported runtime secrets: {', '.join(unknown)}")

    directory = _secret_directory()
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o755)
    missing = [name for name in requested if not _secret_has_value(directory / name)]
    guards = tuple(
        Path(item.strip())
        for item in os.getenv("XIANYU_SECRET_GUARD_DIRS", "").split(",")
        if item.strip()
    )
    guarded_existing_data = any(_directory_has_data(path) for path in guards)

    generated: list[str] = []
    for name in missing:
        environment_name = SECRET_ENVIRONMENT[name]
        supplied = os.getenv(environment_name, "").strip()
        if guarded_existing_data and not supplied:
            raise RuntimeError(
                "existing persistent data was found while runtime secret "
                f"{name} is missing; restore the original secret instead of "
                "generating a replacement"
            )
        value = supplied or secrets.token_urlsafe(48)
        temporary = directory / f".{name}.{os.getpid()}.tmp"
        temporary.write_text(value + "\n", encoding="utf-8")
        os.chmod(temporary, 0o444)
        temporary.replace(directory / name)
        generated.append(name)

    for name in requested:
        _read_secret(name)
    action = "generated" if generated else "reused"
    print(f"runtime secrets {action}: {', '.join(requested)}", flush=True)


def load_runtime_environment() -> None:
    if not os.getenv("XIANYU_RUNTIME_SECRET_DIR", "").strip():
        return

    if not os.getenv("XIANYU_JWT_SECRET", "").strip():
        os.environ["XIANYU_JWT_SECRET"] = _read_secret("jwt-secret")
    if not os.getenv("XIANYU_DATABASE_URL", "").strip():
        host = os.getenv("XIANYU_DATABASE_HOST", "").strip()
        if host:
            user = os.getenv("XIANYU_DATABASE_USER", "xianyu").strip()
            database = os.getenv("XIANYU_DATABASE_NAME", "xianyu_admin").strip()
            port = os.getenv("XIANYU_DATABASE_PORT", "3306").strip()
            password = quote(_read_secret("mysql-password"), safe="")
            os.environ["XIANYU_DATABASE_URL"] = (
                f"mysql+pymysql://{quote(user, safe='')}:{password}@{host}:{port}/"
                f"{quote(database, safe='')}?charset=utf8mb4"
            )
    if not os.getenv("XIANYU_REDIS_URL", "").strip():
        host = os.getenv("XIANYU_REDIS_HOST", "").strip()
        if host:
            port = os.getenv("XIANYU_REDIS_PORT", "6379").strip()
            database = os.getenv("XIANYU_REDIS_DATABASE", "0").strip()
            password = quote(_read_secret("redis-password"), safe="")
            os.environ["XIANYU_REDIS_URL"] = (
                f"redis://:{password}@{host}:{port}/{database}"
            )

    internal_ca = Path("/etc/xianyu/ca/internal-root.crt")
    if internal_ca.is_file():
        os.environ.setdefault("XIANYU_CHATWOOT_CA_BUNDLE", str(internal_ca))


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
    if role == "init-config":
        initialize_runtime_secrets()
        return 0
    if role in {"api", "worker", "worker-health"}:
        load_runtime_environment()
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
    if role == "worker-health":
        import asyncio

        from apps.api.xianyu_admin_api.process_health import read_worker_heartbeat

        state = asyncio.run(read_worker_heartbeat())
        return 0 if state.get("online") else 1
    gateway_configs = {
        "gateway": "/app/deploy/nginx/xianyu-container.conf",
        "chatwoot-gateway": "/app/deploy/nginx/chatwoot-container.conf",
    }
    if role in gateway_configs:
        nginx = shutil.which("nginx")
        if not nginx:
            raise RuntimeError("nginx is not installed")
        exec_command(
            [
                nginx,
                "-c",
                gateway_configs[role],
                "-g",
                "daemon off;",
            ]
        )
    raise SystemExit(f"unsupported container role: {role}")


if __name__ == "__main__":
    raise SystemExit(main())
