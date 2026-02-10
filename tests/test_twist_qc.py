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
