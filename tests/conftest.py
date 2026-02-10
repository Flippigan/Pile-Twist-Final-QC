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
