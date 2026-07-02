"""Deterministic mock LinkedIn client for the sales demo.

Implements the same interface as :class:`ProxycurlClient` but returns
canned responses. Three users are pre-scripted to appear at a NEW company
once :meth:`advance_week` is called, so the weekly-check step in the demo
always yields exactly three alerts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .linkedin_client import LookupResult, ProfileResult


@dataclass
class _ScriptedChange:
    from_company: str
    to_company: str
    new_title: str


# Three scripted job changes that fire on `advance_week()`. Keys match names
# in data/factset_users_demo.csv.
SCRIPTED_CHANGES: dict[str, _ScriptedChange] = {
    "Sophie Laurent": _ScriptedChange(
        from_company="Amundi",
        to_company="BNP Paribas Asset Management",
        new_title="Head of ESG Client Solutions",
    ),
    "Marc Dubois": _ScriptedChange(
        from_company="BlackRock France",
        to_company="Carmignac",
        new_title="Senior Portfolio Manager, Global Equities",
    ),
    "Elena Rossi": _ScriptedChange(
        from_company="UBS Wealth Management",
        to_company="Julius Baer",
        new_title="Executive Director, Private Wealth",
    ),
}


TITLE_BY_NAME: dict[str, str] = {
    "Sophie Laurent": "ESG Client Portfolio Manager",
    "Marc Dubois": "Portfolio Manager, Global Equities",
    "Elena Rossi": "Director, Private Wealth",
    "Thomas Bernard": "Senior Quantitative Analyst",
    "Camille Moreau": "Head of Multi-Asset Solutions",
    "Julien Petit": "Investment Banking Associate",
    "Alice Fournier": "Fixed Income Strategist",
    "Nicolas Girard": "VP, Equity Research",
    "Laura Martinez": "Emerging Markets Analyst",
    "Paolo Ricci": "Head of Institutional Sales",
    "Marta Silva": "Wealth Advisor",
    "David Chen": "Head of Passive Solutions APAC",
    "Emma Wagner": "Multi-Asset Portfolio Manager",
    "Lucas Fischer": "ETF Product Specialist",
    "Isabelle Lefevre": "Emerging Markets Fund Manager",
    "Antoine Roux": "Index Product Manager",
    "Chloe Vidal": "Head of ESG Research",
    "Mathieu Blanc": "Head of Private Markets Sales",
    "Sarah Klein": "Senior Fund Manager, Global Bonds",
    "Raphael Costa": "Head of Investment Solutions",
}


@dataclass
class MockProxycurlClient:
    """Drop-in stand-in for :class:`ProxycurlClient` used by the demo."""

    week: int = 1
    _profile_calls: list[str] = field(default_factory=list)
    _lookup_calls: list[tuple[str, str, str]] = field(default_factory=list)

    def advance_week(self) -> None:
        """Move the simulated clock forward so scripted job changes appear."""
        self.week += 1

    def lookup_person(self, first_name: str, last_name: str, company_name: str,
                      company_domain: str | None = None) -> LookupResult:
        self._lookup_calls.append((first_name, last_name, company_name))
        slug = f"{first_name}-{last_name}".lower().replace(" ", "-")
        url = f"https://www.linkedin.com/in/{slug}-factset-demo"
        return LookupResult(linkedin_url=url, confidence=0.97, raw={"mock": True})

    def fetch_profile(self, linkedin_url: str) -> ProfileResult:
        self._profile_calls.append(linkedin_url)
        full_name = _name_from_url(linkedin_url)
        current_company, current_title = self._resolve_current_role(full_name)
        return ProfileResult(
            current_company=current_company,
            current_title=current_title,
            linkedin_url=linkedin_url,
            raw={"mock": True, "week": self.week, "full_name": full_name},
        )

    def _resolve_current_role(self, full_name: str) -> tuple[str | None, str | None]:
        scripted = SCRIPTED_CHANGES.get(full_name)
        if scripted and self.week >= 2:
            return scripted.to_company, scripted.new_title
        if scripted:
            return scripted.from_company, TITLE_BY_NAME.get(full_name)
        return _INITIAL_COMPANY.get(full_name), TITLE_BY_NAME.get(full_name)


def _name_from_url(url: str) -> str:
    slug = url.rsplit("/in/", 1)[-1].removesuffix("-factset-demo")
    return " ".join(part.capitalize() for part in slug.split("-"))


# Populated from the demo CSV so mock stays in sync with fixture data.
_INITIAL_COMPANY: dict[str, str] = {
    "Sophie Laurent": "Amundi",
    "Marc Dubois": "BlackRock France",
    "Elena Rossi": "UBS Wealth Management",
    "Thomas Bernard": "AXA Investment Managers",
    "Camille Moreau": "Lombard Odier",
    "Julien Petit": "Rothschild & Co",
    "Alice Fournier": "BNP Paribas",
    "Nicolas Girard": "Societe Generale",
    "Laura Martinez": "Santander Asset Management",
    "Paolo Ricci": "Intesa Sanpaolo",
    "Marta Silva": "Millennium BCP",
    "David Chen": "HSBC Global Asset Management",
    "Emma Wagner": "Allianz Global Investors",
    "Lucas Fischer": "DWS Group",
    "Isabelle Lefevre": "Carmignac",
    "Antoine Roux": "Lyxor Asset Management",
    "Chloe Vidal": "Edmond de Rothschild AM",
    "Mathieu Blanc": "Natixis Investment Managers",
    "Sarah Klein": "Deutsche Bank Asset Management",
    "Raphael Costa": "Banco BPI",
}
