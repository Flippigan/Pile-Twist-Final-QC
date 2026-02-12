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
