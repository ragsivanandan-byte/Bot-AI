"""Configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Config:
    proxycurl_api_key: str | None
    db_path: Path
    csv_path: Path

    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_from: str | None
    smtp_to: list[str]
    smtp_use_tls: bool

    teams_webhook_url: str | None

    proxycurl_base_url: str
    proxycurl_use_cache: str  # "if-present", "if-recent", or "no-cache"

    @classmethod
    def load(cls) -> "Config":
        return cls(
            proxycurl_api_key=_env("PROXYCURL_API_KEY"),
            db_path=Path(_env("BOT_DB_PATH", "data/state.db")),
            csv_path=Path(_env("SALESFORCE_CSV_PATH", "data/factset_users.csv")),
            smtp_host=_env("SMTP_HOST"),
            smtp_port=int(_env("SMTP_PORT", "587")),
            smtp_user=_env("SMTP_USER"),
            smtp_password=_env("SMTP_PASSWORD"),
            smtp_from=_env("SMTP_FROM"),
            smtp_to=[a.strip() for a in (_env("SMTP_TO", "") or "").split(",") if a.strip()],
            smtp_use_tls=_env("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"),
            teams_webhook_url=_env("TEAMS_WEBHOOK_URL"),
            proxycurl_base_url=_env("PROXYCURL_BASE_URL", "https://nubela.co/proxycurl/api"),
            proxycurl_use_cache=_env("PROXYCURL_USE_CACHE", "if-recent"),
        )
