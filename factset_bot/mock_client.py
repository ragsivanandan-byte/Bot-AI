"""Deterministic mock LinkedIn provider for the sales demo.

Implements the :class:`LinkedInProvider` protocol from
:mod:`factset_bot.linkedin_client` and returns canned responses. Once
:meth:`advance_week` is called, three users appear at a new company and
two get promoted inside their existing company — so the weekly-check
step in the demo always yields exactly five alerts (3 employer changes
+ 2 internal moves) drawn from data/factset_users_demo.csv.

Destination choices are tuned so the client-directory lookup produces a
mixed story: two departures land at FactSet clients (Amundi, Pictet
Wealth Management — seat may transfer) and one lands at a non-client
firm (Portzamparc Gestion — real churn). That contrast is what makes
the "new employer FactSet client?" flag visible during the demo.
"""
from __future__ import annotations

from dataclasses import dataclass

from .linkedin_client import LookupResult, ProfileResult


@dataclass
class _ScriptedChange:
    from_company: str
    to_company: str
    new_title: str


@dataclass
class _ScriptedPromotion:
    company: str
    new_title: str


# Three scripted employer changes that fire on advance_week(). Destinations
# are picked so the client-directory lookup returns a mix: two clients
# (seat may transfer) and one non-client (real churn).
SCRIPTED_CHANGES: dict[str, _ScriptedChange] = {
    # Destination = Amundi, on the roster → seat may transfer.
    "Sophie Laurent": _ScriptedChange(
        from_company="Sanso Investment Solutions",
        to_company="Amundi",
        new_title="Head of ESG Client Solutions",
    ),
    # Destination = Portzamparc Gestion, NOT on the roster → likely churn.
    "Marc Dubois": _ScriptedChange(
        from_company="Sycomore Asset Management",
        to_company="Portzamparc Gestion",
        new_title="Senior Portfolio Manager, Global Equities",
    ),
    # Destination = Pictet Wealth Management, on the roster → seat may transfer.
    "Elena Rossi": _ScriptedChange(
        from_company="Silex",
        to_company="Pictet Wealth Management",
        new_title="Executive Director, Private Wealth",
    ),
}


# Two scripted intra-company promotions — one SMB, one SMB Growth — so the
# demo shows relationship-opportunity signal in both segments.
SCRIPTED_PROMOTIONS: dict[str, _ScriptedPromotion] = {
    "Julien Petit": _ScriptedPromotion(
        company="Meeschaert Amilton AM",
        new_title="Head of Private Markets",
    ),
    "Chloe Vidal": _ScriptedPromotion(
        company="iM Global Partner",
        new_title="Global Head of ESG Strategy",
    ),
}


# Baseline titles paired with the CSV portfolio.
TITLE_BY_NAME: dict[str, str] = {
    "Sophie Laurent": "ESG Client Portfolio Manager",
    "Marc Dubois": "Portfolio Manager, Global Equities",
    "Elena Rossi": "Director, Private Wealth",
    "Thomas Bernard": "Senior Quantitative Analyst",
    "Camille Moreau": "Head of Multi-Asset Solutions",
    "Julien Petit": "Senior Investment Manager",
    "Alice Fournier": "Fixed Income Strategist",
    "Nicolas Girard": "Head of Equity Research",
    "Laura Martinez": "Small & Mid Cap Analyst",
    "Paolo Ricci": "Head of Institutional Sales",
    "Marta Silva": "Wealth Advisor",
    "David Chen": "Head of Portfolio Management",
    "Emma Wagner": "Emerging Markets Portfolio Manager",
    "Lucas Fischer": "Alternative Investments Manager",
    "Isabelle Lefevre": "Head of Client Solutions",
    "Antoine Roux": "Head of Investment Research",
    "Chloe Vidal": "Head of ESG Research",
    "Mathieu Blanc": "Head of Product",
    "Sarah Klein": "Senior Fund Manager, Small Caps",
    "Raphael Costa": "Head of Investment Solutions",
}


@dataclass
class MockLinkedInProvider:
    """Deterministic in-memory :class:`LinkedInProvider` used by the demo."""

    week: int = 1

    def advance_week(self) -> None:
        """Move the simulated clock forward so scripted job changes appear."""
        self.week += 1

    def lookup_person(self, first_name: str, last_name: str, company_name: str,
                      company_domain: str | None = None) -> LookupResult:
        slug = f"{first_name}-{last_name}".lower().replace(" ", "-")
        url = f"https://www.linkedin.com/in/{slug}-factset-demo"
        return LookupResult(linkedin_url=url, confidence=0.97, raw={"mock": True})

    def fetch_profile(self, linkedin_url: str) -> ProfileResult:
        full_name = _name_from_url(linkedin_url)
        current_company, current_title = self._resolve_current_role(full_name)
        return ProfileResult(
            current_company=current_company,
            current_title=current_title,
            linkedin_url=linkedin_url,
            raw={"mock": True, "week": self.week, "full_name": full_name},
        )

    def _resolve_current_role(self, full_name: str) -> tuple[str | None, str | None]:
        change = SCRIPTED_CHANGES.get(full_name)
        if change and self.week >= 2:
            return change.to_company, change.new_title
        if change:
            return change.from_company, TITLE_BY_NAME.get(full_name)
        promo = SCRIPTED_PROMOTIONS.get(full_name)
        if promo and self.week >= 2:
            return promo.company, promo.new_title
        return _INITIAL_COMPANY.get(full_name), TITLE_BY_NAME.get(full_name)


def _name_from_url(url: str) -> str:
    slug = url.rsplit("/in/", 1)[-1].removesuffix("-factset-demo")
    return " ".join(part.capitalize() for part in slug.split("-"))


# Mirror of the CSV company assignments. Must stay in sync with
# data/factset_users_demo.csv — the fetch_profile path relies on it.
_INITIAL_COMPANY: dict[str, str] = {
    "Sophie Laurent": "Sanso Investment Solutions",
    "Marc Dubois": "Sycomore Asset Management",
    "Elena Rossi": "Silex",
    "Thomas Bernard": "Palatine Asset Management",
    "Camille Moreau": "Mansartis",
    "Julien Petit": "Meeschaert Amilton AM",
    "Alice Fournier": "Talence Gestion",
    "Nicolas Girard": "Financiere Tiepolo",
    "Laura Martinez": "Financiere Arbevel",
    "Paolo Ricci": "Ecofi Investissements",
    "Marta Silva": "Pergam Finance",
    "David Chen": "Auris Gestion",
    "Emma Wagner": "Gemway Assets",
    "Lucas Fischer": "Zadig Asset Management",
    "Isabelle Lefevre": "Erasmus Gestion",
    "Antoine Roux": "Twenty First Capital",
    "Chloe Vidal": "iM Global Partner",
    "Mathieu Blanc": "Yomoni",
    "Sarah Klein": "Kirao AM",
    "Raphael Costa": "Nalo",
}
