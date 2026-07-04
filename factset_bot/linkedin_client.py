"""LinkedIn provider abstraction for the FactSet Client Watch bot.

Historical note (as of July 2026)
---------------------------------
The original demo scaffolded this module against the Proxycurl API from
Nubela. LinkedIn sued Nubela in January 2025 for scraping and running
inauthentic accounts; the case settled mid-2025 and Proxycurl officially
shut down on 4 July 2025. Any production implementation now needs to
target one of the compliant successors listed below.

Compliant options for a production deployment (July 2026):

  Purpose-built job-change tracking, Salesforce-native (BUY)
    - Champify           : Salesforce-only, ~$6-12k/year, exactly the
                           job-change alerting workflow this bot models.
    - UserGems           : Salesforce + HubSpot, ~$20-100k/year, adds
                           champion-tracking and AI opportunity forecasts.

  Data-enrichment APIs (BUILD your own bot around them)
    - Coresignal         : 425M+ job records aggregated from company
                           sites and boards; real-time REST API; the
                           closest drop-in for the endpoints this module
                           used to expose against Proxycurl.
    - People Data Labs   : person + company enrichment; monthly refresh
                           on person profiles; jobs API in beta.

  LinkedIn's own products
    - Sales Navigator    : native job-change alerts, but manual export;
                           does not automate cleanly.
    - SNAP API           : Sales Navigator Advanced Plus only, and
                           restricted to approved CRM partners.

Scraping LinkedIn directly is not an option: it violates the LinkedIn
User Agreement and is what killed Proxycurl.

Design of this module
---------------------
`LinkedInProvider` is the small protocol every provider must satisfy:
resolve a person from name + company, then fetch their current company
and title. The mock in :mod:`factset_bot.mock_client` implements it for
the demo. A real production implementation would wrap Coresignal (or
People Data Labs, or the SNAP API if the org qualifies) behind the same
two methods so nothing downstream has to change when the bot flips from
demo to production.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class LinkedInProviderError(RuntimeError):
    """Raised for non-retryable errors from a LinkedIn data provider."""


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


@runtime_checkable
class LinkedInProvider(Protocol):
    """Protocol every LinkedIn data provider must implement.

    Two operations are enough to run this bot:

      - :meth:`lookup_person` resolves a Salesforce contact
        (first name, last name, current employer) to a LinkedIn URL
        with a confidence score.
      - :meth:`fetch_profile` returns the current employer and job title
        for a previously-resolved LinkedIn URL.

    Any concrete provider — Coresignal, People Data Labs, SNAP, or the
    test mock — implements these two methods and everything downstream
    (matcher, monitor, alerts) stays untouched.
    """

    def lookup_person(self, first_name: str, last_name: str, company_name: str,
                      company_domain: str | None = None) -> LookupResult: ...

    def fetch_profile(self, linkedin_url: str) -> ProfileResult: ...
