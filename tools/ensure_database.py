"""Create the configured development database and initialize its schema."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from sqlalchemy.engine import URL, make_url


DATABASE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _ensure_mysql(url: URL) -> None:
    import pymysql

    connection = pymysql.connect(
        host=url.host or "127.0.0.1",
        port=url.port or 3306,
        user=url.username or "",
        password=url.password or "",
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


def _ensure_postgresql(url: URL) -> None:
    import psycopg
    from psycopg import sql

    connection = psycopg.connect(
        host=url.host or "127.0.0.1",
        port=url.port or 5432,
        user=url.username or "",
        password=url.password or "",
        dbname="postgres",
        connect_timeout=5,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (url.database,),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(url.database or ""),
                        sql.Identifier(url.username or ""),
                    )
                )
    finally:
        connection.close()


def main() -> int:
    database_url = os.getenv("XIANYU_DATABASE_URL", "").strip()
    if not database_url:
        print("XIANYU_DATABASE_URL is required", file=sys.stderr)
        return 1

    url = make_url(database_url)
    backend = url.get_backend_name()
    database_name = url.database or ""
    if backend in {"mysql", "postgresql"} and not DATABASE_NAME_RE.fullmatch(
        database_name
    ):
        print(
            "database name must contain only letters, numbers, and underscore",
            file=sys.stderr,
        )
        return 1

    if backend == "mysql":
        _ensure_mysql(url)
    elif backend == "postgresql":
        _ensure_postgresql(url)
    elif backend != "sqlite":
        print(f"unsupported database backend: {backend}", file=sys.stderr)
        return 1

    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from apps.api.xianyu_admin_api.database import init_database

    init_database()
    print(f"database and schema ready: {database_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
