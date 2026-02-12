# Windows GUI .exe — Design Document

**Date:** 2026-02-12
**Goal:** Package Twist QC Automation as a standalone Windows .exe with a PySide6 GUI so non-technical users can run it without Python installed.

## Decisions

- **Provider:** PaddleOCR only (fully offline, no API keys)
- **GUI framework:** PySide6 (LGPL, free for commercial use)
- **Packaging:** PyInstaller `--onedir` mode
- **Models:** Pre-bundled in the package (no first-run download)
- **Config:** No config.yaml — GUI replaces it entirely

## App Layout

Single window with:
1. **CSV file picker** — native file dialog filtered to `*.csv`
2. **Photos folder picker** — native folder dialog
3. **Run QC button** — disabled until both inputs selected; grays out during processing
4. **Progress log** — scrolling text area showing per-image results
5. **Progress bar** — shows count (e.g., 12/33)

Output folder is auto-created as `QCd/` subfolder inside the selected photos folder.

## Architecture

### New Files
- `gui.py` — PySide6 main window, file dialogs, signal wiring. New entry point.
- `worker.py` — QThread subclass for background batch processing.

### Existing Files (unchanged)
- `image_editor.py` — Pillow annotation
- `csv_updater.py` — pandas CSV updater
- `providers/paddleocr_provider.py` — OCR extraction
- `providers/__init__.py` — provider registry

### Threading Model
- GUI thread: handles all UI updates
- Worker thread (`QCWorker`): runs the processing loop
- Communication via Qt signals:
  - `image_started(str)` — image filename
  - `image_done(str, bool, str)` — filename, success, message
  - `finished(int, int)` — success_count, fail_count

### Processing Flow
1. User picks CSV + photos folder, clicks Run
2. GUI spawns QCWorker with those paths
3. Worker loads PaddleOCR (lazy singleton), iterates images
4. Per image: read angle → annotate → update CSV → emit signal
5. Worker saves CSV at end, emits finished signal
6. GUI shows summary, re-enables Run button

## Error Handling
- PaddleOCR load failure → error dialog
- First launch shows "Loading OCR engine..." status
- CSV must exist and be `.csv`; folder must contain images
- Individual image failures logged and skipped (batch continues)
- CSV saved once at end (no partial corruption on close)
- Images already in QCd/ are skipped

## Packaging

- **Tool:** PyInstaller
- **Mode:** `--onedir` (not `--onefile` — avoids 10-30s startup penalty)
- **Flags:** `--windowed --collect-all paddleocr --collect-all paddlepaddle`
- **Models:** Pre-bundled via PyInstaller data collection
- **Build requirement:** Must be built ON Windows (no cross-compile)
- **Deliverable:** Zipped folder `TwistQC_v1.0/` with .exe + dependencies
- **Expected size:** ~600-800MB

## Dependencies (additions to requirements.txt)
- `PySide6>=6.5.0`
- `pyinstaller>=6.0.0` (dev dependency for building)
