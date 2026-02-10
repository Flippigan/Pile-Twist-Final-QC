# tests/test_twist_qc.py
import pytest
from pathlib import Path
from twist_qc import get_images


class TestGetImages:
    def test_finds_jpg_and_png(self, tmp_path):
        (tmp_path / "123.jpg").touch()
        (tmp_path / "456.png").touch()
        output = tmp_path / "QCd"
        output.mkdir()
        images = get_images(tmp_path, output)
        names = sorted(i.name for i in images)
        assert names == ["123.jpg", "456.png"]

    def test_skips_done_prefix(self, tmp_path):
        (tmp_path / "done123.jpg").touch()
        (tmp_path / "456.jpg").touch()
        output = tmp_path / "QCd"
        output.mkdir()
        images = get_images(tmp_path, output)
        names = [i.name for i in images]
        assert "done123.jpg" not in names
        assert "456.jpg" in names

    def test_skips_macos_resource_forks(self, tmp_path):
        (tmp_path / "._hidden.jpg").touch()
        (tmp_path / "visible.jpg").touch()
        output = tmp_path / "QCd"
        output.mkdir()
        images = get_images(tmp_path, output)
        names = [i.name for i in images]
        assert "._hidden.jpg" not in names
        assert "visible.jpg" in names

    def test_skips_already_in_output(self, tmp_path):
        (tmp_path / "123.jpg").touch()
        output = tmp_path / "QCd"
        output.mkdir()
        (output / "123.jpg").touch()
        images = get_images(tmp_path, output)
        assert len(images) == 0

    def test_single_image_mode(self, tmp_path):
        (tmp_path / "456.jpg").touch()
        output = tmp_path / "QCd"
        output.mkdir()
        images = get_images(tmp_path, output, "456.jpg")
        assert len(images) == 1
        assert images[0].name == "456.jpg"

    def test_single_image_not_found_raises(self, tmp_path):
        output = tmp_path / "QCd"
        output.mkdir()
        with pytest.raises(FileNotFoundError):
            get_images(tmp_path, output, "missing.jpg")

    def test_returns_sorted(self, tmp_path):
        (tmp_path / "zzz.jpg").touch()
        (tmp_path / "aaa.jpg").touch()
        output = tmp_path / "QCd"
        output.mkdir()
        images = get_images(tmp_path, output)
        assert images[0].name == "aaa.jpg"


from unittest.mock import MagicMock
from twist_qc import process_image
from csv_updater import CSVUpdater


class TestProcessImage:
    def test_successful_processing(self, sample_image, sample_csv, tmp_path):
        mock_provider = MagicMock()
        mock_provider.read_image.return_value = {
            "pile_number": 2787,
            "measured_angle": 90.89,
            "old_twist": 3.06,
        }
        csv_updater = CSVUpdater(str(sample_csv))
        output = tmp_path / "QCd"
        output.mkdir()

        success, msg = process_image(
            mock_provider, sample_image, csv_updater, output
        )

        assert success is True
        assert "2787" in msg
        assert (output / sample_image.name).exists()

    def test_dry_run_no_save(self, sample_image, sample_csv, tmp_path):
        mock_provider = MagicMock()
        mock_provider.read_image.return_value = {
            "pile_number": 2787,
            "measured_angle": 90.89,
            "old_twist": 3.06,
        }
        csv_updater = CSVUpdater(str(sample_csv))
        output = tmp_path / "QCd"
        output.mkdir()

        success, msg = process_image(
            mock_provider, sample_image, csv_updater, output, dry_run=True
        )

        assert success is True
        assert "new_twist=-0.89" in msg
        assert not (output / sample_image.name).exists()

    def test_invalid_angle_rejected(self, sample_image, sample_csv, tmp_path):
        mock_provider = MagicMock()
        mock_provider.read_image.return_value = {
            "pile_number": 2787,
            "measured_angle": 200.0,
            "old_twist": 3.06,
        }
        csv_updater = CSVUpdater(str(sample_csv))
        output = tmp_path / "QCd"
        output.mkdir()

        success, msg = process_image(
            mock_provider, sample_image, csv_updater, output
        )

        assert success is False
        assert "Suspicious angle" in msg

    def test_llm_failure_handled(self, sample_image, sample_csv, tmp_path):
        mock_provider = MagicMock()
        mock_provider.read_image.side_effect = Exception("API timeout")
        csv_updater = CSVUpdater(str(sample_csv))
        output = tmp_path / "QCd"
        output.mkdir()

        success, msg = process_image(
            mock_provider, sample_image, csv_updater, output
        )

        assert success is False
        assert "LLM read failed" in msg

    def test_csv_miss_still_saves_image(self, sample_image, sample_csv, tmp_path):
        mock_provider = MagicMock()
        mock_provider.read_image.return_value = {
            "pile_number": 11111,  # Not in CSV
            "measured_angle": 88.0,
            "old_twist": 5.0,
        }
        csv_updater = CSVUpdater(str(sample_csv))
        output = tmp_path / "QCd"
        output.mkdir()

        success, msg = process_image(
            mock_provider, sample_image, csv_updater, output
        )

        assert success is True
        assert "UPN not found" in msg
        assert (output / sample_image.name).exists()
