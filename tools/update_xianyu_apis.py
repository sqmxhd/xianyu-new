"""Inspect or refresh the vendored XianYuApis source snapshot.

The official source is copied into the parent repository working tree. Updates
remain ordinary parent-repository changes and are never committed automatically.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "third_party" / "XianYuApis"
METADATA_PATH = ROOT / "third_party" / "XianYuApis.vendor.json"
VENDOR_RELATIVE = VENDOR_DIR.relative_to(ROOT)
METADATA_RELATIVE = METADATA_PATH.relative_to(ROOT)
PROJECT_OVERRIDES = {Path("utils/package.json")}


def run(
    args: list[str],
    *,
    cwd: Path = ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(args: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=cwd)


def load_metadata() -> dict[str, object]:
    if not METADATA_PATH.is_file():
        raise SystemExit(f"vendor metadata is missing: {METADATA_PATH}")
    data = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(data.get("repository"), str) or not isinstance(data.get("commit"), str):
        raise SystemExit(f"vendor metadata is invalid: {METADATA_PATH}")
    return data


def ensure_vendor() -> None:
    if not VENDOR_DIR.is_dir():
        raise SystemExit(f"vendor directory is missing: {VENDOR_DIR}")
    if (VENDOR_DIR / ".git").exists():
        raise SystemExit(f"vendor directory must not contain Git metadata: {VENDOR_DIR}")


def vendor_status() -> str:
    return git(
        [
            "status",
            "--short",
            "--",
            str(VENDOR_RELATIVE),
            str(METADATA_RELATIVE),
        ]
    ).stdout.strip()


def remote_commit(repository: str, branch: str) -> str:
    result = run(["git", "ls-remote", repository, f"refs/heads/{branch}"])
    line = result.stdout.strip()
    if not line:
        raise SystemExit(f"upstream branch not found: {repository}#{branch}")
    return line.split(maxsplit=1)[0]


def tracked_paths(checkout: Path) -> set[Path]:
    output = git(["ls-files", "-z"], cwd=checkout).stdout
    return {Path(item) for item in output.split("\0") if item}


def current_vendor_paths() -> set[Path]:
    output = git(["ls-files", "-z", "--", str(VENDOR_RELATIVE)]).stdout
    prefix = f"{VENDOR_RELATIVE.as_posix()}/"
    return {
        Path(item.removeprefix(prefix))
        for item in output.split("\0")
        if item.startswith(prefix)
    }


def remove_empty_directories() -> None:
    directories = sorted(
        (path for path in VENDOR_DIR.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


def update(metadata: dict[str, object]) -> None:
    dirty = vendor_status()
    if dirty:
        raise SystemExit(f"vendor source has uncommitted changes; refusing update:\n{dirty}")

    repository = str(metadata["repository"])
    branch = str(metadata.get("branch") or "master")
    before = str(metadata["commit"])
    with tempfile.TemporaryDirectory(prefix="xianyu-apis-update-") as temporary:
        checkout = Path(temporary) / "source"
        run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                branch,
                repository,
                str(checkout),
            ]
        )
        after = git(["rev-parse", "HEAD"], cwd=checkout).stdout.strip()
        upstream_paths = tracked_paths(checkout)

        for relative in current_vendor_paths() - upstream_paths - PROJECT_OVERRIDES:
            target = VENDOR_DIR / relative
            if target.is_file() or target.is_symlink():
                target.unlink()

        for relative in upstream_paths - PROJECT_OVERRIDES:
            source = checkout / relative
            target = VENDOR_DIR / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)

        remove_empty_directories()

    metadata["commit"] = after
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"before: {before[:12]}")
    print(f"after:  {after[:12]}")
    print("The vendor changes are in the parent working tree; review and commit them on main.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or refresh vendored XianYuApis")
    parser.add_argument("--update", action="store_true", help="copy the latest official source into the vendor directory")
    args = parser.parse_args()

    ensure_vendor()
    metadata = load_metadata()
    repository = str(metadata["repository"])
    branch = str(metadata.get("branch") or "master")
    pinned = str(metadata["commit"])
    latest = remote_commit(repository, branch)
    dirty = vendor_status()

    print(f"path:    {VENDOR_DIR}")
    print(f"source:  {repository}#{branch}")
    print(f"pinned:  {pinned[:12]}")
    print(f"latest:  {latest[:12]}")
    print("status:  clean" if not dirty else f"status:\n{dirty}")
    if args.update:
        update(metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
