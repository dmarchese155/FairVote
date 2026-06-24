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
#   "First Last"                   — brand-new record created; verify no manual dupe exists
#   "First Last - Duplicate names" — multiple existing Airtable records matched; new record still created
new_records: list[str] = []

# In-memory index of all existing Airtable records, built once at startup.
# Key:   last_name_lower (exact)
# Value: list of all records sharing that last name (first name matched via contains)
_airtable_index: dict[str, list[dict]] = {}


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

    The index is keyed by exact lowercase last name. Each key maps to a list of
    all records sharing that last name, which find_user then searches via
    contains-matching on the first name.

    Args:
        table: pyairtable Table instance.
    """
    print("Loading existing Airtable records into memory ...")
    all_records = table.all()
    time.sleep(REQUEST_DELAY)

    for record in all_records:
        fields = record.get("fields", {})
        last = fields.get(FIELD_NAMES["Principal Last"], "").strip().lower()
        if not last:
            continue
        _airtable_index.setdefault(last, []).append(record)

    print(f"  {len(all_records)} records indexed.")


def _col(row: dict, header: str) -> str:
    """Return a stripped cell value by its CSV header name, or '' if missing."""
    return row.get(header, "").strip()


def _build_fields(row: dict, *, existing_record: dict | None = None) -> dict:
    """
    Build the Airtable fields dict from a CSV row.

    Principal First/Last and Location are always written (overwrite intended).
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
        primary_email    = new_primary    if not existing_fields.get(FIELD_NAMES["Email"])             else ""
        additional_email = new_additional if not existing_fields.get(FIELD_NAMES["Additional Emails"]) else ""
    else:
        primary_email    = new_primary
        additional_email = new_additional

    # ── Assemble fields dict ──────────────────────────────────────────────────
    # Note: Principal First/Last and Location intentionally overwrite existing
    # Airtable values — WealthEngine data is treated as authoritative for these
    # fields. Only emails are protected from overwrite.
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

    Last name must match exactly (case-insensitive). Among records sharing that
    last name, the CSV first name must appear somewhere in the Airtable Principal
    First value (case-insensitive contains). This handles joint records such as
    "John and Sarah" / "Smith" matching a CSV row for "John" / "Smith".

    If multiple records satisfy both conditions, logs the ambiguity and returns
    None — main() will create a new record since we cannot safely pick one.

    Args:
        first_name: The person's first name from the CSV.
        last_name:  The person's last name from the CSV.

    Returns:
        The single matching Airtable record dict, or None if not found / ambiguous.
    """
    first_lower = first_name.strip().lower()
    last_lower  = last_name.strip().lower()

    # O(1) last-name key lookup; contains-match only over that subset
    candidates = _airtable_index.get(last_lower, [])
    matches = [
        record for record in candidates
        if first_lower in record["fields"].get(FIELD_NAMES["Principal First"], "").strip().lower()
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        # Multiple records already exist in Airtable with this name.
        # Log the ambiguity and return None; main() will create a new record.
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

    # Keep the index current so later rows in the same CSV can detect this entry
    last = _col(row, "Last Name").lower()
    _airtable_index.setdefault(last, []).append(new_record)


def flush_updates(table, update_queue: list[tuple[str, dict]]) -> None:
    """
    Flush a queue of pending updates to Airtable in batches of 10.

    pyairtable's batch_update sends up to 10 records per API call. If a batch
    fails, each record in it is retried individually so we can identify and log
    the specific failing record without losing the rest of the batch.

    Args:
        table:        pyairtable Table instance.
        update_queue: List of (record_id, fields) pairs to write.
    """
    BATCH_SIZE = 10

    for batch_start in range(0, len(update_queue), BATCH_SIZE):
        batch = update_queue[batch_start : batch_start + BATCH_SIZE]
        # pyairtable batch_update expects a list of dicts with "id" and "fields"
        payload = [{"id": rec_id, "fields": fields} for rec_id, fields in batch]

        try:
            table.batch_update(payload)
            time.sleep(REQUEST_DELAY)
        except Exception as batch_err:
            print(f"  Batch update failed ({batch_err}), retrying individually ...")
            for rec_id, fields in batch:
                try:
                    table.update(rec_id, fields)
                    time.sleep(REQUEST_DELAY)
                except Exception as e:
                    print(f"  ERROR updating record {rec_id}: {e}")


def process(row: dict, update_queue: list[tuple[str, dict]]) -> None:
    """
    Process a single CSV row: validate, look up in Airtable, then queue an
    update or create immediately.

    Skips rows with no name or a WealthEngine "No Match" P2G result.
    Newly created records are logged in new_records.txt for manual review.
    Rows where Airtable already contains multiple matching records are also
    logged (flagged as "- Duplicate names") and a new record is created.

    Args:
        row:          Parsed CSV row dict.
        update_queue: Mutable list; matched rows append (record_id, fields) here
                      for batch flushing by the caller.
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
        # Creates are single-record so the index stays current for later rows
        # in the same file (duplicates within a single import are caught).
        # NOTE: write_new is called directly on the table, not via the queue,
        # because creates are expected to be far less common than updates.
        pass  # handled below to keep the table reference out of process()
    else:
        fields = _build_fields(row, existing_record=record)
        if fields:
            update_queue.append((record["id"], fields))

    # Return the result so main() can call write_new when needed
    return record


def write_new_records_file() -> None:
    """
    Write all logged entries to new_records.txt.

    The file contains two kinds of entries:
      "First Last"                   — a new record was created; verify no manual dupe exists
      "First Last - Duplicate names" — multiple Airtable records matched; a new one was still created
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

    Loads all existing Airtable records into memory first. Updates are queued
    and flushed in batches of 10; creates (less common) are written immediately
    so the local index stays current for duplicate detection within the same file.

    Args:
        input_file: Path to the WealthEngine CSV export.
    """
    table = get_table()
    build_index(table)

    with open(input_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} rows from '{input_file}' ...")

    update_queue: list[tuple[str, dict]] = []

    for i, row in enumerate(rows, start=1):
        try:
            first_name = _col(row, "First Name")
            last_name  = _col(row, "Last Name")

            if not first_name or not last_name:
                continue

            p2g_description = _col(row, "P2G Description")
            if p2g_description == "No Match":
                continue

            record = find_user(first_name, last_name)

            if record is None:
                write_new(table, row)
                new_records.append(f"{first_name} {last_name}")
            else:
                fields = _build_fields(row, existing_record=record)
                if fields:
                    update_queue.append((record["id"], fields))

        except Exception as e:
            first = row.get("First Name", "?").strip()
            last  = row.get("Last Name", "?").strip()
            print(f"  [Row {i}] ERROR for {first} {last}: {e}")

        if i % 10 == 0:
            print(f"  {i}/{len(rows)} processed ...")

    print(f"Flushing {len(update_queue)} updates in batches of 10 ...")
    flush_updates(table, update_queue)

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
