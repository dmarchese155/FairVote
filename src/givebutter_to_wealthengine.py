"""
Givebutter → WealthEngine CSV Converter
Cleans a Givebutter contacts export for upload to WealthEngine.

Usage (via launcher):
    Open main.py, select this script, and choose your input file.

Usage (command line):
    python givebutter_to_wealthengine.py

The input file is configured in the CONFIG section below.
Two output files are always written next to the input file:
    <input>_cleaned.csv      — records that look like real individuals
    <input>_manual_review.csv — records that may be businesses/orgs/etc.

See the examples/ folder for properly formatted input/output examples.
"""

import csv
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG — edit this line when running from the command line.
# When run via the launcher, INPUT_FILE is replaced by the file you pick.
# ---------------------------------------------------------------------------
INPUT_FILE = "input.csv"   # <-- your Givebutter export (CLI fallback)

# ---------------------------------------------------------------------------
# Output columns
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "First Name",
    "Last Name",
    "Address Line 1",
    "Address Line 2",
    "City",
    "State",
    "Postal Code",
    "Total Contributions",
    "Primary Phone",
    "Primary Email",
]

# ---------------------------------------------------------------------------
# Suspicious-name detection
# Names matching these patterns are routed to the manual review file.
# ---------------------------------------------------------------------------

SUSPICIOUS_PATTERNS = [
    r"&",
    r"\bthe\b",
    r"\band\b",
    r"\bfund\b",
    r"\bcharity\b",
    r"\bfoundation\b",
    r"\banonymous\b",
    r"\bfamily\b",
    r"\btrust\b",
    r'"',
    r"\(",
    r"\)",
    r"\.",
]

SUSPICIOUS_REGEX = re.compile(
    "|".join(SUSPICIOUS_PATTERNS),
    flags=re.IGNORECASE,
)

# Additional punctuation characters to flag
PUNCTUATION_REGEX = re.compile(r"[!@#$%^*_=+\[\]{}|\\/:;<>?~`]")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_phone(phone: str) -> str:
    """Remove a leading '+' from phone numbers."""
    if not phone:
        return ""
    phone = phone.strip()
    if phone.startswith("+"):
        phone = phone[1:]
    return phone


def is_suspicious_name(first_name: str, last_name: str) -> bool:
    """Return True if the name looks like a business, org, or contains
    unexpected punctuation or special characters."""
    full_name = f"{first_name} {last_name}".strip()
    if SUSPICIOUS_REGEX.search(full_name):
        return True
    if PUNCTUATION_REGEX.search(full_name):
        return True
    return False


def build_output_row(row: dict) -> dict:
    """Extract and clean the columns we care about from a raw CSV row."""
    first_name = row.get("First Name", "").strip()
    last_name  = row.get("Last Name",  "").strip()
    return {
        "First Name":           first_name,
        "Last Name":            last_name,
        "Address Line 1":       row.get("Address Line 1",      "").strip(),
        "Address Line 2":       row.get("Address Line 2",      "").strip(),
        "City":                 row.get("City",                "").strip(),
        "State":                row.get("State",               "").strip(),
        "Postal Code":          row.get("Postal Code",         "").strip(),
        "Total Contributions":  row.get("Total Contributions", "").strip(),
        "Primary Phone":        clean_phone(row.get("Primary Phone", "")),
        "Primary Email":        row.get("Primary Email",       "").strip(),
    }

# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def _run(input_path: Path):
    """Run the conversion given a resolved input Path."""
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    output_path = input_path.parent / f"{input_path.stem}_cleaned.csv"
    review_path = input_path.parent / f"{input_path.stem}_manual_review.csv"

    cleaned_rows = []
    review_rows  = []

    print(f"Reading: {input_path}")

    with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        expected_input_cols = {
            "First Name", "Last Name", "Address Line 1", "Address Line 2",
            "City", "State", "Postal Code", "Total Contributions",
            "Primary Phone", "Primary Email",
        }
        missing = expected_input_cols - set(reader.fieldnames or [])
        if missing:
            print("\nWARNING: The following expected input columns were not found and will be blank:")
            for col in sorted(missing):
                print(f"  - {col}")
            print()

        for row in reader:
            output_row = build_output_row(row)
            first_name = output_row["First Name"]
            last_name  = output_row["Last Name"]

            if is_suspicious_name(first_name, last_name):
                review_rows.append(output_row)
                print(f"  REVIEW: {first_name} {last_name}")
            else:
                cleaned_rows.append(output_row)

    # Write cleaned export
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    # Write review export
    with open(review_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"\n{'='*60}")
    print("PROCESSING COMPLETE")
    print('='*60)
    print(f"  Clean records:   {len(cleaned_rows)}")
    print(f"  Review records:  {len(review_rows)}")
    print(f"  Written: {output_path}")
    print(f"  Written: {review_path}")
    print('='*60)
    print()

# ---------------------------------------------------------------------------
# Launcher entry point
# ---------------------------------------------------------------------------

def run(input_file: str):
    """Called by main.py. Accepts the path to the input CSV as a string."""
    _run(Path(input_file))

# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main():
    script_dir = Path(__file__).parent
    _run(script_dir / INPUT_FILE)


if __name__ == "__main__":
    main()