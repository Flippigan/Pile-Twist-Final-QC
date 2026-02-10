# Twist QC Automation - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI that batch-processes pile plot images: uses LLM vision to read pile number + measured angle, calculates new twist (90 - angle), annotates the image with Pillow (red strikethrough on old value, green new value), updates the CSV, and saves to QCd/.

**Architecture:** Swappable LLM vision providers (OpenAI/Claude/Gemini) behind a common interface, a Pillow-based image editor that locates and annotates the title text, a pandas CSV updater, and an argparse CLI orchestrator tying it all together. Skip-and-continue error handling with batch summary.

**Tech Stack:** Python 3.11+, Pillow, pandas, PyYAML, openai, anthropic, google-generativeai, pytest

---

## Reference: Before/After Image Format

**Before** (e.g., `Needs QC/done7770.jpg`): Matplotlib scatter plot, title has two centered lines:
- Line 1: `Pile: 777.0` (gray text, ~y=15px from top)
- Line 2: `Twist: 4.69°` (gray text, ~y=37px from top)
- Blue "North" vertical line, red "Calc Axis" line, legend box

**After human measurement** (images waiting in `Needs QC/` without "done" prefix): Same plot + a green arc and green angle text (e.g., `87.35°`) drawn near the intersection of lines.

**After tool processing** (e.g., `Needs QC/QCd/7770.jpg`): Same as above + in the title:
- Red horizontal strikethrough line through `4.69°` (number + degree symbol)
- Green text `2.65` written immediately right of the strikethrough (no degree symbol)

**Verified formula:** `new_twist = 90 - measured_angle`
- Pile 777: 90 - 87.35 = 2.65 ✓
- Pile 2787: 90 - 90.89 = -0.89 ✓
- Pile 2791: 90 - 92.35 = -2.35 ✓

**CSV:** `Needs QC/Final_Report.csv`, 61,896 rows, column `UPN` (integer) for lookup, column `Twist_Deg` for update.

**Image filenames:** `{pile_number}0.jpg` (pile number × 10, e.g., pile 777 → `7770.jpg`).

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `providers/__init__.py` (empty placeholder)
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py` (shared fixtures)

**Step 1: Create requirements.txt**

```
# requirements.txt
openai>=1.0.0
anthropic>=0.30.0
google-generativeai>=0.8.0
Pillow>=10.0.0
pandas>=2.0.0
PyYAML>=6.0
pytest>=8.0.0
```

**Step 2: Create config.yaml**

```yaml
# config.yaml
# API keys come from environment variables:
#   OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY

# Paths (relative to project root)
input_folder: ./Needs QC
output_folder: ./Needs QC/QCd
csv_path: ./Needs QC/Final_Report.csv

# Default LLM provider
default_provider: openai
```

**Step 3: Create directory structure and empty __init__ files**

```bash
mkdir -p providers tests
touch providers/__init__.py tests/__init__.py
```

**Step 4: Create tests/conftest.py with shared fixtures**

```python
# tests/conftest.py
import csv
import pytest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


@pytest.fixture
def sample_csv(tmp_path):
    """Create a minimal CSV matching Final_Report.csv schema."""
    csv_path = tmp_path / "Final_Report.csv"
    headers = [
        "UPN", "Detected", "Pile_Height", "Top_X", "Top_Y", "Top_Z",
        "Bot_X", "Bot_Y", "Bot_Z", "Twist_Deg", "Lean_East_Deg",
        "Lean_North_Deg", "Tracker_Slope_Pct", "Elv_Dz_Deg",
        "Abs_Elv_Dz", "Bot_X_1ft", "Bot_Y_1ft", "Bot_Z_1ft",
    ]
    rows = [
        [2787, "FALSE", 0, 0, 0, 0, 0, 0, 0, "", 0, 0, 0, 0, 0, 0, 0, 0],
        [777, "FALSE", 0, 0, 0, 0, 0, 0, 0, "", 0, 0, 0, 0, 0, 0, 0, 0],
        [15256, "FALSE", 0, 0, 0, 0, 0, 0, 0, "", 0, 0, 0, 0, 0, 0, 0, 0],
        [99999, "FALSE", 0, 0, 0, 0, 0, 0, 0, "", 0, 0, 0, 0, 0, 0, 0, 0],
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def sample_image(tmp_path):
    """Create a plot-like image with title text matching matplotlib output."""
    img = Image.new("RGB", (640, 480), "white")
    draw = ImageDraw.Draw(img)
    # Use default font (won't match matplotlib exactly, but good for unit tests)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
    # Simulate centered matplotlib title
    draw.text((240, 12), "Pile: 2787.0", fill="gray", font=font)
    draw.text((230, 34), "Twist: 3.06\u00b0", fill="gray", font=font)
    path = tmp_path / "27870.jpg"
    img.save(str(path))
    return path
```

**Step 5: Install dependencies**

Run: `pip install -r requirements.txt`

**Step 6: Verify pytest runs with no tests**

Run: `python -m pytest tests/ -v`
Expected: "no tests ran" (exit 5), no import errors

**Step 7: Commit**

```bash
git init
git add requirements.txt config.yaml providers/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: project scaffolding with deps, config, and test fixtures"
```

---

### Task 2: Vision Provider Base Class + Registry

**Files:**
- Modify: `providers/__init__.py`
- Create: `tests/test_providers.py`

**Step 1: Write the failing tests**

```python
# tests/test_providers.py
import pytest
from providers import VisionProvider, register_provider, get_provider, PROVIDERS


class TestParseResponse:
    """Test the shared JSON parsing logic in VisionProvider."""

    def _make_provider(self):
        """Create a concrete subclass for testing the base class methods."""
        class FakeProvider(VisionProvider):
            def read_image(self, image_path):
                return {}
        return FakeProvider({})

    def test_valid_json(self):
        p = self._make_provider()
        result = p.parse_response(
            '{"pile_number": 2787, "measured_angle": 90.89, "old_twist": 3.06}'
        )
        assert result == {
            "pile_number": 2787,
            "measured_angle": 90.89,
            "old_twist": 3.06,
        }

    def test_json_embedded_in_text(self):
        p = self._make_provider()
        result = p.parse_response(
            'Here is the data: {"pile_number": 777, "measured_angle": 87.35, "old_twist": 4.69} done.'
        )
        assert result["pile_number"] == 777
        assert result["measured_angle"] == 87.35

    def test_no_json_raises(self):
        p = self._make_provider()
        with pytest.raises(ValueError, match="No JSON found"):
            p.parse_response("I cannot read this image")

    def test_missing_fields_raises(self):
        p = self._make_provider()
        with pytest.raises(ValueError, match="Missing required fields"):
            p.parse_response('{"pile_number": 2787}')

    def test_types_coerced(self):
        p = self._make_provider()
        result = p.parse_response(
            '{"pile_number": "2787", "measured_angle": "90.89", "old_twist": "3.06"}'
        )
        assert isinstance(result["pile_number"], int)
        assert isinstance(result["measured_angle"], float)
        assert isinstance(result["old_twist"], float)


class TestRegistry:
    def test_register_and_get(self):
        @register_provider("fake_test")
        class FakeTestProvider(VisionProvider):
            def __init__(self, config):
                pass
            def read_image(self, image_path):
                return {}

        provider = get_provider("fake_test", {})
        assert isinstance(provider, FakeTestProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent_provider_xyz", {})
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_providers.py -v`
Expected: FAIL (VisionProvider etc. not defined yet)

**Step 3: Implement providers/__init__.py**

```python
# providers/__init__.py
from abc import ABC, abstractmethod
import json
import re


class VisionProvider(ABC):
    """Base class for LLM vision providers."""

    PROMPT = (
        "Look at this plot image. Extract exactly three values:\n"
        '1. The "Pile" number from the title (e.g., "Pile: 2787.0" -> 2787)\n'
        "2. The angle measurement annotation drawn by the human (a green number\n"
        '   followed by a degree symbol that is NOT part of the "Twist:" label)\n'
        '3. The current "Twist" value from the title (e.g., "Twist: 3.06°" -> 3.06)\n'
        "\n"
        "Return JSON only: "
        '{"pile_number": 2787, "measured_angle": 90.89, "old_twist": 3.06}'
    )

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def read_image(self, image_path: str) -> dict:
        """Returns {"pile_number": int, "measured_angle": float, "old_twist": float}"""

    def parse_response(self, text: str) -> dict:
        """Extract JSON from LLM response text."""
        match = re.search(r"\{[^}]+\}", text)
        if not match:
            raise ValueError(f"No JSON found in response: {text[:200]}")
        data = json.loads(match.group())
        required = {"pile_number", "measured_angle", "old_twist"}
        if not required.issubset(data.keys()):
            raise ValueError(
                f"Missing required fields. Need {required}, got {set(data.keys())}"
            )
        return {
            "pile_number": int(data["pile_number"]),
            "measured_angle": float(data["measured_angle"]),
            "old_twist": float(data["old_twist"]),
        }


PROVIDERS: dict[str, type] = {}


def register_provider(name: str):
    def decorator(cls):
        PROVIDERS[name] = cls
        return cls
    return decorator


def get_provider(name: str, config: dict) -> VisionProvider:
    if name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}"
        )
    return PROVIDERS[name](config)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_providers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add providers/__init__.py tests/test_providers.py
git commit -m "feat: vision provider base class with JSON parsing and provider registry"
```

---

### Task 3: OpenAI Vision Provider

**Files:**
- Create: `providers/openai_provider.py`
- Modify: `tests/test_providers.py`

**Step 1: Add test for OpenAI provider (mocked)**

Append to `tests/test_providers.py`:

```python
from unittest.mock import patch, MagicMock


class TestOpenAIProvider:
    def test_read_image_calls_api(self, sample_image):
        from providers.openai_provider import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '{"pile_number": 2787, "measured_angle": 90.89, "old_twist": 3.06}'
        )

        with patch("providers.openai_provider.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_response
            provider = OpenAIProvider({"openai_api_key": "test-key"})
            result = provider.read_image(str(sample_image))

        assert result["pile_number"] == 2787
        assert result["measured_angle"] == 90.89
        assert result["old_twist"] == 3.06
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_providers.py::TestOpenAIProvider -v`
Expected: FAIL (module not found)

**Step 3: Implement OpenAI provider**

```python
# providers/openai_provider.py
import base64
from pathlib import Path

from openai import OpenAI

from . import VisionProvider, register_provider


@register_provider("openai")
class OpenAIProvider(VisionProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.client = OpenAI(api_key=config.get("openai_api_key"))

    def read_image(self, image_path: str) -> dict:
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        suffix = Path(image_path).suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{image_data}"},
                        },
                    ],
                }
            ],
            max_tokens=200,
        )
        return self.parse_response(response.choices[0].message.content)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_providers.py::TestOpenAIProvider -v`
Expected: PASS

**Step 5: Commit**

```bash
git add providers/openai_provider.py tests/test_providers.py
git commit -m "feat: OpenAI GPT-4o vision provider"
```

---

### Task 4: Claude Vision Provider

**Files:**
- Create: `providers/claude_provider.py`
- Modify: `tests/test_providers.py`

**Step 1: Add test for Claude provider (mocked)**

Append to `tests/test_providers.py`:

```python
class TestClaudeProvider:
    def test_read_image_calls_api(self, sample_image):
        from providers.claude_provider import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = (
            '{"pile_number": 777, "measured_angle": 87.35, "old_twist": 4.69}'
        )

        with patch("providers.claude_provider.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response
            provider = ClaudeProvider({"claude_api_key": "test-key"})
            result = provider.read_image(str(sample_image))

        assert result["pile_number"] == 777
        assert result["measured_angle"] == 87.35
        assert result["old_twist"] == 4.69
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_providers.py::TestClaudeProvider -v`
Expected: FAIL

**Step 3: Implement Claude provider**

```python
# providers/claude_provider.py
import base64
from pathlib import Path

import anthropic

from . import VisionProvider, register_provider


@register_provider("claude")
class ClaudeProvider(VisionProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.client = anthropic.Anthropic(api_key=config.get("claude_api_key"))

    def read_image(self, image_path: str) -> dict:
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        suffix = Path(image_path).suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": self.PROMPT},
                    ],
                }
            ],
        )
        return self.parse_response(response.content[0].text)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_providers.py::TestClaudeProvider -v`
Expected: PASS

**Step 5: Commit**

```bash
git add providers/claude_provider.py tests/test_providers.py
git commit -m "feat: Claude vision provider"
```

---

### Task 5: Gemini Vision Provider

**Files:**
- Create: `providers/gemini_provider.py`
- Modify: `tests/test_providers.py`

**Step 1: Add test for Gemini provider (mocked)**

Append to `tests/test_providers.py`:

```python
class TestGeminiProvider:
    def test_read_image_calls_api(self, sample_image):
        from providers.gemini_provider import GeminiProvider

        mock_response = MagicMock()
        mock_response.text = (
            '{"pile_number": 2791, "measured_angle": 92.35, "old_twist": -3.11}'
        )

        with patch("providers.gemini_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response
            provider = GeminiProvider({"gemini_api_key": "test-key"})
            result = provider.read_image(str(sample_image))

        assert result["pile_number"] == 2791
        assert result["measured_angle"] == 92.35
        assert result["old_twist"] == -3.11
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_providers.py::TestGeminiProvider -v`
Expected: FAIL

**Step 3: Implement Gemini provider**

```python
# providers/gemini_provider.py
import base64
from pathlib import Path

from google import genai

from . import VisionProvider, register_provider


@register_provider("gemini")
class GeminiProvider(VisionProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.client = genai.Client(api_key=config.get("gemini_api_key"))

    def read_image(self, image_path: str) -> dict:
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        suffix = Path(image_path).suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"

        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"inline_data": {"mime_type": mime, "data": image_data}},
                self.PROMPT,
            ],
        )
        return self.parse_response(response.text)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_providers.py::TestGeminiProvider -v`
Expected: PASS

**Step 5: Commit**

```bash
git add providers/gemini_provider.py tests/test_providers.py
git commit -m "feat: Gemini vision provider"
```

---

### Task 6: Image Editor

This is the most visually critical component. It annotates the matplotlib plot title with a red strikethrough on the old twist value and a green new twist value.

**Files:**
- Create: `image_editor.py`
- Create: `tests/test_image_editor.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_image_editor.py -v`
Expected: FAIL (module not found)

**Step 3: Implement image_editor.py**

```python
# image_editor.py
"""Pillow-based image annotation for twist QC.

Adds red strikethrough over old twist value and green new value
in the title area of matplotlib plot images.
"""
from pathlib import Path
import platform

from PIL import Image, ImageDraw, ImageFont


def _find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font approximating matplotlib's default (DejaVu Sans).

    Tries matplotlib's bundled font first, then system fonts, then Pillow default.
    """
    candidates = []

    # Best match: matplotlib's own bundled DejaVu Sans
    try:
        import matplotlib
        mpl_font = (
            Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
        )
        candidates.append(str(mpl_font))
    except ImportError:
        pass

    # System fonts by platform
    if platform.system() == "Darwin":
        candidates += [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    elif platform.system() == "Linux":
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    else:
        candidates += ["C:/Windows/Fonts/arial.ttf"]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    return ImageFont.load_default()


def annotate_image(
    image_path: str,
    old_twist: float,
    new_twist: float,
) -> Image.Image:
    """Annotate a plot image with red strikethrough on old twist, green new twist.

    Args:
        image_path: Path to the matplotlib plot image.
        old_twist: The current twist value shown in the title (e.g., 3.06).
        new_twist: The corrected twist value to display (e.g., -0.89).

    Returns:
        Annotated PIL Image (original file is not modified).
    """
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Font size: matplotlib default title is ~12pt at 100 DPI.
    # For a 480px image that's ~16px. Scale proportionally.
    font_size = max(12, int(height * 0.033))
    font = _find_font(font_size)

    # Format old twist as it appears in the matplotlib title
    old_str = f"{old_twist:.2f}\u00b0"  # e.g., "3.06°" or "-4.82°"

    # Full twist line as matplotlib renders it (centered)
    twist_line_text = f"Twist: {old_str}"
    twist_bbox = draw.textbbox((0, 0), twist_line_text, font=font)
    twist_width = twist_bbox[2] - twist_bbox[0]
    text_height = twist_bbox[3] - twist_bbox[1]

    # X: centered on image width
    twist_line_x = (width - twist_width) // 2

    # Y: second line of two-line title. In matplotlib default layout,
    # the second title line sits at roughly 7% from the top of the image.
    twist_line_y = int(height * 0.068)

    # Calculate where the value starts (after "Twist: " label)
    label_text = "Twist: "
    label_bbox = draw.textbbox((0, 0), label_text, font=font)
    label_width = label_bbox[2] - label_bbox[0]

    value_x = twist_line_x + label_width
    value_bbox = draw.textbbox((0, 0), old_str, font=font)
    value_width = value_bbox[2] - value_bbox[0]

    # Red strikethrough line through the old value (horizontal, centered vertically)
    line_y = twist_line_y + text_height // 2
    draw.line(
        [(value_x, line_y), (value_x + value_width, line_y)],
        fill=(255, 0, 0),
        width=2,
    )

    # Green new twist value, right after the struck-through old value
    new_text = f"{new_twist:.2f}"
    gap = max(5, int(width * 0.012))
    new_x = value_x + value_width + gap
    draw.text(
        (new_x, twist_line_y),
        new_text,
        fill=(0, 160, 0),
        font=font,
    )

    return img
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_image_editor.py -v`
Expected: All PASS

**Step 5: Visual spot-check against reference image**

Run this one-off script to compare against a known good QCd image:

```bash
python -c "
from image_editor import annotate_image
# Process the 'done' original, compare visually to QCd reference
img = annotate_image('Needs QC/done7770.jpg', 4.69, 2.65)
img.save('/tmp/test_7770_qc.jpg')
print('Saved to /tmp/test_7770_qc.jpg - compare visually to Needs QC/QCd/7770.jpg')
"
```

If the strikethrough or green text position is off, adjust the `height * 0.068` Y-offset or `height * 0.033` font-size multiplier in `annotate_image()` and re-run until it matches the reference.

**Step 6: Commit**

```bash
git add image_editor.py tests/test_image_editor.py
git commit -m "feat: Pillow image editor for twist annotation with strikethrough"
```

---

### Task 7: CSV Updater

**Files:**
- Create: `csv_updater.py`
- Create: `tests/test_csv_updater.py`

**Step 1: Write the failing tests**

```python
# tests/test_csv_updater.py
import pandas as pd
import pytest
from csv_updater import CSVUpdater


class TestCSVUpdater:
    def test_update_existing_upn(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        assert updater.update_twist(2787, -0.89) is True
        updater.save()
        df = pd.read_csv(sample_csv)
        assert df.loc[df["UPN"] == 2787, "Twist_Deg"].values[0] == -0.89

    def test_nonexistent_upn_returns_false(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        assert updater.update_twist(11111, 1.0) is False

    def test_multiple_updates_single_save(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        updater.update_twist(2787, -0.89)
        updater.update_twist(777, 2.65)
        updater.save()
        df = pd.read_csv(sample_csv)
        assert df.loc[df["UPN"] == 2787, "Twist_Deg"].values[0] == -0.89
        assert df.loc[df["UPN"] == 777, "Twist_Deg"].values[0] == 2.65

    def test_overwrites_existing_twist_value(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        updater.update_twist(2787, 1.0)
        updater.update_twist(2787, -0.89)  # overwrite
        updater.save()
        df = pd.read_csv(sample_csv)
        assert df.loc[df["UPN"] == 2787, "Twist_Deg"].values[0] == -0.89

    def test_preserves_other_columns(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        updater.update_twist(2787, -0.89)
        updater.save()
        df = pd.read_csv(sample_csv)
        row = df[df["UPN"] == 2787].iloc[0]
        assert row["Detected"] == False  # pandas reads "FALSE" as bool
        assert row["Pile_Height"] == 0
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_csv_updater.py -v`
Expected: FAIL

**Step 3: Implement csv_updater.py**

```python
# csv_updater.py
"""Pandas-based CSV updater for Twist_Deg values."""
import pandas as pd


class CSVUpdater:
    """Loads CSV once, applies batch updates, saves once at end."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)

    def update_twist(self, pile_number: int, new_twist: float) -> bool:
        """Update Twist_Deg for the given UPN. Returns True if UPN found."""
        mask = self.df["UPN"] == pile_number
        if not mask.any():
            return False
        self.df.loc[mask, "Twist_Deg"] = round(new_twist, 2)
        return True

    def save(self):
        """Write the updated DataFrame back to CSV."""
        self.df.to_csv(self.csv_path, index=False)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_csv_updater.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add csv_updater.py tests/test_csv_updater.py
git commit -m "feat: pandas CSV updater for batch Twist_Deg updates"
```

---

### Task 8: CLI Orchestrator - Image Discovery

**Files:**
- Create: `twist_qc.py`
- Create: `tests/test_twist_qc.py`

**Step 1: Write the failing tests for image discovery**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_twist_qc.py -v`
Expected: FAIL

**Step 3: Implement get_images in twist_qc.py (partial, just the function)**

```python
# twist_qc.py
"""Twist QC Automation - CLI entry point and orchestrator."""
import argparse
import os
import sys
import time
from pathlib import Path

import yaml

from csv_updater import CSVUpdater
from image_editor import annotate_image
from providers import get_provider

# Import providers to trigger @register_provider decorators
import providers.openai_provider  # noqa: F401
import providers.claude_provider  # noqa: F401
import providers.gemini_provider  # noqa: F401


def load_config(config_path: str = "config.yaml") -> dict:
    """Load config from YAML file, with env var overrides for API keys."""
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    for key, env_var in [
        ("openai_api_key", "OPENAI_API_KEY"),
        ("claude_api_key", "ANTHROPIC_API_KEY"),
        ("gemini_api_key", "GOOGLE_API_KEY"),
    ]:
        env_val = os.environ.get(env_var)
        if env_val:
            config[key] = env_val
    return config


def get_images(
    input_folder: Path, output_folder: Path, single_image: str | None = None
) -> list[Path]:
    """Get list of images to process, applying skip rules."""
    if single_image:
        path = input_folder / single_image
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        return [path]

    existing = set()
    if output_folder.exists():
        existing = {f.name for f in output_folder.iterdir() if f.is_file()}

    images = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for path in input_folder.glob(ext):
            name = path.name
            if name.startswith("._"):
                continue
            if name.startswith("done"):
                continue
            if name in existing:
                continue
            images.append(path)

    return sorted(images)


def process_image(provider, image_path, csv_updater, output_folder, dry_run=False):
    """Process a single image. Returns (success: bool, message: str)."""
    try:
        data = provider.read_image(str(image_path))
    except Exception as e:
        return False, f"LLM read failed: {e}"

    pile_number = data["pile_number"]
    measured_angle = data["measured_angle"]
    old_twist = data["old_twist"]

    if not (0 <= measured_angle <= 180):
        return False, f"Suspicious angle {measured_angle}\u00b0 (outside 0-180)"

    new_twist = round(90 - measured_angle, 2)

    if dry_run:
        msg = (
            f"Pile {pile_number}: angle={measured_angle}\u00b0, "
            f"old_twist={old_twist}\u00b0, new_twist={new_twist}\u00b0"
        )
        return True, msg

    try:
        annotated = annotate_image(str(image_path), old_twist, new_twist)
    except Exception as e:
        return False, f"Image annotation failed: {e}"

    csv_found = csv_updater.update_twist(pile_number, new_twist)
    csv_msg = "" if csv_found else " (UPN not found in CSV)"

    output_path = output_folder / image_path.name
    annotated.save(str(output_path))

    return True, f"Pile {pile_number}: {old_twist}\u00b0 \u2192 {new_twist}\u00b0{csv_msg}"


def compare_providers(images, config):
    """Run all providers on same images and compare results."""
    from providers import PROVIDERS

    providers = {}
    for name in ["openai", "claude", "gemini"]:
        try:
            providers[name] = get_provider(name, config)
        except Exception as e:
            print(f"  Skipping {name}: {e}")

    for image_path in images:
        print(f"\n{'=' * 50}")
        print(f"Image: {image_path.name}")
        print(f"{'=' * 50}")

        for name, provider in providers.items():
            start = time.time()
            try:
                data = provider.read_image(str(image_path))
                elapsed = time.time() - start
                new_twist = round(90 - data["measured_angle"], 2)
                print(
                    f"  {name:8s}: pile={data['pile_number']}, "
                    f"angle={data['measured_angle']}\u00b0, "
                    f"new_twist={new_twist}\u00b0 ({elapsed:.1f}s)"
                )
            except Exception as e:
                elapsed = time.time() - start
                print(f"  {name:8s}: FAILED - {e} ({elapsed:.1f}s)")


def main():
    parser = argparse.ArgumentParser(description="Twist QC Automation")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["openai", "claude", "gemini", "all"],
    )
    parser.add_argument("--image", default=None, help="Process a single image file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Log results without saving changes"
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args()

    config = load_config(args.config)
    provider_name = args.provider or config.get("default_provider", "openai")

    input_folder = Path(config["input_folder"])
    output_folder = Path(config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)

    images = get_images(input_folder, output_folder, args.image)
    if not images:
        print("No images to process.")
        return

    print(f"Found {len(images)} image(s) to process.")

    if provider_name == "all":
        compare_providers(images, config)
        return

    provider = get_provider(provider_name, config)
    csv_updater = CSVUpdater(config["csv_path"])

    results = {"success": [], "failed": []}

    for image_path in images:
        print(f"\nProcessing {image_path.name}...")
        success, msg = process_image(
            provider, image_path, csv_updater, output_folder, args.dry_run
        )
        if success:
            results["success"].append((image_path.name, msg))
            print(f"  \u2713 {msg}")
        else:
            results["failed"].append((image_path.name, msg))
            print(f"  \u2717 {msg}")

    if not args.dry_run:
        csv_updater.save()

    print(f"\n--- Summary ---")
    print(f"Processed: {len(images)}")
    print(f"Success:   {len(results['success'])}")
    print(f"Failed:    {len(results['failed'])}")
    if results["failed"]:
        print("\nFailed images:")
        for name, msg in results["failed"]:
            print(f"  {name}: {msg}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_twist_qc.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add twist_qc.py tests/test_twist_qc.py
git commit -m "feat: CLI orchestrator with image discovery, processing, and comparison mode"
```

---

### Task 9: CLI Orchestrator - Process Image + Integration Tests

**Files:**
- Modify: `tests/test_twist_qc.py`

**Step 1: Add process_image tests**

Append to `tests/test_twist_qc.py`:

```python
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
```

**Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/test_twist_qc.py
git commit -m "test: add process_image integration tests with mocked provider"
```

---

### Task 10: Visual Calibration Against Reference Images

This task calibrates the image editor against the known-good QCd reference images.

**Files:**
- Possibly modify: `image_editor.py` (adjust constants)

**Step 1: Check actual image dimensions**

```bash
python -c "
from PIL import Image
for name in ['done7770.jpg', 'done27870.jpg', 'done6003150.jpg']:
    img = Image.open(f'Needs QC/{name}')
    print(f'{name}: {img.size}')
"
```

Note the dimensions. If they're not 640x480, the font size and Y-offset may need adjustment.

**Step 2: Generate test annotations and compare**

```bash
python -c "
from image_editor import annotate_image

# Test case 1: Pile 777, old_twist=4.69, new_twist=2.65
img = annotate_image('Needs QC/done7770.jpg', 4.69, 2.65)
img.save('/tmp/test_7770.jpg')

# Test case 2: Pile 2787, old_twist=3.06, new_twist=-0.89
img = annotate_image('Needs QC/done27870.jpg', 3.06, -0.89)
img.save('/tmp/test_27870.jpg')

# Test case 3: Pile 600315, old_twist=-4.82, new_twist=-1.86
img = annotate_image('Needs QC/done6003150.jpg', -4.82, -1.86)
img.save('/tmp/test_6003150.jpg')

print('Compare /tmp/test_*.jpg against Needs QC/QCd/*.jpg')
"
```

Open the generated images side-by-side with the QCd references. Check:
1. Is the red strikethrough line positioned over the old twist number?
2. Is the green text positioned right after the strikethrough?
3. Are font sizes approximately matching?

**Step 3: Adjust constants if needed**

If the Y position is off, modify the `height * 0.068` multiplier in `image_editor.py`.
If the font size is off, modify the `height * 0.033` multiplier.
Re-run step 2 until it looks right.

**Step 4: Commit any adjustments**

```bash
git add image_editor.py
git commit -m "fix: calibrate image editor text positioning against reference images"
```

---

### Task 11: End-to-End Smoke Test

**Step 1: Test with a single real image using dry-run**

Pick an image that has a green measurement annotation (check visually first):

```bash
python twist_qc.py --provider openai --image done7770.jpg --dry-run
```

This tests the full pipeline except saving. Verify the output shows correct pile number, angle, and new twist.

Note: `done7770.jpg` doesn't have a green measurement line (it's the original). Use one of the non-done images that has been measured, or use one of the done images that corresponds to a QCd output (those had measurement lines drawn before being renamed to "done").

**Step 2: Test with a real image (saves output)**

```bash
python twist_qc.py --provider openai --image <filename>.jpg
```

Check:
- Annotated image appears in `Needs QC/QCd/`
- `Final_Report.csv` has updated `Twist_Deg` for the correct UPN
- The annotation looks correct visually

**Step 3: Test provider comparison mode**

```bash
python twist_qc.py --provider all --image <filename>.jpg --dry-run
```

Verify all three providers return similar values.

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: end-to-end smoke test verified"
```

---

## File Summary

| File | Purpose |
|---|---|
| `requirements.txt` | Python dependencies |
| `config.yaml` | Paths and default provider |
| `providers/__init__.py` | VisionProvider ABC, JSON parser, registry |
| `providers/openai_provider.py` | GPT-4o vision integration |
| `providers/claude_provider.py` | Claude Sonnet vision integration |
| `providers/gemini_provider.py` | Gemini Flash vision integration |
| `image_editor.py` | Pillow strikethrough + green text annotation |
| `csv_updater.py` | Pandas batch CSV updater |
| `twist_qc.py` | CLI orchestrator (argparse, batch loop, summary) |
| `tests/conftest.py` | Shared test fixtures |
| `tests/test_providers.py` | Provider base class + mocked API tests |
| `tests/test_image_editor.py` | Image annotation tests |
| `tests/test_csv_updater.py` | CSV update tests |
| `tests/test_twist_qc.py` | Image discovery + process_image tests |
