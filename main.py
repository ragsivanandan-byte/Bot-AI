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

Usage :
    python main.py                 # run complet
    python main.py --no-network    # force le mode hors-ligne (rapports dégradés)
    python main.py --discover      # tente la découverte de nouveaux concurrents
    python main.py --verbose       # logs détaillés
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from src.analysis import build_profile, rank_competitors
from src.config_loader import ConfigError, load_config
from src.etsy_parser import ShopData, parse_shop_page
from src.fetcher import RespectfulFetcher
from src.prompt_generator import generate_daily_prompts
from src.report_generator import (render_competitors, render_grok_prompts,
                                   render_guidelines, write_reports)
from src.seo import build_opportunities
from src.trends import fetch_trends
from src.utils import setup_logging


def shop_url(slug: str, market: str) -> str:
    """Construit l'URL d'une boutique Etsy à partir de son slug et marché."""
    market = (market or "com").strip("/")
    if market in ("com", ""):
        return f"https://www.etsy.com/shop/{slug}"
    return f"https://www.etsy.com/{market}/shop/{slug}"


def collect_competitors(cfg, fetcher, logger, allow_network: bool):
    """
    Récupère et parse chaque concurrent listé dans la config.
    Renvoie (profiles, degraded) où degraded=True si AUCUNE page n'a été obtenue.
    """
    competitors = cfg.get("competitors", [])
    my_shop = cfg["shop"]
    rev_cfg = cfg.get("revenue_estimation", {})
    ai_cfg = cfg.get("ai_inference", {})

    profiles = []
    any_fetched = False

    for comp in competitors:
        slug = comp.get("slug", "").strip()
        if not slug:
            continue
        market = comp.get("market", "com")
        url = shop_url(slug, market)

        if not allow_network:
            shop = ShopData(slug=slug, market=market, url=url, fetched=False,
                            source_note="mode hors-ligne (--no-network)")
        else:
            logger.info("Récupération concurrent : %s (%s)", slug, url)
            res = fetcher.get(url)
            if res.ok:
                any_fetched = True
                shop = parse_shop_page(res.text, slug, market, url)
            else:
                reason = ("bloqué par robots.txt" if res.blocked_by_robots
                          else f"échec réseau ({res.error or res.status})")
                shop = ShopData(slug=slug, market=market, url=url, fetched=False,
                                source_note=reason)
                logger.warning("Concurrent %s non récupéré : %s", slug, reason)

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
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"[ERREUR CONFIG] {e}", file=sys.stderr)
        return 2

    logger = setup_logging(cfg["output"]["logs_dir"], verbose=args.verbose)
    logger.info("=== Démarrage du run %s ===", date.today().isoformat())

    allow_network = not args.no_network
    fetcher = RespectfulFetcher(cfg["network"])

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
        from src.demo_fixtures import demo_competitors
        rev_cfg = cfg.get("revenue_estimation", {})
        ai_cfg = cfg.get("ai_inference", {})
        profiles = rank_competitors([
            build_profile(s, cfg["shop"], rev_cfg, ai_cfg)
            for s in demo_competitors()])
        degraded = False  # on a des données (fictives mais complètes)
    else:
        profiles, degraded = collect_competitors(cfg, fetcher, logger,
                                                 allow_network)

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

    # --- 3. Opportunités SEO -------------------------------------------------
    opportunities = build_opportunities(niche_cfg, trend_results)

    # --- 4. Prompts Grok du jour ---------------------------------------------
    prompts = generate_daily_prompts(cfg["grok_prompts"], niche_cfg,
                                      opportunities)

    # --- 5. Rendu des rapports -----------------------------------------------
    competitors_md = render_competitors(profiles, cfg["shop"], degraded)
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

    paths = write_reports(cfg["output"]["reports_dir"], competitors_md,
                          prompts_md, guidelines_md)

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
