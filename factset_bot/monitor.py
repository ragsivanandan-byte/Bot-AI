"""Weekly job-change monitor: detects employer changes AND intra-company role changes."""
from __future__ import annotations

import logging

from .linkedin_client import ProxycurlClient, ProxycurlError
from .normalize import normalize_company
from .storage import CHANGE_TYPE_COMPANY, CHANGE_TYPE_ROLE, Storage, User

log = logging.getLogger(__name__)


def check_all(storage: Storage, client: ProxycurlClient,
              limit: int | None = None) -> tuple[int, int, int]:
    """Fetch each matched user's LinkedIn profile and record any change.

    Two change types are detected, in order of priority:
      1. company_change - the observed employer differs from the last one.
      2. role_change    - same employer, but the job title has changed.

    Returns (checked, company_changes, role_changes).
    """
    users = storage.get_matched_users()
    if limit is not None:
        users = users[:limit]

    checked = 0
    company_changes = 0
    role_changes = 0
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

        if _is_company_change(user, new_company):
            storage.record_change(
                salesforce_id=user.salesforce_id,
                change_type=CHANGE_TYPE_COMPANY,
                previous_company=user.current_company or user.salesforce_company,
                new_company=new_company,
                previous_title=user.current_title,
                new_title=new_title,
                linkedin_url=user.linkedin_url,
            )
            company_changes += 1
            log.info("Company change for %s: %s -> %s",
                     user.full_name, user.current_company, new_company)
        elif _is_role_change(user, new_title):
            storage.record_change(
                salesforce_id=user.salesforce_id,
                change_type=CHANGE_TYPE_ROLE,
                previous_company=user.current_company,
                new_company=new_company,
                previous_title=user.current_title,
                new_title=new_title,
                linkedin_url=user.linkedin_url,
            )
            role_changes += 1
            log.info("Role change for %s @ %s: %s -> %s",
                     user.full_name, new_company, user.current_title, new_title)

        storage.record_check(user.salesforce_id, new_company, new_title)
    return checked, company_changes, role_changes


def _is_company_change(user: User, new_company: str | None) -> bool:
    """True when the observed employer differs from the one we last stored."""
    if not new_company:
        return False
    baseline = user.current_company or user.salesforce_company
    return normalize_company(new_company) != normalize_company(baseline)


def _is_role_change(user: User, new_title: str | None) -> bool:
    """True when title differs from the last stored title (same employer implied by caller).

    Skipped on the very first check when we have no baseline title to compare
    against, so we do not flood the sales manager with 'new title detected'
    for every user the first week the bot runs.
    """
    if not new_title or not user.current_title:
        return False
    return new_title.strip().casefold() != user.current_title.strip().casefold()
