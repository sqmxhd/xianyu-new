"""Pre-commit audit for files that should not be committed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PREFIXES = (
    ".venv/",
    "node_modules/",
    "apps/admin/node_modules/",
    "apps/admin/dist/",
    "data/",
)
FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
}


def git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def staged_files() -> list[str]:
    raw = git(["diff", "--cached", "--name-only"])
    return [line.strip() for line in raw.splitlines() if line.strip()]


def main() -> int:
    staged = staged_files()
    violations: list[str] = []
    for path in staged:
        if path in FORBIDDEN_NAMES or path.endswith(".pyc") or path.endswith(".tsbuildinfo"):
            violations.append(path)
            continue
        if any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            violations.append(path)

    upstream_git = ROOT / "third_party" / "XianYuApis" / ".git"
    if upstream_git.exists():
        violations.append("third_party/XianYuApis/.git")

    if violations:
        print("forbidden staged files:")
        for path in violations:
            print(f"  - {path}")
        return 1

    print("git audit ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
