"""Ingest FactSet-user CSV exports from Salesforce into the state store."""
from __future__ import annotations

import csv
from pathlib import Path

from .storage import Storage


REQUIRED_COLUMNS = {"salesforce_id", "full_name", "company"}
OPTIONAL_COLUMNS = {"email"}


def _normalize_headers(headers: list[str]) -> dict[str, str]:
    """Map common Salesforce export column names to our canonical schema."""
    mapping = {}
    for raw in headers:
        key = raw.strip().lower().replace(" ", "_")
        if key in ("id", "user_id", "contact_id", "sfdc_id"):
            mapping[raw] = "salesforce_id"
        elif key in ("name", "contact_name", "user_name"):
            mapping[raw] = "full_name"
        elif key in ("account", "account_name", "account_company", "organization"):
            mapping[raw] = "company"
        elif key in ("email_address",):
            mapping[raw] = "email"
        else:
            mapping[raw] = key
    return mapping


def load_csv(csv_path: Path, storage: Storage) -> tuple[int, int]:
    """Read CSV, upsert every row; return (rows_seen, rows_ingested)."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Salesforce CSV not found at {csv_path}")

    seen = 0
    ingested = 0
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row")
        header_map = _normalize_headers(reader.fieldnames)
        canonical = set(header_map.values())
        missing = REQUIRED_COLUMNS - canonical
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing)}. "
                f"Found columns: {reader.fieldnames}"
            )

        for row in reader:
            seen += 1
            canonical_row = {header_map[k]: (v or "").strip() for k, v in row.items()}
            sf_id = canonical_row.get("salesforce_id", "")
            name = canonical_row.get("full_name", "")
            company = canonical_row.get("company", "")
            email = canonical_row.get("email") or None
            if not sf_id or not name or not company:
                continue
            storage.upsert_user_from_csv(sf_id, name, email, company)
            ingested += 1
    return seen, ingested
