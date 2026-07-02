"""Lookup: is a given company an existing FactSet client?

In production this is a Salesforce query on the Account object
(WHERE Type = 'Customer' AND Product__c INCLUDES 'FactSet'). In demo mode
we load a CSV roster and use the same company normalization the monitor
uses so vendor-side spelling drift ("Amundi" vs "Amundi Asset Management")
does not miss a match.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .normalize import normalize_company


@dataclass(frozen=True)
class ClientRecord:
    company_name: str
    account_id: str
    region: str | None


class ClientDirectory:
    """In-memory index of FactSet-client companies, keyed by normalized name."""

    def __init__(self, records: dict[str, ClientRecord]):
        self._records = records

    @classmethod
    def from_csv(cls, csv_path: Path) -> "ClientDirectory":
        if not csv_path.exists():
            raise FileNotFoundError(f"Client roster not found at {csv_path}")
        records: dict[str, ClientRecord] = {}
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("company_name") or "").strip()
                if not name:
                    continue
                key = normalize_company(name)
                if not key:
                    continue
                records[key] = ClientRecord(
                    company_name=name,
                    account_id=(row.get("account_id") or "").strip(),
                    region=(row.get("region") or "").strip() or None,
                )
        return cls(records)

    def lookup(self, company_name: str | None) -> ClientRecord | None:
        """Return the matching client record, or None if the company is not on the roster."""
        if not company_name:
            return None
        return self._records.get(normalize_company(company_name))

    def __len__(self) -> int:
        return len(self._records)
