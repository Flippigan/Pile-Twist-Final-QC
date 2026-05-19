# twist_qc_gui.spec — PyInstaller spec for Twist QC Automation GUI
# Build: pyinstaller twist_qc_gui.spec --clean
# Must be run ON WINDOWS (no cross-compile).

import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all PaddleOCR + PaddlePaddle + PaddleX data files, binaries, hidden imports.
# PaddleX is needed because PaddleOCR v2.9+ delegates pipeline resolution to PaddleX,
# which loads configs from paddlex/configs/pipelines/*.yaml via __file__ path traversal.
paddle_datas, paddle_bins, paddle_imports = collect_all("paddlepaddle")
ocr_datas, ocr_bins, ocr_imports = collect_all("paddleocr")
pdx_datas, pdx_bins, pdx_imports = collect_all("paddlex")

# Bundle pre-downloaded PaddleX/PaddleOCR models for offline use.
# PaddleOCR v2.9+ caches models via PaddleX. The build workflow sets
# PADDLE_PDX_CACHE_HOME explicitly so the pre-download step and this spec
# agree on the cache location. We fall back to ~/.paddlex for local builds.
# At runtime, PADDLE_PDX_CACHE_HOME is set to this bundled directory (see gui.py).
paddlex_dir = os.environ.get("PADDLE_PDX_CACHE_HOME") or os.path.expanduser("~/.paddlex")
print(f"[spec] PADDLE cache lookup: {paddlex_dir!r} (exists={os.path.isdir(paddlex_dir)})")
if not os.path.isdir(paddlex_dir):
    raise FileNotFoundError(
        f"PaddleX cache directory not found at {paddlex_dir!r}. "
        f"Run pre-download step first or set PADDLE_PDX_CACHE_HOME."
    )
official_models_dir = os.path.join(paddlex_dir, "official_models")
if not os.path.isdir(official_models_dir):
    raise FileNotFoundError(
        f"official_models/ not found under {paddlex_dir!r}. Pre-download did not populate models."
    )

# PyInstaller's `datas=[(dir, dest)]` directory-tuple recursion was producing
# empty bundles on Windows — the .paddlex/ shell was created but no model
# weight files made it through. Enumerate files explicitly so PyInstaller
# receives a flat list of (file, dest_dir) pairs, which it handles reliably.
model_datas = []
for root, _, files in os.walk(paddlex_dir):
    for fn in files:
        src_path = os.path.join(root, fn)
        rel_dir = os.path.relpath(root, paddlex_dir)
        dest_dir = ".paddlex" if rel_dir == "." else os.path.join(".paddlex", rel_dir)
        model_datas.append((src_path, dest_dir))
if not model_datas:
    raise FileNotFoundError(
        f"No model files found under {paddlex_dir!r}. Pre-download did not populate models."
    )
print(f"[spec] Bundling {len(model_datas)} model files from {paddlex_dir!r} -> .paddlex/ in bundle")

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=paddle_bins + ocr_bins + pdx_bins,
    datas=paddle_datas + ocr_datas + pdx_datas + model_datas,
    hiddenimports=[
        "providers",
        "providers.paddleocr_provider",
        "csv_updater",
        "image_editor",
        "twist_qc",
        "worker",
    ]
    + paddle_imports
    + ocr_imports
    + pdx_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Unused LLM provider deps
        "openai",
        "anthropic",
        "google.genai",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TwistQC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # --windowed: no terminal window
    icon=None,  # TODO: add icon path if desired
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TwistQC",
)
