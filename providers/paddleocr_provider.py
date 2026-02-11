# providers/paddleocr_provider.py
"""PaddleOCR-based angle extraction from pile plot images."""
import re

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

from . import VisionProvider, register_provider


def _find_green_bounds(img_array: np.ndarray):
    """Find bounding box of green-dominant pixels in the image.

    Returns:
        Tuple of (green_mask, rmin, rmax, cmin, cmax) with padding applied.

    Raises:
        ValueError: If no green pixels are found.
    """
    r = img_array[:, :, 0].astype(int)
    g = img_array[:, :, 1].astype(int)
    b = img_array[:, :, 2].astype(int)

    green_mask = (g > 60) & (g > r + 20) & (g > b + 20)

    rows_any = np.any(green_mask, axis=1)
    cols_any = np.any(green_mask, axis=0)

    if not rows_any.any():
        raise ValueError("No green pixels found in image")

    rmin, rmax = np.where(rows_any)[0][[0, -1]]
    cmin, cmax = np.where(cols_any)[0][[0, -1]]

    pad = 20
    rmin = max(0, rmin - pad)
    rmax = min(img_array.shape[0], rmax + pad + 1)
    cmin = max(0, cmin - pad)
    cmax = min(img_array.shape[1], cmax + pad + 1)

    return green_mask, rmin, rmax, cmin, cmax


def isolate_green_text(img_array: np.ndarray) -> np.ndarray:
    """Isolate green annotation pixels and return a binary image for OCR.

    Masks green-dominant pixels, crops to their bounding box, and produces
    a high-contrast black-on-white image suitable for OCR.

    Args:
        img_array: RGB image as numpy array (H, W, 3), dtype uint8.

    Returns:
        Binary numpy array (H', W', 3) — black text on white background,
        upscaled with LANCZOS for OCR readability.

    Raises:
        ValueError: If no green pixels are found in the image.
    """
    green_mask, rmin, rmax, cmin, cmax = _find_green_bounds(img_array)

    cropped_mask = green_mask[rmin:rmax, cmin:cmax]
    binary = np.full((*cropped_mask.shape, 3), 255, dtype=np.uint8)
    binary[cropped_mask] = [0, 0, 0]

    # Upscale for OCR accuracy — LANCZOS produces smooth edges
    pil_img = Image.fromarray(binary)
    scale = max(6, 360 // max(binary.shape[0], 1))
    pil_img = pil_img.resize(
        (pil_img.width * scale, pil_img.height * scale),
        Image.LANCZOS,
    )
    return np.array(pil_img)


def _crop_green_region(img_array: np.ndarray) -> np.ndarray:
    """Crop the original image to the green text region, upscaled for OCR.

    Unlike isolate_green_text(), this preserves the original pixel colors.
    OCR can sometimes read the green text directly better than a binary mask.

    Args:
        img_array: RGB image as numpy array (H, W, 3), dtype uint8.

    Returns:
        Upscaled crop of the original image around the green text region.

    Raises:
        ValueError: If no green pixels are found in the image.
    """
    _, rmin, rmax, cmin, cmax = _find_green_bounds(img_array)

    crop = img_array[rmin:rmax, cmin:cmax]
    pil_crop = Image.fromarray(crop)
    scale = max(4, 240 // max(crop.shape[0], 1))
    pil_crop = pil_crop.resize(
        (pil_crop.width * scale, pil_crop.height * scale),
        Image.LANCZOS,
    )
    return np.array(pil_crop)


# Lazy singleton — avoids reloading ~100MB of models per image
_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _ocr_instance


def _extract_candidates(ocr_results) -> list:
    """Extract (angle_float, confidence) candidates from OCR results."""
    candidates = []
    for page in ocr_results:
        texts = page["rec_texts"]
        scores = page["rec_scores"]
        for text, confidence in zip(texts, scores):
            # Strip degree symbol, asterisks/percent (misread °), and whitespace
            cleaned = text.replace("°", "").replace("*", "").replace("%", "").replace(" ", "").strip()
            match = re.match(r"^(\d+\.?\d*)$", cleaned)
            if match:
                candidates.append((float(match.group(1)), confidence))
    return candidates


def _parse_angle_from_ocr(ocr_results) -> float:
    """Extract a numeric angle value from PaddleOCR predict() results.

    PaddleOCR v2.9+ returns OCRResult objects with rec_texts and rec_scores.

    Raises:
        ValueError: If no numeric angle value is found.
    """
    candidates = _extract_candidates(ocr_results)

    if not candidates:
        raise ValueError(
            f"No angle value found in OCR results: {ocr_results}"
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

        ocr = _get_ocr()

        # Strategy: try both binary mask and original crop, pick best result.
        # Binary mask works well for clear text; original crop preserves
        # letter shapes better when the mask loses edge pixels.
        all_candidates = []

        binary = isolate_green_text(img_array)
        result_bin = list(ocr.predict(binary))
        all_candidates.extend(_extract_candidates(result_bin))

        crop = _crop_green_region(img_array)
        result_crop = list(ocr.predict(crop))
        all_candidates.extend(_extract_candidates(result_crop))

        if not all_candidates:
            raise ValueError(
                f"No angle value found in OCR results for {image_path}"
            )

        # Prefer candidates in the expected 40-140° range (typical for pile plots)
        in_range = [(v, c) for v, c in all_candidates if 40 <= v <= 140]
        pool = in_range if in_range else all_candidates

        # Pick highest-confidence numeric result
        pool.sort(key=lambda c: c[1], reverse=True)
        measured_angle = pool[0][0]
        return {"measured_angle": measured_angle}
