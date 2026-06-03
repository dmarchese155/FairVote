"""
Airtable Donor CSV Converter
Converts from legacy Airtable export format to new CRM format.

Usage:
    python convert_donors.py

All file names are configured in the CONFIG section below.
The output file is always written fresh — never edited.
"""

import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG — edit these lines as needed.
# All files must be in the same folder as this script.
# ---------------------------------------------------------------------------
INPUT_FILE       = "input.csv"        # <-- your Airtable export
OUTPUT_FILE      = "output.csv"       # <-- written fresh every run
DONOR_CHECK_FILE = "donor_check.csv"  # <-- set to None to process all rows
BATCH_SIZE       = None               # <-- e.g. 100 to split into batches, or None

# ---------------------------------------------------------------------------
# Column mappings & lookup tables
# ---------------------------------------------------------------------------

DONOR_MARKET_MAP = {
    "1 - key account - institutional": "Large Institutional",
    "2 - key account - uhni":          "UHNI Individual",
    "3 - individual - $50k+":          "$50k+",
    "4 - mid tier institutional":      "Mid Tier Institutional",
    "5 - individual - $5k-$50k":       "$25k-50k",
    "6 - individual $1k-$5k":          "$5k-25k",
    "partner / ally":                  None,   # flagged
}

STEWARDSHIP_MAP = {
    "1 - identification": "1 - Identification",
    "2 - introduction":   "2 - Introduction",
    "3 - cultivation":    "3 - Cultivation",
    "4 - pitching":       "4 - Pitching",
    "6 - stewardship":    "6 - Stewardship",
}

PRIORITY_MAP = {
    "1 - very high": "1 - Very High",
    "2 - high":      "2 - High",
    "3 - medium":    "3 - Medium",
    "4 - low":       "4 - Low",
}

OUTPUT_COLUMNS = [
    "Name",
    "Donor Type",
    "Donor Market",
    "Stewardship Stage",
    "Priority Level",
    "Relationship Leads",
    "Relationship Support",
    "Principal Name (if institutional)",
    "Email",
    "Location (city, state)",
    "Events",
    "Internal Notes",
    "Additional Contacts",
    "Portfolios",
    "Outreach & Follow-Up Log",
    "Collateral",
]

# ---------------------------------------------------------------------------
# Donor check filter
# ---------------------------------------------------------------------------

def load_unprocessed_names(script_dir: Path) -> set | None:
    """
    Load the donor-check CSV and return a set of names (lowercase) that
    should be processed — those whose 'Donor Check' value is '#N/A'.
    Returns None if DONOR_CHECK_FILE is not set or file doesn't exist
    (all rows processed in that case).
    """
    if not DONOR_CHECK_FILE:
        return None

    check_path = script_dir / DONOR_CHECK_FILE
    if not check_path.exists():
        print(f"WARNING: Donor check file '{DONOR_CHECK_FILE}' not found in {script_dir}.")
        print("         Proceeding without donor filter — all rows will be processed.\n")
        return None

    allowed = set()
    skipped_donors = []

    with open(check_path, newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        # Handle BOM on first header key
        fieldnames = [k.lstrip("\ufeff") for k in (reader.fieldnames or [])]
        reader.fieldnames = fieldnames

        for row in reader:
            name  = row.get("Name", "").strip()
            check = row.get("Donor Check", "").strip()
            if check == "#N/A":
                allowed.add(name.lower())
            else:
                skipped_donors.append(name)

    print(f"Donor check file loaded: {len(allowed)} to process, "
          f"{len(skipped_donors)} already donated (will be skipped).")
    if skipped_donors:
        print("  Skipping existing donors:")
        for name in skipped_donors:
            print(f"    - {name}")
    print()
    return allowed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(value: str) -> str:
    """Strip whitespace and lowercase for safe lookup."""
    return value.strip().lower() if value else ""


def is_individual(institution: str) -> bool:
    """Return True if the institution value indicates an individual donor.
    Handles values like '[individual]', 'individual', or blank."""
    val = normalize(institution).strip("[]")
    return not val or val == "individual"


def map_donor_type(institution: str) -> str:
    return "Individual" if is_individual(institution) else "Institution"


def map_principal_name(institution: str, first: str, last: str) -> str:
    """Blank for individuals; 'First Last' for institutions."""
    if is_individual(institution):
        return ""
    parts = [p.strip() for p in [first, last] if p.strip()]
    return " ".join(parts)


def map_donor_market(raw: str, row_num: int, issues: list) -> str:
    key = normalize(raw)
    if key == "partner / ally":
        issues.append(
            f"  Row {row_num}: Donor Market 'Partner / Ally' has no output equivalent — left blank."
        )
        return ""
    if key in DONOR_MARKET_MAP:
        return DONOR_MARKET_MAP[key]
    if raw.strip():
        issues.append(
            f"  Row {row_num}: Unrecognised Donor Market '{raw.strip()}' — left blank."
        )
    return ""


def map_lookup(raw: str, lookup: dict, field_name: str, row_num: int, issues: list,
               default: str = "") -> str:
    key = normalize(raw)
    if key in lookup:
        return lookup[key]
    if raw.strip():
        issues.append(
            f"  Row {row_num}: Unrecognised {field_name} '{raw.strip()}' — copied as-is."
        )
        return raw.strip()
    return default  # return default when value is blank

# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def convert_row(row: dict, row_num: int, issues: list) -> dict:
    institution = row.get("Institution", "")

    donor_type   = map_donor_type(institution)
    donor_market = map_donor_market(row.get("Donor Market", ""), row_num, issues)

    # Default stewardship to 1 - Identification when blank
    stewardship  = map_lookup(row.get("Stewardship Stage", ""), STEWARDSHIP_MAP,
                              "Stewardship Stage", row_num, issues,
                              default="1 - Identification")

    priority     = map_lookup(row.get("Priority Level", ""), PRIORITY_MAP,
                              "Priority Level", row_num, issues)

    return {
        "Name":                              row.get("Name", "").strip(),
        "Donor Type":                        donor_type,
        "Donor Market":                      donor_market,
        "Stewardship Stage":                 stewardship,
        "Priority Level":                    priority,
        "Relationship Leads":                row.get("Relationship Lead", "").strip(),
        "Relationship Support":              row.get("Relationship Support", "").strip(),
        "Principal Name (if institutional)": map_principal_name(
                                                institution,
                                                row.get("Principal First", ""),
                                                row.get("Principal Last", ""),
                                             ),
        "Email":                             row.get("Email", "").strip(),
        "Location (city, state)":            row.get("Location (city, state)", "").strip(),
        "Events":                            "",
        "Internal Notes":                    "",
        "Additional Contacts":               row.get("Additional contacts", "").strip(),
        "Portfolios":                        "",
        "Outreach & Follow-Up Log":          "",
        "Collateral":                        "",
    }


def write_output(rows: list, output_path: Path):
    """Always write a fresh output file, splitting into batches if configured."""
    if BATCH_SIZE is None:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  Written: {output_path}  ({len(rows)} rows)")
    else:
        stem   = output_path.stem
        suffix = output_path.suffix
        parent = output_path.parent
        for idx, start in enumerate(range(0, len(rows), BATCH_SIZE)):
            batch = rows[start:start + BATCH_SIZE]
            path  = parent / f"{stem}_{idx + 1}{suffix}"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
                writer.writeheader()
                writer.writerows(batch)
            print(f"  Written: {path}  ({len(batch)} rows)")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    script_dir  = Path(__file__).parent
    input_path  = script_dir / INPUT_FILE
    output_path = script_dir / OUTPUT_FILE

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    unprocessed = load_unprocessed_names(script_dir)

    output_rows = []
    all_issues  = []
    skipped     = 0
    filtered    = 0

    print(f"Reading: {input_path}")

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # BOM already stripped by utf-8-sig encoding

        expected_input_cols = {
            "Name", "Donor Status", "Donor Market", "Stewardship Stage",
            "Priority Level", "Relationship Lead", "Relationship Support",
            "Principal First", "Principal Last", "Institution",
            "Email", "Location (city, state)", "Additional contacts",
        }
        missing = expected_input_cols - set(reader.fieldnames or [])
        if missing:
            print("\nWARNING: The following expected input columns were not found and will be blank:")
            for col in sorted(missing):
                print(f"  - {col}")

        for row_num, row in enumerate(reader, start=2):
            try:
                name = row.get("Name", "").strip()

                if unprocessed is not None and name.lower() not in unprocessed:
                    filtered += 1
                    continue

                output_rows.append(convert_row(row, row_num, all_issues))
            except Exception as exc:
                skipped += 1
                all_issues.append(
                    f"  Row {row_num}: UNEXPECTED ERROR — {exc}. Row skipped entirely."
                )

    if all_issues:
        print(f"\n{'='*60}")
        print("ROWS REQUIRING MANUAL REVIEW:")
        print('='*60)
        for issue in all_issues:
            print(issue)
        print('='*60)
    else:
        print("\nNo mapping issues found.")

    print(f"\nWriting {len(output_rows)} rows "
          f"({filtered} filtered as existing donors, {skipped} skipped due to errors)...")
    write_output(output_rows, output_path)
    print("\nDone.\n")


if __name__ == "__main__":
    main()