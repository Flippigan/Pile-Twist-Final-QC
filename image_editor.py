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


def _find_text_x_extent(img_array: np.ndarray, y_start: int,
                        scan_height: int, img_width: int) -> tuple[int, int] | None:
    """Find the horizontal extent of gray text pixels on a title line.

    Scans rows from y_start through scan_height to find the leftmost
    and rightmost gray text pixels. Returns (left_x, right_x) or None.
    """
    left_x = img_width
    right_x = 0
    y_end = min(img_array.shape[0], y_start + scan_height)

    for y in range(y_start, y_end):
        row = img_array[y]
        for x in range(img_width):
            r, g, b = int(row[x, 0]), int(row[x, 1]), int(row[x, 2])
            if (40 < r < 150
                    and abs(r - g) < 20
                    and abs(g - b) < 20):
                left_x = min(left_x, x)
                right_x = max(right_x, x)

    if right_x > left_x:
        return (left_x, right_x)
    return None


def annotate_image(
    image_path: str,
    new_twist: float,
) -> Image.Image:
    """Annotate a plot image with red strikethrough on old twist, green new twist.

    Args:
        image_path: Path to the matplotlib plot image.
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

    # Y: find the actual "Twist:" line by scanning for gray title text
    img_array = np.array(img)
    twist_line_y = _find_twist_line_y(img_array)
    if twist_line_y is None:
        # Fallback: assume second title line at ~18.6% from top
        twist_line_y = int(height * 0.186)

    # Estimate text height from font
    sample_bbox = draw.textbbox((0, 0), "Twist: 0.00\u00b0", font=font)
    text_height = sample_bbox[3] - sample_bbox[1]

    # Find X extent of the twist line text by pixel scanning
    text_extent = _find_text_x_extent(img_array, twist_line_y,
                                      text_height + 4, width)

    # Calculate where the value starts (after "Twist: " label)
    label_text = "Twist: "
    label_bbox = draw.textbbox((0, 0), label_text, font=font)
    label_width = label_bbox[2] - label_bbox[0]

    if text_extent:
        text_left, text_right = text_extent
        value_x = text_left + label_width
        value_end_x = text_right + 1
    else:
        # Fallback: estimate from centered template
        template = "Twist: 0.00\u00b0"
        tmpl_bbox = draw.textbbox((0, 0), template, font=font)
        tmpl_width = tmpl_bbox[2] - tmpl_bbox[0]
        text_left = (width - tmpl_width) // 2
        value_x = text_left + label_width
        value_end_x = text_left + tmpl_width

    # Red strikethrough line through the old value (horizontal, centered vertically)
    line_y = twist_line_y + text_height // 2
    draw.line(
        [(value_x, line_y), (value_end_x, line_y)],
        fill=(255, 0, 0),
        width=2,
    )

    # Green new twist value, right after the struck-through old value
    new_text = f"{new_twist:.2f}"
    gap = max(10, int(width * 0.04))
    new_x = value_end_x + gap
    draw.text(
        (new_x, twist_line_y),
        new_text,
        fill=(0, 160, 0),
        font=font,
    )

    return img
