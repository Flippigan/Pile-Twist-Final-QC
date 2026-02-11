# twist_qc.py
"""Twist QC Automation - CLI entry point and orchestrator."""
import argparse
import os
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from csv_updater import CSVUpdater
from image_editor import annotate_image
from providers import get_provider

# Import providers to trigger @register_provider decorators
import providers.openai_provider  # noqa: F401
import providers.claude_provider  # noqa: F401
import providers.gemini_provider  # noqa: F401
import providers.paddleocr_provider  # noqa: F401


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
    # Pile number comes from the filename with trailing 0 removed (e.g., 1526800.jpg → 152680)
    pile_number = int(image_path.stem[:-1])

    try:
        data = provider.read_image(str(image_path))
    except Exception as e:
        return False, f"LLM read failed: {e}"

    measured_angle = data["measured_angle"]

    if not (0 <= measured_angle <= 180):
        return False, f"Suspicious angle {measured_angle}\u00b0 (outside 0-180)"

    new_twist = round(90 - measured_angle, 2)

    if dry_run:
        msg = (
            f"Pile {pile_number}: angle={measured_angle}\u00b0, "
            f"new_twist={new_twist}\u00b0"
        )
        return True, msg

    try:
        annotated = annotate_image(str(image_path), new_twist)
    except Exception as e:
        return False, f"Image annotation failed: {e}"

    csv_found = csv_updater.update_twist(pile_number, new_twist)
    csv_msg = "" if csv_found else " (UPN not found in CSV)"

    output_path = output_folder / image_path.name
    annotated.save(str(output_path))

    return True, f"Pile {pile_number}: new_twist={new_twist}\u00b0{csv_msg}"


def compare_providers(images, config):
    """Run all providers on same images and compare results."""
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
        choices=["openai", "claude", "gemini", "paddleocr", "all"],
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
