"""
keywords_api.py — Connecteur Keywords Everywhere (volumes de recherche réels).

Keywords Everywhere est l'un des rares outils de volumes de mots-clés à exposer
une API documentée et bon marché (système de crédits, paiement à l'usage). Il
fournit, par mot-clé : volume de recherche mensuel, CPC, et un indice de
concurrence (0-1). Ces volumes sont d'origine Google (un PROXY de l'intention
d'achat sur Etsy, pas le volume Etsy exact — voir LIMITS.md).

Clé lue depuis la variable d'environnement  KEYWORDS_EVERYWHERE_API_KEY.
Sans clé, le module est INACTIF (available=False) -> l'outil retombe sur Google
Trends (intérêt relatif) / « à valider ». Aucune dépendance, aucun crash.

⚠️ Honnêteté : chaque appel CONSOMME des crédits payants. Le module ne demande
que les mots-clés qu'on lui passe, et regroupe en un seul appel (l'API accepte
des lots), pour minimiser la consommation.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger("market_intel")

_ENDPOINT = "https://api.keywordseverywhere.com/v1/get_keyword_data"
ENV_KEY = "KEYWORDS_EVERYWHERE_API_KEY"


@dataclass
class KeywordVolume:
    keyword: str
    volume: int | None = None       # volume de recherche mensuel (Google)
    cpc: float | None = None        # coût par clic indicatif
    competition: float | None = None  # 0 (faible) à 1 (forte)
    source: str = "Keywords Everywhere API (volume Google, proxy de l'intention)"


class KeywordsEverywhereClient:
    """Client minimal pour l'API Keywords Everywhere."""

    def __init__(self, api_key: str | None = None, country: str = "fr",
                 currency: str = "eur", data_source: str = "gkp",
                 timeout: int = 25, max_retries: int = 3,
                 backoff_base: float = 2.0):
        self.api_key = api_key or os.environ.get(ENV_KEY)
        self.country = country
        self.currency = currency
        self.data_source = data_source  # "gkp" (Google Keyword Planner) ou "cli"
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            })

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def get_volumes(self, keywords: list[str]) -> dict[str, KeywordVolume]:
        """
        Renvoie un dict {mot-clé -> KeywordVolume}. Vide si pas de clé ou échec.
        Un seul appel groupé pour limiter la consommation de crédits.
        """
        if not self.available or not keywords:
            return {}

        # L'API accepte un lot de mots-clés via le paramètre répété kw[].
        payload = {
            "country": self.country,
            "currency": self.currency,
            "dataSource": self.data_source,
            "kw[]": keywords,
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.post(_ENDPOINT, data=payload,
                                          timeout=self.timeout)
                if resp.status_code == 200:
                    return self._parse(resp.json())
                if resp.status_code in (401, 403):
                    logger.error("Keywords Everywhere : clé refusée (HTTP %s). "
                                 "Vérifie %s.", resp.status_code, ENV_KEY)
                    return {}
                if resp.status_code == 402:
                    logger.error("Keywords Everywhere : crédits épuisés (HTTP 402).")
                    return {}
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    logger.info("Keywords Everywhere HTTP %s (tentative %d/%d)",
                                resp.status_code, attempt, self.max_retries)
                else:
                    logger.warning("Keywords Everywhere : HTTP %s", resp.status_code)
                    return {}
            except requests.RequestException as e:
                logger.info("Keywords Everywhere erreur réseau (%d/%d) : %s",
                            attempt, self.max_retries, e)
            if attempt < self.max_retries:
                time.sleep(self.backoff_base * (2 ** (attempt - 1)))
        logger.error("Keywords Everywhere : échec définitif.")
        return {}

    @staticmethod
    def _parse(data: dict) -> dict[str, KeywordVolume]:
        """Transforme la réponse JSON en dict de KeywordVolume."""
        out: dict[str, KeywordVolume] = {}
        for item in (data.get("data") or []):
            kw = item.get("keyword")
            if not kw:
                continue
            cpc = item.get("cpc")
            cpc_val = None
            if isinstance(cpc, dict):
                try:
                    cpc_val = float(cpc.get("value"))
                except (TypeError, ValueError):
                    cpc_val = None
            out[kw] = KeywordVolume(
                keyword=kw,
                volume=_as_int(item.get("vol")),
                cpc=cpc_val,
                competition=_as_float(item.get("competition")),
            )
        return out


def _as_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _as_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None
