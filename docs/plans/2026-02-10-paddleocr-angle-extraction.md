# PaddleOCR Angle Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace LLM API calls with local PaddleOCR to read the green angle annotation from plot images — free, fast, and deterministic.

**Architecture:** New `PaddleOCRProvider` registered via existing `@register_provider("paddleocr")` pattern. Green pixel isolation extracts annotation text from the plot, creates a high-contrast binary image, feeds it to PaddleOCR. The provider implements the same `VisionProvider.read_image() -> {"measured_angle": float}` contract as the LLM providers.

**Tech Stack:** PaddlePaddle, PaddleOCR, NumPy (already present), Pillow (already present)

---

## Task 1: Add PaddleOCR Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Add packages to requirements.txt**

Add these two lines after the existing dependencies:

```
paddlepaddle>=3.0.0
paddleocr>=2.9.0
```

Full file should be:
```
openai>=1.0.0
anthropic>=0.30.0
google-genai>=1.0.0
Pillow>=10.0.0
pandas>=2.0.0
PyYAML>=6.0
python-dotenv>=1.0.0
pytest>=8.0.0
paddlepaddle>=3.0.0
paddleocr>=2.9.0
```

**Step 2: Install the new packages**

Run: `source .venv/bin/activate && pip install paddlepaddle paddleocr`

Expected: Successful install. PaddlePaddle is ~500MB. First PaddleOCR import will download ~100MB of models.

**Step 3: Verify import works**

Run: `source .venv/bin/activate && python -c "from paddleocr import PaddleOCR; print('OK')"`

Expected: Prints `OK` (may print model download progress on first run).

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add paddlepaddle and paddleocr dependencies"
```

---

## Task 2: Green Pixel Isolation Function + Tests

This function takes a plot image (as numpy array), masks green-dominant pixels, crops to the green text bounding box, and returns a high-contrast binary image (black text on white) suitable for OCR.

**Files:**
- Create: `providers/paddleocr_provider.py`
- Modify: `tests/conftest.py` (add fixture)
- Create: `tests/test_paddleocr_provider.py`

**Step 1: Add a test fixture — `sample_image_with_green`**

Add this fixture to `tests/conftest.py` after the existing `sample_image` fixture:

```python
@pytest.fixture
def sample_image_with_green(tmp_path):
    """Create a plot-like image with green angle annotation text."""
    img = Image.new("RGB", (500, 500), (240, 240, 240))  # light gray bg
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
    # Gray title text (like matplotlib)
    draw.text((180, 12), "Pile: 15268.0", fill=(100, 100, 100), font=font)
    draw.text((180, 34), "Twist: 4.91\u00b0", fill=(100, 100, 100), font=font)
    # Red line (Calc Axis)
    draw.line([(50, 250), (450, 260)], fill=(200, 0, 0), width=2)
    # Blue line (North)
    draw.line([(250, 50), (250, 450)], fill=(0, 0, 200), width=2)
    # Green angle text — THIS is what we need to extract
    draw.text((200, 230), "86.97\u00b0", fill=(0, 128, 0), font=font)
    path = tmp_path / "152680.jpg"
    img.save(str(path))
    return path
```

**Step 2: Write failing tests for `isolate_green_text()`**

Create `tests/test_paddleocr_provider.py`:

```python
# tests/test_paddleocr_provider.py
import numpy as np
import pytest
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

    def test_returns_binary_image(self):
        from providers.paddleocr_provider import isolate_green_text

        img_array = self._draw_green_text()
        binary = isolate_green_text(img_array)

        assert binary.ndim == 3
        assert binary.shape[2] == 3
        # Binary: only black (0) and white (255) pixels
        unique = set(np.unique(binary))
        assert unique <= {0, 255}

    def test_crops_to_green_region(self):
        from providers.paddleocr_provider import isolate_green_text

        img_array = self._draw_green_text()
        binary = isolate_green_text(img_array)

        # Cropped should be much smaller than 500x500 original
        assert binary.shape[0] < 200
        assert binary.shape[1] < 200

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
        # Should be small crop (just the text area, not full image)
        assert binary.shape[0] < 200

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

        # Should crop to just the green text region, not the scatter points
        assert binary.shape[0] < 200
        assert binary.shape[1] < 200
```

**Step 3: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_paddleocr_provider.py -v`

Expected: `ModuleNotFoundError` or `ImportError` — the provider module doesn't exist yet.

**Step 4: Implement `isolate_green_text()`**

Create `providers/paddleocr_provider.py` with the isolation function (provider class comes in Task 3):

```python
# providers/paddleocr_provider.py
"""PaddleOCR-based angle extraction — no LLM API calls needed."""
import re

import numpy as np
from PIL import Image


def isolate_green_text(img_array: np.ndarray) -> np.ndarray:
    """Isolate green annotation pixels and return a binary image for OCR.

    Masks green-dominant pixels, crops to their bounding box, and produces
    a high-contrast black-on-white image suitable for OCR.

    Args:
        img_array: RGB image as numpy array (H, W, 3), dtype uint8.

    Returns:
        Binary numpy array (H', W', 3) — black text on white background.

    Raises:
        ValueError: If no green pixels are found in the image.
    """
    r = img_array[:, :, 0].astype(int)
    g = img_array[:, :, 1].astype(int)
    b = img_array[:, :, 2].astype(int)

    # Green-dominant: G channel clearly higher than both R and B
    green_mask = (g > 60) & (g > r + 20) & (g > b + 20)

    rows_any = np.any(green_mask, axis=1)
    cols_any = np.any(green_mask, axis=0)

    if not rows_any.any():
        raise ValueError("No green pixels found in image")

    rmin, rmax = np.where(rows_any)[0][[0, -1]]
    cmin, cmax = np.where(cols_any)[0][[0, -1]]

    # Pad the bounding box
    pad = 15
    rmin = max(0, rmin - pad)
    rmax = min(img_array.shape[0], rmax + pad + 1)
    cmin = max(0, cmin - pad)
    cmax = min(img_array.shape[1], cmax + pad + 1)

    # Build binary image: green pixels → black, everything else → white
    cropped_mask = green_mask[rmin:rmax, cmin:cmax]
    binary = np.full((*cropped_mask.shape, 3), 255, dtype=np.uint8)
    binary[cropped_mask] = [0, 0, 0]

    # Upscale small crops for better OCR accuracy
    if binary.shape[0] < 60:
        pil_img = Image.fromarray(binary)
        scale = 3
        pil_img = pil_img.resize(
            (pil_img.width * scale, pil_img.height * scale),
            Image.NEAREST,
        )
        binary = np.array(pil_img)

    return binary
```

**Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_paddleocr_provider.py::TestIsolateGreenText -v`

Expected: All 5 tests PASS.

**Step 6: Commit**

```bash
git add providers/paddleocr_provider.py tests/test_paddleocr_provider.py tests/conftest.py
git commit -m "feat: add green pixel isolation for OCR-based angle extraction"
```

---

## Task 3: PaddleOCR Provider Class + Mocked Tests

Implement the `PaddleOCRProvider` class that uses `isolate_green_text()` + PaddleOCR to extract the measured angle. All tests mock PaddleOCR to avoid the heavy dependency in unit tests.

**Files:**
- Modify: `providers/paddleocr_provider.py`
- Modify: `tests/test_paddleocr_provider.py`

**Step 1: Write failing tests for `PaddleOCRProvider`**

Add to `tests/test_paddleocr_provider.py`:

```python
from unittest.mock import patch, MagicMock


class TestPaddleOCRProvider:
    """Test PaddleOCR provider with mocked OCR engine."""

    def test_registered_in_registry(self):
        import providers.paddleocr_provider  # noqa: F401 — triggers registration
        from providers import PROVIDERS

        assert "paddleocr" in PROVIDERS

    def test_read_image_returns_measured_angle(self, sample_image_with_green):
        from providers.paddleocr_provider import PaddleOCRProvider

        mock_ocr_result = [[
            [
                [[200, 230], [280, 230], [280, 250], [200, 250]],
                ("86.97", 0.95),
            ],
        ]]

        with patch("providers.paddleocr_provider.PaddleOCR") as MockOCR:
            mock_instance = MagicMock()
            MockOCR.return_value = mock_instance
            mock_instance.ocr.return_value = mock_ocr_result

            provider = PaddleOCRProvider({})
            result = provider.read_image(str(sample_image_with_green))

        assert result == {"measured_angle": 86.97}

    def test_handles_degree_symbol(self, sample_image_with_green):
        from providers.paddleocr_provider import PaddleOCRProvider

        mock_ocr_result = [[
            [
                [[200, 230], [290, 230], [290, 250], [200, 250]],
                ("86.97\u00b0", 0.92),
            ],
        ]]

        with patch("providers.paddleocr_provider.PaddleOCR") as MockOCR:
            mock_instance = MagicMock()
            MockOCR.return_value = mock_instance
            mock_instance.ocr.return_value = mock_ocr_result

            provider = PaddleOCRProvider({})
            result = provider.read_image(str(sample_image_with_green))

        assert result == {"measured_angle": 86.97}

    def test_handles_spaces_in_ocr_text(self, sample_image_with_green):
        """OCR may insert spaces in the number (e.g., '86. 97')."""
        from providers.paddleocr_provider import PaddleOCRProvider

        mock_ocr_result = [[
            [
                [[200, 230], [290, 230], [290, 250], [200, 250]],
                ("86. 97", 0.88),
            ],
        ]]

        with patch("providers.paddleocr_provider.PaddleOCR") as MockOCR:
            mock_instance = MagicMock()
            MockOCR.return_value = mock_instance
            mock_instance.ocr.return_value = mock_ocr_result

            provider = PaddleOCRProvider({})
            result = provider.read_image(str(sample_image_with_green))

        assert result == {"measured_angle": 86.97}

    def test_picks_numeric_result_from_multiple(self, sample_image_with_green):
        """If OCR finds multiple text boxes, pick the one with a number."""
        from providers.paddleocr_provider import PaddleOCRProvider

        mock_ocr_result = [[
            [
                [[100, 100], [150, 100], [150, 120], [100, 120]],
                ("arc", 0.60),  # noise from the green arc
            ],
            [
                [[200, 230], [280, 230], [280, 250], [200, 250]],
                ("90.55", 0.95),  # the actual angle
            ],
        ]]

        with patch("providers.paddleocr_provider.PaddleOCR") as MockOCR:
            mock_instance = MagicMock()
            MockOCR.return_value = mock_instance
            mock_instance.ocr.return_value = mock_ocr_result

            provider = PaddleOCRProvider({})
            result = provider.read_image(str(sample_image_with_green))

        assert result == {"measured_angle": 90.55}

    def test_no_text_detected_raises(self, sample_image_with_green):
        from providers.paddleocr_provider import PaddleOCRProvider

        # PaddleOCR returns empty/None when no text found
        mock_ocr_result = [None]

        with patch("providers.paddleocr_provider.PaddleOCR") as MockOCR:
            mock_instance = MagicMock()
            MockOCR.return_value = mock_instance
            mock_instance.ocr.return_value = mock_ocr_result

            provider = PaddleOCRProvider({})
            with pytest.raises(ValueError, match="No angle value found"):
                provider.read_image(str(sample_image_with_green))

    def test_no_numeric_text_raises(self, sample_image_with_green):
        from providers.paddleocr_provider import PaddleOCRProvider

        mock_ocr_result = [[
            [
                [[100, 100], [150, 100], [150, 120], [100, 120]],
                ("abc", 0.80),
            ],
        ]]

        with patch("providers.paddleocr_provider.PaddleOCR") as MockOCR:
            mock_instance = MagicMock()
            MockOCR.return_value = mock_instance
            mock_instance.ocr.return_value = mock_ocr_result

            provider = PaddleOCRProvider({})
            with pytest.raises(ValueError, match="No angle value found"):
                provider.read_image(str(sample_image_with_green))
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_paddleocr_provider.py::TestPaddleOCRProvider -v`

Expected: FAIL — `PaddleOCRProvider` class doesn't exist yet.

**Step 3: Implement `PaddleOCRProvider`**

Add to `providers/paddleocr_provider.py` (after `isolate_green_text`):

```python
from paddleocr import PaddleOCR as _PaddleOCR

from . import VisionProvider, register_provider

# Lazy singleton — avoids reloading ~100MB of models per image
_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = _PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
    return _ocr_instance


def _parse_angle_from_ocr(ocr_result: list) -> float:
    """Extract a numeric angle value from PaddleOCR result.

    PaddleOCR returns: [[box, (text, confidence)], ...]
    We find the text that looks like a decimal number (the angle).

    Raises:
        ValueError: If no numeric angle value is found.
    """
    candidates = []
    for page in ocr_result:
        if page is None:
            continue
        for detection in page:
            text = detection[1][0]
            confidence = detection[1][1]
            # Strip degree symbol and whitespace
            cleaned = text.replace("\u00b0", "").replace(" ", "").strip()
            match = re.match(r"^(\d+\.?\d*)$", cleaned)
            if match:
                candidates.append((float(match.group(1)), confidence))

    if not candidates:
        raise ValueError(
            f"No angle value found in OCR results: {ocr_result}"
        )

    # Pick the highest-confidence numeric result
    candidates.sort(key=lambda c: c[1], reverse=True)
    return candidates[0][0]


@register_provider("paddleocr")
class PaddleOCRProvider(VisionProvider):
    """Extract angle measurement using local PaddleOCR — no API calls."""

    def __init__(self, config: dict):
        super().__init__(config)

    def read_image(self, image_path: str) -> dict:
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img)

        binary = isolate_green_text(img_array)

        ocr = _get_ocr()
        result = ocr.ocr(binary, cls=False)

        measured_angle = _parse_angle_from_ocr(result)
        return {"measured_angle": measured_angle}
```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_paddleocr_provider.py -v`

Expected: All tests PASS (both `TestIsolateGreenText` and `TestPaddleOCRProvider`).

**Step 5: Commit**

```bash
git add providers/paddleocr_provider.py tests/test_paddleocr_provider.py
git commit -m "feat: add PaddleOCR provider with mocked unit tests"
```

---

## Task 4: Register Provider in CLI + Update Config

Wire the new provider into the CLI entry point and argparse choices.

**Files:**
- Modify: `twist_qc.py` (2 changes: import + argparse choices)
- Modify: `config.yaml` (update default_provider)

**Step 1: Write a test verifying PaddleOCR is available as a CLI choice**

Add to `tests/test_twist_qc.py`:

```python
def test_paddleocr_provider_available():
    """PaddleOCR should be importable and registered."""
    import providers.paddleocr_provider  # noqa: F401
    from providers import PROVIDERS

    assert "paddleocr" in PROVIDERS
```

**Step 2: Run the test to verify it passes**

This test should already pass from Task 3 (the provider is registered). Run it to confirm:

Run: `source .venv/bin/activate && python -m pytest tests/test_twist_qc.py::test_paddleocr_provider_available -v`

Expected: PASS.

**Step 3: Add provider import to `twist_qc.py`**

In `twist_qc.py`, after the existing provider imports (around line 23), add:

```python
import providers.paddleocr_provider  # noqa: F401
```

**Step 4: Add `"paddleocr"` to argparse choices**

In `twist_qc.py`, update the `--provider` argument (around line 99):

```python
choices=["openai", "claude", "gemini", "paddleocr", "all"],
```

**Step 5: Update `config.yaml` default provider**

Change `default_provider` to `paddleocr`:

```yaml
default_provider: paddleocr
```

**Step 6: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest -v`

Expected: All existing tests + new tests PASS. The LLM provider tests still work (they're mocked).

**Step 7: Commit**

```bash
git add twist_qc.py config.yaml
git commit -m "feat: register paddleocr provider in CLI, set as default"
```

---

## Task 5: Edge Case — `_parse_angle_from_ocr` Robustness Tests

Add focused unit tests for the OCR result parser to handle edge cases discovered during integration.

**Files:**
- Modify: `tests/test_paddleocr_provider.py`

**Step 1: Write edge case tests**

Add to `tests/test_paddleocr_provider.py`:

```python
class TestParseAngleFromOCR:
    """Unit tests for the OCR result parser, independent of images."""

    def test_simple_number(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [[
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("86.97", 0.95)],
        ]]
        assert _parse_angle_from_ocr(result) == 86.97

    def test_integer_angle(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [[
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("90", 0.90)],
        ]]
        assert _parse_angle_from_ocr(result) == 90.0

    def test_degree_symbol_stripped(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [[
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("88.94\u00b0", 0.93)],
        ]]
        assert _parse_angle_from_ocr(result) == 88.94

    def test_spaces_stripped(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [[
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("86. 97", 0.85)],
        ]]
        assert _parse_angle_from_ocr(result) == 86.97

    def test_picks_highest_confidence(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [[
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("12.34", 0.50)],
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("86.97", 0.95)],
        ]]
        assert _parse_angle_from_ocr(result) == 86.97

    def test_none_page_skipped(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [None, [
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("90.55", 0.90)],
        ]]
        assert _parse_angle_from_ocr(result) == 90.55

    def test_empty_result_raises(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        with pytest.raises(ValueError, match="No angle value found"):
            _parse_angle_from_ocr([None])

    def test_non_numeric_text_ignored(self):
        from providers.paddleocr_provider import _parse_angle_from_ocr

        result = [[
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("North", 0.90)],
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("86.97", 0.85)],
        ]]
        assert _parse_angle_from_ocr(result) == 86.97
```

**Step 2: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_paddleocr_provider.py::TestParseAngleFromOCR -v`

Expected: All 8 tests PASS.

**Step 3: Commit**

```bash
git add tests/test_paddleocr_provider.py
git commit -m "test: add edge case tests for OCR angle parser"
```

---

## Task 6: Integration Test on Real Images

Run the PaddleOCR provider against the 34 test images in `Needs QC - LLM Test/QCd/` and verify accuracy. This is NOT an automated test — it's a manual validation step.

**Files:**
- No files modified (manual testing)

**Step 1: Dry-run on a single test image**

Run:
```bash
source .venv/bin/activate && python twist_qc.py \
  --provider paddleocr \
  --image 152680.jpg \
  --dry-run \
  --config config-test.yaml
```

Expected output should show: `Pile 152680: angle=86.97°, new_twist=3.03°`

If the angle is wrong, adjust green pixel thresholds in `isolate_green_text()`:
- If green text missed → lower the `g > 60` threshold or reduce the `+ 20` gap
- If non-green pixels included → raise thresholds
- If small text unreadable → increase the upscale factor from 3 to 4

**Step 2: Dry-run on the full test set**

Run:
```bash
source .venv/bin/activate && python twist_qc.py \
  --provider paddleocr \
  --dry-run \
  --config config-test.yaml
```

Expected: All 34 images processed. Review the angles — they should be between 80-100 for most images.

**Step 3: Compare with LLM provider results (optional)**

If LLM API keys are configured, compare accuracy:

```bash
source .venv/bin/activate && python twist_qc.py \
  --provider paddleocr \
  --image 60090.jpg \
  --dry-run \
  --config config-test.yaml

source .venv/bin/activate && python twist_qc.py \
  --provider claude \
  --image 60090.jpg \
  --dry-run \
  --config config-test.yaml
```

Compare the measured_angle values. PaddleOCR should match or exceed Claude accuracy since it reads directly from the image without hallucination risk.

**Step 4: Run full test suite to confirm nothing broke**

Run: `source .venv/bin/activate && python -m pytest -v`

Expected: All tests PASS (original 36 + new PaddleOCR tests).

**Step 5: Commit any threshold tuning**

If thresholds were adjusted in Step 1/2:

```bash
git add providers/paddleocr_provider.py
git commit -m "fix: tune green pixel thresholds for OCR accuracy"
```

---

## Task 7: Final Cleanup + Documentation

**Files:**
- Modify: `docs/progress.md` (append implementation log entry)

**Step 1: Append to `docs/progress.md`**

Add a new section documenting the PaddleOCR integration:

```markdown
## PaddleOCR Integration (YYYY-MM-DD)

- Added PaddleOCR as a new provider (`--provider paddleocr`)
- Green pixel isolation: RGB threshold mask → crop → binary image → OCR
- No API keys needed — runs locally, free, fast, deterministic
- Set as default provider in config.yaml
- Tested against 34 images in LLM Test set
- Dependencies: paddlepaddle (~500MB), paddleocr (~100MB models on first run)
```

**Step 2: Run full test suite one final time**

Run: `source .venv/bin/activate && python -m pytest -v`

Expected: All tests PASS.

**Step 3: Final commit**

```bash
git add docs/progress.md
git commit -m "docs: add PaddleOCR integration to progress log"
```

---

## Summary

| Task | Description | New Tests |
|------|-------------|-----------|
| 1 | Add PaddleOCR dependencies | 0 |
| 2 | Green pixel isolation function | 5 |
| 3 | PaddleOCR provider class | 7 |
| 4 | Wire into CLI + config | 1 |
| 5 | OCR parser edge cases | 8 |
| 6 | Integration test on real images | 0 (manual) |
| 7 | Documentation | 0 |

**Total new tests: 21**

## Key Thresholds to Tune (if OCR accuracy is low)

Located in `providers/paddleocr_provider.py`, function `isolate_green_text()`:

| Parameter | Default | What it controls |
|-----------|---------|-----------------|
| `g > 60` | Green channel minimum | Lower → catches darker greens |
| `g > r + 20` | Green dominance over red | Lower → more permissive |
| `g > b + 20` | Green dominance over blue | Lower → more permissive |
| `pad = 15` | Bounding box padding (px) | Higher → more context around text |
| `binary.shape[0] < 60` | Upscale trigger height | Higher → more upscaling |
| `scale = 3` | Upscale multiplier | Higher → larger OCR input |
