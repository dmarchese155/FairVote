"""
Wealthengine → Airtable CSV Converter
Uploads a WealthEngine export into the Airtable development base.

Usage (via launcher):
    Open main.py, select this script, and choose your input file.

Usage (command line):
    python wealthengine_to_airtable.py
    python wealthengine_to_airtable.py path/to/file.csv

The input file is configured via argument or prompted at runtime.
One output file is written:
    potential_duplicates.txt

See the examples/ folder for properly formatted input/output examples.
"""

import csv
import os
import sys
import time

from dotenv import load_dotenv
from pyairtable import Api

load_dotenv()

# ── CONFIG ────────────────────────────────────────────────────────────────────

BASE_ID  = "appfCqEQOmGlRhg9j"
TABLE_ID = "tbl6wdKck5JUnD832"

# Delay between Airtable API calls (seconds). Airtable allows 5 req/s;
# 0.25 s gives comfortable headroom.
REQUEST_DELAY = 0.25

# Field IDs for every column we write in Airtable.
FIELD_IDS: dict[str, str] = {
    "Name":                       "fldJDAn24IkdBz602",
    "Principal First":            "fldxtrz1GfFLPSECr",
    "Principal Last":             "fld3imK3izgq6GSJT",
    "Email":                      "fldou36sB8VLuUgVh",
    "Additional Emails":          "flduqGJb81A9QTbNa",
    "Location (city, state)":     "flduYaaFGuXgLq9Cz",
    "Wealth Score":               "fldwunFpf8SaxP165",
    "P2G Score 1":                "fld7tPfJZBguRW5Dx",
    "P2G Score 2":                "fld29iDtSMHNx3MG2",
    "Estimated Annual Donations": "fldrBXNxYicGWooPT",
    "Gift Capacity Range":        "fld1aR6CN5f3RUgKn",
    "Charitable Donations":       "fld2mhgTzxlaWfT2V",
    "Political Donations":        "fld0Gyn9rBGJl7EWT",
    "Total Donations":            "fldTAH9tb5tlorobz",
}

# ── GLOBALS ───────────────────────────────────────────────────────────────────

potential_dupes: list[str] = []   # entries written to potential_duplicates.txt


# ── HELPERS ───────────────────────────────────────────────────────────────────

def get_table():
    """Return a pyairtable Table instance using the API key from .env."""
    api_key = os.environ.get("AIRTABLE_KEY")
    if not api_key:
        raise EnvironmentError("AIRTABLE_KEY not found in environment / .env file.")
    api = Api(api_key)
    return api.table(BASE_ID, TABLE_ID)


def _col(row: dict, header: str) -> str:
    """Return a stripped cell value by its CSV header name, or '' if missing."""
    return row.get(header, "").strip()


def _build_fields(row: dict, *, existing_record: dict | None = None) -> dict:
    """
    Build the Airtable fields dict from a CSV row.

    Args:
        row:             Parsed CSV row (dict keyed by header name).
        existing_record: The current Airtable record dict, or None for new records.
                         When provided, email fields are only written if currently blank.

    Returns:
        Dict mapping Airtable field IDs to values.
    """
    first_name = _col(row, "First Name")
    last_name  = _col(row, "Last Name")
    city       = _col(row, "City")
    state      = _col(row, "State")

    # Compose location string
    location_parts = [p for p in (city, state) if p]
    location = ", ".join(location_parts)

    # Compose full name
    name = f"{first_name} {last_name}".strip()

    # ── Email logic ───────────────────────────────────────────────────────────
    # Primary email: Personal email 1
    # Additional emails: Personal email 2, Personal email 3, Business email 1
    primary_email_candidates = [_col(row, "Personal email 1")]
    additional_email_candidates = [
        _col(row, "Personal email 2"),
        _col(row, "Personal email 3"),
        _col(row, "Business email 1"),
    ]

    new_primary    = next((e for e in primary_email_candidates if e), "")
    new_additional = ", ".join(e for e in additional_email_candidates if e)

    if existing_record is not None:
        # Only fill email fields when they are currently blank in Airtable
        existing_fields = existing_record.get("fields", {})
        primary_email    = new_primary    if not existing_fields.get(FIELD_IDS["Email"])              else ""
        additional_email = new_additional if not existing_fields.get(FIELD_IDS["Additional Emails"]) else ""
    else:
        primary_email    = new_primary
        additional_email = new_additional

    # ── Assemble fields dict ──────────────────────────────────────────────────
    fields: dict[str, str] = {
        FIELD_IDS["Name"]:                       name,
        FIELD_IDS["Principal First"]:            first_name,
        FIELD_IDS["Principal Last"]:             last_name,
        FIELD_IDS["Location (city, state)"]:     location,
        FIELD_IDS["Wealth Score"]:               _col(row, "WealthScore"),
        FIELD_IDS["P2G Score 1"]:                _col(row, "P2G Score (first digit)"),
        FIELD_IDS["P2G Score 2"]:                _col(row, "P2G Score (second digit)"),
        FIELD_IDS["Estimated Annual Donations"]: _col(row, "Estimated Annual Donations"),
        FIELD_IDS["Gift Capacity Range"]:        _col(row, "Gift Capacity Range"),
        FIELD_IDS["Charitable Donations"]:       _col(row, "Charitable Donations"),
        FIELD_IDS["Political Donations"]:        _col(row, "Political Donations"),
        FIELD_IDS["Total Donations"]:            _col(row, "Total Donations"),
    }

    # Only include email keys when we actually have a value to write
    if primary_email:
        fields[FIELD_IDS["Email"]] = primary_email
    if additional_email:
        fields[FIELD_IDS["Additional Emails"]] = additional_email

    # Drop any fields that ended up as empty strings to avoid overwriting
    # existing Airtable data with blanks on updates.
    fields = {k: v for k, v in fields.items() if v != ""}

    return fields


# ── CORE FUNCTIONS ────────────────────────────────────────────────────────────

def find_user(table, first_name: str, last_name: str) -> dict | None:
    """
    Attempt to find a single Airtable record matching first and last name.

    Matching is case-insensitive and ignores leading/trailing whitespace.
    Both first AND last name must match. If zero or multiple records match,
    returns None (multiple matches are also flagged in the duplicate log).

    Args:
        table:      pyairtable Table instance.
        first_name: The person's first name.
        last_name:  The person's last name.

    Returns:
        The matching Airtable record dict, or None if not found / ambiguous.
    """
    first_lower = first_name.lower()
    last_lower  = last_name.lower()

    # Use Airtable formula to pre-filter by last name (reduces data transferred)
    formula = f"LOWER({{Principal Last}}) = '{last_lower}'"
    candidates = table.all(formula=formula)
    time.sleep(REQUEST_DELAY)

    matches = [
        r for r in candidates
        if r["fields"].get(FIELD_IDS["Principal First"], "").strip().lower() == first_lower
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        # Multiple Airtable records already exist — flag it but don't touch either
        potential_dupes.append(f"{first_name} {last_name} - Duplicate names")

    return None


def write_new(table, row: dict) -> None:
    """
    Create a new record in Airtable from a CSV row.

    Args:
        table: pyairtable Table instance.
        row:   Parsed CSV row dict.
    """
    fields = _build_fields(row)
    table.create(fields)
    time.sleep(REQUEST_DELAY)


def update(table, row: dict, record: dict) -> None:
    """
    Update an existing Airtable record with data from a CSV row.
    Email fields are only written when currently blank on the record.

    Args:
        table:  pyairtable Table instance.
        row:    Parsed CSV row dict.
        record: The existing Airtable record dict (from find_user).
    """
    fields = _build_fields(row, existing_record=record)
    table.update(record["id"], fields)
    time.sleep(REQUEST_DELAY)


def process(table, row: dict) -> None:
    """
    Process a single CSV row: validate, look up in Airtable, then create or update.

    Skips rows with no name or a WealthEngine "No Match" result.
    New records (no existing Airtable entry) are flagged in potential_duplicates.txt
    for manual review.

    Args:
        table: pyairtable Table instance.
        row:   Parsed CSV row dict.
    """
    first_name: str = _col(row, "First Name")
    last_name: str  = _col(row, "Last Name")

    if not first_name or not last_name:
        return

    p2g_description: str = _col(row, "P2G Description")
    if p2g_description == "No Match":
        return

    record = find_user(table, first_name, last_name)

    if record is None:
        write_new(table, row)
        potential_dupes.append(f"{first_name} {last_name}")
    else:
        update(table, row, record)


def write_duplicates_file() -> None:
    """Write all entries in potential_dupes to potential_duplicates.txt."""
    with open("potential_duplicates.txt", "w", encoding="utf-8") as f:
        for entry in potential_dupes:
            f.write(entry + "\n")
    print(f"potential_duplicates.txt written ({len(potential_dupes)} entries).")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main(input_file: str) -> None:
    """
    Read all rows of the WealthEngine CSV and process each one.

    Args:
        input_file: Path to the WealthEngine CSV export.
    """
    table = get_table()

    with open(input_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} rows from '{input_file}' ...")

    for i, row in enumerate(rows, start=1):
        try:
            process(table, row)
        except Exception as e:
            first = row.get("First Name", "?").strip()
            last  = row.get("Last Name", "?").strip()
            print(f"  [Row {i}] ERROR for {first} {last}: {e}")

        if i % 10 == 0:
            print(f"  {i}/{len(rows)} processed ...")

    write_duplicates_file()
    print("Done.")


if __name__ == "__main__":
    # Supports both launcher calls (main.py passes a path) and direct CLI usage.
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = input("Enter path to WealthEngine CSV file: ").strip()

    if not os.path.isfile(input_path):
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    main(input_path)