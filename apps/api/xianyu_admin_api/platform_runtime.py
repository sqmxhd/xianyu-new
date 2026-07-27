"""Small operating-system compatibility helpers for the application runtime."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterator


def is_root_process() -> bool:
    get_effective_user_id = getattr(os, "geteuid", None)
    return bool(callable(get_effective_user_id) and get_effective_user_id() == 0)


def iter_process_arguments() -> Iterator[tuple[int, list[str]]]:
    """Yield process arguments where the host exposes a Linux-style procfs."""

    proc_root = Path("/proc")
    if os.name != "posix" or not proc_root.is_dir():
        return
    for process_dir in proc_root.glob("[0-9]*"):
        try:
            arguments = [
                item.decode("utf-8", "ignore")
                for item in (process_dir / "cmdline").read_bytes().split(b"\0")
                if item
            ]
            yield int(process_dir.name), arguments
        except (OSError, PermissionError, ValueError):
            continue


def system_browser_candidates() -> tuple[str, ...]:
    candidates: list[str] = []
    for command in (
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "chrome.exe",
        "msedge.exe",
    ):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(resolved)

    if os.name == "nt":
        roots = tuple(
            Path(value)
            for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
            if (value := os.getenv(name, "").strip())
        )
        relative_paths = (
            Path("Google/Chrome/Application/chrome.exe"),
            Path("Chromium/Application/chrome.exe"),
            Path("Microsoft/Edge/Application/msedge.exe"),
        )
        for root in roots:
            for relative in relative_paths:
                candidate = root / relative
                if candidate.is_file():
                    candidates.append(str(candidate))

    return tuple(dict.fromkeys(candidates))
