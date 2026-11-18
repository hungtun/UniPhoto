# -*- mode: python ; coding: utf-8 -*-
"""Slim PyInstaller --onedir specification for the standalone UniPhoto FastAPI + ONNX + MediaPipe backend."""

import importlib.util
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/uniphoto-mpl")

from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
)

PROJECT_ROOT = Path(SPECPATH).resolve()

datas = []
binaries = []
hiddenimports = []

# Collect full UniPhoto application package (lazy-imported ONNX cv2.dnn, pure-DCT pHash, MediaPipe services)
hiddenimports += collect_submodules("app")

# Packages with custom native C libraries / task assets without complete built-in PyInstaller hooks
for pkg in (
    "mediapipe",
    "pillow_heif",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += [
        (src, dst)
        for (src, dst) in pkg_datas
        if "mediapipe/tasks/python/test" not in dst.replace("\\", "/")
    ]
    binaries += pkg_binaries
    hiddenimports += [
        mod
        for mod in pkg_hidden
        if not mod.startswith("mediapipe.tasks.python.test")
    ]

hiddenimports += collect_submodules("pydantic_settings")

# Explicit runtime submodules loaded dynamically by Uvicorn, FastAPI, and SQLAlchemy SQLite
hiddenimports += [
    "sqlalchemy.dialects.sqlite",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "multipart",
]

# Ensure MediaPipe Tasks C library remains addressable at mediapipe/tasks/c/libmediapipe.dylib
try:
    _mp_spec = importlib.util.find_spec("mediapipe")
    if _mp_spec and _mp_spec.origin:
        _mp_c_lib = (
            Path(_mp_spec.origin).resolve().parent / "tasks" / "c" / "libmediapipe.dylib"
        )
        if _mp_c_lib.is_file() and not any(
            dst.replace("\\", "/") == "mediapipe/tasks/c" and Path(src).name == "libmediapipe.dylib"
            for (src, dst) in binaries
        ):
            binaries.append((str(_mp_c_lib), "mediapipe/tasks/c"))
except Exception:
    pass

# Exclude heavy ML training/export stacks (torch, torchvision, scipy, imagehash, pywt, matplotlib, sklearn)
# and unused GUI/audio/DB-driver packages
excludes = [
    "torch",
    "torchvision",
    "torchaudio",
    "scipy",
    "pywt",
    "imagehash",
    "sklearn",
    "scikit_learn",
    "matplotlib",
    "mpl_toolkits",
    "contourpy",
    "kiwisolver",
    "fontTools",
    "cycler",
    "pyparsing",
    "sounddevice",
    "_sounddevice_data",
    "mediapipe.tasks.python.test",
    "tkinter",
    "_tkinter",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "pip",
    "setuptools",
    "MySQLdb",
    "psycopg2",
    "pysqlite2",
    "oracledb",
    "cx_Oracle",
    "pyodbc",
    "pymssql",
    "watchfiles",
    "werkzeug",
    "cryptography",
]

a = Analysis(
    [str(PROJECT_ROOT / "run.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(PROJECT_ROOT / "scripts" / "pyi_rth_stub_unused.py")],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="uniphoto-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name="uniphoto-backend",
)
