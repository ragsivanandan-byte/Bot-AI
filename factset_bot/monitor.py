"""Weekly job-change monitor: detects employer changes AND intra-company role changes."""
from __future__ import annotations

import logging

from .client_directory import ClientDirectory
from .linkedin_client import ProxycurlClient, ProxycurlError
from .normalize import normalize_company
from .storage import CHANGE_TYPE_COMPANY, CHANGE_TYPE_ROLE, Storage, User

log = logging.getLogger(__name__)


def check_all(storage: Storage, client: ProxycurlClient,
              directory: ClientDirectory | None = None,
              limit: int | None = None) -> tuple[int, int, int]:
    """Fetch each matched user's LinkedIn profile and record any change.

    Two change types are detected, weighted equally:
      - company_change: the observed employer differs from the last one.
      - role_change:    same employer, but the job title has changed.

    When a company_change is detected and a ClientDirectory is supplied, the
    new employer is looked up so downstream alerts can flag whether the
    person is joining an existing FactSet client (seat may transfer) or a
    non-client firm (likely churn).

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
            client_record = directory.lookup(new_company) if directory else None
            storage.record_change(
                salesforce_id=user.salesforce_id,
                change_type=CHANGE_TYPE_COMPANY,
                previous_company=user.current_company or user.salesforce_company,
                new_company=new_company,
                previous_title=user.current_title,
                new_title=new_title,
                linkedin_url=user.linkedin_url,
                new_employer_is_client=(client_record is not None) if directory else None,
                new_employer_account_id=client_record.account_id if client_record else None,
            )
            company_changes += 1
            log.info("Company change for %s: %s -> %s (new employer is FactSet client: %s)",
                     user.full_name, user.current_company, new_company,
                     "yes" if client_record else "no" if directory else "unknown")
        elif _is_role_change(user, new_company, new_title):
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

        # Only persist fields we actually observed. An empty LinkedIn response
        # must not erase our previously-known baseline — otherwise the next
        # weekly run would fall back to the Salesforce company and re-fire a
        # phantom "employer change" alert.
        persisted_company = new_company or user.current_company
        persisted_title = new_title or user.current_title
        storage.record_check(user.salesforce_id, persisted_company, persisted_title)
    return checked, company_changes, role_changes


def _is_company_change(user: User, new_company: str | None) -> bool:
    """True when the observed employer differs from the one we last stored."""
    if not new_company:
        return False
    baseline = user.current_company or user.salesforce_company
    return normalize_company(new_company) != normalize_company(baseline)


def _is_role_change(user: User, new_company: str | None, new_title: str | None) -> bool:
    """True when the title has changed at the same known employer.

    Skipped when the previously-stored title is empty (first check) or when
    the observed company is unknown / disagrees with our baseline — a role
    change is only meaningful in the context of a stable known employer.
    """
    if not new_title or not user.current_title or not new_company:
        return False
    baseline_company = user.current_company or user.salesforce_company
    if normalize_company(new_company) != normalize_company(baseline_company):
        return False
    return new_title.strip().casefold() != user.current_title.strip().casefold()
