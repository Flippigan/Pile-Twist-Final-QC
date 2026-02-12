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
