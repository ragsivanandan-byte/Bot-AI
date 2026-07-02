"""SQLite persistence for tracked users and detected job changes."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    salesforce_id      TEXT PRIMARY KEY,
    full_name          TEXT NOT NULL,
    email              TEXT,
    salesforce_company TEXT NOT NULL,
    linkedin_url       TEXT,
    current_company    TEXT,
    current_title      TEXT,
    match_confidence   REAL,
    last_matched_at    TEXT,
    last_checked_at    TEXT
);

CREATE TABLE IF NOT EXISTS changes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    salesforce_id      TEXT NOT NULL,
    detected_at        TEXT NOT NULL,
    change_type        TEXT NOT NULL DEFAULT 'company_change',
    previous_company   TEXT,
    new_company        TEXT,
    previous_title     TEXT,
    new_title          TEXT,
    linkedin_url       TEXT,
    notified           INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(salesforce_id) REFERENCES users(salesforce_id)
);

CREATE INDEX IF NOT EXISTS idx_changes_notified ON changes(notified);
CREATE INDEX IF NOT EXISTS idx_users_linkedin ON users(linkedin_url);
"""


@dataclass
class User:
    salesforce_id: str
    full_name: str
    email: str | None
    salesforce_company: str
    linkedin_url: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    match_confidence: float | None = None
    last_matched_at: str | None = None
    last_checked_at: str | None = None


CHANGE_TYPE_COMPANY = "company_change"
CHANGE_TYPE_ROLE = "role_change"


@dataclass
class Change:
    salesforce_id: str
    full_name: str
    detected_at: str
    change_type: str
    previous_company: str | None
    new_company: str | None
    previous_title: str | None
    new_title: str | None
    linkedin_url: str | None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_user_from_csv(self, salesforce_id: str, full_name: str, email: str | None,
                             salesforce_company: str) -> None:
        """Insert a Salesforce-sourced user, preserving any prior LinkedIn match."""
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO users (salesforce_id, full_name, email, salesforce_company)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(salesforce_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    email = excluded.email,
                    salesforce_company = excluded.salesforce_company
                """,
                (salesforce_id, full_name, email, salesforce_company),
            )

    def set_linkedin_match(self, salesforce_id: str, linkedin_url: str | None,
                           current_company: str | None, current_title: str | None,
                           confidence: float | None) -> None:
        with self._conn() as c:
            c.execute(
                """
                UPDATE users
                SET linkedin_url = ?, current_company = ?, current_title = ?,
                    match_confidence = ?, last_matched_at = ?
                WHERE salesforce_id = ?
                """,
                (linkedin_url, current_company, current_title, confidence, now_iso(), salesforce_id),
            )

    def record_check(self, salesforce_id: str, current_company: str | None,
                     current_title: str | None) -> None:
        with self._conn() as c:
            c.execute(
                """
                UPDATE users
                SET current_company = ?, current_title = ?, last_checked_at = ?
                WHERE salesforce_id = ?
                """,
                (current_company, current_title, now_iso(), salesforce_id),
            )

    def record_change(self, salesforce_id: str, change_type: str,
                      previous_company: str | None, new_company: str | None,
                      previous_title: str | None, new_title: str | None,
                      linkedin_url: str | None) -> int:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO changes (salesforce_id, detected_at, change_type,
                                     previous_company, new_company,
                                     previous_title, new_title, linkedin_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (salesforce_id, now_iso(), change_type,
                 previous_company, new_company, previous_title, new_title, linkedin_url),
            )
            return cur.lastrowid

    def get_all_users(self) -> list[User]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM users ORDER BY full_name").fetchall()
            return [User(**dict(r)) for r in rows]

    def get_unmatched_users(self) -> list[User]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM users WHERE linkedin_url IS NULL ORDER BY full_name"
            ).fetchall()
            return [User(**dict(r)) for r in rows]

    def get_matched_users(self) -> list[User]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM users WHERE linkedin_url IS NOT NULL ORDER BY full_name"
            ).fetchall()
            return [User(**dict(r)) for r in rows]

    def get_pending_changes(self) -> list[Change]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT ch.salesforce_id, u.full_name, ch.detected_at, ch.change_type,
                       ch.previous_company, ch.new_company,
                       ch.previous_title, ch.new_title, ch.linkedin_url
                FROM changes ch
                JOIN users u ON u.salesforce_id = ch.salesforce_id
                WHERE ch.notified = 0
                ORDER BY
                  CASE ch.change_type WHEN 'company_change' THEN 0 ELSE 1 END,
                  ch.detected_at DESC
                """
            ).fetchall()
            return [Change(**dict(r)) for r in rows]

    def mark_all_pending_notified(self) -> int:
        """Mark every currently-pending change as notified. Returns row count."""
        with self._conn() as c:
            cur = c.execute("UPDATE changes SET notified = 1 WHERE notified = 0")
            return cur.rowcount
