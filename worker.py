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
