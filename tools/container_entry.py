"""Role-based Docker entrypoint for API, worker, and HTTPS gateways."""

from __future__ import annotations

import os
import pwd
import secrets
import shutil
import signal
import ssl
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


APP_USER = "xianyu"
SECRET_ENVIRONMENT = {
    "jwt-secret": "XIANYU_JWT_SECRET",
    "mysql-root-password": "MYSQL_ROOT_PASSWORD",
    "mysql-password": "MYSQL_PASSWORD",
    "postgres-root-password": "POSTGRES_ROOT_PASSWORD",
    "postgres-password": "POSTGRES_PASSWORD",
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
    missing = [name for name in requested if not _secret_has_value(directory / name)]
    if not missing:
        for name in requested:
            _read_secret(name)
        print(f"runtime secrets reused: {', '.join(requested)}", flush=True)
        return

    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o755)
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
    print(f"runtime secrets generated: {', '.join(generated)}", flush=True)


def load_runtime_environment() -> None:
    if not os.getenv("XIANYU_RUNTIME_SECRET_DIR", "").strip():
        return

    if not os.getenv("XIANYU_JWT_SECRET", "").strip():
        os.environ["XIANYU_JWT_SECRET"] = _read_secret("jwt-secret")
    if not os.getenv("XIANYU_DATABASE_URL", "").strip():
        host = os.getenv("XIANYU_DATABASE_HOST", "").strip()
        if host:
            scheme = os.getenv(
                "XIANYU_DATABASE_SCHEME", "postgresql+psycopg"
            ).strip()
            user = os.getenv("XIANYU_DATABASE_USER", "xianyu_app").strip()
            database = os.getenv("XIANYU_DATABASE_NAME", "xianyu_admin").strip()
            default_port = "3306" if scheme.startswith("mysql") else "5432"
            port = os.getenv("XIANYU_DATABASE_PORT", default_port).strip()
            default_secret = (
                "mysql-password" if scheme.startswith("mysql") else "postgres-password"
            )
            secret_name = os.getenv(
                "XIANYU_DATABASE_PASSWORD_SECRET", default_secret
            ).strip()
            password = quote(_read_secret(secret_name), safe="")
            query = "?charset=utf8mb4" if scheme.startswith("mysql") else ""
            os.environ["XIANYU_DATABASE_URL"] = (
                f"{scheme}://{quote(user, safe='')}:{password}@{host}:{port}/"
                f"{quote(database, safe='')}{query}"
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


def _application_process_kwargs() -> dict[str, object]:
    """Return subprocess identity settings for unprivileged application roles."""

    if os.geteuid() != 0:
        return {}
    account = pwd.getpwnam(APP_USER)
    return {
        "user": account.pw_uid,
        "group": account.pw_gid,
        "extra_groups": (),
    }


def _terminate_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline and any(
        process.poll() is None for process in processes
    ):
        time.sleep(0.2)
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    for process in processes:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def run_application_stack() -> int:
    """Run API, background worker, and both HTTPS virtual hosts together."""

    initialize_runtime_secrets()
    load_runtime_environment()
    prepare_writable_directories()
    nginx = shutil.which("nginx")
    if not nginx:
        raise RuntimeError("nginx is not installed")

    app_environment = os.environ.copy()
    app_environment["HOME"] = pwd.getpwnam(APP_USER).pw_dir
    application_kwargs = _application_process_kwargs()
    commands = (
        (
            "api",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "apps.api.xianyu_admin_api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-proxy-headers",
            ],
            app_environment,
            application_kwargs,
        ),
        (
            "worker",
            [sys.executable, "-m", "apps.api.xianyu_admin_api.worker"],
            app_environment,
            application_kwargs,
        ),
        (
            "nginx",
            [
                nginx,
                "-c",
                "/app/deploy/nginx/xianyu-container.conf",
                "-g",
                "daemon off;",
            ],
            os.environ.copy(),
            {},
        ),
    )
    processes: list[subprocess.Popen[bytes]] = []
    names: dict[int, str] = {}
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    previous_handlers = {
        sig: signal.signal(sig, request_stop)
        for sig in (signal.SIGTERM, signal.SIGINT)
    }
    try:
        for name, command, environment, identity in commands:
            process = subprocess.Popen(
                command,
                env=environment,
                start_new_session=True,
                **identity,
            )
            processes.append(process)
            names[process.pid] = name
            print(f"started {name} pid={process.pid}", flush=True)

        exit_code = 0
        while not stopping:
            exited = next(
                (process for process in processes if process.poll() is not None),
                None,
            )
            if exited is not None:
                exit_code = exited.returncode or 1
                print(
                    f"critical process exited name={names[exited.pid]} "
                    f"exit_code={exit_code}",
                    file=sys.stderr,
                    flush=True,
                )
                break
            time.sleep(0.5)
        _terminate_processes(processes)
        return exit_code
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


def application_health() -> int:
    """Validate the public gateway, API, and worker heartbeat."""

    load_runtime_environment()
    context = ssl._create_unverified_context()
    try:
        urlopen(
            "https://127.0.0.1:8443/api/health",
            context=context,
            timeout=3,
        ).read()
    except Exception:
        return 1

    import asyncio

    from apps.api.xianyu_admin_api.process_health import read_worker_heartbeat

    state = asyncio.run(read_worker_heartbeat())
    return 0 if state.get("online") else 1


def main() -> int:
    role = sys.argv[1] if len(sys.argv) > 1 else "api"
    if role == "init-config":
        initialize_runtime_secrets()
        return 0
    if role in {"api", "worker", "worker-health", "app-health"}:
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
    if role == "app":
        return run_application_stack()
    if role == "app-health":
        return application_health()
    gateway_configs = {
        "gateway": "/app/deploy/nginx/xianyu-container.conf",
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
