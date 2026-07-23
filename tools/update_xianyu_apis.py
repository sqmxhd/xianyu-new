"""Safely inspect or update third_party/XianYuApis.

This script never edits integration adapter code. It only operates inside the
upstream checkout and refuses to update when that checkout has local changes.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_DIR = ROOT / "third_party" / "XianYuApis"


def git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(UPSTREAM_DIR), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ensure_checkout() -> None:
    if not (UPSTREAM_DIR / ".git").exists():
        raise SystemExit(f"not a git checkout: {UPSTREAM_DIR}")


def status() -> str:
    return git(["status", "--short"]).stdout.strip()


def current_ref() -> str:
    branch = git(["branch", "--show-current"]).stdout.strip()
    commit = git(["rev-parse", "--short", "HEAD"]).stdout.strip()
    return f"{branch or 'detached'}@{commit}"


def update() -> None:
    dirty = status()
    if dirty:
        raise SystemExit(f"upstream checkout is dirty; refusing update:\n{dirty}")
    print(f"before: {current_ref()}")
    git(["fetch", "--prune", "origin"])
    git(["pull", "--ff-only"])
    print(f"after:  {current_ref()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or update third_party/XianYuApis")
    parser.add_argument("--update", action="store_true", help="fetch and fast-forward pull upstream")
    args = parser.parse_args()

    ensure_checkout()
    print(f"path:   {UPSTREAM_DIR}")
    print(f"ref:    {current_ref()}")
    dirty = status()
    print("status: clean" if not dirty else f"status:\n{dirty}")
    if args.update:
        update()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
