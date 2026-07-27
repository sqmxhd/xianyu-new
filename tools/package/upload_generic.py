"""Upload tagged native artifacts to the GitLab Generic Package Registry."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("linux-x64", "windows-x64"), required=True)
    args = parser.parse_args()

    tag = os.getenv("CI_COMMIT_TAG", "").strip()
    if not tag:
        print("not a tag pipeline; generic package upload skipped")
        return 0
    version = tag[1:] if tag.startswith("v") else tag
    api = os.getenv("CI_API_V4_URL", "").rstrip("/")
    project_id = os.getenv("CI_PROJECT_ID", "").strip()
    token = os.getenv("CI_JOB_TOKEN", "").strip()
    if not all((api, project_id, token)):
        raise RuntimeError("GitLab package upload variables are incomplete")

    root = Path(__file__).resolve().parents[2]
    candidates = sorted(
        (root / "artifacts").glob(f"xianyu-admin-*-{args.platform}.*")
    )
    files = [
        path
        for path in candidates
        if path.is_file()
        and (
            path.name.endswith((".tar.gz", ".zip"))
            or path.name.endswith((".tar.gz.sha256", ".zip.sha256"))
        )
    ]
    if not files:
        raise RuntimeError(f"no {args.platform} artifacts found")

    for path in files:
        encoded_name = urllib.parse.quote(path.name, safe="")
        encoded_version = urllib.parse.quote(version, safe="")
        url = (
            f"{api}/projects/{project_id}/packages/generic/"
            f"xianyu-admin/{encoded_version}/{encoded_name}"
        )
        request = urllib.request.Request(
            url,
            data=path.read_bytes(),
            method="PUT",
            headers={
                "JOB-TOKEN": token,
                "Content-Type": "application/octet-stream",
            },
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            if response.status not in {200, 201}:
                raise RuntimeError(
                    f"upload failed for {path.name}: HTTP {response.status}"
                )
        print(f"uploaded {path.name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise
