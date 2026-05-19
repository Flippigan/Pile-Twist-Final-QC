# gui.py
"""PySide6 GUI for Twist QC Automation."""
import os
import sys

# When running as a PyInstaller bundle, point PaddleX at the bundled model
# cache and disable its network connectivity probes. These env vars are read
# once at paddlex.utils.cache / paddlex.utils.flags import time, so they MUST
# be set before any transitive paddle/paddleocr import below.
if getattr(sys, "frozen", False):
    _bundle_data_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ["PADDLE_PDX_CACHE_HOME"] = os.path.join(_bundle_data_dir, ".paddlex")
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

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
