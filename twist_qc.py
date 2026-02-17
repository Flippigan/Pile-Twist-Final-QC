# twist_qc.py
"""Twist QC Automation - CLI entry point and orchestrator."""
import argparse
import sys
from pathlib import Path

import yaml
from csv_updater import CSVUpdater
from image_editor import annotate_image
from providers import get_provider

# Import provider to trigger @register_provider decorator
import providers.paddleocr_provider  # noqa: F401


def load_config(config_path: str = "config.yaml") -> dict:
    """Load config from YAML file."""
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    return config


def find_csv(input_folder: Path, config: dict) -> Path:
    """Find the CSV file to update. Uses csv_path from config if set,
    otherwise auto-detects a single CSV in input_folder or its parent."""
    if "csv_path" in config:
        return Path(config["csv_path"])

    search_dirs = [input_folder, input_folder.parent]
    csvs = []
    for d in search_dirs:
        csvs.extend(
            c for c in d.glob("*.csv") if not c.name.startswith("._")
        )
    # Deduplicate (in case input_folder == parent somehow)
    csvs = list({c.resolve(): c for c in csvs}.values())

    if len(csvs) == 0:
        raise FileNotFoundError(
            f"No CSV file found in {input_folder} or {input_folder.parent}"
        )
    if len(csvs) > 1:
        names = ", ".join(c.name for c in csvs)
        raise RuntimeError(
            f"Multiple CSV files found: {names}. "
            f"Set csv_path in config or remove extras."
        )
    return csvs[0]


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
    # Pile number comes from the filename with trailing 0 removed (e.g., 1526800.jpg -> 152680)
    pile_number = int(image_path.stem[:-1])

    try:
        data = provider.read_image(str(image_path))
    except Exception as e:
        return False, f"OCR read failed: {e}"

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


def main():
    parser = argparse.ArgumentParser(description="Twist QC Automation")
    parser.add_argument("--image", default=None, help="Process a single image file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Log results without saving changes"
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args()

    config = load_config(args.config)

    input_folder = Path(config["input_folder"])
    output_folder = Path(config["output_folder"])
    output_folder.mkdir(parents=True, exist_ok=True)

    images = get_images(input_folder, output_folder, args.image)
    if not images:
        print("No images to process.")
        return

    print(f"Found {len(images)} image(s) to process.")

    provider = get_provider("paddleocr", config)
    csv_path = find_csv(input_folder, config)
    print(f"Using CSV: {csv_path.name}")
    csv_updater = CSVUpdater(str(csv_path))

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
