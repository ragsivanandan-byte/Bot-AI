"""
currency.py — Conversion automatique des prix vers l'EUR.

Contexte : l'API Etsy renvoie les prix dans la devise de la boutique (USD, GBP,
AUD…). Ce module les convertit en EUR pour que les comparaisons et estimations
de CA soient homogènes.

Sources de taux, par ordre de priorité (dégradation gracieuse) :
  1. cache local récent (cache/fx_rates.json, TTL configurable) ;
  2. API publique GRATUITE sans clé (Frankfurter / BCE) si réseau dispo ;
  3. table de repli STATIQUE embarquée (taux approximatifs datés) — toujours
     disponible pour que la conversion ne tombe JAMAIS en panne.

⚠️ Honnêteté : la source du taux est toujours indiquée. En mode repli statique,
les taux sont APPROXIMATIFS et datés (voir _STATIC_DATE) — à ne pas confondre
avec un taux du jour. La devise d'origine et le prix d'origine sont conservés
dans le ShopData (jamais écrasés en silence).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger("market_intel")

# Table de repli : unités de devise pour 1 EUR. Approximatif, à titre de secours.
_STATIC_DATE = "2026-01 (approximatif, repli hors-ligne)"
_STATIC_RATES_PER_EUR = {
    "EUR": 1.0, "USD": 1.08, "GBP": 0.85, "AUD": 1.65, "CAD": 1.47,
    "JPY": 170.0, "CHF": 0.95, "SEK": 11.5, "NOK": 11.7, "DKK": 7.46,
    "PLN": 4.30, "NZD": 1.78, "CZK": 25.0, "HUF": 390.0, "RON": 4.97,
    "BRL": 5.9, "MXN": 19.5, "INR": 90.0, "SGD": 1.46, "HKD": 8.4,
}


class CurrencyConverter:
    """Convertit des montants vers l'EUR avec mise en cache et repli robuste."""

    def __init__(self, cache_path: str = "cache/fx_rates.json",
                 ttl_hours: float = 24, allow_network: bool = True,
                 api_url: str = "https://api.frankfurter.dev/v1/latest",
                 timeout: int = 15):
        self.cache_path = Path(cache_path)
        self.ttl_s = ttl_hours * 3600
        self.allow_network = allow_network
        self.api_url = api_url
        self.timeout = timeout
        self._rates: dict[str, float] | None = None
        self._source: str = ""

    # --- chargement des taux (lazy, une seule fois) --------------------------
    def _ensure_rates(self) -> None:
        if self._rates is not None:
            return
        # 1) cache récent
        cached = self._read_cache()
        if cached:
            self._rates, self._source = cached
            return
        # 2) API gratuite si réseau autorisé
        if self.allow_network:
            fetched = self._fetch_rates()
            if fetched:
                self._rates, self._source = fetched
                self._write_cache(fetched)
                return
        # 3) repli statique
        self._rates = dict(_STATIC_RATES_PER_EUR)
        self._source = f"table statique embarquée {_STATIC_DATE}"
        logger.info("Taux de change : repli statique utilisé (%s).", _STATIC_DATE)

    def _read_cache(self):
        try:
            if not self.cache_path.exists():
                return None
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if time.time() - data.get("fetched_at", 0) > self.ttl_s:
                return None
            rates = data.get("rates")
            if not isinstance(rates, dict) or "EUR" not in rates:
                return None
            return rates, data.get("source", "cache local")
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.debug("Cache FX illisible (%s) — ignoré.", e)
            return None

    def _write_cache(self, fetched) -> None:
        rates, source = fetched
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(
                {"fetched_at": time.time(), "source": source, "rates": rates},
                ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            logger.debug("Écriture cache FX impossible (%s) — ignoré.", e)

    def _fetch_rates(self):
        """Récupère les taux EUR->X depuis l'API gratuite. None si échec."""
        try:
            resp = requests.get(self.api_url, params={"base": "EUR"},
                                timeout=self.timeout)
            if resp.status_code != 200:
                logger.info("API taux de change indisponible (HTTP %s) -> repli.",
                            resp.status_code)
                return None
            data = resp.json()
            rates = data.get("rates") or {}
            rates["EUR"] = 1.0
            src = (f"API {self.api_url.split('//')[-1].split('/')[0]} "
                   f"(taux du {data.get('date', 'n/a')})")
            return rates, src
        except (requests.RequestException, ValueError) as e:
            logger.info("Récupération des taux échouée (%s) -> repli statique.", e)
            return None

    # --- conversion ----------------------------------------------------------
    def to_eur(self, amount: float | None, currency: str | None):
        """
        Convertit `amount` (exprimé en `currency`) vers l'EUR.
        Renvoie (valeur_eur | None, note_source). Ne lève jamais d'exception.
        """
        if amount is None:
            return None, "montant indisponible"
        if not currency:
            return None, "devise inconnue — pas de conversion"
        cur = currency.upper()
        if cur == "EUR":
            return round(float(amount), 2), "déjà en EUR (aucune conversion)"
        self._ensure_rates()
        rate = (self._rates or {}).get(cur)
        if not rate:
            return None, f"taux {cur} indisponible — conversion impossible"
        return round(float(amount) / rate, 2), f"converti de {cur} via {self._source}"


def convert_shop_prices(shop, converter: CurrencyConverter) -> None:
    """
    Convertit en place les prix d'un ShopData vers l'EUR si une devise non-EUR
    est connue. Préserve le prix d'origine (avg_price_original) et note le taux.
    """
    if shop is None or not shop.currency:
        return
    if shop.currency.upper() == "EUR":
        return  # déjà en EUR, rien à faire
    if shop.avg_price_eur is None:
        return  # pas de prix à convertir

    # On garde la valeur d'origine pour la transparence.
    original_avg = shop.avg_price_eur
    eur_avg, note = converter.to_eur(original_avg, shop.currency)
    if eur_avg is None:
        shop.fx_note = note  # conversion impossible -> on signale, on n'invente pas
        return

    shop.avg_price_original = original_avg
    shop.avg_price_eur = eur_avg
    if shop.price_min_eur is not None:
        v, _ = converter.to_eur(shop.price_min_eur, shop.currency)
        shop.price_min_eur = v if v is not None else shop.price_min_eur
    if shop.price_max_eur is not None:
        v, _ = converter.to_eur(shop.price_max_eur, shop.currency)
        shop.price_max_eur = v if v is not None else shop.price_max_eur
    shop.fx_note = note
    shop.source_note = f"{shop.source_note} | prix {note}"
