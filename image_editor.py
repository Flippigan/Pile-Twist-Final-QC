# image_editor.py
"""Pillow-based image annotation for twist QC.

Adds red strikethrough over old twist value and green new value
in the title area of matplotlib plot images.
"""
from pathlib import Path
import platform

import numpy as np
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


def _find_twist_line_y(img_array: np.ndarray) -> int | None:
    """Scan the image for the Y position of the 'Twist:' title text.

    Looks for clusters of dark gray pixels (matplotlib title text) in the
    top 30% of the image. Returns the top Y of the second text cluster
    (the 'Twist:' line), or None if not found.
    """
    height, width = img_array.shape[:2]
    scan_limit = int(height * 0.30)

    # Find rows with centered dark gray pixels (title text is gray, centered)
    center_start = int(width * 0.25)
    center_end = int(width * 0.75)
    text_rows = []

    for y in range(scan_limit):
        row = img_array[y, center_start:center_end, :]
        # Dark gray: R=G=B, between 50-140
        gray_mask = (
            (row[:, 0] > 40) & (row[:, 0] < 150)
            & (np.abs(row[:, 0].astype(int) - row[:, 1].astype(int)) < 20)
            & (np.abs(row[:, 1].astype(int) - row[:, 2].astype(int)) < 20)
        )
        if gray_mask.sum() >= 4:
            text_rows.append(y)

    if not text_rows:
        return None

    # Group into clusters (text lines) separated by gaps
    clusters = []
    current = [text_rows[0]]
    for y in text_rows[1:]:
        if y - current[-1] <= 3:  # within same text line
            current.append(y)
        else:
            clusters.append(current)
            current = [y]
    clusters.append(current)

    # The second cluster is the "Twist:" line
    if len(clusters) >= 2:
        return clusters[1][0]
    # If only one cluster, it might be the "Twist:" line itself
    if len(clusters) == 1:
        return clusters[0][0]
    return None


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

    # Font size: calibrated against 500x500 matplotlib plots where title is ~14px.
    font_size = max(12, int(height * 0.028))
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

    # Y: find the actual "Twist:" line by scanning for gray title text
    img_array = np.array(img)
    twist_line_y = _find_twist_line_y(img_array)
    if twist_line_y is None:
        # Fallback: assume second title line at ~18.6% from top
        twist_line_y = int(height * 0.186)

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
