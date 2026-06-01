"""
demo_fixtures.py — Données SYNTHÉTIQUES de démonstration.

⚠️⚠️⚠️ AVERTISSEMENT ⚠️⚠️⚠️
Tout ce qui est ici est 100 % FICTIF et INVENTÉ pour la démonstration. Aucune de
ces boutiques, ventes ou prix n'est réel. Le SEUL but est de montrer ce que
produisent les moteurs d'analyse (estimation de CA, inférence IA, comparaison)
quand des données existent — puisque l'accès live à Etsy est bloqué dans
l'environnement de build.

NE JAMAIS confondre ces chiffres avec des données réelles. Le mode `--demo`
préfixe d'ailleurs chaque rapport d'un bandeau « DONNÉES FICTIVES ».
"""
from __future__ import annotations

from .etsy_parser import ShopData


def demo_competitors() -> list[ShopData]:
    """Renvoie 4 profils synthétiques couvrant des cas variés (humain, IA, etc.)."""
    return [
        # Cas 1 : gros vendeur, catalogue massif, prix bas -> heuristique IA forte
        ShopData(
            slug="DEMO_MassVolumeStudio", market="com",
            url="https://www.etsy.com/shop/DEMO_MassVolumeStudio",
            fetched=True, source_note="DONNÉE FICTIVE (démo)",
            name="DEMO_MassVolumeStudio",
            total_sales=48000, active_listings=620, reviews=9100,
            avg_rating=4.8, avg_price_eur=2.9, price_min_eur=1.5,
            price_max_eur=6.0, currency="USD", age_text="On Etsy since 2022",
            has_strikethrough_price=True, languages=["en-US"],
            sample_titles=[
                "Boho Wall Art Printable Set Terracotta Neutral Minimalist "
                "Digital Download Living Room Decor Abstract Modern Trendy Gift, "
                "Instant Print, 16x20, A4, A3, 5x7",
                "Japandi Wall Art Print Set of 6 Beige Earthy Tones Minimalist "
                "Digital Download Bedroom Decor Printable Poster, Instant",
            ],
        ),
        # Cas 2 : vendeur établi, prix moyen, sets -> profil humain probable
        ShopData(
            slug="DEMO_WarmHausCurated", market="com",
            url="https://www.etsy.com/shop/DEMO_WarmHausCurated",
            fetched=True, source_note="DONNÉE FICTIVE (démo)",
            name="DEMO_WarmHausCurated",
            total_sales=3200, active_listings=58, reviews=540,
            avg_rating=4.9, avg_price_eur=14.0, price_min_eur=8.0,
            price_max_eur=29.0, age_text="On Etsy since 2021",
            has_strikethrough_price=True, languages=["en-GB"],
            sample_titles=[
                "Set of 3 Wabi Sabi Wall Art",
                "Terracotta Arch Print Bundle",
            ],
        ),
        # Cas 3 : petit vendeur de niche, catalogue étroit -> faille longue traîne
        ShopData(
            slug="DEMO_NurseryNeutralCo", market="fr",
            url="https://www.etsy.com/fr/shop/DEMO_NurseryNeutralCo",
            fetched=True, source_note="DONNÉE FICTIVE (démo)",
            name="DEMO_NurseryNeutralCo",
            total_sales=410, active_listings=22, reviews=63,
            avg_rating=5.0, avg_price_eur=9.5, price_min_eur=5.0,
            price_max_eur=18.0, age_text="On Etsy since 2023",
            has_strikethrough_price=None, languages=["fr-FR"],
            sample_titles=[
                "Affiche bébé neutre lune",
                "Set 2 illustrations nursery beige",
            ],
        ),
        # Cas 4 : page partiellement illisible -> démontre la dégradation par champ
        ShopData(
            slug="DEMO_PartialData", market="com",
            url="https://www.etsy.com/shop/DEMO_PartialData",
            fetched=True, source_note="DONNÉE FICTIVE (démo, page partielle)",
            name="DEMO_PartialData",
            total_sales=1500, active_listings=None, reviews=None,
            avg_rating=None, avg_price_eur=None,
            age_text=None, has_strikethrough_price=None, languages=[],
            sample_titles=[],
        ),
    ]
