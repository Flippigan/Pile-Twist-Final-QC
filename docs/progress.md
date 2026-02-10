# Twist QC Automation - Implementation Progress

**Plan:** [2026-02-10-twist-qc-implementation-plan.md](plans/2026-02-10-twist-qc-implementation-plan.md)
**Started:** 2026-02-10

---

## Task 1: Project Scaffolding — DONE
**Commit:** `3c6919a` — `chore: project scaffolding with deps, config, and test fixtures`

- Created `requirements.txt` (openai, anthropic, google-generativeai, Pillow, pandas, PyYAML, pytest)
- Created `config.yaml` (paths, default provider)
- Created `providers/__init__.py`, `tests/__init__.py`, `tests/conftest.py`
- Set up `.venv` with Python 3.14.1, all deps installed
- Initialized git repo with `.gitignore` (excludes .venv, __pycache__, Needs QC/)
- Verified: `pytest` runs clean (no tests, no import errors)

## Task 2: Vision Provider Base Class + Registry — DONE
**Commit:** `e0544b0` — `feat: vision provider base class with JSON parsing and provider registry`

- `providers/__init__.py`: `VisionProvider` ABC with shared `PROMPT` and `parse_response()` JSON extractor
- `register_provider()` decorator + `get_provider()` factory + `PROVIDERS` dict
- 7 tests passing: JSON parsing (valid, embedded, no-json, missing-fields, type-coercion), registry (register+get, unknown-error)

## Task 3: OpenAI Vision Provider — DONE
**Commit:** `cb2f149` — `feat: OpenAI GPT-4o vision provider`

- `providers/openai_provider.py`: GPT-4o vision via base64-encoded image, registered as `"openai"`
- 1 mocked test: verifies API call structure and response parsing
- Full suite: 8 tests passing

## Task 4: Claude Vision Provider — DONE
**Commit:** `831d533` — `feat: Claude vision provider`

- `providers/claude_provider.py`: Claude Sonnet 4.5 vision via base64-encoded image, registered as `"claude"`
- 1 mocked test: verifies API call structure and response parsing
- Full suite: 9 tests passing

## Task 5: Gemini Vision Provider — DONE
**Commit:** `221144e` — `feat: Gemini vision provider`

- `providers/gemini_provider.py`: Gemini 2.0 Flash vision via base64-encoded image, registered as `"gemini"`
- Fixed `requirements.txt`: switched from deprecated `google-generativeai` to `google-genai` (new SDK)
- 1 mocked test: verifies API call structure and response parsing
- Full suite: 10 tests passing

## Task 6: Image Editor — DONE
**Commit:** `ca11a96` — `feat: Pillow image editor for twist annotation with strikethrough`

- `image_editor.py`: Pillow-based annotation with red strikethrough on old twist + green new twist text
- `_find_font()`: tries matplotlib DejaVu Sans, then system fonts, then Pillow default
- 9 tests: font loading, returns image, size unchanged, original unmodified, red/green pixels, negative values, PNG support
- Full suite: 19 tests passing

## Task 7: CSV Updater — DONE
**Commit:** `949ac5c` — `feat: pandas CSV updater for batch Twist_Deg updates`

- `csv_updater.py`: Loads CSV once, applies batch updates to `Twist_Deg`, saves once at end
- 5 tests: update existing UPN, nonexistent returns false, multiple updates, overwrites, preserves other columns
- Full suite: 24 tests passing

## Task 8: CLI Orchestrator - Image Discovery — DONE
**Commit:** `cf671d5` — `feat: CLI orchestrator with image discovery, processing, and comparison mode`

- `twist_qc.py`: Full CLI with argparse (--provider, --image, --dry-run, --config)
- `get_images()`: discovers jpg/png, skips done* prefix, macOS resource forks, already-processed
- `process_image()`: LLM read → validate angle → annotate → CSV update → save
- `compare_providers()`: run all providers on same images, compare results
- 7 tests for image discovery
- Full suite: 31 tests passing

## Task 9: CLI Orchestrator - Integration Tests — DONE
**Commit:** `b476469` — `test: add process_image integration tests with mocked provider`

- 5 integration tests: successful processing, dry-run no save, invalid angle rejected, LLM failure handled, CSV miss still saves image
- Full suite: 36 tests passing

## Task 10: Visual Calibration — DONE
**Commit:** `4256d3c` — `fix: calibrate image editor text positioning against reference images`

- Pixel-scanned reference 500x500 images to find actual title text Y positions
- Initial calibration: adjusted Y-offset from 6.8% to 18.6%, font size from 3.3% to 2.8%
- Later replaced with dynamic `_find_twist_line_y()` pixel scanner (see Task 11)

## Task 11: End-to-End Smoke Test — DONE
**Commit:** `eafadfb` — `feat: E2E smoke test verified with Claude vision provider`

- Added `python-dotenv` for `.env` file API key loading
- Fixed all providers to let SDKs read env vars when key not in config
- Replaced fixed-percentage Y-offset with dynamic `_find_twist_line_y()` that scans for gray title pixels — works for both 500x500 and 600x600 images
- Added `.env.example` template, `.env` to `.gitignore`
- E2E verified: Claude reads pile 2796 image → angle=88.91° → new_twist=1.09° → annotated image saved → CSV updated
- Annotation visually matches reference QCd images on both image sizes

## Post-plan: Prompt Tuning & Annotation Spacing
**Commit:** `4ed741b` — `fix: improve LLM prompt for 90° angles and widen annotation gap`

- Batch-tested 34 images from `Needs QC - LLM Test/QCd/` with Claude: 34/34 succeeded (94s, 2.8s/image)
- Found ~5 misreads where Claude dropped leading "90" from angles near 90° (e.g., 90.55° → 0.55°)
- Improved prompt: specifies angle is typically 80-100°, emphasizes reading ALL digits
- Verified fix: Claude now correctly reads 90.55° on previously-misread image
- Widened gap between strikethrough and green text (1.2% → 4% of image width) to prevent overlap
- Output images saved to `Needs QC - LLM Test/Output/` (34 annotated images, pre-prompt-fix)

---

## ALL 11 PLAN TASKS + POST-PLAN FIXES COMPLETE

## Test Suite Status
- **Total tests:** 36
- **All passing:** yes
- **Last full run:** after prompt/gap fix commit

## Batch Run Results (pre-prompt-fix, Claude provider)
- **Images processed:** 34/34
- **Time:** 94s (2.8s/image average)
- **Misreads (now fixed):** ~5 angles near 90° where leading digits were dropped
- **Output location:** `Needs QC - LLM Test/Output/`

## Known Considerations
- Input images must have green angle annotation drawn by human before processing
- Images in `Needs QC/` (without "done" prefix and not already in QCd/) are auto-discovered
- `Needs QC - LLM Test/QCd/` contains human-measured test images (not connected to default config)
- API keys loaded from `.env` file (gitignored) or environment variables
