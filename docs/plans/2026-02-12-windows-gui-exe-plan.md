# Windows GUI .exe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Package Twist QC Automation as a standalone Windows .exe with a PySide6 GUI so non-technical users can run it without Python installed.

**Architecture:** Two new files: `worker.py` (QThread that reuses `process_image()` and `get_images()` from `twist_qc.py`) and `gui.py` (PySide6 MainWindow with file pickers, progress bar, and scrolling log). All existing modules (`providers/`, `image_editor.py`, `csv_updater.py`) remain unchanged. The GUI replaces `config.yaml` entirely — users pick CSV and photos folder via native file dialogs. PyInstaller packages everything into a `--onedir` distributable.

**Tech Stack:** PySide6 (GUI), PyInstaller (packaging), pytest-qt (testing)

**Design doc:** `docs/plans/2026-02-12-windows-gui-exe-design.md`

---

### Task 1: Update Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Add PySide6 and pytest-qt to requirements.txt**

Append to `requirements.txt`:
```
PySide6>=6.5.0
pytest-qt>=4.2.0
```

**Step 2: Install new dependencies**

Run: `source .venv/bin/activate && pip install PySide6 pytest-qt`

**Step 3: Verify existing tests still pass**

Run: `python -m pytest -v`
Expected: All 59 existing tests PASS

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add PySide6 and pytest-qt dependencies for GUI"
```

---

### Task 2: Create worker.py — QCWorker QThread

The worker reuses `process_image()` and `get_images()` from `twist_qc.py` (no duplication). It wraps the existing batch loop in a QThread with signal-based progress reporting.

**Files:**
- Create: `worker.py`
- Create: `tests/test_worker.py`

**Step 1: Write failing tests for QCWorker**

Create `tests/test_worker.py`:

```python
"""Tests for QCWorker background thread."""
import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker import QCWorker


@pytest.fixture
def worker_csv(tmp_path):
    """Minimal CSV for worker tests."""
    csv_path = tmp_path / "test.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["UPN", "Twist_Deg"])
        writer.writerow([27870, ""])
        writer.writerow([7770, ""])
    return csv_path


@pytest.fixture
def worker_photos(tmp_path):
    """Photos folder with two dummy .jpg files."""
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "278700.jpg").write_bytes(b"\xff\xd8dummy")
    (photos / "77700.jpg").write_bytes(b"\xff\xd8dummy")
    return photos


class TestQCWorkerSignals:

    @patch("worker.process_image")
    @patch("worker._preload_ocr")
    def test_emits_image_started_and_done(
        self, mock_preload, mock_process, qtbot, worker_csv, worker_photos
    ):
        mock_process.return_value = (True, "Pile 27870: new_twist=1.50\u00b0")
        worker = QCWorker(worker_csv, worker_photos)

        started = []
        done = []
        worker.image_started.connect(lambda f: started.append(f))
        worker.image_done.connect(lambda f, ok, msg: done.append((f, ok, msg)))

        with qtbot.waitSignal(worker.finished, timeout=10000):
            worker.start()

        assert len(started) == 2
        assert len(done) == 2
        assert all(ok for _, ok, _ in done)

    @patch("worker.process_image")
    @patch("worker._preload_ocr")
    def test_emits_finished_with_correct_counts(
        self, mock_preload, mock_process, qtbot, worker_csv, worker_photos
    ):
        mock_process.side_effect = [
            (True, "Pile 27870: new_twist=1.50\u00b0"),
            (False, "OCR read failed: bad image"),
        ]
        worker = QCWorker(worker_csv, worker_photos)

        with qtbot.waitSignal(worker.finished, timeout=10000) as blocker:
            worker.start()

        assert blocker.args == [1, 1]

    @patch("worker.process_image")
    @patch("worker._preload_ocr")
    def test_emits_progress_setup_with_image_count(
        self, mock_preload, mock_process, qtbot, worker_csv, worker_photos
    ):
        mock_process.return_value = (True, "ok")
        worker = QCWorker(worker_csv, worker_photos)

        counts = []
        worker.progress_setup.connect(lambda n: counts.append(n))

        with qtbot.waitSignal(worker.finished, timeout=10000):
            worker.start()

        assert counts == [2]

    @patch("worker._preload_ocr")
    def test_emits_finished_zero_when_no_images(
        self, mock_preload, qtbot, worker_csv, tmp_path
    ):
        empty_photos = tmp_path / "empty"
        empty_photos.mkdir()
        worker = QCWorker(worker_csv, empty_photos)

        with qtbot.waitSignal(worker.finished, timeout=10000) as blocker:
            worker.start()

        assert blocker.args == [0, 0]

    @patch("worker._preload_ocr", side_effect=RuntimeError("PaddleOCR not found"))
    def test_emits_error_on_engine_failure(
        self, mock_preload, qtbot, worker_csv, worker_photos
    ):
        worker = QCWorker(worker_csv, worker_photos)

        with qtbot.waitSignal(worker.error, timeout=10000) as blocker:
            worker.start()

        assert "PaddleOCR" in blocker.args[0]

    @patch("worker.process_image")
    @patch("worker._preload_ocr")
    def test_saves_csv_after_processing(
        self, mock_preload, mock_process, qtbot, worker_csv, worker_photos
    ):
        mock_process.return_value = (True, "ok")
        worker = QCWorker(worker_csv, worker_photos)

        with qtbot.waitSignal(worker.finished, timeout=10000):
            worker.start()

        # Verify CSV is still valid (save was called)
        import pandas as pd
        df = pd.read_csv(worker_csv)
        assert len(df) == 2

    @patch("worker.process_image")
    @patch("worker._preload_ocr")
    def test_creates_qcd_subfolder(
        self, mock_preload, mock_process, qtbot, worker_csv, worker_photos
    ):
        mock_process.return_value = (True, "ok")
        worker = QCWorker(worker_csv, worker_photos)

        with qtbot.waitSignal(worker.finished, timeout=10000):
            worker.start()

        assert (worker_photos / "QCd").is_dir()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_worker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'worker'`

**Step 3: Implement worker.py**

Create `worker.py`:

```python
# worker.py
"""Background worker thread for QC batch processing."""
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from csv_updater import CSVUpdater
from providers import get_provider
from twist_qc import get_images, process_image

# Side-effect import: registers PaddleOCR via @register_provider decorator
import providers.paddleocr_provider  # noqa: F401


def _preload_ocr():
    """Pre-load the OCR engine so the first image doesn't stall silently.

    Raises on failure so the caller can show an error dialog.
    """
    from providers.paddleocr_provider import _get_ocr

    _get_ocr()


class QCWorker(QThread):
    """Runs the QC batch loop in a background thread.

    Signals:
        status(str)                — general status messages
        progress_setup(int)        — total image count (set progress bar max)
        image_started(str)         — filename of image about to be processed
        image_done(str, bool, str) — filename, success flag, result message
        finished(int, int)         — success_count, fail_count
        error(str)                 — fatal error message (stops processing)
    """

    status = Signal(str)
    progress_setup = Signal(int)
    image_started = Signal(str)
    image_done = Signal(str, bool, str)
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, csv_path: Path, photos_folder: Path, parent=None):
        super().__init__(parent)
        self.csv_path = csv_path
        self.photos_folder = photos_folder

    def run(self):
        try:
            self.status.emit("Loading OCR engine...")
            _preload_ocr()
        except Exception as e:
            self.error.emit(f"Failed to load OCR engine: {e}")
            return

        try:
            provider = get_provider("paddleocr", {})

            output_folder = self.photos_folder / "QCd"
            output_folder.mkdir(exist_ok=True)

            images = get_images(self.photos_folder, output_folder)
            if not images:
                self.status.emit("No images to process.")
                self.finished.emit(0, 0)
                return

            self.progress_setup.emit(len(images))
            csv_updater = CSVUpdater(str(self.csv_path))

            success_count = 0
            fail_count = 0

            for image_path in images:
                self.image_started.emit(image_path.name)
                ok, msg = process_image(
                    provider, image_path, csv_updater, output_folder
                )
                self.image_done.emit(image_path.name, ok, msg)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1

            csv_updater.save()
            self.finished.emit(success_count, fail_count)

        except Exception as e:
            self.error.emit(str(e))
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_worker.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add worker.py tests/test_worker.py
git commit -m "feat: add QCWorker background thread with signal-based progress"
```

---

### Task 3: Create gui.py — PySide6 Main Window

Single window with CSV picker, photos folder picker, Run button (disabled until both inputs selected), scrolling progress log, and progress bar. Communicates with `QCWorker` via Qt signals.

**Files:**
- Create: `gui.py`
- Create: `tests/test_gui.py`

**Step 1: Write failing tests for MainWindow**

Create `tests/test_gui.py`:

```python
"""Tests for the PySide6 GUI main window."""
from pathlib import Path

import pytest

from gui import MainWindow


class TestMainWindowInit:
    """Initial widget state."""

    def test_run_button_disabled_initially(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert not win.run_btn.isEnabled()

    def test_log_is_read_only(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.log.isReadOnly()

    def test_progress_bar_starts_at_zero(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.progress.value() == 0

    def test_window_title(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert "Twist QC" in win.windowTitle()


class TestMainWindowInputs:
    """File picker logic and Run button enable/disable."""

    def test_run_enabled_when_both_inputs_set(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.csv_path = Path("/fake/test.csv")
        win.photos_path = Path("/fake/photos")
        win._check_ready()
        assert win.run_btn.isEnabled()

    def test_run_disabled_when_csv_missing(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.csv_path = None
        win.photos_path = Path("/fake/photos")
        win._check_ready()
        assert not win.run_btn.isEnabled()

    def test_run_disabled_when_photos_missing(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.csv_path = Path("/fake/test.csv")
        win.photos_path = None
        win._check_ready()
        assert not win.run_btn.isEnabled()


class TestMainWindowSlots:
    """Signal handler methods update UI correctly."""

    def test_on_image_started_logs_message(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win._on_image_started("278700.jpg")
        assert "278700.jpg" in win.log.toPlainText()

    def test_on_image_done_success_shows_checkmark(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.progress.setMaximum(1)
        win._on_image_done("278700.jpg", True, "Pile 27870: new_twist=1.50\u00b0")
        text = win.log.toPlainText()
        assert "\u2713" in text
        assert "1.50\u00b0" in text

    def test_on_image_done_failure_shows_x(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.progress.setMaximum(1)
        win._on_image_done("278700.jpg", False, "OCR read failed")
        text = win.log.toPlainText()
        assert "\u2717" in text

    def test_on_image_done_increments_progress(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.progress.setMaximum(3)
        win._on_image_done("a.jpg", True, "ok")
        assert win.progress.value() == 1
        win._on_image_done("b.jpg", True, "ok")
        assert win.progress.value() == 2

    def test_on_finished_re_enables_run(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.csv_path = Path("/fake/test.csv")
        win.photos_path = Path("/fake/photos")
        win.run_btn.setEnabled(False)
        win._on_finished(5, 1)
        assert win.run_btn.isEnabled()
        assert "5" in win.log.toPlainText()

    def test_on_progress_setup_sets_max(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win._on_progress_setup(33)
        assert win.progress.maximum() == 33

    def test_on_error_shows_message_and_unlocks(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        win.csv_path = Path("/fake/test.csv")
        win.photos_path = Path("/fake/photos")
        win.run_btn.setEnabled(False)
        win._on_error("Engine failed")
        assert "Engine failed" in win.log.toPlainText()
        assert win.run_btn.isEnabled()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_gui.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui'`

**Step 3: Implement gui.py**

Create `gui.py`:

```python
# gui.py
"""PySide6 GUI for Twist QC Automation."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from worker import QCWorker


class MainWindow(QMainWindow):
    """Single-window GUI for Twist QC batch processing."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Twist QC Automation")
        self.setMinimumSize(600, 500)

        self.csv_path: Path | None = None
        self.photos_path: Path | None = None
        self.worker: QCWorker | None = None

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- CSV picker row ---
        csv_row = QHBoxLayout()
        csv_label = QLabel("CSV File:")
        csv_label.setFixedWidth(90)
        csv_row.addWidget(csv_label)
        self.csv_edit = QLineEdit()
        self.csv_edit.setReadOnly(True)
        self.csv_edit.setPlaceholderText("Select a CSV file...")
        csv_row.addWidget(self.csv_edit)
        self.csv_btn = QPushButton("Browse...")
        self.csv_btn.setFixedWidth(90)
        csv_row.addWidget(self.csv_btn)
        layout.addLayout(csv_row)

        # --- Photos folder picker row ---
        photos_row = QHBoxLayout()
        photos_label = QLabel("Photos Folder:")
        photos_label.setFixedWidth(90)
        photos_row.addWidget(photos_label)
        self.photos_edit = QLineEdit()
        self.photos_edit.setReadOnly(True)
        self.photos_edit.setPlaceholderText("Select a folder of images...")
        photos_row.addWidget(self.photos_edit)
        self.photos_btn = QPushButton("Browse...")
        self.photos_btn.setFixedWidth(90)
        photos_row.addWidget(self.photos_btn)
        layout.addLayout(photos_row)

        # --- Run button ---
        self.run_btn = QPushButton("Run QC")
        self.run_btn.setEnabled(False)
        self.run_btn.setMinimumHeight(40)
        layout.addWidget(self.run_btn)

        # --- Progress log ---
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, stretch=1)

        # --- Progress bar ---
        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m")
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # --- Connect buttons ---
        self.csv_btn.clicked.connect(self._pick_csv)
        self.photos_btn.clicked.connect(self._pick_photos)
        self.run_btn.clicked.connect(self._start_qc)

    # ---- File pickers ----

    def _pick_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )
        if path:
            self.csv_path = Path(path)
            self.csv_edit.setText(path)
            self._check_ready()

    def _pick_photos(self):
        path = QFileDialog.getExistingDirectory(self, "Select Photos Folder")
        if path:
            self.photos_path = Path(path)
            self.photos_edit.setText(path)
            self._check_ready()

    def _check_ready(self):
        """Enable Run button only when both inputs are set."""
        self.run_btn.setEnabled(
            self.csv_path is not None and self.photos_path is not None
        )

    # ---- Worker lifecycle ----

    def _start_qc(self):
        self.run_btn.setEnabled(False)
        self.csv_btn.setEnabled(False)
        self.photos_btn.setEnabled(False)
        self.log.clear()
        self.progress.setValue(0)
        self.progress.setMaximum(0)  # indeterminate until progress_setup

        self.worker = QCWorker(self.csv_path, self.photos_path, parent=self)
        self.worker.status.connect(self._on_status)
        self.worker.progress_setup.connect(self._on_progress_setup)
        self.worker.image_started.connect(self._on_image_started)
        self.worker.image_done.connect(self._on_image_done)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    # ---- Slots (called by worker signals on the GUI thread) ----

    def _on_status(self, msg: str):
        self.log.append(msg)

    def _on_progress_setup(self, total: int):
        self.progress.setMaximum(total)

    def _on_image_started(self, filename: str):
        self.log.append(f"Processing {filename}...")

    def _on_image_done(self, filename: str, success: bool, msg: str):
        icon = "\u2713" if success else "\u2717"
        self.log.append(f"  {icon} {msg}")
        self.progress.setValue(self.progress.value() + 1)

    def _on_finished(self, success_count: int, fail_count: int):
        total = success_count + fail_count
        self.log.append(f"\n--- Done ---")
        self.log.append(f"Processed: {total}")
        self.log.append(f"Success: {success_count}")
        self.log.append(f"Failed: {fail_count}")
        self._unlock_ui()

    def _on_error(self, msg: str):
        self.log.append(f"\nERROR: {msg}")
        self._unlock_ui()

    def _unlock_ui(self):
        self.csv_btn.setEnabled(True)
        self.photos_btn.setEnabled(True)
        self._check_ready()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_gui.py -v`
Expected: All 14 tests PASS

**Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: All 80 tests PASS (59 existing + 7 worker + 14 GUI)

**Step 6: Commit**

```bash
git add gui.py tests/test_gui.py
git commit -m "feat: add PySide6 GUI main window with file pickers, progress log, and bar"
```

---

### Task 4: Manual Smoke Test

**Step 1: Launch the GUI**

Run: `source .venv/bin/activate && python gui.py`

Verify:
- Window opens with title "Twist QC Automation"
- Run button is grayed out
- Browse buttons open native file/folder dialogs
- Selecting CSV populates the path field
- Selecting photos folder populates the path field
- Run button enables once both are set

**Step 2: Run a real batch (requires PaddleOCR engine)**

- CSV: any CSV with UPN and Twist_Deg columns
- Photos: `Needs QC - LLM Test/QCd/` (clear annotations for testing)
- Click Run QC
- Verify: "Loading OCR engine..." appears in log
- Verify: progress bar advances per image
- Verify: log shows per-image results with checkmarks/x marks
- Verify: `QCd/` subfolder created inside selected photos folder
- Verify: Run button re-enables after completion

**Step 3: Commit if any tweaks were needed**

```bash
git add -A
git commit -m "fix: smoke test adjustments"
```

---

### Task 5: PyInstaller Build Configuration

The actual build MUST run on Windows (PyInstaller cannot cross-compile). This task creates the build config and documents the process.

**Files:**
- Create: `twist_qc_gui.spec`
- Create: `build.bat`

**Step 1: Create PyInstaller spec file**

Create `twist_qc_gui.spec`:

```python
# twist_qc_gui.spec — PyInstaller spec for Twist QC Automation GUI
# Build: pyinstaller twist_qc_gui.spec --clean
# Must be run ON WINDOWS (no cross-compile).

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all PaddleOCR + PaddlePaddle data files, binaries, hidden imports
paddle_datas, paddle_bins, paddle_imports = collect_all("paddlepaddle")
ocr_datas, ocr_bins, ocr_imports = collect_all("paddleocr")

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=paddle_bins + ocr_bins,
    datas=paddle_datas + ocr_datas,
    hiddenimports=[
        "providers",
        "providers.paddleocr_provider",
        "csv_updater",
        "image_editor",
        "twist_qc",
        "worker",
    ]
    + paddle_imports
    + ocr_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Unused LLM provider deps (already removed from codebase)
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
```

**Step 2: Create Windows build script**

Create `build.bat`:

```batch
@echo off
REM Build Twist QC Automation .exe (run on Windows only)
REM Prerequisites: Python 3.13, pip install -r requirements.txt

echo === Building Twist QC Automation ===
echo.

pip install pyinstaller
pyinstaller twist_qc_gui.spec --clean

echo.
echo Build complete. Output: dist\TwistQC\
echo Zip the dist\TwistQC folder for distribution.
pause
```

**Step 3: Commit**

```bash
git add twist_qc_gui.spec build.bat
git commit -m "feat: add PyInstaller spec and Windows build script"
```

---

### Task 6: PaddleOCR Model Bundling (Windows Build-Time)

> **Note:** This task runs on the Windows build machine, not the macOS dev machine. Document it here for the build engineer.

PaddleOCR downloads ~100MB of models on first use to `~/.paddleocr/`. For the offline .exe, these must be pre-bundled.

**Step 1: Pre-download models on the build machine**

Run once on Windows (in the project venv):
```bash
python -c "from providers.paddleocr_provider import _get_ocr; _get_ocr()"
```

This caches models to `C:\Users\<user>\.paddleocr\`.

**Step 2: Add model directory to PyInstaller spec**

Update the `datas` list in `twist_qc_gui.spec` to include the cached model directory. The exact path depends on the PaddleOCR version and OS — inspect `~/.paddleocr/` after Step 1 to find the model files.

Example addition to `datas` in the spec:
```python
import os
model_dir = os.path.expanduser("~/.paddleocr")
# Add to datas list:
datas=paddle_datas + ocr_datas + [(model_dir, ".paddleocr")],
```

**Step 3: Configure PaddleOCR to find bundled models**

Modify `providers/paddleocr_provider.py` `_get_ocr()` to detect frozen mode:
```python
import sys

def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        kwargs = dict(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        # When running as PyInstaller bundle, use bundled model directory
        if getattr(sys, "frozen", False):
            import os
            bundle_dir = os.path.dirname(sys.executable)
            kwargs["model_dir"] = os.path.join(bundle_dir, ".paddleocr")
        _ocr_instance = PaddleOCR(**kwargs)
    return _ocr_instance
```

**Step 4: Rebuild and test the .exe**

Run `build.bat` again, then test the .exe on a clean Windows machine (no Python installed) to verify OCR works offline.

**Step 5: Commit**

```bash
git add providers/paddleocr_provider.py twist_qc_gui.spec
git commit -m "feat: bundle PaddleOCR models for offline .exe"
```

---

## Task Summary

| Task | Description | New Files | Tests |
|------|-------------|-----------|-------|
| 1 | Update dependencies | — | — |
| 2 | QCWorker thread | `worker.py` | 7 |
| 3 | PySide6 GUI | `gui.py` | 14 |
| 4 | Manual smoke test | — | Manual |
| 5 | PyInstaller config | `twist_qc_gui.spec`, `build.bat` | — |
| 6 | Model bundling | Modify `paddleocr_provider.py` | — |

**Total new tests:** 21 (7 worker + 14 GUI)
**Total test count after:** 80 (59 existing + 21 new)
**New files:** `worker.py`, `gui.py`, `tests/test_worker.py`, `tests/test_gui.py`, `twist_qc_gui.spec`, `build.bat`
**Modified files:** `requirements.txt`, `providers/paddleocr_provider.py` (Task 6 only)

## Key Design Notes

- **No config.yaml:** The GUI replaces it entirely. Users pick CSV + photos folder via native dialogs.
- **Output folder:** Auto-created as `QCd/` inside the selected photos folder.
- **PaddleOCR only:** No provider selection UI needed. The `get_provider("paddleocr", {})` call passes an empty config dict.
- **Existing code reuse:** `worker.py` imports `process_image()` and `get_images()` directly from `twist_qc.py` — zero duplication.
- **Thread safety:** Qt signal/slot mechanism handles cross-thread communication. The OCR singleton is only used from the single worker thread.
- **Error resilience:** Individual image failures are logged and skipped. CSV is saved once at the end (no partial corruption). OCR engine load failure emits `error` signal for a user-visible message.
