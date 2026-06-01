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
    search_volume: int | None = None     # volume RÉEL (Keywords Everywhere)
    competition: float | None = None     # 0 (faible) à 1 (forte), si dispo


def build_opportunities(niche_cfg: dict,
                        trend_results: list[TrendResult],
                        volumes: dict | None = None) -> list[SeoOpportunity]:
    """
    Croise piliers + sous-niches montantes + tendances (+ volumes réels si une
    clé Keywords Everywhere est fournie) pour produire une liste d'opportunités
    SEO priorisées et honnêtement étiquetées.

    `volumes` : dict {mot-clé -> KeywordVolume} (optionnel). S'il est présent,
    les volumes RÉELS priment sur l'intérêt relatif pour le classement.
    """
    saturated = {s.lower() for s in niche_cfg.get("saturated_topics", [])}
    trend_by_kw = {t.keyword.lower(): t for t in trend_results}
    volumes = volumes or {}

    opportunities: list[SeoOpportunity] = []

    # Sous-niches montantes = priorité haute (moins cannibalisées par hypothèse).
    for kw in niche_cfg.get("emerging_subniches", []):
        opportunities.append(_make_opp(kw, trend_by_kw, saturated, volumes,
                                        base_conf="partielle",
                                        why="sous-niche montante déclarée, "
                                            "potentiellement sous-exploitée"))

    # Piliers = socle, souvent plus concurrentiels.
    for kw in niche_cfg.get("pillars", []):
        opportunities.append(_make_opp(kw, trend_by_kw, saturated, volumes,
                                        base_conf="à valider",
                                        why="pilier de niche, demande établie "
                                            "mais concurrence probablement élevée"))

    # Tri : confirmées > partielles > à valider, puis volume réel (sinon intérêt
    # relatif) décroissant.
    rank = {"confirmée": 0, "partielle": 1, "à valider": 2}
    opportunities.sort(key=lambda o: (rank.get(o.confirmation, 3),
                                      -(o.search_volume or 0),
                                      -(o.relative_interest or 0)))
    return opportunities


def _make_opp(kw: str, trend_by_kw: dict, saturated: set, volumes: dict,
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

    # Volume RÉEL (Keywords Everywhere) -> donnée la plus forte, prime sur le reste.
    vol = None
    comp = None
    kv = volumes.get(kw)
    if kv is not None and getattr(kv, "volume", None) is not None:
        vol = kv.volume
        comp = kv.competition
        sources.append(kv.source)
        if vol > 0:
            # Volume réel mesuré -> demande confirmée ; bonus si concurrence faible.
            conf = "confirmée"
            low_comp = comp is not None and comp <= 0.35
            why += (f" ; volume de recherche réel = {vol}/mois"
                    + (" avec concurrence FAIBLE (opportunité forte)"
                       if low_comp else ""))

    is_sat = any(s in kw.lower() for s in saturated)
    if is_sat:
        conf = "à valider"
        why += " ; ⚠️ proche d'un sujet marqué SATURÉ -> prudence"

    return SeoOpportunity(keyword=kw, confirmation=conf, rationale=why,
                          sources=sources, relative_interest=rel,
                          direction=direction, saturated=is_sat,
                          search_volume=vol, competition=comp)


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
