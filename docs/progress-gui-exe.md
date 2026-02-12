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

## Test Suite Status
- **Total tests:** 71 (50 existing + 7 worker + 14 GUI)
- **All passing:** yes
- **Last full run:** after Task 6

## New Files Created
| File | Description |
|------|-------------|
| `worker.py` | QCWorker QThread for background batch processing |
| `gui.py` | PySide6 MainWindow with file pickers, log, progress bar |
| `tests/test_worker.py` | 7 tests for QCWorker signals and behavior |
| `tests/test_gui.py` | 14 tests for MainWindow UI state and slots |
| `twist_qc_gui.spec` | PyInstaller spec for Windows .exe build |
| `build.bat` | Windows build script (pre-downloads models + builds) |
