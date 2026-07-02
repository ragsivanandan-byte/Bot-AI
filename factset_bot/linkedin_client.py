"""Thin wrapper around the Proxycurl API for LinkedIn identity and profile lookups."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import requests

log = logging.getLogger(__name__)


class ProxycurlError(RuntimeError):
    """Raised for non-retryable Proxycurl API failures."""


@dataclass
class LookupResult:
    linkedin_url: str | None
    confidence: float | None
    raw: dict[str, Any]


@dataclass
class ProfileResult:
    current_company: str | None
    current_title: str | None
    linkedin_url: str | None
    raw: dict[str, Any]


class ProxycurlClient:
    def __init__(self, api_key: str, base_url: str = "https://nubela.co/proxycurl/api",
                 use_cache: str = "if-recent", timeout: int = 30,
                 max_retries: int = 4, session: "requests.Session | None" = None):
        import requests  # lazy so demo mode does not require the package
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.use_cache = use_cache
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        backoff = 2.0
        for attempt in range(1, self.max_retries + 1):
            resp = self.session.get(url, headers=self._headers(), params=params,
                                    timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                log.warning("Proxycurl %s -> HTTP %s (attempt %d/%d)",
                            path, resp.status_code, attempt, self.max_retries)
                if attempt == self.max_retries:
                    break
                time.sleep(backoff)
                backoff *= 2
                continue
            if resp.status_code == 404:
                return {}
            raise ProxycurlError(
                f"Proxycurl {path} failed HTTP {resp.status_code}: {resp.text[:200]}"
            )
        raise ProxycurlError(f"Proxycurl {path} exhausted retries")

    def lookup_person(self, first_name: str, last_name: str, company_name: str,
                      company_domain: str | None = None) -> LookupResult:
        """Resolve a LinkedIn profile URL from name + company."""
        params: dict[str, Any] = {
            "first_name": first_name,
            "last_name": last_name,
            "company_domain": company_domain or "",
            "enrich_profile": "skip",
        }
        if not company_domain:
            params["title"] = ""
            params["location"] = ""
            params["similarity_checks"] = "include"
            params["company_name"] = company_name
        data = self._get("/linkedin/profile/resolve", params)
        url = data.get("url") if isinstance(data, dict) else None
        confidence = None
        if isinstance(data, dict):
            confidence = data.get("similarity_score") or data.get("name_similarity_score")
        return LookupResult(linkedin_url=url, confidence=confidence, raw=data or {})

    def fetch_profile(self, linkedin_url: str) -> ProfileResult:
        """Retrieve the current profile snapshot for a LinkedIn URL."""
        data = self._get(
            "/v2/linkedin",
            {"url": linkedin_url, "use_cache": self.use_cache, "fallback_to_cache": "on-error"},
        )
        return _parse_profile(data, linkedin_url)


def _parse_profile(data: dict[str, Any], linkedin_url: str) -> ProfileResult:
    experiences = data.get("experiences") or [] if isinstance(data, dict) else []
    current = _pick_current_experience(experiences)
    company = None
    title = None
    if current:
        company = current.get("company")
        title = current.get("title")
    return ProfileResult(current_company=company, current_title=title,
                         linkedin_url=linkedin_url, raw=data or {})


def _pick_current_experience(experiences: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the experience that best represents 'where they work now'.

    Proxycurl orders experiences newest-first. An `ends_at` of None means the
    role is still current. If multiple are current we take the one with the
    latest `starts_at`; if none is marked current we fall back to the first.
    """
    if not experiences:
        return None
    current = [e for e in experiences if e.get("ends_at") in (None, {})]
    pool = current or experiences
    return max(pool, key=lambda e: _year(e.get("starts_at")), default=pool[0])


def _year(date_dict: Any) -> int:
    if isinstance(date_dict, dict):
        return int(date_dict.get("year") or 0)
    return 0
