# Twist QC Automation

A CLI tool that batch-processes pile plot images to extract measured angles using OCR, calculate new twist values, annotate images, and update a CSV report.

## How It Works

1. Reads each image from an input folder
2. Extracts the green angle measurement from the scatter plot using PaddleOCR
3. Calculates the new twist: `new_twist = 90 - measured_angle`
4. Annotates the image with the new twist value (red strikethrough on the old value, green new value)
5. Saves the annotated image to an output folder
6. Updates the `Twist_Deg` column in a CSV report, matched by pile number (UPN)

The pile number (UPN) is derived from the image filename by removing a single trailing zero (e.g., `1526800.jpg` corresponds to UPN `152680`).

## Requirements

- Python 3.13 or earlier (PaddleOCR does not support 3.14+)

## Setup

1. Clone or copy this project to your machine.

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuring for Your Dataset

Edit `config.yaml` to point to your data:

```yaml
# Paths (relative to project root or absolute)
input_folder: /path/to/your/input/images
output_folder: /path/to/your/output/folder
csv_path: /path/to/your/Final_Report.csv
```

### Input folder requirements
- Contains `.jpg`, `.jpeg`, or `.png` pile plot images
- Each filename must be the UPN with a trailing zero appended (e.g., `1526800.jpg` for UPN `152680`)
- Images already present in the output folder are automatically skipped

### CSV requirements
- Must contain a `UPN` column (integer pile numbers) and a `Twist_Deg` column
- The tool updates `Twist_Deg` in place; all other columns are preserved

## Usage

### Process all images
```bash
python twist_qc.py
```

### Process a single image
```bash
python twist_qc.py --image 1526800.jpg
```

### Dry run (log results without saving)
```bash
python twist_qc.py --dry-run
```

### Use a different config file
```bash
python twist_qc.py --config /path/to/other/config.yaml
```

## Running Tests

```bash
pytest
```
