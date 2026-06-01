"""
seo.py — Opportunités SEO et sélection des demandes confirmées.

Honnêteté : sans accès à un outil de volumes (eRank/Marmalead) ou à Etsy live,
on ne peut PAS donner de vrais volumes de recherche. On combine donc :
  * les piliers/sous-niches déclarés dans config.yaml,
  * les signaux de tendance (Trends, intérêt relatif), quand dispo,
  * une heuristique de "saturation" basée sur la liste saturated_topics.

Chaque opportunité indique son niveau de CONFIRMATION et ses sources. Aucun
volume absolu n'est inventé : on parle d'intérêt relatif ou on marque "à valider".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .trends import TrendResult
from .utils import UNAVAILABLE

logger = logging.getLogger("market_intel")


@dataclass
class SeoOpportunity:
    keyword: str
    confirmation: str          # "confirmée", "partielle", "à valider"
    rationale: str             # pourquoi c'est une opportunité
    sources: list[str] = field(default_factory=list)
    relative_interest: float | None = None
    direction: str = UNAVAILABLE
    saturated: bool = False


def build_opportunities(niche_cfg: dict,
                        trend_results: list[TrendResult]) -> list[SeoOpportunity]:
    """
    Croise piliers + sous-niches montantes + tendances pour produire une liste
    d'opportunités SEO priorisées et honnêtement étiquetées.
    """
    saturated = {s.lower() for s in niche_cfg.get("saturated_topics", [])}
    trend_by_kw = {t.keyword.lower(): t for t in trend_results}

    opportunities: list[SeoOpportunity] = []

    # Sous-niches montantes = priorité haute (moins cannibalisées par hypothèse).
    for kw in niche_cfg.get("emerging_subniches", []):
        opportunities.append(_make_opp(kw, trend_by_kw, saturated,
                                        base_conf="partielle",
                                        why="sous-niche montante déclarée, "
                                            "potentiellement sous-exploitée"))

    # Piliers = socle, souvent plus concurrentiels.
    for kw in niche_cfg.get("pillars", []):
        opportunities.append(_make_opp(kw, trend_by_kw, saturated,
                                        base_conf="à valider",
                                        why="pilier de niche, demande établie "
                                            "mais concurrence probablement élevée"))

    # Tri : confirmées > partielles > à valider, puis intérêt relatif décroissant.
    rank = {"confirmée": 0, "partielle": 1, "à valider": 2}
    opportunities.sort(key=lambda o: (rank.get(o.confirmation, 3),
                                      -(o.relative_interest or 0)))
    return opportunities


def _make_opp(kw: str, trend_by_kw: dict, saturated: set,
              base_conf: str, why: str) -> SeoOpportunity:
    sources = ["config.yaml (déclaratif)"]
    rel = None
    direction = UNAVAILABLE
    conf = base_conf

    # Match tendance par recouvrement de mots (le mot-clé exact rarement présent).
    t = _match_trend(kw, trend_by_kw)
    if t and t.available:
        rel = t.relative_interest
        direction = t.direction
        sources.append(t.source)
        if direction == "montant":
            conf = "confirmée"
            why += " ; intérêt en hausse sur Google Trends"
        elif direction == "stable" and (rel or 0) > 20:
            conf = "partielle" if conf == "à valider" else conf
            why += " ; intérêt stable et non négligeable sur Trends"

    is_sat = any(s in kw.lower() for s in saturated)
    if is_sat:
        conf = "à valider"
        why += " ; ⚠️ proche d'un sujet marqué SATURÉ -> prudence"

    return SeoOpportunity(keyword=kw, confirmation=conf, rationale=why,
                          sources=sources, relative_interest=rel,
                          direction=direction, saturated=is_sat)


def _match_trend(kw: str, trend_by_kw: dict) -> TrendResult | None:
    """Trouve un TrendResult dont le mot-clé recouvre `kw` (best-effort)."""
    kw_l = kw.lower()
    if kw_l in trend_by_kw:
        return trend_by_kw[kw_l]
    kw_words = set(kw_l.split())
    best = None
    best_overlap = 0
    for other, t in trend_by_kw.items():
        overlap = len(kw_words & set(other.split()))
        if overlap > best_overlap:
            best_overlap, best = overlap, t
    return best if best_overlap >= 1 else None
