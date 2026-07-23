"""Create the configured MySQL database when it does not exist.

This is a local/deployment bootstrap helper. It deliberately avoids printing
credentials and only creates the database named in XIANYU_DATABASE_URL.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pymysql
from sqlalchemy.engine import make_url


MYSQL_DATABASE_RE = re.compile(r"^[A-Za-z0-9_]+$")


def main() -> int:
    database_url = os.getenv("XIANYU_DATABASE_URL", "").strip()
    if not database_url:
        print("XIANYU_DATABASE_URL is required", file=sys.stderr)
        return 1

    url = make_url(database_url)
    backend = url.get_backend_name()
    if backend != "mysql":
        print("XIANYU_DATABASE_URL must use mysql+pymysql", file=sys.stderr)
        return 1

    database_name = url.database or ""
    if not MYSQL_DATABASE_RE.fullmatch(database_name):
        print("MySQL database name must contain only letters, numbers, and underscore", file=sys.stderr)
        return 1

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
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()

    # Apply schema changes once before API and worker processes start in parallel.
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from apps.api.xianyu_admin_api.database import init_database

    init_database()
    print(f"database and schema ready: {database_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
