"""Fail CI when known unsafe packaging and cross-platform patterns return."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def cache_key_file_counts(content: str) -> list[tuple[str, int]]:
    """Return GitLab jobs whose cache key tracks more than two files."""

    lines = content.splitlines()
    keys_by_indent: dict[int, str] = {}
    results: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        matched = re.match(r"^(\s*)([A-Za-z0-9_.:-]+):(?:\s+.*)?$", line)
        if not matched:
            continue
        indent = len(matched.group(1))
        key = matched.group(2)
        for existing_indent in tuple(keys_by_indent):
            if existing_indent >= indent:
                keys_by_indent.pop(existing_indent)
        keys_by_indent[indent] = key
        path = [keys_by_indent[level] for level in sorted(keys_by_indent)]
        if path[-3:] != ["cache", "key", "files"]:
            continue
        count = 0
        for child in lines[index + 1 :]:
            if not child.strip():
                continue
            child_indent = len(child) - len(child.lstrip())
            if child_indent <= indent:
                break
            if re.match(r"^\s*-\s+\S", child):
                count += 1
        if count > 2:
            results.append((path[0], count))
    return results


def main() -> int:
    failures: list[str] = []
    allowed = {
        ROOT / "apps" / "api" / "xianyu_admin_api" / "platform_runtime.py",
    }
    for root in (ROOT / "apps", ROOT / "integrations"):
        for path in root.rglob("*.py"):
            if path in allowed:
                continue
            content = path.read_text(encoding="utf-8")
            for pattern in ("os.geteuid(", 'Path("/proc")', "select.select("):
                if pattern in content:
                    failures.append(f"{path.relative_to(ROOT)} contains {pattern}")

    forbidden_ci = (
        "--insecure-registry",
        "GIT_SSL_NO_VERIFY",
        "http = true",
        "insecure = true",
    )
    for path in (ROOT / ".gitlab").rglob("*.yml"):
        content = path.read_text(encoding="utf-8")
        for pattern in forbidden_ci:
            if pattern in content:
                failures.append(f"{path.relative_to(ROOT)} contains {pattern}")

    stage_names = {"test", "binary", "docker"}
    for path in (ROOT / ".gitlab" / "ci").glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        for job_name, count in cache_key_file_counts(content):
            failures.append(
                f"{path.relative_to(ROOT)} {job_name}.cache.key.files "
                f"has {count} items; GitLab allows at most 2"
            )
        for line_number, line in enumerate(
            content.splitlines(),
            start=1,
        ):
            matched = re.match(r"^([A-Za-z0-9][A-Za-z0-9:_-]*):\s*$", line)
            if not matched:
                continue
            job_name = matched.group(1)
            if any(
                job_name == stage
                or job_name.startswith(f"{stage}:")
                or job_name.startswith(f"{stage}-")
                for stage in stage_names
            ):
                failures.append(
                    f"{path.relative_to(ROOT)}:{line_number} job name mixes in stage: {job_name}"
                )

    if failures:
        raise SystemExit("\n".join(failures))
    print("portability and CI naming checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
