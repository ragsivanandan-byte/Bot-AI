"""
etsy_api.py — Connecteur à l'API officielle Etsy (Open API v3).

Pourquoi ce module : c'est la voie PROPRE et AUTORISÉE pour récupérer des
données concurrents (ventes cumulées, fiches actives, avis, note, prix). Elle
remplace avantageusement le scraping HTML quand une clé API est disponible :
pas de 403, pas de robots.txt à craindre, données structurées et fiables.

Authentification : pour les lectures de données PUBLIQUES (boutiques/fiches), une
simple clé d'application (« keystring ») suffit, envoyée dans l'en-tête
`x-api-key`. Aucune connexion OAuth utilisateur n'est requise pour ces appels.

Clé lue depuis la variable d'environnement  ETSY_API_KEY  (jamais en dur).
Sans clé, ce module est INACTIF (available=False) et l'outil retombe sur le
parsing HTML — dégradation gracieuse, aucun crash.

⚠️ Honnêteté :
  * Les prix sont renvoyés dans la DEVISE de la boutique (pas forcément EUR).
    On conserve la devise réelle dans `ShopData.currency` ; aucune conversion
    n'est inventée (voir LIMITS.md).
  * Obtenir une clé nécessite de créer une app sur le portail développeur Etsy
    et une validation manuelle d'Etsy (gratuite). Les quotas s'appliquent
    (≈ 10 req/s, 10 000 req/jour au moment de l'écriture — à reconfirmer).
"""
from __future__ import annotations

import logging
import os
import time

import requests

from .etsy_parser import ShopData

logger = logging.getLogger("market_intel")

_BASE = "https://openapi.etsy.com/v3/application"
ENV_KEY = "ETSY_API_KEY"


class EtsyApiClient:
    """Client minimal pour les endpoints publics de l'API Etsy v3."""

    def __init__(self, api_key: str | None = None, timeout: int = 20,
                 max_retries: int = 4, backoff_base: float = 2.0,
                 min_delay: float = 0.2):
        self.api_key = api_key or os.environ.get(ENV_KEY)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.min_delay = min_delay  # respect du quota ≈10 req/s -> 0.2s mini
        self._last_call = 0.0
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"x-api-key": self.api_key,
                                          "Accept": "application/json"})

    @property
    def available(self) -> bool:
        """True seulement si une clé API est présente."""
        return bool(self.api_key)

    # --- bas niveau ----------------------------------------------------------
    def _get(self, path: str, params: dict | None = None) -> dict | None:
        """GET avec retries/backoff. Renvoie le JSON (dict) ou None si échec."""
        if not self.available:
            return None
        url = f"{_BASE}{path}"
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            # throttle simple pour respecter le quota
            wait = self.min_delay - (time.time() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
                self._last_call = time.time()
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in (401, 403):
                    logger.error("API Etsy : clé refusée (HTTP %s). Vérifie "
                                 "ETSY_API_KEY.", resp.status_code)
                    return None
                if resp.status_code == 404:
                    logger.info("API Etsy : ressource introuvable (404) %s", url)
                    return None
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    last_err = f"HTTP {resp.status_code}"
                    logger.info("API Etsy %s (tentative %d/%d)", last_err,
                                attempt, self.max_retries)
                else:
                    logger.warning("API Etsy : HTTP %s sur %s", resp.status_code, url)
                    return None
            except requests.RequestException as e:
                last_err = str(e)
                logger.info("API Etsy erreur réseau (tentative %d/%d) : %s",
                            attempt, self.max_retries, e)
            if attempt < self.max_retries:
                time.sleep(self.backoff_base * (2 ** (attempt - 1)))
        logger.error("API Etsy : échec définitif sur %s (%s)", url, last_err)
        return None

    # --- haut niveau ---------------------------------------------------------
    def get_shop(self, shop_name: str, market: str = "com",
                 sample_listings: int = 24) -> ShopData | None:
        """
        Récupère une boutique par son nom + un échantillon de fiches pour le prix.
        Renvoie un ShopData ou None si la clé manque / l'appel échoue.
        """
        if not self.available:
            return None
        url = (f"https://www.etsy.com/{market}/shop/{shop_name}"
               if market not in ("com", "") else
               f"https://www.etsy.com/shop/{shop_name}")

        data = self._get("/shops", params={"shop_name": shop_name})
        if not data:
            return None
        results = data.get("results") or []
        if not results:
            logger.info("API Etsy : aucune boutique nommée '%s'", shop_name)
            return None
        shop = results[0]

        sd = ShopData(slug=shop_name, market=market, url=url, fetched=True,
                      source_note="API Etsy officielle (v3)")
        sd.name = shop.get("shop_name") or shop_name
        sd.total_sales = _as_int(shop.get("transaction_sold_count"))
        sd.active_listings = _as_int(shop.get("listing_active_count"))
        sd.reviews = _as_int(shop.get("review_count"))
        sd.avg_rating = _as_float(shop.get("review_average"))
        sd.currency = shop.get("currency_code")
        created = shop.get("create_date") or shop.get("created_timestamp")
        if created:
            sd.age_text = _year_from_epoch(created)

        shop_id = shop.get("shop_id")
        if shop_id and sample_listings > 0:
            self._enrich_with_listings(sd, shop_id, sample_listings)
        return sd

    def _enrich_with_listings(self, sd: ShopData, shop_id: int,
                              limit: int) -> None:
        """Ajoute prix moyen/min/max + titres d'exemple depuis les fiches actives."""
        data = self._get(f"/shops/{shop_id}/listings/active",
                         params={"limit": min(limit, 100)})
        if not data:
            return
        prices: list[float] = []
        titles: list[str] = []
        currency = sd.currency
        for listing in data.get("results", []):
            title = listing.get("title")
            if title:
                titles.append(title)
            price = listing.get("price")
            # v3 : price = {amount, divisor, currency_code}
            if isinstance(price, dict) and price.get("divisor"):
                val = _as_float(price.get("amount"))
                div = _as_float(price.get("divisor")) or 100.0
                if val is not None:
                    prices.append(val / div)
                currency = currency or price.get("currency_code")
        if prices:
            sd.avg_price_eur = round(sum(prices) / len(prices), 2)
            sd.price_min_eur = round(min(prices), 2)
            sd.price_max_eur = round(max(prices), 2)
        if currency:
            sd.currency = currency
        if titles:
            sd.sample_titles = titles[:12]


# --- helpers -----------------------------------------------------------------

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


def _year_from_epoch(epoch) -> str | None:
    try:
        from datetime import datetime, timezone
        y = datetime.fromtimestamp(int(epoch), tz=timezone.utc).year
        return f"On Etsy since {y}"
    except (TypeError, ValueError, OSError):
        return None
