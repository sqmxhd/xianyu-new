"""Initialize the private source-runtime environment without exposing secrets."""

from __future__ import annotations

import os
import secrets
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".env.example"
TARGET = ROOT / ".env.local"
AUTOMATIC_NAME = "XIANYU_JWT_SECRET"
REQUIRED_NAMES = ("XIANYU_DATABASE_URL", "XIANYU_REDIS_URL")


def _active_values(contents: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip()
    return values


def initialize_local_environment(target: Path = TARGET) -> tuple[bool, tuple[str, ...]]:
    created = False
    if not target.exists():
        shutil.copy2(TEMPLATE, target)
        created = True

    contents = target.read_text(encoding="utf-8")
    values = _active_values(contents)
    current_secret = values.get(AUTOMATIC_NAME, "")
    if not current_secret or "replace" in current_secret.lower():
        generated = secrets.token_urlsafe(48)
        lines = contents.splitlines()
        replacement = f"{AUTOMATIC_NAME}={generated}"
        replaced = False
        for index, raw_line in enumerate(lines):
            normalized = raw_line.strip().lstrip("#").strip()
            if normalized.startswith(f"{AUTOMATIC_NAME}="):
                lines[index] = replacement
                replaced = True
                break
        if not replaced:
            lines.append(replacement)
        contents = "\n".join(lines) + "\n"
        target.write_text(contents, encoding="utf-8")
        created = True

    os.chmod(target, 0o600)
    values = _active_values(contents)
    missing = tuple(
        name
        for name in REQUIRED_NAMES
        if not values.get(name, "") or "replace-me" in values[name].lower()
    )
    return created, missing


def main() -> int:
    changed, missing = initialize_local_environment()
    if changed:
        print("已初始化 .env.local，并安全生成本地 JWT 密钥。")
    if missing:
        print(
            ".env.local 仍需填写：" + "、".join(missing),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
