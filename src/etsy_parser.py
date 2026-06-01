"""
etsy_parser.py — Extraction de données publiques depuis les pages Etsy.

Ce module transforme du HTML brut de page boutique Etsy en un dictionnaire
structuré. Il est volontairement DEFENSIF :
  * chaque champ est extrait via plusieurs stratégies (JSON-LD, balises meta,
    motifs texte) et vaut None si rien n'est trouvé ;
  * il ne suppose JAMAIS une valeur ; un champ absent reste explicitement absent
    (None) -> le rapport le marquera "donnée indisponible".

⚠️ Le HTML d'Etsy change régulièrement. Si l'extraction d'un champ tombe à zéro
en mode live, c'est probablement que la structure de la page a évolué : les
sélecteurs ci-dessous sont à ajuster. C'est documenté dans LIMITS.md.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger("market_intel")


@dataclass
class ShopData:
    """Données publiques d'une boutique. Tout champ inconnu reste None."""
    slug: str
    market: str
    url: str
    fetched: bool = False                 # a-t-on réussi à charger la page ?
    source_note: str = ""                 # d'où vient la donnée / pourquoi absente
    name: str | None = None
    total_sales: int | None = None        # ventes publiques cumulées (lifetime)
    active_listings: int | None = None
    reviews: int | None = None
    avg_rating: float | None = None
    avg_price_eur: float | None = None
    price_min_eur: float | None = None
    price_max_eur: float | None = None
    currency: str | None = None           # devise réelle (API). None si inconnue.
    age_text: str | None = None           # ancienneté brute si trouvée
    has_strikethrough_price: bool | None = None  # prix barré (promo) détecté ?
    languages: list[str] = field(default_factory=list)
    sample_titles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


# --- Helpers d'extraction ----------------------------------------------------

def _to_int(s: str | None) -> int | None:
    """Extrait un entier depuis une chaîne ('1,234 Sales' -> 1234)."""
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def _to_float(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", s)
    if not m:
        return None
    return float(m.group(0).replace(",", "."))


def _extract_jsonld(soup: BeautifulSoup) -> list[dict]:
    """Récupère tous les blocs JSON-LD (souvent présents sur Etsy)."""
    blocks: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            blocks.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks


def parse_shop_page(html: str, slug: str, market: str, url: str) -> ShopData:
    """
    Parse une page boutique Etsy. Retourne un ShopData. Les champs non trouvés
    restent None (jamais inventés).
    """
    data = ShopData(slug=slug, market=market, url=url, fetched=True,
                    source_note="page boutique Etsy publique")
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    # --- Nom de la boutique --------------------------------------------------
    if soup.title and soup.title.string:
        data.name = soup.title.string.split("-")[0].strip() or slug

    # --- Nombre de ventes (badge public "X Sales") ---------------------------
    # Plusieurs formulations possibles selon la langue / le marché.
    sales_match = re.search(r"([\d.,]+)\s*(?:Sales|Ventes|ventes)\b", text)
    if sales_match:
        data.total_sales = _to_int(sales_match.group(1))

    # --- Avis et note --------------------------------------------------------
    rating_match = re.search(r"([\d.,]+)\s*(?:out of 5|sur 5|étoiles|stars)", text)
    if rating_match:
        data.avg_rating = _to_float(rating_match.group(1))
    reviews_match = re.search(r"([\d.,]+)\s*(?:reviews|avis|évaluations)", text,
                              re.IGNORECASE)
    if reviews_match:
        data.reviews = _to_int(reviews_match.group(1))

    # --- Nombre de fiches actives --------------------------------------------
    listings_match = re.search(r"([\d.,]+)\s*(?:items|articles|listings|produits)",
                               text, re.IGNORECASE)
    if listings_match:
        data.active_listings = _to_int(listings_match.group(1))

    # --- Prix (collecte de tous les prix affichés sur la page) ---------------
    prices = _collect_prices(soup, text)
    if prices:
        data.price_min_eur = round(min(prices), 2)
        data.price_max_eur = round(max(prices), 2)
        data.avg_price_eur = round(sum(prices) / len(prices), 2)

    # --- Prix barré (promo) --------------------------------------------------
    data.has_strikethrough_price = _detect_strikethrough(soup, text)

    # --- Langue cible (depuis <html lang> ou meta) ---------------------------
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        data.languages = [html_tag.get("lang")]

    # --- Titres d'exemple (pour l'analyse de patterns SEO / IA) --------------
    data.sample_titles = _collect_titles(soup)

    # --- Ancienneté (souvent "On Etsy since 20XX") ---------------------------
    age_match = re.search(r"(?:On Etsy since|Sur Etsy depuis|since)\s*(\d{4})",
                          text, re.IGNORECASE)
    if age_match:
        data.age_text = age_match.group(0)

    _log_extraction_summary(data)
    return data


def _collect_prices(soup: BeautifulSoup, text: str) -> list[float]:
    """Collecte les prix affichés. JSON-LD d'abord, puis motifs texte."""
    prices: list[float] = []

    for block in _extract_jsonld(soup):
        offers = block.get("offers")
        if isinstance(offers, dict):
            p = _to_float(str(offers.get("price", "")))
            if p:
                prices.append(p)
        elif isinstance(offers, list):
            for off in offers:
                if isinstance(off, dict):
                    p = _to_float(str(off.get("price", "")))
                    if p:
                        prices.append(p)

    # Repli : motifs de prix dans le texte (€, $, £, AUD). On reste prudent et
    # on borne les valeurs plausibles pour un printable (0,5 à 80).
    if not prices:
        for m in re.finditer(r"(?:[€$£]|AU\$|USD|EUR|AUD)\s?([\d]+(?:[.,]\d{2})?)",
                             text):
            v = _to_float(m.group(1))
            if v and 0.5 <= v <= 80:
                prices.append(v)

    return prices


def _detect_strikethrough(soup: BeautifulSoup, text: str) -> bool | None:
    """Tente de détecter un prix barré (promo). None si indéterminable."""
    if soup.find(["del", "s"]):
        return True
    if re.search(r"(?:Sale|Solde|Promo|% off|de r[ée]duction)", text,
                 re.IGNORECASE):
        return True
    return None  # indéterminé plutôt que False par excès de confiance


def _collect_titles(soup: BeautifulSoup, limit: int = 12) -> list[str]:
    """Récupère des titres de fiches pour l'analyse de patterns."""
    titles: list[str] = []
    # Etsy expose souvent les titres dans des balises <h3> de carte produit.
    for tag in soup.find_all(["h3", "h2"]):
        t = tag.get_text(" ", strip=True)
        if t and len(t) > 15 and t not in titles:
            titles.append(t)
        if len(titles) >= limit:
            break
    return titles


def _log_extraction_summary(d: ShopData) -> None:
    found = [k for k in ("total_sales", "active_listings", "reviews",
                         "avg_price_eur") if getattr(d, k) is not None]
    logger.debug("Parse %s : champs trouvés = %s", d.slug,
                 found or "AUCUN (structure HTML possiblement changée)")
