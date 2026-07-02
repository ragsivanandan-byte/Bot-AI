"""Weekly job-change monitor: fetches each matched user's current LinkedIn company."""
from __future__ import annotations

import logging

from .linkedin_client import ProxycurlClient, ProxycurlError
from .normalize import normalize_company
from .storage import Storage, User

log = logging.getLogger(__name__)


def check_all(storage: Storage, client: ProxycurlClient,
              limit: int | None = None) -> tuple[int, int]:
    """Fetch each matched user's LinkedIn profile and record any employer change.

    A change is recorded when the newly-observed company differs from the
    company we last stored for them. Returns (checked, changes_detected).
    """
    users = storage.get_matched_users()
    if limit is not None:
        users = users[:limit]

    checked = 0
    changes = 0
    for user in users:
        assert user.linkedin_url is not None
        checked += 1
        try:
            profile = client.fetch_profile(user.linkedin_url)
        except ProxycurlError as exc:
            log.error("Profile fetch failed for %s: %s", user.full_name, exc)
            continue

        new_company = profile.current_company
        new_title = profile.current_title

        if _is_employer_change(user, new_company):
            storage.record_change(
                salesforce_id=user.salesforce_id,
                previous_company=user.current_company,
                new_company=new_company,
                new_title=new_title,
                linkedin_url=user.linkedin_url,
            )
            changes += 1
            log.info("Employer change detected for %s: %s -> %s",
                     user.full_name, user.current_company, new_company)

        storage.record_check(user.salesforce_id, new_company, new_title)
    return checked, changes


def _is_employer_change(user: User, new_company: str | None) -> bool:
    """True when the newly-observed company differs from the one we last stored.

    We deliberately compare against the *last observed* company (`current_company`)
    rather than the Salesforce-declared company, so that a change is only flagged
    once — the week it happens — and stays stable afterwards.
    """
    if not new_company:
        return False
    baseline = user.current_company or user.salesforce_company
    return normalize_company(new_company) != normalize_company(baseline)
