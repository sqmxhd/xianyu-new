"""Internal network health checks for local Xianyu admin testing.

The script intentionally avoids printing database or Redis credentials.
It validates only connectivity and basic service responses.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.xianyu_admin_api.database import build_engine
from apps.api.xianyu_admin_api.settings import settings


@dataclass(slots=True)
class CheckResult:
    name: str
    ok: bool
    message: str
    elapsed_ms: int


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def check_database() -> CheckResult:
    start = time.perf_counter()
    try:
        engine = build_engine(settings.database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return CheckResult("mysql/database", True, "connected", _elapsed_ms(start))
    except Exception as exc:  # noqa: BLE001 - health checks should report exact failure class.
        return CheckResult("mysql/database", False, exc.__class__.__name__, _elapsed_ms(start))


def check_redis() -> CheckResult:
    start = time.perf_counter()
    if not settings.redis_url:
        return CheckResult("redis", False, "XIANYU_REDIS_URL not configured", _elapsed_ms(start))
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
        pong = client.ping()
        return CheckResult("redis", bool(pong), "pong" if pong else "no pong", _elapsed_ms(start))
    except Exception as exc:  # noqa: BLE001
        return CheckResult("redis", False, exc.__class__.__name__, _elapsed_ms(start))


def check_api_health() -> CheckResult:
    start = time.perf_counter()
    try:
        with urlopen(settings.api_health_url, timeout=3) as response:  # noqa: S310 - local/internal operator URL.
            body = json.loads(response.read().decode("utf-8"))
        ok = (
            response.status == 200
            and bool(body.get("ok"))
        )
        detail = f"HTTP {response.status}; API event loop responsive"
        return CheckResult("api/health", ok, detail, _elapsed_ms(start))
    except URLError as exc:
        return CheckResult("api/health", False, exc.__class__.__name__, _elapsed_ms(start))
    except Exception as exc:  # noqa: BLE001
        return CheckResult("api/health", False, exc.__class__.__name__, _elapsed_ms(start))


def main() -> int:
    checks = [check_database(), check_redis(), check_api_health()]
    for item in checks:
        status = "OK" if item.ok else "FAIL"
        print(f"[{status}] {item.name}: {item.message} ({item.elapsed_ms}ms)")
    return 0 if all(item.ok for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
