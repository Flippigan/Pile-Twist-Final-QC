# Windows GUI .exe — Implementation Progress

**Plan:** [2026-02-12-windows-gui-exe-plan.md](plans/2026-02-12-windows-gui-exe-plan.md)
**Design:** [2026-02-12-windows-gui-exe-design.md](plans/2026-02-12-windows-gui-exe-design.md)
**Branch:** `feat/windows-gui-exe`
**Started:** 2026-02-12

---

## Task 1: Update Dependencies — DONE
**Commit:** `8257155` — `feat: add PySide6 and pytest-qt dependencies for GUI`

- Added `PySide6>=6.5.0` and `pytest-qt>=4.2.0` to `requirements.txt`
- Installed: PySide6 6.10.2, pytest-qt 4.5.0, shiboken6 6.10.2
- All 50 existing tests pass (no regressions)

## Task 2: QCWorker QThread — DONE
**Commit:** `a78f661` — `feat: add QCWorker background thread with signal-based progress`

- Created `worker.py`: QCWorker QThread with 6 signals (status, progress_setup, image_started, image_done, finished, error)
- `_preload_ocr()` function pre-loads OCR engine, raises on failure for user-visible error
- Reuses `process_image()` and `get_images()` from `twist_qc.py` (zero duplication)
- Created `tests/test_worker.py`: 7 tests covering signal emissions, progress counts, error handling, CSV save, QCd folder creation
- All 7 tests pass

## Task 3: PySide6 GUI Main Window — DONE
**Commit:** `00496a5` — `feat: add PySide6 GUI main window with file pickers, progress log, and bar`

- Created `gui.py`: MainWindow with CSV picker, photos folder picker, Run button (disabled until both inputs set), scrolling progress log, progress bar
- File pickers use native OS dialogs (QFileDialog)
- Worker lifecycle: connects all 6 signals, locks UI during processing, unlocks on completion/error
- Created `tests/test_gui.py`: 14 tests covering initial state, input validation, all slot methods
- All 14 tests pass
- Full suite: **71/71 tests pass** (50 existing + 7 worker + 14 GUI)

## Task 4: Manual Smoke Test — DONE

- Launched `python gui.py` on macOS — window opens, browse buttons work, Run button enables after both inputs set
- PaddleOCR processing works end-to-end through the GUI

## Task 5: PyInstaller Build Configuration — DONE

- Created `twist_qc_gui.spec`: PyInstaller spec with `collect_all` for paddlepaddle/paddleocr, hidden imports for all project modules, `--windowed` mode (no console), excludes unused LLM deps
- Created `build.bat`: Windows build script that pre-downloads PaddleOCR models, installs PyInstaller, builds the .exe
- Spec includes model bundling from `~/.paddleocr/` (auto-detected if present)
- Actual build must run on Windows (no cross-compile)

## Task 6: PaddleOCR Model Bundling — DONE

- Modified `providers/paddleocr_provider.py` `_get_ocr()` to detect `sys.frozen` (PyInstaller bundle mode)
- When frozen: sets `model_dir` kwarg to `os.path.join(os.path.dirname(sys.executable), ".paddleocr")`
- Spec file bundles `~/.paddleocr/` as `.paddleocr` in the dist folder
- `build.bat` runs model pre-download before build to ensure cache exists
- All 71 tests still pass (frozen mode path not triggered in normal Python)

---

## Known Issues

### FIXED: `model_dir` is not a valid PaddleOCR argument
- **Error:** `Failed to load OCR engine: Unknown argument model_dir`
- **Root cause (two bugs):**
  1. `_get_ocr()` passed `model_dir` kwarg to `PaddleOCR()`, but v2.9+ doesn't accept it — models are per-component (`text_detection_model_dir`, `text_recognition_model_dir`)
  2. Spec file bundled `~/.paddleocr/` which doesn't exist — v2.9+ caches models via PaddleX in `~/.paddlex/official_models/`
- **Fix:** Set `PADDLE_PDX_CACHE_HOME` env var when `sys.frozen` (redirects all PaddleX model resolution to bundled dir). Updated spec to bundle `~/.paddlex` instead of `~/.paddleocr`.
- **Status:** Fixed — 71/71 tests pass

### FIXED: PaddleOCR pipeline not found in PyInstaller bundle
- **Error:** `Failed to load OCR engine: The pipeline (OCR) does not exist! Please use a pipeline name or a config file path!`
- **Root cause:** Spec only collected `paddlepaddle` and `paddleocr` but not `paddlex`. PaddleOCR v2.9+ delegates pipeline resolution to PaddleX, which resolves `"OCR"` → `paddlex/configs/pipelines/OCR.yaml` via `Path(__file__)` traversal. Without `collect_all("paddlex")`, the YAML config files aren't in the bundle.
- **Fix:** Added `collect_all("paddlex")` to `twist_qc_gui.spec` — bundles all PaddleX data files including pipeline configs.
- **Status:** Fixed

### FIXED: Dependency error during pipeline creation in PyInstaller bundle
- **Error:** `Failed to load OCR engine: A dependency error occurred during pipeline creation. Please refer to the installation documentation to ensure all required dependencies are installed.`
- **Where:** `providers/paddleocr_provider.py` `_get_ocr()` — PaddleOCR/PaddleX pipeline creation fails when running as bundled .exe

#### Root Cause (traced)

**Error chain:**
1. `PaddleOCR()` → `_create_paddlex_pipeline()` (`paddleocr/_pipelines/base.py:104`)
2. `OCRPipeline.__init__()` has `@pipeline_requires_extra("ocr", alt="ocr-core")` decorator (`paddlex/inference/pipelines/ocr/pipeline.py:485`)
3. `require_extra()` → `is_extra_available("ocr") or is_extra_available("ocr-core")` (`paddlex/utils/deps.py:191`)
4. `is_extra_available()` iterates deps, calls `is_dep_available(dep)` for each (`paddlex/utils/deps.py:180`)
5. `is_dep_available()` uses `importlib.metadata.version(dep)` to check if packages are installed (`paddlex/utils/deps.py:112`)
6. If metadata lookup fails → `DependencyError` → caught in `base.py:106-108` and re-raised as `RuntimeError` with the generic message

**Why it fails in the bundle:**
- The `ocr-core` extra requires 6 deps: `imagesize`, `opencv-contrib-python`, `pyclipper`, `pypdfium2`, `python-bidi`, `shapely`
- All 6 are installed locally and `is_extra_available("ocr-core")` = True in dev — PaddleOCR works fine
- The spec only runs `collect_all()` for `paddlepaddle`, `paddleocr`, `paddlex` — bundling only their `.dist-info` metadata
- The 6 `ocr-core` deps are bundled as **code** (via transitive dependency analysis) but their `.dist-info` metadata is NOT collected
- `importlib.metadata.version("pyclipper")` → `PackageNotFoundError` → `is_dep_available()` returns `False`
- `is_extra_available("ocr-core")` → `False`, `is_extra_available("ocr")` → also `False` → `DependencyError`

**In short:** The actual libraries are in the bundle, but PaddleX can't verify them because their package metadata is missing.

#### Fix (v2 — comprehensive)

Previous fix only patched `require_extra`, which was insufficient. Two additional problems:
1. **`@lru_cache` poisoning:** `is_dep_available()` and `is_extra_available()` cache `False` results during the import chain (triggered by top-level `from paddleocr import PaddleOCR`). Even with `require_extra` bypassed, other code paths reading cached results could trigger errors.
2. **Multiple raise paths:** `DependencyError` can be raised from `require_deps`, `require_hpip`, etc. — not just `require_extra`.

New fix in `_get_ocr()` when `sys.frozen` is True:
1. Clear `is_dep_available.cache_clear()` and `is_extra_available.cache_clear()` (purge stale `False` results from import-time)
2. Replace `is_dep_available` → always returns `True`
3. Replace `is_extra_available` → always returns `True`
4. Replace `require_extra` → no-op
5. Replace `require_deps` → no-op

Safe because all required libraries ARE present in the bundle — only their `.dist-info` metadata is missing. Forward-compatible: doesn't depend on specific dep names.

- **Status:** Fixed — 73/73 tests pass. Needs Windows bundle verification.

---

## Test Suite Status
- **Total tests:** 73 (50 existing + 7 worker + 14 GUI + 2 frozen-mode patch)
- **All passing:** yes
- **Last full run:** after comprehensive dependency monkey-patch fix (v2)

## New Files Created
| File | Description |
|------|-------------|
| `worker.py` | QCWorker QThread for background batch processing |
| `gui.py` | PySide6 MainWindow with file pickers, log, progress bar |
| `tests/test_worker.py` | 7 tests for QCWorker signals and behavior |
| `tests/test_gui.py` | 14 tests for MainWindow UI state and slots |
| `twist_qc_gui.spec` | PyInstaller spec for Windows .exe build |
| `build.bat` | Windows build script (pre-downloads models + builds) |
