"""Resolve LinkedIn profiles for Salesforce-sourced users."""
from __future__ import annotations

import logging

from .linkedin_client import ProxycurlClient, ProxycurlError
from .normalize import split_name
from .storage import Storage, User

log = logging.getLogger(__name__)


def match_all_unresolved(storage: Storage, client: ProxycurlClient,
                         limit: int | None = None) -> tuple[int, int]:
    """For every user with no LinkedIn URL yet, ask Proxycurl to resolve one.

    Returns (attempted, matched).
    """
    users = storage.get_unmatched_users()
    if limit is not None:
        users = users[:limit]

    attempted = 0
    matched = 0
    for user in users:
        attempted += 1
        try:
            result = _resolve_one(user, client)
        except ProxycurlError as exc:
            log.error("Lookup failed for %s (%s): %s", user.full_name, user.salesforce_id, exc)
            continue
        if not result:
            log.info("No LinkedIn match for %s at %s", user.full_name, user.salesforce_company)
            continue
        linkedin_url, current_company, current_title, confidence = result
        storage.set_linkedin_match(user.salesforce_id, linkedin_url, current_company,
                                   current_title, confidence)
        matched += 1
    return attempted, matched


def _resolve_one(user: User, client: ProxycurlClient) -> tuple[str, str | None, str | None, float | None] | None:
    first_name, last_name = split_name(user.full_name)
    if not last_name:
        return None
    lookup = client.lookup_person(first_name, last_name, user.salesforce_company)
    if not lookup.linkedin_url:
        return None
    profile = client.fetch_profile(lookup.linkedin_url)
    return lookup.linkedin_url, profile.current_company, profile.current_title, lookup.confidence
