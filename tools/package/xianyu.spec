# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(os.environ["XIANYU_BUILD_ROOT"]).resolve()
BUILD_INFO = Path(os.environ["XIANYU_BUILD_INFO"]).resolve()

datas = [
    (
        str(ROOT / "apps" / "api" / "xianyu_admin_api" / "data"),
        "apps/api/xianyu_admin_api/data",
    ),
    (
        str(ROOT / "apps" / "api" / "xianyu_admin_api" / "product_regions.json"),
        "apps/api/xianyu_admin_api",
    ),
    (
        str(ROOT / "integrations" / "xianyu_core" / "protocol_decrypt_worker.cjs"),
        "integrations/xianyu_core",
    ),
    (str(ROOT / "apps" / "admin" / "dist"), "apps/admin/dist"),
    (str(ROOT / ".env.example"), "."),
    (str(BUILD_INFO), "."),
]

upstream_root = ROOT / "third_party" / "XianYuApis"
for source in upstream_root.rglob("*"):
    if not source.is_file():
        continue
    relative = source.relative_to(ROOT)
    if (
        "__pycache__" in relative.parts
        or source.suffix in {".pyc", ".pyo"}
        or source.name.startswith(".env")
    ):
        continue
    datas.append((str(source), str(relative.parent)))

datas += collect_data_files("playwright")

hiddenimports = sorted(
    set(
        collect_submodules("apps.api.xianyu_admin_api")
        + collect_submodules("integrations.xianyu_core")
        + [
            "blackboxprotobuf",
            "execjs",
            "sqlalchemy.dialects.mysql.pymysql",
            "sqlalchemy.dialects.sqlite",
            "uvicorn.logging",
            "uvicorn.loops.auto",
            "uvicorn.protocols.http.auto",
            "uvicorn.protocols.websockets.auto",
            "uvicorn.lifespan.on",
        ]
    )
)

analysis = Analysis(
    [str(ROOT / "tools" / "package" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="xianyu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="xianyu",
)
