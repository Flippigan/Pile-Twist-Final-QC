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
# PaddleOCR v2.9+ caches models via PaddleX in ~/.paddlex/official_models/.
# At runtime, PADDLE_PDX_CACHE_HOME is set to this bundled directory.
paddlex_dir = os.path.expanduser("~/.paddlex")
model_datas = [(paddlex_dir, ".paddlex")] if os.path.isdir(paddlex_dir) else []

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
