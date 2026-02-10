# PaddleOCR Angle Extraction — Replace LLM Vision

## Goal
Replace LLM API calls (Claude/OpenAI/Gemini) with local PaddleOCR to read the green angle annotation from plot images. Combined with filename-based pile numbers, this eliminates all LLM dependencies — making processing free, fast, and deterministic.

## Why PaddleOCR
- Highest accuracy of the major Python OCR libraries for small/scene text
- Handles text detection + recognition in one pipeline
- pip-installable (`paddlepaddle`, `paddleocr`)
- No system-level dependencies (unlike Tesseract)
- Supports angle detection natively

## Approach

### 1. Isolate Green Annotation Pixels
The green angle text (e.g., "90.55°") is the only green element on the plot. Isolate it by color filtering:
- Convert image to HSV or use RGB thresholds to mask green pixels
- Similar to existing `_find_twist_line_y()` gray pixel scanner, but targeting green
- Produce a high-contrast binary image (black text on white background) from the mask

### 2. Crop to Annotation Region
- The green text is near the intersection of the blue and red lines, roughly in the center of the plot area
- Crop to the region of interest to avoid OCR picking up axis labels or title text
- Could scan for the green pixel cluster centroid and crop a bounding box around it

### 3. Run PaddleOCR on Cleaned Region
- Feed the cropped, contrast-enhanced image to PaddleOCR
- Extract the numeric text result
- Parse as float (strip degree symbol if detected)

### 4. Integrate as a New Provider (or Replace Provider Layer)
Two options:
- **Option A:** Add as a new provider (`@register_provider("paddleocr")`) that implements `read_image()` — keeps the existing provider architecture, allows fallback to LLM if OCR fails
- **Option B:** Replace the provider layer entirely since OCR is now the only extraction method and pile number comes from filename — simpler but removes LLM comparison capability

## Dependencies
```
paddlepaddle
paddleocr
```

## Considerations
- PaddleOCR pulls in PaddlePaddle (~500MB+). Acceptable for a batch processing tool, but notable.
- First run downloads OCR models (~100MB). Subsequent runs use cached models.
- Green pixel isolation quality depends on image compression artifacts (JPG vs PNG)
- May need to tune HSV/RGB thresholds against the actual green color used in annotations
- The degree symbol (°) may or may not be recognized — parse defensively
- Test against the full 34-image set in `Needs QC - LLM Test/QCd/` and compare accuracy to Claude results
