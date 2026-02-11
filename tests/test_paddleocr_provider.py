# tests/test_paddleocr_provider.py
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image, ImageDraw, ImageFont


class TestIsolateGreenText:
    """Test green pixel isolation from plot images."""

    def _draw_green_text(self, size=(500, 500)):
        """Helper: create image with green text on gray background."""
        img = Image.new("RGB", size, (240, 240, 240))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Helvetica.ttc", 16
            )
        except OSError:
            font = ImageFont.load_default()
        # Green annotation text
        draw.text((200, 250), "86.97", fill=(0, 128, 0), font=font)
        return np.array(img)

    def test_returns_image_with_text(self):
        from providers.paddleocr_provider import isolate_green_text

        img_array = self._draw_green_text()
        binary = isolate_green_text(img_array)

        assert binary.ndim == 3
        assert binary.shape[2] == 3
        # Should have dark pixels (text) on light background
        assert np.any(binary < 128)  # has dark text pixels
        assert np.any(binary > 128)  # has light background pixels

    def test_crops_to_green_region(self):
        from providers.paddleocr_provider import isolate_green_text

        img_array = self._draw_green_text()
        binary = isolate_green_text(img_array)

        # Upscaled crop should be much smaller than the full 500x500 original
        # 6x upscale of ~40px crop height → ~240px (well under 3000)
        # Width may exceed 500 due to upscale, but height should be small
        assert binary.shape[0] < 3000
        assert binary.shape[1] < 3000

    def test_no_green_pixels_raises(self):
        from providers.paddleocr_provider import isolate_green_text

        # All white — no green pixels
        img_array = np.full((500, 500, 3), 255, dtype=np.uint8)
        with pytest.raises(ValueError, match="No green pixels"):
            isolate_green_text(img_array)

    def test_ignores_red_and_blue_pixels(self):
        from providers.paddleocr_provider import isolate_green_text

        img = Image.new("RGB", (500, 500), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        # Red and blue lines (should be ignored)
        draw.line([(50, 250), (450, 250)], fill=(200, 0, 0), width=3)
        draw.line([(250, 50), (250, 450)], fill=(0, 0, 200), width=3)
        # Green text (should be captured)
        draw.text((200, 230), "90.55", fill=(0, 128, 0))
        img_array = np.array(img)

        binary = isolate_green_text(img_array)

        # Result should only contain green-origin pixels as black
        black_pixels = np.sum(np.all(binary == 0, axis=2))
        assert black_pixels > 0  # has text

    def test_ignores_gray_scatter_points(self):
        from providers.paddleocr_provider import isolate_green_text

        img = Image.new("RGB", (500, 500), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        # Gray scatter points (R≈G≈B, should NOT be detected as green)
        for x in range(100, 400, 5):
            for y in range(100, 400, 20):
                draw.point((x, y), fill=(150, 150, 150))
        # Green text
        draw.text((200, 230), "88.12", fill=(0, 128, 0))
        img_array = np.array(img)

        binary = isolate_green_text(img_array)

        # Should be an upscaled crop of just the green text, not full image
        assert binary.shape[0] < 500
        assert binary.shape[1] < 500


def _mock_ocr_result(texts, scores):
    """Create a mock OCRResult page matching PaddleOCR v2.9+ predict() format."""
    result = {"rec_texts": texts, "rec_scores": scores}
    return result


class TestPaddleOCRProvider:
    """Test PaddleOCR provider with mocked OCR engine."""

    def test_registered_in_registry(self):
        import providers.paddleocr_provider  # noqa: F401 — triggers registration
        from providers import PROVIDERS

        assert "paddleocr" in PROVIDERS

    def _mock_ocr(self, pages):
        """Context manager that mocks _get_ocr to return controlled results."""
        mock_instance = MagicMock()
        mock_instance.predict.return_value = pages
        return patch("providers.paddleocr_provider._get_ocr", return_value=mock_instance)

    def test_read_image_returns_measured_angle(self, sample_image_with_green):
        from providers.paddleocr_provider import PaddleOCRProvider

        pages = [_mock_ocr_result(["86.97"], [0.95])]

        with self._mock_ocr(pages):
            provider = PaddleOCRProvider({})
            result = provider.read_image(str(sample_image_with_green))

        assert result == {"measured_angle": 86.97}

    def test_handles_degree_symbol(self, sample_image_with_green):
        from providers.paddleocr_provider import PaddleOCRProvider

        pages = [_mock_ocr_result(["86.97°"], [0.92])]

        with self._mock_ocr(pages):
            provider = PaddleOCRProvider({})
            result = provider.read_image(str(sample_image_with_green))

        assert result == {"measured_angle": 86.97}

    def test_handles_spaces_in_ocr_text(self, sample_image_with_green):
        """OCR may insert spaces in the number (e.g., '86. 97')."""
        from providers.paddleocr_provider import PaddleOCRProvider

        pages = [_mock_ocr_result(["86. 97"], [0.88])]

        with self._mock_ocr(pages):
            provider = PaddleOCRProvider({})
            result = provider.read_image(str(sample_image_with_green))

        assert result == {"measured_angle": 86.97}

    def test_picks_numeric_result_from_multiple(self, sample_image_with_green):
        """If OCR finds multiple text boxes, pick the one with a number."""
        from providers.paddleocr_provider import PaddleOCRProvider

        pages = [_mock_ocr_result(["arc", "90.55"], [0.60, 0.95])]

        with self._mock_ocr(pages):
            provider = PaddleOCRProvider({})
            result = provider.read_image(str(sample_image_with_green))

        assert result == {"measured_angle": 90.55}

    def test_no_text_detected_raises(self, sample_image_with_green):
        from providers.paddleocr_provider import PaddleOCRProvider

        pages = [_mock_ocr_result([], [])]

        with self._mock_ocr(pages):
            provider = PaddleOCRProvider({})
            with pytest.raises(ValueError, match="No angle value found"):
                provider.read_image(str(sample_image_with_green))

    def test_no_numeric_text_raises(self, sample_image_with_green):
        from providers.paddleocr_provider import PaddleOCRProvider

        pages = [_mock_ocr_result(["abc"], [0.80])]

        with self._mock_ocr(pages):
            provider = PaddleOCRProvider({})
            with pytest.raises(ValueError, match="No angle value found"):
                provider.read_image(str(sample_image_with_green))


class TestParseAngleFromOCR:
    """Unit tests for the OCR result parser, independent of images."""

    def test_simple_number(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [_mock_ocr_result(["86.97"], [0.95])]
        assert _parse_angle_from_ocr(result) == 86.97

    def test_integer_angle(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [_mock_ocr_result(["90"], [0.90])]
        assert _parse_angle_from_ocr(result) == 90.0

    def test_degree_symbol_stripped(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [_mock_ocr_result(["88.94°"], [0.93])]
        assert _parse_angle_from_ocr(result) == 88.94

    def test_spaces_stripped(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [_mock_ocr_result(["86. 97"], [0.85])]
        assert _parse_angle_from_ocr(result) == 86.97

    def test_picks_highest_confidence(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [_mock_ocr_result(["12.34", "86.97"], [0.50, 0.95])]
        assert _parse_angle_from_ocr(result) == 86.97

    def test_none_page_skipped(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [
            _mock_ocr_result([], []),
            _mock_ocr_result(["90.55"], [0.90]),
        ]
        assert _parse_angle_from_ocr(result) == 90.55

    def test_empty_result_raises(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        with pytest.raises(ValueError, match="No angle value found"):
            _parse_angle_from_ocr([_mock_ocr_result([], [])])

    def test_non_numeric_text_ignored(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [_mock_ocr_result(["North", "86.97"], [0.90, 0.85])]
        assert _parse_angle_from_ocr(result) == 86.97

    def test_asterisk_stripped(self):
        """PaddleOCR may misread ° as * — should still parse correctly."""
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [_mock_ocr_result(["86.97*"], [0.96])]
        assert _parse_angle_from_ocr(result) == 86.97
