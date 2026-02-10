# Twist QC Automation Tool - Design Document

## Problem

A human manually QC's pile twist measurements: draws an angle measurement line on a plot image, crosses out the old twist value, writes the new one, and updates a CSV spreadsheet. This is repetitive and error-prone. The tool automates everything after the human draws the measurement line.

## Workflow

```
[Human measures angle in external software, draws green line on image]
        |
[Drops image into Needs QC/ folder]
        |
[Runs: python twist_qc.py --provider openai]
        |
For each image (.jpg and .png):
  1. LLM Vision reads: Pile number + measured angle from green annotation
  2. Calculates new twist = 90 - measured_angle
  3. Strips decimal from Pile number (2787.0 -> 2787) for CSV lookup
  4. Pillow edits image:
     - Red strikethrough over old "Twist: X.XX deg" text
     - Green new twist value written next to struck-through text
  5. Looks up UPN in Final_Report.csv -> updates Twist_Deg column
  6. Saves annotated image to QCd/ subfolder
        |
[Summary: processed N images, M successes, K failures]
```

## Project Structure

```
twist-qc/
  twist_qc.py           # CLI entry point & orchestrator
  config.yaml            # API keys, paths, provider selection
  providers/
    __init__.py          # Base class + provider registry
    openai_provider.py   # GPT-4o vision
    claude_provider.py   # Claude vision
    gemini_provider.py   # Gemini vision
  image_editor.py        # Pillow-based annotation (strikethrough + new text)
  csv_updater.py         # Pandas CSV lookup & update
  requirements.txt
```

## Components

### 1. LLM Vision Provider (swappable)

Base class with a single method:

```python
class VisionProvider:
    def read_image(self, image_path: str) -> dict:
        """Returns {"pile_number": int, "measured_angle": float}"""
```

Each provider (OpenAI, Claude, Gemini) wraps its SDK and sends the image with the same structured prompt so results are directly comparable.

**Shared prompt:**
```
Look at this plot image. Extract exactly two values:
1. The "Pile" number from the title (e.g., "Pile: 2787.0" -> 2787)
2. The angle measurement annotation drawn by the human (a number
   followed by a degree symbol that is NOT part of the "Twist:" label)

Return JSON only: {"pile_number": 2787, "measured_angle": 90.89}
```

Switch providers via CLI flag: `--provider openai|claude|gemini`

### 2. Image Editor (Pillow)

- Locates the "Twist: X.XX deg" text region (consistent position in matplotlib plots)
- Draws a red strikethrough line over the old twist value
- Writes the new twist value in green, positioned right after the struck-through text
- Handles both .jpg and .png formats

### 3. CSV Updater (Pandas)

- Loads Final_Report.csv (~62K rows)
- Finds row where UPN == pile_number (integer, no decimal)
- Updates Twist_Deg column with new value
- Saves CSV

### 4. CLI Orchestrator

Scans input folder for images. Skips:
- Files prefixed with `done` (already manually QC'd)
- Files prefixed with `._` (macOS resource forks)
- Files already present in QCd/

For each valid image: LLM read -> calculate twist -> edit image -> update CSV -> save to QCd/

## Configuration

```yaml
# config.yaml
# API Keys (or set via environment variables, env vars take precedence)
openai_api_key: ${OPENAI_API_KEY}
claude_api_key: ${ANTHROPIC_API_KEY}
gemini_api_key: ${GOOGLE_API_KEY}

# Paths
input_folder: ./Needs QC
output_folder: ./Needs QC/QCd
csv_path: ./Needs QC/Final_Report.csv

# Defaults
default_provider: openai
```

## Error Handling

Strategy: skip failures, continue batch, print summary.

| Scenario | Behavior |
|---|---|
| LLM can't read Pile number or angle | Skip image, log warning, continue |
| UPN not found in CSV | Skip CSV update, still save annotated image, log warning |
| Image already exists in QCd/ | Skip (don't reprocess), log as "already done" |
| LLM API rate limit / error | Retry once with backoff, then skip and log |
| Invalid angle (outside 0-180 deg) | Skip image, log as suspicious |

## CLI Usage

```bash
# Process all images with OpenAI
python twist_qc.py --provider openai

# Process with Claude
python twist_qc.py --provider claude

# Compare all three providers (test mode, doesn't save edits)
python twist_qc.py --provider all --dry-run

# Process a single image
python twist_qc.py --provider gemini --image 152560.jpg
```

## Provider Comparison Mode

`--provider all` processes the same image through all three APIs and logs:
- Extracted values from each provider
- Agreement/disagreement
- Response time per provider

Useful for initial calibration before committing to one provider.

## Key Decisions

- **LLM role: Vision OCR only.** LLM reads text from images. All image editing is programmatic (Pillow) for pixel-perfect precision.
- **New twist formula:** `90 - measured_angle`
- **Annotation color:** Always green (hardcoded).
- **Strikethrough color:** Red.
- **UPN mapping:** Pile number from image title, strip `.0` decimal, look up integer in CSV.
- **Output:** Annotated images saved to QCd/ subfolder. Originals untouched.
