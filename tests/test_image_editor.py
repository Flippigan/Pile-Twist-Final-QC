# tests/test_image_editor.py
from PIL import Image
from image_editor import annotate_image, _find_font


class TestFindFont:
    def test_returns_usable_font(self):
        font = _find_font(14)
        assert font is not None
        # Should be able to get text bbox without error
        bbox = font.getbbox("test")
        assert bbox is not None


class TestAnnotateImage:
    def test_returns_image(self, sample_image):
        result = annotate_image(str(sample_image), 3.06, -0.89)
        assert isinstance(result, Image.Image)

    def test_image_size_unchanged(self, sample_image):
        original = Image.open(str(sample_image))
        result = annotate_image(str(sample_image), 3.06, -0.89)
        assert result.size == original.size

    def test_original_file_not_modified(self, sample_image):
        original_bytes = sample_image.read_bytes()
        annotate_image(str(sample_image), 3.06, -0.89)
        assert sample_image.read_bytes() == original_bytes

    def test_adds_red_pixels_for_strikethrough(self, sample_image):
        result = annotate_image(str(sample_image), 3.06, -0.89)
        pixels = list(result.getdata())
        red_pixels = [p for p in pixels if p[0] > 200 and p[1] < 50 and p[2] < 50]
        assert len(red_pixels) > 0, "Expected red strikethrough pixels"

    def test_adds_green_pixels_for_new_value(self, sample_image):
        result = annotate_image(str(sample_image), 3.06, -0.89)
        pixels = list(result.getdata())
        green_pixels = [p for p in pixels if p[1] > 100 and p[0] < 50 and p[2] < 50]
        assert len(green_pixels) > 0, "Expected green text pixels"

    def test_handles_negative_old_twist(self, sample_image):
        result = annotate_image(str(sample_image), -4.82, -1.86)
        assert isinstance(result, Image.Image)

    def test_handles_negative_new_twist(self, sample_image):
        result = annotate_image(str(sample_image), 3.06, -0.89)
        assert isinstance(result, Image.Image)

    def test_handles_png(self, tmp_path):
        img = Image.new("RGB", (640, 480), "white")
        path = tmp_path / "test.png"
        img.save(str(path))
        result = annotate_image(str(path), 3.06, -0.89)
        assert isinstance(result, Image.Image)
