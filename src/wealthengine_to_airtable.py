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
    new_records.txt  — all newly created records (for manual dupe review)
                       plus any ambiguous matches (flagged with "- Duplicate names")

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

# Field IDs — used when WRITING records to Airtable (create / update calls).
FIELD_IDS: dict[str, str] = {
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

# Field NAMES — used when READING records returned by pyairtable.
# pyairtable returns fields keyed by name (not ID) by default.
FIELD_NAMES: dict[str, str] = {
    "Email":             "Email",
    "Additional Emails": "Additional Emails",
    "Principal First":   "Principal First",
    "Principal Last":    "Principal Last",
}

# ── GLOBALS ───────────────────────────────────────────────────────────────────

# Entries written to new_records.txt at the end of the run.
# Contains two categories:
#   "First Last"                  — brand-new record created; verify no manual dupe exists
#   "First Last - Duplicate names" — multiple existing Airtable records matched; skipped
new_records: list[str] = []

# In-memory index of all existing Airtable records, built once at startup.
# Key: (first_name_lower, last_name_lower)
# Value: list of matching records (list len > 1 means ambiguous)
_airtable_index: dict[tuple[str, str], list[dict]] = {}


# ── HELPERS ───────────────────────────────────────────────────────────────────

def get_table():
    """Return a pyairtable Table instance using the API key from .env."""
    api_key = os.environ.get("AIRTABLE_KEY")
    if not api_key:
        raise EnvironmentError("AIRTABLE_KEY not found in environment / .env file.")
    api = Api(api_key)
    return api.table(BASE_ID, TABLE_ID)


def build_index(table) -> None:
    """
    Fetch all existing Airtable records once and build an in-memory lookup index.

    This replaces per-row API searches, reducing total API calls significantly.
    The index is keyed by (first_name_lower, last_name_lower); values are lists
    of matching records (a list longer than 1 means there are already duplicates).

    Args:
        table: pyairtable Table instance.
    """
    print("Loading existing Airtable records into memory ...")
    all_records = table.all()
    time.sleep(REQUEST_DELAY)

    for record in all_records:
        fields = record.get("fields", {})
        first = fields.get(FIELD_NAMES["Principal First"], "").strip().lower()
        last  = fields.get(FIELD_NAMES["Principal Last"],  "").strip().lower()
        if not first and not last:
            continue
        key = (first, last)
        _airtable_index.setdefault(key, []).append(record)

    print(f"  {len(all_records)} records indexed.")


def _col(row: dict, header: str) -> str:
    """Return a stripped cell value by its CSV header name, or '' if missing."""
    return row.get(header, "").strip()


def _build_fields(row: dict, *, existing_record: dict | None = None) -> dict:
    """
    Build the Airtable fields dict from a CSV row.

    Name, Principal First/Last, and Location are always written (overwrite intended).
    Email fields are only written if currently blank on an existing record.

    Args:
        row:             Parsed CSV row (dict keyed by CSV header name).
        existing_record: The current Airtable record dict, or None for new records.
                         When provided, email fields are only written if blank.

    Returns:
        Dict mapping Airtable field IDs to non-empty values.
    """
    first_name = _col(row, "First Name")
    last_name  = _col(row, "Last Name")
    city       = _col(row, "City")
    state      = _col(row, "State")

    # Compose location string
    location_parts = [p for p in (city, state) if p]
    location = ", ".join(location_parts)

    # ── Email logic ───────────────────────────────────────────────────────────
    # Primary:    Personal email 1
    # Additional: Personal email 2, Personal email 3, Business email 1
    # Duplicates across both buckets are removed.
    new_primary = _col(row, "Personal email 1")

    additional_candidates = [
        _col(row, "Personal email 2"),
        _col(row, "Personal email 3"),
        _col(row, "Business email 1"),
    ]
    # Deduplicate additional emails and exclude the primary if it appears again
    seen: set[str] = {new_primary} if new_primary else set()
    deduped_additional: list[str] = []
    for email in additional_candidates:
        if email and email not in seen:
            deduped_additional.append(email)
            seen.add(email)
    new_additional = ", ".join(deduped_additional)

    if existing_record is not None:
        # Only fill email fields when currently blank in Airtable.
        existing_fields = existing_record.get("fields", {})
        primary_email    = new_primary    if not\
            existing_fields.get(FIELD_NAMES["Email"])             else ""
        additional_email = new_additional if not\
            existing_fields.get(FIELD_NAMES["Additional Emails"]) else ""
    else:
        primary_email    = new_primary
        additional_email = new_additional

    # ── Assemble fields dict ──────────────────────────────────────────────────
    # Note: Principal First/Last and Location intentionally overwrite
    # existing Airtable values — WealthEngine data is treated as authoritative
    # for these fields. Only emails are protected from overwrite.
    fields: dict[str, str | int] = {
        FIELD_IDS["Principal First"]:            first_name,
        FIELD_IDS["Principal Last"]:             last_name,
        FIELD_IDS["Location (city, state)"]:     location,
        FIELD_IDS["Wealth Score"]:               int(_col(row, "WealthScore")),
        FIELD_IDS["P2G Score 1"]:                int(_col(row, "P2G Score (first digit)")),
        FIELD_IDS["P2G Score 2"]:                int(_col(row, "P2G Score (second digit)")),
        FIELD_IDS["Estimated Annual Donations"]: _col(row, "Estimated Annual Donations"),
        FIELD_IDS["Gift Capacity Range"]:        _col(row, "Gift Capacity Range"),
        FIELD_IDS["Charitable Donations"]:       _col(row, "Charitable Donations"),
        FIELD_IDS["Political Donations"]:        _col(row, "Political Donations"),
        FIELD_IDS["Total Donations"]:            _col(row, "Total Donations"),
    }

    # Only include email keys when we have a value to write
    if primary_email:
        fields[FIELD_IDS["Email"]] = primary_email
    if additional_email:
        fields[FIELD_IDS["Additional Emails"]] = additional_email

    # Strip empty strings so we never overwrite existing data with a blank
    return {k: v for k, v in fields.items() if v != ""}


# ── CORE FUNCTIONS ────────────────────────────────────────────────────────────

def find_user(first_name: str, last_name: str) -> dict | None:
    """
    Look up an existing Airtable record from the in-memory index.

    Matching is case-insensitive. Both first AND last name must match.
    If multiple records share the same name, logs the ambiguity and returns
    None — the CSV row will still be processed and a new record created, since
    we cannot safely determine which existing record to update.

    Args:
        first_name: The person's first name.
        last_name:  The person's last name.

    Returns:
        The single matching Airtable record dict, or None if not found / ambiguous.
    """
    key = (first_name.strip().lower(), last_name.strip().lower())
    matches = _airtable_index.get(key, [])

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        # Multiple records already exist in Airtable with this name.
        # Log the ambiguity and return None; process() will create a new record.
        new_records.append(f"{first_name} {last_name} - Duplicate names")

    return None


def write_new(table, row: dict) -> None:
    """
    Create a new record in Airtable from a CSV row and update the local index.

    Args:
        table: pyairtable Table instance.
        row:   Parsed CSV row dict.
    """
    fields = _build_fields(row)
    new_record = table.create(fields)
    time.sleep(REQUEST_DELAY)

    # Keep the index current so later rows in the same file can detect this new entry
    first = _col(row, "First Name").lower()
    last  = _col(row, "Last Name").lower()
    _airtable_index.setdefault((first, last), []).append(new_record)


def update(table, row: dict, record: dict) -> None:
    """
    Update an existing Airtable record with data from a CSV row.
    Email fields are only written when currently blank on the record.
    Skips the API call entirely if there are no fields to change.

    Args:
        table:  pyairtable Table instance.
        row:    Parsed CSV row dict.
        record: The existing Airtable record dict (from find_user).
    """
    fields = _build_fields(row, existing_record=record)
    if fields:
        table.update(record["id"], fields)
        time.sleep(REQUEST_DELAY)


def process(table, row: dict) -> None:
    """
    Process a single CSV row: validate, look up in Airtable, then create or update.

    Skips rows with no name or a WealthEngine "No Match" P2G result.
    Newly created records are logged in new_records.txt for manual review.
    Rows where Airtable already contains multiple matching records are also
    logged (flagged as "- Duplicate names") and a new record is created.

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

    record = find_user(first_name, last_name)

    if record is None:
        write_new(table, row)
        # Log every new record for manual review — new_records.txt may contain
        # both genuinely new contacts and entries created due to ambiguous matches.
        new_records.append(f"{first_name} {last_name}")
    else:
        update(table, row, record)


def write_new_records_file() -> None:
    """
    Write all logged entries to new_records.txt.

    The file contains two kinds of entries:
      "First Last"                   — a new record was created; verify no manual dupe exists
      "First Last - Duplicate names" — multiple Airtable records matched;
       a new one was still created
    """
    with open("new_records.txt", "w", encoding="utf-8") as f:
        f.write("# New records created this run\n")
        f.write("# Lines ending in '- Duplicate names' had multiple existing Airtable matches.\n\n")
        for entry in new_records:
            f.write(entry + "\n")
    print(f"new_records.txt written ({len(new_records)} entries).")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main(input_file: str) -> None:
    """
    Read all rows of the WealthEngine CSV and process each one.

    Loads all existing Airtable records into memory first, then processes
    each CSV row with only create/update API calls (no per-row searches).

    Args:
        input_file: Path to the WealthEngine CSV export.
    """
    table = get_table()
    build_index(table)

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

    write_new_records_file()
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
