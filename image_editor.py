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
