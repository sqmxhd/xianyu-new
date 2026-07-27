"""Runtime and bundled-resource path helpers shared by source and frozen builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled).resolve() if bundled else source_root()


def runtime_root() -> Path:
    configured = os.getenv("XIANYU_RUNTIME_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return source_root()


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def runtime_path(*parts: str) -> Path:
    return runtime_root().joinpath(*parts)


def configure_bundled_runtime() -> Path:
    """Set the working directory and external-runtime search paths."""

    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    os.environ.setdefault("XIANYU_RUNTIME_ROOT", str(root))

    node_root = root / "runtime" / "node"
    node_binary_dir = node_root
    if node_binary_dir.is_dir():
        path_items = os.environ.get("PATH", "").split(os.pathsep)
        if str(node_binary_dir) not in path_items:
            os.environ["PATH"] = os.pathsep.join(
                [str(node_binary_dir), *[item for item in path_items if item]]
            )

    if os.name == "posix":
        node_library_dir = node_root / "lib"
        if node_library_dir.is_dir():
            current = os.environ.get("LD_LIBRARY_PATH", "")
            library_items = [item for item in current.split(os.pathsep) if item]
            if str(node_library_dir) not in library_items:
                os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
                    [str(node_library_dir), *library_items]
                )
    return root
