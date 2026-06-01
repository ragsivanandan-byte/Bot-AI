#!/usr/bin/env python3
"""
main.py — Point d'entrée CLI de l'outil d'intelligence marché NeutralWallDesign.

Pipeline quotidien :
  1. charge config.yaml
  2. (optionnel) découvre des concurrents via la recherche Etsy publique
  3. récupère + parse les pages boutiques des concurrents (mode respectueux)
  4. estime CA + infère "probablement IA" + compare à ma boutique
  5. récupère les tendances (Google Trends, optionnel)
  6. construit les opportunités SEO
  7. génère 5 prompts Grok du jour
  8. écrit les 3 rapports markdown dans reports/AAAA-MM-JJ/

Robustesse : si une source externe échoue, l'outil CONTINUE en mode dégradé et
le note dans les rapports + les logs. `python main.py` ne doit jamais crasher
à cause d'un blocage réseau.

Sources de données (par ordre de priorité, dégradation gracieuse) :
    - API officielle Etsy (si ETSY_API_KEY défini) -> sinon parsing HTML public
    - Keywords Everywhere (si KEYWORDS_EVERYWHERE_API_KEY défini) -> sinon Trends

Usage :
    python main.py                 # run complet
    python main.py --selftest      # diagnostic (config, clés API, accès live)
    python main.py --no-network    # force le mode hors-ligne (rapports dégradés)
    python main.py --discover      # tente la découverte de nouveaux concurrents
    python main.py --demo          # rapport de démonstration (données fictives)
    python main.py --verbose       # logs détaillés
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from src.analysis import build_profile, rank_competitors
from src.config_loader import ConfigError, load_config
from src.etsy_parser import ShopData, parse_shop_page
from src.fetcher import RespectfulFetcher
from src.prompt_generator import generate_daily_prompts
from src.report_generator import (render_competitors, render_grok_prompts,
                                   render_guidelines, write_reports)
from src.seo import build_opportunities
from src.storage import HistoryStore
from src.trends import fetch_trends
from src.utils import setup_logging, today_str


def shop_url(slug: str, market: str) -> str:
    """Construit l'URL d'une boutique Etsy à partir de son slug et marché."""
    market = (market or "com").strip("/")
    if market in ("com", ""):
        return f"https://www.etsy.com/shop/{slug}"
    return f"https://www.etsy.com/{market}/shop/{slug}"


def collect_competitors(cfg, fetcher, logger, allow_network: bool,
                        etsy_client=None, converter=None):
    """
    Récupère et parse chaque concurrent listé dans la config.

    Stratégie par concurrent :
      1. si une clé API Etsy est dispo -> API officielle (propre, fiable) ;
      2. sinon (ou si l'API échoue) -> parsing HTML public respectueux ;
      3. sinon -> marqué indisponible (mode dégradé).

    Renvoie (profiles, degraded) où degraded=True si AUCUNE donnée n'a été obtenue.
    """
    from src.currency import convert_shop_prices
    competitors = cfg.get("competitors", [])
    my_shop = cfg["shop"]
    rev_cfg = cfg.get("revenue_estimation", {})
    ai_cfg = cfg.get("ai_inference", {})
    use_api = bool(etsy_client and etsy_client.available)

    profiles = []
    any_fetched = False

    for comp in competitors:
        slug = comp.get("slug", "").strip()
        if not slug:
            continue
        market = comp.get("market", "com")
        url = shop_url(slug, market)
        shop = None

        if not allow_network:
            shop = ShopData(slug=slug, market=market, url=url, fetched=False,
                            source_note="mode hors-ligne (--no-network)")
        else:
            # 1) API officielle Etsy en priorité si clé présente
            if use_api:
                logger.info("API Etsy : récupération de %s", slug)
                try:
                    shop = etsy_client.get_shop(slug, market)
                except Exception as e:  # l'API ne doit jamais tuer le run
                    logger.warning("API Etsy en échec pour %s (%s) -> repli HTML",
                                   slug, e)
                if shop is not None:
                    any_fetched = True

            # 2) Repli parsing HTML si pas d'API ou API infructueuse
            if shop is None:
                logger.info("Récupération concurrent (HTML) : %s (%s)", slug, url)
                res = fetcher.get(url)
                if res.ok:
                    any_fetched = True
                    shop = parse_shop_page(res.text, slug, market, url)
                else:
                    reason = ("bloqué par robots.txt" if res.blocked_by_robots
                              else f"échec réseau ({res.error or res.status})")
                    shop = ShopData(slug=slug, market=market, url=url,
                                    fetched=False, source_note=reason)
                    logger.warning("Concurrent %s non récupéré : %s", slug, reason)

        # Conversion des prix en EUR (si devise connue et convertisseur fourni).
        if converter is not None:
            convert_shop_prices(shop, converter)

        profiles.append(build_profile(shop, my_shop, rev_cfg, ai_cfg))

    profiles = rank_competitors(profiles)
    # Dégradé si on n'a obtenu AUCUNE page (réseau bloqué) ou mode hors-ligne.
    degraded = (allow_network and not any_fetched) or (not allow_network)
    return profiles, degraded


def discover_competitors(cfg, fetcher, logger):
    """
    Découverte (best-effort) de slugs concurrents via la recherche Etsy publique.
    En mode dégradé (Etsy bloqué), ne renvoie rien et le note. NON destructif :
    n'écrit pas dans config.yaml, affiche juste des suggestions.
    """
    from bs4 import BeautifulSoup
    import re

    disc = cfg.get("discovery", {})
    if not disc.get("enabled"):
        logger.info("Découverte désactivée dans la config.")
        return []

    found: set[str] = set()
    for query in disc.get("search_queries", []):
        url = f"https://www.etsy.com/search?q={query.replace(' ', '+')}"
        logger.info("Découverte via recherche : %s", query)
        res = fetcher.get(url)
        if not res.ok:
            logger.warning("Recherche '%s' indisponible : %s", query,
                           res.error or res.status)
            continue
        soup = BeautifulSoup(res.text, "lxml")
        for a in soup.find_all("a", href=True):
            m = re.search(r"/shop/([A-Za-z0-9_-]+)", a["href"])
            if m:
                found.add(m.group(1))

    if found:
        logger.info("Slugs concurrents potentiels découverts : %s",
                    ", ".join(sorted(found)))
        print("\nConcurrents potentiels découverts (à valider et ajouter à "
              "config.yaml) :")
        for s in sorted(found):
            print(f"  - {s}")
    else:
        logger.warning("Aucun concurrent découvert (Etsy probablement bloqué). "
                       "À faire manuellement — voir LIMITS.md.")
    return sorted(found)


def run_selftest(cfg, logger) -> int:
    """
    Diagnostic d'environnement. Vérifie ce qui marche AVANT un vrai run, sans
    rien écrire. Très utile au premier lancement sur une nouvelle machine pour
    savoir si Etsy/Trends sont joignables depuis ton réseau.
    """
    print("\n=== SELF-TEST — diagnostic de l'environnement ===\n")
    results: list[tuple[str, str, str]] = []  # (composant, statut, détail)

    # 1. Config
    n_comp = len(cfg.get("competitors", []))
    results.append(("config.yaml", "OK", f"{n_comp} concurrent(s) configuré(s)"))

    # 2. Moteurs d'analyse sur données fictives
    try:
        from src.analysis import build_profile
        from src.demo_fixtures import demo_competitors
        prof = build_profile(demo_competitors()[0], cfg["shop"],
                             cfg.get("revenue_estimation", {}),
                             cfg.get("ai_inference", {}))
        ok = prof.revenue.available and prof.ai.score > 0
        results.append(("moteurs d'analyse", "OK" if ok else "ANOMALIE",
                        "estimation CA + inférence IA fonctionnelles"))
    except Exception as e:
        results.append(("moteurs d'analyse", "ÉCHEC", str(e)))

    # 3. Historique SQLite
    store = HistoryStore()
    results.append(("historique SQLite",
                    "OK" if store.available else "DÉGRADÉ",
                    str(store.db_path) if store.available else "indisponible"))
    store.close()

    # 4. pytrends (présence sans l'importer réellement)
    import importlib.util
    if importlib.util.find_spec("pytrends") is not None:
        results.append(("pytrends (Trends)", "OK", "installé"))
    else:
        results.append(("pytrends (Trends)", "DÉGRADÉ",
                        "non installé (optionnel) -> tendances 'à valider'"))

    # 4b. Clés API (présence des variables d'environnement)
    from src.etsy_api import ENV_KEY as ETSY_ENV
    from src.keywords_api import ENV_KEY as KWE_ENV
    results.append(("clé API Etsy", "OK" if os.environ.get(ETSY_ENV) else "ABSENTE",
                    f"${ETSY_ENV} " + ("définie -> API officielle active"
                    if os.environ.get(ETSY_ENV) else "non définie -> repli HTML")))
    results.append(("clé Keywords Everywhere",
                    "OK" if os.environ.get(KWE_ENV) else "ABSENTE",
                    f"${KWE_ENV} " + ("définie -> volumes réels"
                    if os.environ.get(KWE_ENV) else "non définie -> Google Trends")))

    # 5. Accès réseau Etsy (une seule requête respectueuse)
    fetcher = RespectfulFetcher(cfg["network"])
    test_url = shop_url(cfg["competitors"][0]["slug"] if cfg.get("competitors")
                        else "NeutralWallDesign",
                        cfg["competitors"][0].get("market", "com")
                        if cfg.get("competitors") else "com")
    res = fetcher.get(test_url, use_cache=False)
    if res.ok:
        results.append(("accès Etsy (live)", "OK", f"{test_url} joignable"))
    elif res.blocked_by_robots:
        results.append(("accès Etsy (live)", "BLOQUÉ", "robots.txt interdit"))
    else:
        results.append(("accès Etsy (live)", "INDISPONIBLE",
                        f"{res.error or res.status} — relance depuis ta machine"))

    # 6. Accès Google Trends (probe HTTP simple)
    tr = fetcher.get("https://trends.google.com/trends/", use_cache=False)
    results.append(("accès Google Trends", "OK" if tr.ok else "INDISPONIBLE",
                    "joignable" if tr.ok else f"{tr.error or tr.status}"))

    # Affichage
    width = max(len(c) for c, _, _ in results)
    for comp, status, detail in results:
        icon = {"OK": "✅", "DÉGRADÉ": "🟡", "BLOQUÉ": "🚫", "ABSENTE": "⚪",
                "INDISPONIBLE": "🔌", "ANOMALIE": "⚠️", "ÉCHEC": "❌"}.get(status, "•")
        print(f"  {icon} {comp.ljust(width)}  [{status}]  {detail}")

    degraded = any(s in ("INDISPONIBLE", "BLOQUÉ", "ÉCHEC")
                   for _, s, _ in results if s != "DÉGRADÉ")
    print("\nVerdict :", "⚠️ run live partiel attendu (sources externes bloquées)"
          if degraded else "✅ environnement prêt pour un run complet.")
    print()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Outil d'intelligence marché "
                                                 "Etsy pour NeutralWallDesign.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--no-network", action="store_true",
                        help="Force le mode hors-ligne (rapports dégradés).")
    parser.add_argument("--discover", action="store_true",
                        help="Tente de découvrir de nouveaux concurrents.")
    parser.add_argument("--demo", action="store_true",
                        help="Génère un rapport avec des DONNÉES FICTIVES de "
                             "démonstration (pour voir l'analyse à l'œuvre).")
    parser.add_argument("--selftest", action="store_true",
                        help="Diagnostic d'environnement : config, modules, "
                             "accès Etsy/Trends. N'écrit aucun rapport.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"[ERREUR CONFIG] {e}", file=sys.stderr)
        return 2

    logger = setup_logging(cfg["output"]["logs_dir"], verbose=args.verbose)

    if args.selftest:
        return run_selftest(cfg, logger)

    logger.info("=== Démarrage du run %s ===", date.today().isoformat())

    allow_network = not args.no_network
    fetcher = RespectfulFetcher(cfg["network"])

    # --- Connecteurs API optionnels (actifs seulement si clé en env) ---------
    from src.etsy_api import EtsyApiClient
    from src.keywords_api import KeywordsEverywhereClient
    api_cfg = cfg.get("api", {})
    etsy_client = EtsyApiClient() if api_cfg.get("use_etsy_api", True) else None
    kwe_client = (KeywordsEverywhereClient(
        country=api_cfg.get("keywords_country", "fr"),
        currency=api_cfg.get("keywords_currency", "eur"))
        if api_cfg.get("use_keywords_everywhere", True) else None)
    if etsy_client and etsy_client.available:
        logger.info("API Etsy ACTIVE (clé détectée).")
    if kwe_client and kwe_client.available:
        logger.info("Keywords Everywhere ACTIF (clé détectée).")

    # Convertisseur de devises -> EUR (gratuit, cache + repli statique).
    from src.currency import CurrencyConverter
    fx_cfg = cfg.get("currency_conversion", {})
    converter = (CurrencyConverter(
        cache_path=str(Path(cfg["network"]["cache_dir"]) / "fx_rates.json"),
        ttl_hours=fx_cfg.get("cache_ttl_hours", 24),
        allow_network=allow_network,
        api_url=fx_cfg.get("api_url", "https://api.frankfurter.dev/v1/latest"))
        if fx_cfg.get("enabled", True) else None)

    # --- Découverte optionnelle (non bloquante) ------------------------------
    if args.discover and allow_network:
        try:
            discover_competitors(cfg, fetcher, logger)
        except Exception as e:  # la découverte ne doit jamais tuer le run
            logger.warning("Découverte en échec (ignorée) : %s", e)

    # --- 1. Concurrents ------------------------------------------------------
    if args.demo:
        logger.warning("MODE DÉMO : utilisation de DONNÉES FICTIVES "
                       "(aucune donnée réelle).")
        from src.currency import convert_shop_prices
        from src.demo_fixtures import demo_competitors
        rev_cfg = cfg.get("revenue_estimation", {})
        ai_cfg = cfg.get("ai_inference", {})
        demo_shops = demo_competitors()
        if converter is not None:
            for s in demo_shops:
                convert_shop_prices(s, converter)  # montre la conversion en EUR
        profiles = rank_competitors([
            build_profile(s, cfg["shop"], rev_cfg, ai_cfg) for s in demo_shops])
        degraded = False  # on a des données (fictives mais complètes)
    else:
        profiles, degraded = collect_competitors(cfg, fetcher, logger,
                                                 allow_network, etsy_client,
                                                 converter)

    # --- 2. Tendances (optionnel, dégrade gracieusement) ---------------------
    niche_cfg = cfg["niche"]
    trend_keywords = (niche_cfg.get("emerging_subniches", [])
                      + niche_cfg.get("pillars", []))
    if allow_network:
        trend_results = fetch_trends(trend_keywords[:10])  # limite raisonnable
    else:
        from src.trends import TrendResult
        trend_results = [TrendResult(k, available=False,
                         note="mode hors-ligne") for k in trend_keywords]

    # --- 3. Volumes de recherche réels (Keywords Everywhere, optionnel) ------
    volumes = {}
    if kwe_client and kwe_client.available and allow_network and not args.demo:
        try:
            volumes = kwe_client.get_volumes(trend_keywords)
            logger.info("Keywords Everywhere : %d volumes récupérés.", len(volumes))
        except Exception as e:  # ne jamais tuer le run
            logger.warning("Keywords Everywhere en échec (ignoré) : %s", e)

    # --- 4. Opportunités SEO -------------------------------------------------
    opportunities = build_opportunities(niche_cfg, trend_results, volumes)

    # --- 5. Prompts Grok du jour ---------------------------------------------
    prompts = generate_daily_prompts(cfg["grok_prompts"], niche_cfg,
                                      opportunities)

    # --- 6. Historisation + diffs (vraie veille jour à jour) --------------
    deltas = {}
    if not args.demo:  # on n'historise pas les données fictives
        store = HistoryStore()
        shops_now = [p.shop for p in profiles]
        deltas = store.compute_deltas(shops_now, today_str())
        store.save_snapshot(today_str(), shops_now)
        store.close()

    # --- 7. Rendu des rapports -----------------------------------------------
    competitors_md = render_competitors(profiles, cfg["shop"], degraded, deltas)
    prompts_md = render_grok_prompts(prompts)
    guidelines_md = render_guidelines(profiles, opportunities, cfg["shop"],
                                      cfg.get("goals", {}), degraded)

    if args.demo:
        banner = ("> 🧪 **RAPPORT DE DÉMONSTRATION — DONNÉES FICTIVES.** Les "
                  "boutiques, ventes et prix « DEMO_* » ci-dessous sont INVENTÉS "
                  "pour illustrer le fonctionnement des moteurs d'analyse. "
                  "Ne PAS les prendre pour des données réelles.\n\n")
        competitors_md = banner + competitors_md
        guidelines_md = banner + guidelines_md

    # guidelines_claude_chat.md = SUR-ENSEMBLE (stratégie + veille + prompts) pour
    # que Claude chat ait tout le contexte en un seul copier-coller. Les fichiers
    # veille_concurrents.md et prompts_grok_du_jour.md restent générés séparément.
    from src.report_generator import build_merged_guidelines
    guidelines_merged = build_merged_guidelines(guidelines_md, competitors_md,
                                                prompts_md)

    paths = write_reports(cfg["output"]["reports_dir"], competitors_md,
                          prompts_md, guidelines_merged)

    logger.info("=== Run terminé %s ===", "(MODE DÉGRADÉ)" if degraded else "")
    print("\n✅ Rapports générés :")
    for name, path in paths.items():
        print(f"   - {path}")
    if degraded:
        print("\n⚠️  MODE DÉGRADÉ : accès live à Etsy indisponible dans cet "
              "environnement. Relance depuis ta machine pour des données réelles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
