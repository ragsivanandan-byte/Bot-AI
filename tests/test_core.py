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

from src.analysis import ai_inference, estimate_revenue
from src.config_loader import load_config
from src.etsy_parser import ShopData, parse_shop_page
from src.prompt_generator import generate_daily_brief
from src.seo import build_opportunities
from src.storage import HistoryStore

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
    print("\n[brief visuel Grok : 3 images -> 4 mockups+cover -> 1 vidéo]")
    from datetime import date
    cfg = load_config("config.yaml")
    ops = build_opportunities(cfg["niche"], [])
    b = generate_daily_brief(cfg["grok_prompts"], cfg["niche"], ops, date(2026, 6, 6))
    check(len(b.raw_prompts) == 3, "3 prompts d'images brutes")
    check(len(b.mockup_prompts) == 4, "4 prompts de mockups")
    check(sum(1 for m in b.mockup_prompts if m.is_cover) == 1, "exactement 1 cover")
    check(bool(b.video_prompt), "1 prompt vidéo présent")

    raw = b.raw_prompts[0].prompt_text.lower()
    check("no outline" in raw and "no rainbow" in raw,
          "image brute : negative 'no outline / no rainbow' présent")
    cover = next(m for m in b.mockup_prompts if m.is_cover).prompt_text.lower()
    check("paste the provided poster" in cover and "opaque" in cover,
          "mockup cover : règle compositing 'PASTE UNCHANGED / OPAQUE'")
    check("frozen and identical in every frame" in b.video_prompt.lower(),
          "vidéo : règle anti-morphing 'frozen every frame'")
    check(b.output_dir == "~/Downloads", "sortie imposée vers ~/Downloads")
    nvar = cfg["grok_prompts"].get("variations_per_design", 8)
    check(len(b.raw_prompts[0].variation_files) == nvar,
          f"{nvar} variations attendues listées par design")
    check(b.raw_prompts[0].variation_files[0].endswith("_01_v1.png"),
          "nommage des variations correct")

    # Déterminisme par date
    b2 = generate_daily_brief(cfg["grok_prompts"], cfg["niche"], ops, date(2026, 6, 6))
    check(b.raw_prompts[0].prompt_text == b2.raw_prompts[0].prompt_text,
          "brief déterministe pour une date donnée")


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


def test_api_connectors():
    print("\n[connecteurs API : dégradation + parsing]")
    from src.etsy_api import EtsyApiClient
    from src.keywords_api import KeywordsEverywhereClient

    # Sans clé -> inactifs, jamais d'appel réseau, jamais de crash
    e = EtsyApiClient(api_key=None)
    check(not e.available, "EtsyApiClient inactif sans clé")
    check(e.get_shop("Whatever") is None, "get_shop renvoie None sans clé (pas de réseau)")

    k = KeywordsEverywhereClient(api_key=None)
    check(not k.available, "KeywordsEverywhere inactif sans clé")
    check(k.get_volumes(["x"]) == {}, "get_volumes renvoie {} sans clé")

    # Parsing d'une réponse JSON Keywords Everywhere simulée (logique pure)
    sample = {"data": [
        {"keyword": "japandi wall art", "vol": 2400,
         "cpc": {"currency": "€", "value": "0.42"}, "competition": 0.18},
        {"keyword": "boho print", "vol": 900, "competition": 0.6},
    ]}
    parsed = KeywordsEverywhereClient._parse(sample)
    check(parsed["japandi wall art"].volume == 2400, "volume KWE parsé (2400)")
    check(abs(parsed["japandi wall art"].cpc - 0.42) < 0.001, "CPC KWE parsé (0.42)")
    check(parsed["boho print"].cpc is None, "CPC absent -> None (pas inventé)")


def test_etsy_api_mapping():
    print("\n[API Etsy : réponse simulée -> ShopData]")
    from src.etsy_api import EtsyApiClient

    # Réponses JSON simulées comme celles de l'API v3.
    shop_resp = {"results": [{
        "shop_id": 123, "shop_name": "CoolShop", "transaction_sold_count": 4200,
        "listing_active_count": 88, "review_count": 510, "review_average": 4.9,
        "currency_code": "EUR", "create_date": 1609459200,  # 2021
    }]}
    listings_resp = {"results": [
        {"title": "Japandi Wall Art Set of 3",
         "price": {"amount": 1250, "divisor": 100, "currency_code": "EUR"}},
        {"title": "Terracotta Arch Print",
         "price": {"amount": 800, "divisor": 100, "currency_code": "EUR"}},
    ]}

    client = EtsyApiClient(api_key="FAKE_FOR_TEST")
    # On court-circuite le réseau en remplaçant _get par des réponses canned.
    client._get = lambda path, params=None: (  # type: ignore
        shop_resp if path == "/shops" else listings_resp)

    sd = client.get_shop("CoolShop", "fr")
    check(sd is not None and sd.total_sales == 4200, "ventes mappées depuis l'API (4200)")
    check(sd.active_listings == 88 and sd.reviews == 510, "fiches/avis mappés")
    check(sd.currency == "EUR", "devise réelle conservée (EUR)")
    check(abs((sd.avg_price_eur or 0) - 10.25) < 0.01, "prix moyen calculé (12.5+8)/2")
    check("2021" in (sd.age_text or ""), "année d'ouverture déduite (2021)")
    check(len(sd.sample_titles) == 2, "titres récupérés pour analyse")


def test_seo_with_volumes():
    print("\n[SEO avec volumes réels]")
    from src.keywords_api import KeywordVolume
    niche = {"emerging_subniches": ["japandi wall art"], "pillars": [],
             "saturated_topics": []}
    volumes = {"japandi wall art": KeywordVolume("japandi wall art", volume=2400,
                                                 competition=0.18)}
    ops = build_opportunities(niche, [], volumes)
    op = next(o for o in ops if o.keyword == "japandi wall art")
    check(op.search_volume == 2400, "volume réel injecté dans l'opportunité")
    check(op.confirmation == "confirmée", "volume réel > 0 -> demande confirmée")
    check("concurrence FAIBLE" in op.rationale, "concurrence faible signalée")

    # Sans volumes -> comportement d'origine inchangé
    ops2 = build_opportunities(niche, [])
    check(next(o for o in ops2 if o.keyword == "japandi wall art").search_volume
          is None, "sans clé KWE, pas de volume inventé")


def test_currency():
    print("\n[conversion devises -> EUR]")
    from src.currency import CurrencyConverter, convert_shop_prices

    # Convertisseur en mode hors-ligne -> utilise la table de repli statique.
    conv = CurrencyConverter(cache_path=tempfile.mktemp(suffix=".json"),
                             allow_network=False)

    # EUR -> EUR : identité, pas de conversion
    val, note = conv.to_eur(10.0, "EUR")
    check(val == 10.0 and "aucune conversion" in note, "EUR->EUR inchangé")

    # USD -> EUR : 108 USD / 1.08 (taux repli) = 100 €
    val, note = conv.to_eur(108.0, "USD")
    check(val is not None and abs(val - 100.0) < 0.01, "USD->EUR via repli (108->100)")
    check("USD" in note, "note de conversion mentionne la devise source")

    # Devise inconnue -> None (jamais inventé)
    val, note = conv.to_eur(10.0, "XYZ")
    check(val is None, "devise inconnue -> pas de conversion inventée")

    # Application sur un ShopData (prix passe de USD à EUR, original conservé)
    shop = ShopData("S", "com", "u", avg_price_eur=21.6, price_min_eur=10.8,
                    price_max_eur=32.4, currency="USD", fetched=True)
    convert_shop_prices(shop, conv)
    check(abs(shop.avg_price_eur - 20.0) < 0.01, "prix moyen converti (21.6 USD->20€)")
    check(shop.avg_price_original == 21.6, "prix d'origine conservé (transparence)")
    check(shop.fx_note is not None, "note de conversion attachée au ShopData")
    check(abs(shop.price_min_eur - 10.0) < 0.01, "prix min aussi converti")


def test_integration_full_pipeline():
    print("\n[intégration : pipeline complet avec API + volumes + conversion]")
    import main as cli
    from src.currency import CurrencyConverter
    from src.keywords_api import KeywordVolume

    # Faux client Etsy : renvoie une boutique en USD avec prix.
    class FakeEtsy:
        available = True
        def get_shop(self, slug, market="com"):
            return ShopData(slug=slug, market=market, url="u", fetched=True,
                            source_note="API Etsy (simulée)", total_sales=5000,
                            active_listings=120, reviews=800, avg_rating=4.9,
                            avg_price_eur=10.8, price_min_eur=5.4,
                            price_max_eur=21.6, currency="USD",
                            sample_titles=["Japandi Wall Art Set of 3"])

    cfg = load_config("config.yaml")
    cfg["competitors"] = [{"slug": "FakeShopUSD", "market": "com"}]
    conv = CurrencyConverter(cache_path=tempfile.mktemp(suffix=".json"),
                             allow_network=False)

    profiles, degraded = cli.collect_competitors(
        cfg, fetcher=None, logger=cli_logger(), allow_network=True,
        etsy_client=FakeEtsy(), converter=conv)
    check(not degraded, "pipeline non dégradé quand l'API fournit des données")
    p = profiles[0]
    check(abs(p.shop.avg_price_eur - 10.0) < 0.01, "prix API USD converti en EUR (10.8->10)")
    check(p.revenue.available, "CA estimé à partir des données API")
    # Le CA utilise bien le prix EUR converti : 5000 * 10 = 50000 € lifetime low
    check(p.revenue.lifetime_low_eur == 50000, "CA lifetime cohérent avec prix converti")

    # Volumes réels -> opportunités confirmées
    vols = {"japandi wall art": KeywordVolume("japandi wall art", volume=3000,
                                              competition=0.2)}
    ops = build_opportunities({"emerging_subniches": ["japandi wall art"],
                               "pillars": [], "saturated_topics": []}, [], vols)
    check(ops[0].search_volume == 3000, "volume réel propagé dans le pipeline SEO")


def cli_logger():
    import logging
    lg = logging.getLogger("market_intel")
    lg.addHandler(logging.NullHandler())
    return lg


def test_cli_smoke():
    print("\n[smoke CLI : les modes tournent sans erreur — ISOLÉ]")
    import os
    import shutil
    from datetime import date
    import main as cli

    import yaml
    repo = Path(__file__).resolve().parent.parent
    cwd0 = os.getcwd()
    tmp = tempfile.mkdtemp()
    try:
        # On copie config.yaml dans un tmp et on FORCE les dossiers de sortie en
        # local (reports/cache/logs relatifs au tmp). Indispensable car la vraie
        # config écrit dans ~/Downloads/reports : sans override, le test
        # polluerait le vrai dossier Téléchargements de la machine.
        with open(repo / "config.yaml", encoding="utf-8") as f:
            c = yaml.safe_load(f)
        c.setdefault("output", {})["reports_dir"] = "reports"
        c["output"]["logs_dir"] = "logs"
        c.setdefault("network", {})["cache_dir"] = "cache"
        with open(Path(tmp) / "config.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(c, f, allow_unicode=True)
        os.chdir(tmp)
        rc1 = cli.main(["--no-network"])
        check(rc1 == 0, "`main.py --no-network` se termine proprement (code 0)")
        rc2 = cli.main(["--demo", "--no-network"])
        check(rc2 == 0, "`main.py --demo --no-network` -> code 0")
        rep = Path(tmp) / "reports" / date.today().isoformat()
        for f in ("veille_concurrents.md", "prompts_grok_du_jour.md",
                  "guidelines_claude_chat.md"):
            check((rep / f).exists(), f"rapport généré : {f}")
        # guidelines = sur-ensemble fusionné (veille + prompts en annexes)
        gtext = (rep / "guidelines_claude_chat.md").read_text(encoding="utf-8")
        check("ANNEXE A" in gtext and "ANNEXE B" in gtext,
              "guidelines fusionné contient veille + prompts (1 copier-coller)")
    finally:
        os.chdir(cwd0)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("=== TESTS — outil intelligence marché ===")
    test_config()
    test_revenue()
    test_ai_inference()
    test_prompts()
    test_parser()
    test_storage()
    test_api_connectors()
    test_etsy_api_mapping()
    test_seo_with_volumes()
    test_currency()
    test_integration_full_pipeline()
    test_cli_smoke()
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
