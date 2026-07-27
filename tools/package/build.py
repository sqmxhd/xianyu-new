"""Build a native onedir distribution and a platform-specific archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
SAFE_VERSION = re.compile(r"[^A-Za-z0-9._-]+")


def resolve_version(explicit: str | None) -> str:
    raw = str(explicit or os.getenv("CI_COMMIT_TAG") or "").strip()
    if raw.startswith("v") and len(raw) > 1:
        raw = raw[1:]
    if not raw:
        raw = str(os.getenv("CI_COMMIT_SHORT_SHA") or "").strip()
    if not raw:
        completed = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        raw = completed.stdout.strip()
    normalized = SAFE_VERSION.sub("-", raw).strip("-.")
    if not normalized:
        raise RuntimeError("unable to derive a safe package version")
    return normalized


def copy_node_runtime(distribution: Path) -> str:
    node = shutil.which("node.exe" if os.name == "nt" else "node")
    if not node:
        raise RuntimeError("Node.js 20+ must be installed before packaging")
    completed = subprocess.run(
        [node, "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    version = completed.stdout.strip()
    match = re.match(r"v(\d+)", version)
    if not match or int(match.group(1)) < 20:
        raise RuntimeError(f"Node.js 20+ is required, found {version}")

    target_root = distribution / "runtime" / "node"
    target_root.mkdir(parents=True, exist_ok=True)
    source = Path(node).resolve()
    target = target_root / ("node.exe" if os.name == "nt" else "node")
    shutil.copy2(source, target)
    if os.name == "posix":
        target.chmod(0o755)
        libraries = subprocess.run(
            ["ldd", str(source)],
            check=False,
            capture_output=True,
            text=True,
        ).stdout
        library_root = target_root / "lib"
        system_libraries = {
            "ld-linux-x86-64.so.2",
            "libc.so.6",
            "libdl.so.2",
            "libm.so.6",
            "libpthread.so.0",
            "librt.so.1",
        }
        for line in libraries.splitlines():
            matched = re.search(r"=>\s+(/[^\s]+)", line)
            if not matched:
                continue
            dependency = Path(matched.group(1))
            if dependency.name in system_libraries or not dependency.is_file():
                continue
            library_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dependency, library_root / dependency.name)
    return version


def write_launchers(distribution: Path) -> None:
    if os.name == "nt":
        (distribution / "start-api.cmd").write_text(
            '@echo off\r\n"%~dp0xianyu.exe" serve %*\r\n',
            encoding="utf-8",
        )
        (distribution / "start-worker.cmd").write_text(
            '@echo off\r\n"%~dp0xianyu.exe" worker %*\r\n',
            encoding="utf-8",
        )
        return
    launchers = {
        "start-api.sh": '#!/usr/bin/env sh\nexec "$(dirname "$0")/xianyu" serve "$@"\n',
        "start-worker.sh": '#!/usr/bin/env sh\nexec "$(dirname "$0")/xianyu" worker "$@"\n',
    }
    for name, content in launchers.items():
        path = distribution / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)


def archive_distribution(distribution: Path, destination: Path, platform: str) -> None:
    if platform == "windows-x64":
        with zipfile.ZipFile(
            destination,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as bundle:
            for source in distribution.rglob("*"):
                if source.is_file():
                    bundle.write(
                        source,
                        Path(distribution.name) / source.relative_to(distribution),
                    )
        return
    with tarfile.open(destination, mode="w:gz", compresslevel=9) as bundle:
        bundle.add(distribution, arcname=distribution.name, recursive=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("linux-x64", "windows-x64"), required=True)
    parser.add_argument("--version")
    args = parser.parse_args()

    expected_platform = "windows-x64" if os.name == "nt" else "linux-x64"
    if args.platform != expected_platform:
        raise RuntimeError(
            f"{args.platform} must be built on its native host; current host is {expected_platform}"
        )
    frontend_index = ROOT / "apps" / "admin" / "dist" / "index.html"
    if not frontend_index.is_file():
        raise RuntimeError("frontend is not built: apps/admin/dist/index.html is missing")

    version = resolve_version(args.version)
    package_base = f"xianyu-admin-{version}-{args.platform}"
    staging = ARTIFACTS / ".package" / args.platform
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    build_info_path = staging / "build-info.json"
    build_info = {
        "name": "xianyu-admin",
        "version": version,
        "platform": args.platform,
        "commit": os.getenv("CI_COMMIT_SHA", ""),
        "built_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
    }
    build_info_path.write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    environment = {
        **os.environ,
        "XIANYU_BUILD_ROOT": str(ROOT),
        "XIANYU_BUILD_INFO": str(build_info_path),
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(staging / "dist"),
            "--workpath",
            str(staging / "work"),
            str(ROOT / "tools" / "package" / "xianyu.spec"),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )

    generated = staging / "dist" / "xianyu"
    distribution = staging / package_base
    generated.rename(distribution)
    shutil.copy2(ROOT / ".env.example", distribution / ".env.example")
    shutil.copy2(build_info_path, distribution / "build-info.json")
    for directory in (
        distribution / "data" / "product-images",
        distribution / "data" / "browser-profiles",
        distribution / "third_party" / "fingerprint-chromium",
        distribution / "third_party" / "standard-chromium",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    build_info["node"] = copy_node_runtime(distribution)
    (distribution / "build-info.json").write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_launchers(distribution)

    executable = distribution / ("xianyu.exe" if os.name == "nt" else "xianyu")
    subprocess.run(
        [str(executable), "verify"],
        cwd=distribution,
        check=True,
        timeout=120,
    )

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    suffix = ".zip" if args.platform == "windows-x64" else ".tar.gz"
    destination = ARTIFACTS / f"{package_base}{suffix}"
    destination.unlink(missing_ok=True)
    archive_distribution(distribution, destination, args.platform)
    digest_builder = hashlib.sha256()
    with destination.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest_builder.update(chunk)
    digest = digest_builder.hexdigest()
    checksum = destination.with_name(destination.name + ".sha256")
    checksum.write_text(f"{digest}  {destination.name}\n", encoding="ascii")
    print(destination)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
