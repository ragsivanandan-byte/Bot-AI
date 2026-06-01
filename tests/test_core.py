"""
test_core.py — Tests de non-régression du coeur métier.

Volontairement SANS dépendance externe (pas de pytest requis) : exécutables via
    python -m tests.test_core
ou
    python tests/test_core.py

Couvre : config, estimation CA, inférence IA, structure des prompts Grok,
parsing HTML défensif, et l'historisation SQLite + diffs. Aucun accès réseau.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Permet `python tests/test_core.py` depuis la racine du repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis import (ai_inference, build_profile, estimate_revenue,
                          rank_competitors)
from src.config_loader import load_config
from src.etsy_parser import ShopData, parse_shop_page
from src.prompt_generator import generate_daily_prompts
from src.seo import build_opportunities
from src.storage import HistoryStore
from src.trends import TrendResult

_FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ✅ {msg}")
    else:
        print(f"  ❌ {msg}")
        _FAILURES.append(msg)


# --- Config ------------------------------------------------------------------

def test_config():
    print("\n[config]")
    cfg = load_config("config.yaml")
    check("shop" in cfg and "niche" in cfg, "config charge les sections clés")
    check(cfg["grok_prompts"]["count_per_day"] == 5, "5 prompts/jour configurés")


# --- Estimation de CA --------------------------------------------------------

def test_revenue():
    print("\n[estimation CA]")
    rev_cfg = {"fallback_avg_price_eur_low": 4, "fallback_avg_price_eur_high": 12,
               "recent_sales_share_low": 0.02, "recent_sales_share_high": 0.08}

    # Cas avec ventes connues -> estimation disponible et bornée
    shop = ShopData("X", "com", "u", total_sales=1000, avg_price_eur=5.0)
    est = estimate_revenue(shop, rev_cfg)
    check(est.available, "CA estimé quand ventes connues")
    check(est.lifetime_low_eur == 5000, "CA lifetime = ventes × prix (1000×5)")
    check(est.monthly_low_eur <= est.monthly_high_eur, "fourchette mensuelle ordonnée")

    # Cas sans ventes -> on ne devine PAS
    shop2 = ShopData("Y", "com", "u", total_sales=None)
    est2 = estimate_revenue(shop2, rev_cfg)
    check(not est2.available, "PAS d'estimation inventée si ventes inconnues")


# --- Inférence IA ------------------------------------------------------------

def test_ai_inference():
    print("\n[inférence IA]")
    ai_cfg = {"enabled": True, "threshold": 4,
              "weights": {"low_price": 2, "high_listing_count": 2,
                          "keyword_stuffed_titles": 2, "high_sales_velocity": 1},
              "low_price_threshold_eur": 3.5,
              "high_listing_count_threshold": 150}

    ai_shop = ShopData("Z", "com", "u", total_sales=40000, active_listings=600,
                       avg_price_eur=2.5, age_text="since 2022",
                       sample_titles=["A " * 25 + ", b, c, d, e, f"])
    res = ai_inference(ai_shop, ai_cfg)
    check(res.probably_ai, "boutique prix bas + massive + titres empilés -> INFÉRENCE IA")
    check(len(res.signals) >= 3, "signaux IA listés pour transparence")

    human = ShopData("H", "com", "u", total_sales=300, active_listings=20,
                     avg_price_eur=14.0, sample_titles=["Set of 3 wabi sabi art"])
    check(not ai_inference(human, ai_cfg).probably_ai,
          "petite boutique prix moyen -> PAS marquée IA")


# --- Prompts Grok ------------------------------------------------------------

def test_prompts():
    print("\n[prompts Grok]")
    cfg = load_config("config.yaml")
    ops = build_opportunities(cfg["niche"], [])
    prompts = generate_daily_prompts(cfg["grok_prompts"], cfg["niche"], ops)
    check(len(prompts) == 5, "exactement 5 prompts générés")
    p = prompts[0]
    txt = p.prompt_text.lower()
    check("solid filled" in txt, "structure 'solid filled' présente")
    check("no outline" in txt and "no line drawing" in txt,
          "negative prompt 'no outline / no line drawing' présent")
    check("silhouette silhouette" not in txt, "pas de doublon 'silhouette silhouette'")
    # Reproductibilité par date
    from datetime import date
    a = generate_daily_prompts(cfg["grok_prompts"], cfg["niche"], ops, date(2026, 6, 1))
    b = generate_daily_prompts(cfg["grok_prompts"], cfg["niche"], ops, date(2026, 6, 1))
    check(a[0].prompt_text == b[0].prompt_text, "prompts déterministes pour une date")


# --- Parsing défensif --------------------------------------------------------

def test_parser():
    print("\n[parsing HTML]")
    html = """
    <html lang="en-US"><head><title>CoolShop - Etsy</title></head>
    <body><p>1,234 Sales</p><p>4.9 out of 5</p><p>320 reviews</p>
    <p>56 items</p><p>On Etsy since 2021</p>
    <script type="application/ld+json">{"offers":{"price":"12.50"}}</script>
    <h3>Boho Terracotta Wall Art Printable Set of 3 Neutral Modern Decor</h3>
    </body></html>"""
    data = parse_shop_page(html, "CoolShop", "com", "u")
    check(data.total_sales == 1234, "ventes extraites (1234)")
    check(data.reviews == 320, "avis extraits (320)")
    check(data.active_listings == 56, "fiches extraites (56)")
    check(abs((data.avg_price_eur or 0) - 12.5) < 0.01, "prix JSON-LD extrait (12.50)")

    # Page vide -> tout None, jamais d'exception ni de valeur inventée
    empty = parse_shop_page("<html></html>", "Empty", "com", "u")
    check(empty.total_sales is None, "champ absent reste None (pas inventé)")


# --- Historisation + diffs ---------------------------------------------------

def test_storage():
    print("\n[historique SQLite + diffs]")
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "h.sqlite3")
        store = HistoryStore(db)
        check(store.available, "base SQLite initialisée")

        # Jour 1
        s_d1 = [ShopData("A", "com", "u", total_sales=1000, active_listings=50,
                         reviews=100, avg_price_eur=10.0, fetched=True)]
        store.save_snapshot("2026-05-31", s_d1)

        # Jour 2 : +200 ventes, +5 fiches
        s_d2 = [ShopData("A", "com", "u", total_sales=1200, active_listings=55,
                         reviews=110, avg_price_eur=10.0, fetched=True)]
        deltas = store.compute_deltas(s_d2, "2026-06-01")
        check("A" in deltas, "diff calculé pour la boutique connue")
        check(deltas["A"].sales_delta == 200, "Δ ventes = +200")
        check(deltas["A"].listings_delta == 5, "Δ fiches = +5")
        check(deltas["A"].has_change, "changement détecté")

        # Boutique inconnue -> pas de diff (pas d'invention)
        s_new = [ShopData("NEW", "com", "u", total_sales=5, fetched=True)]
        check("NEW" not in store.compute_deltas(s_new, "2026-06-01"),
              "pas de diff pour une boutique sans historique")
        store.close()


def main() -> int:
    print("=== TESTS — outil intelligence marché ===")
    test_config()
    test_revenue()
    test_ai_inference()
    test_prompts()
    test_parser()
    test_storage()
    print(f"\n{'='*42}")
    if _FAILURES:
        print(f"❌ {len(_FAILURES)} test(s) en échec :")
        for f in _FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ Tous les tests passent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
