"""Fail CI when known unsafe packaging and cross-platform patterns return."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
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
