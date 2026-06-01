"""
trends.py — Signaux de tendance (Google Trends via pytrends, OPTIONNEL).

pytrends est une dépendance optionnelle. Si elle n'est pas installée, ou si
Google Trends est inaccessible (réseau bloqué, rate limit, 429...), ce module
dégrade gracieusement et renvoie des résultats marqués "indisponible".

⚠️ Google Trends donne un INTÉRÊT RELATIF (0-100), PAS un volume de recherche
absolu. On ne convertit jamais ça en "X recherches/mois" : ce serait inventer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .utils import UNAVAILABLE

logger = logging.getLogger("market_intel")


@dataclass
class TrendResult:
    keyword: str
    available: bool
    relative_interest: float | None = None   # moyenne 0-100 sur la période
    direction: str = UNAVAILABLE              # "montant", "stable", "déclin"
    source: str = "Google Trends (intérêt relatif 0-100, PAS un volume)"
    note: str = ""


def _safe_import_pytrends():
    """Importe pytrends si dispo, sinon None (sans planter)."""
    try:
        from pytrends.request import TrendReq  # type: ignore
        return TrendReq
    except Exception as e:  # ImportError ou erreur d'init de dépendance
        logger.info("pytrends indisponible (%s) — module Trends en mode dégradé.",
                    type(e).__name__)
        return None


def fetch_trends(keywords: list[str], timeframe: str = "today 12-m",
                 geo: str = "") -> list[TrendResult]:
    """
    Récupère l'intérêt relatif pour une liste de mots-clés.

    Renvoie toujours une liste (jamais d'exception). Chaque entrée est marquée
    available=False si la donnée n'a pas pu être obtenue.
    """
    if not keywords:
        return []

    TrendReq = _safe_import_pytrends()
    if TrendReq is None:
        return [TrendResult(k, available=False,
                            note="pytrends non installé — voir requirements.txt")
                for k in keywords]

    results: list[TrendResult] = []
    try:
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
        # Google Trends limite à 5 mots-clés par requête.
        for batch_start in range(0, len(keywords), 5):
            batch = keywords[batch_start:batch_start + 5]
            try:
                pytrends.build_payload(batch, timeframe=timeframe, geo=geo)
                df = pytrends.interest_over_time()
            except Exception as e:
                logger.info("Trends indisponible pour %s : %s", batch, e)
                results.extend(TrendResult(k, available=False,
                               note=f"Google Trends inaccessible ({type(e).__name__})")
                               for k in batch)
                continue

            if df is None or df.empty:
                results.extend(TrendResult(k, available=False,
                               note="aucune donnée Trends renvoyée") for k in batch)
                continue

            for k in batch:
                if k not in df.columns:
                    results.append(TrendResult(k, available=False,
                                   note="mot-clé absent de la réponse Trends"))
                    continue
                series = df[k].dropna()
                avg = float(series.mean()) if len(series) else None
                direction = _trend_direction(series.tolist())
                results.append(TrendResult(k, available=True,
                               relative_interest=round(avg, 1) if avg else None,
                               direction=direction))
    except Exception as e:
        logger.warning("Échec global du module Trends : %s", e)
        return [TrendResult(k, available=False,
                            note=f"échec global Trends ({type(e).__name__})")
                for k in keywords]

    return results


def _trend_direction(values: list[float]) -> str:
    """Compare la 2e moitié à la 1re moitié pour déduire une tendance."""
    if len(values) < 4:
        return UNAVAILABLE
    half = len(values) // 2
    first = sum(values[:half]) / half
    second = sum(values[half:]) / (len(values) - half)
    if first == 0:
        return "montant" if second > 0 else "stable"
    change = (second - first) / first
    if change > 0.15:
        return "montant"
    if change < -0.15:
        return "déclin"
    return "stable"
