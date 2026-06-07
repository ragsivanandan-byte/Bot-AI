"""
test_extended.py — Tests exhaustifs (chemins succès ET échec) de TOUS les modules.

Complète test_core.py. Couvre, via des doublures réseau (sans vrai réseau) :
config, fetcher (robots/cache/retry/403/panne), parser (cas variés), analyse,
trends, seo, prompts, rapports, storage, currency, connecteurs API, et le
câblage de main(). Aucune dépendance à pytest.

Lancement :  python tests/test_extended.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests._fakes import FakeResponse, FakeSession, RequestException  # noqa: E402

_FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ✅ {msg}")
    else:
        print(f"  ❌ {msg}")
        _FAILURES.append(msg)


def _net_cfg(cache_dir: str, **over) -> dict:
    cfg = {"user_agent": "Test/1.0", "request_timeout_seconds": 5,
           "min_delay_seconds": 0, "max_delay_jitter_seconds": 0,
           "max_retries": 3, "backoff_base_seconds": 0.0,
           "respect_robots_txt": False, "cache_ttl_hours": 1,
           "cache_dir": cache_dir}
    cfg.update(over)
    return cfg


# --- config_loader -----------------------------------------------------------

def test_config_errors():
    print("\n[config_loader : erreurs]")
    from src.config_loader import ConfigError, load_config

    try:
        load_config("/n/existe/pas.yaml")
        check(False, "fichier absent -> ConfigError")
    except ConfigError:
        check(True, "fichier absent -> ConfigError")

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write("ceci: [n'est pas: valide")  # YAML cassé
        bad = f.name
    try:
        load_config(bad)
        check(False, "YAML invalide -> ConfigError")
    except ConfigError:
        check(True, "YAML invalide -> ConfigError")
    finally:
        os.unlink(bad)

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write("shop: {}\n")  # sections obligatoires manquantes
        incomplete = f.name
    try:
        load_config(incomplete)
        check(False, "sections manquantes -> ConfigError")
    except ConfigError:
        check(True, "sections manquantes -> ConfigError")
    finally:
        os.unlink(incomplete)


def test_config_defaults():
    print("\n[config_loader : valeurs par défaut]")
    from src.config_loader import load_config
    minimal = ("shop: {name: X}\nniche: {pillars: []}\nnetwork: {}\n"
               "grok_prompts: {}\noutput: {}\n")
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(minimal)
        path = f.name
    try:
        cfg = load_config(path)
        check(cfg["network"]["max_retries"] == 4, "défaut max_retries appliqué")
        check(cfg["grok_prompts"]["count_per_day"] == 5, "défaut count_per_day")
        check(cfg["output"]["reports_dir"] == "reports", "défaut reports_dir")
        check("competitors" in cfg, "clé competitors créée par défaut")
    finally:
        os.unlink(path)


# --- fetcher -----------------------------------------------------------------

def test_fetcher_robots_block():
    print("\n[fetcher : robots.txt bloque]")
    from src.fetcher import RespectfulFetcher
    with tempfile.TemporaryDirectory() as tmp:
        f = RespectfulFetcher(_net_cfg(tmp, respect_robots_txt=True))

        def handler(method, url, params, data, n):
            if url.endswith("robots.txt"):
                return FakeResponse(200, text="User-agent: *\nDisallow: /")
            return FakeResponse(200, text="<html>secret</html>")
        f._session = FakeSession(handler)
        res = f.get("https://example.com/shop/X")
        check(res.blocked_by_robots and not res.ok,
              "page interdite par robots.txt -> blocked, pas de contenu")


def test_fetcher_cache_and_status():
    print("\n[fetcher : cache, 200, 403, retry 5xx, panne réseau]")
    from src.fetcher import RespectfulFetcher

    # 200 + cache (2e appel ne refait pas de requête)
    with tempfile.TemporaryDirectory() as tmp:
        f = RespectfulFetcher(_net_cfg(tmp))
        f._session = FakeSession(lambda *a: FakeResponse(200, text="OK-BODY"))
        r1 = f.get("https://e.com/p")
        r2 = f.get("https://e.com/p")
        check(r1.ok and "OK-BODY" in r1.text, "HTTP 200 -> contenu renvoyé")
        check(r2.from_cache and f._session.n_get == 1, "2e appel servi par le cache")

    # 403 -> pas de retry
    with tempfile.TemporaryDirectory() as tmp:
        f = RespectfulFetcher(_net_cfg(tmp))
        f._session = FakeSession(lambda *a: FakeResponse(403))
        r = f.get("https://e.com/p")
        check(not r.ok and r.status == 403 and f._session.n_get == 1,
              "HTTP 403 -> pas de retry (respect du refus)")

    # 500 puis 200 -> retry réussi
    with tempfile.TemporaryDirectory() as tmp:
        f = RespectfulFetcher(_net_cfg(tmp))
        f._session = FakeSession(
            lambda m, u, p, d, n: FakeResponse(500) if n == 1 else FakeResponse(200, text="Y"))
        r = f.get("https://e.com/p")
        check(r.ok and f._session.n_get == 2, "HTTP 500 puis 200 -> retry réussi")

    # panne réseau puis succès
    with tempfile.TemporaryDirectory() as tmp:
        f = RespectfulFetcher(_net_cfg(tmp))

        def flaky(m, u, p, d, n):
            if n == 1:
                raise RequestException("boom")
            return FakeResponse(200, text="Z")
        f._session = FakeSession(flaky)
        r = f.get("https://e.com/p")
        check(r.ok and f._session.n_get == 2, "panne réseau puis succès -> retry")


def test_fetcher_cache_expiry():
    print("\n[fetcher : expiration du cache]")
    from src.fetcher import RespectfulFetcher
    with tempfile.TemporaryDirectory() as tmp:
        f = RespectfulFetcher(_net_cfg(tmp, cache_ttl_hours=1))
        url = "https://e.com/x"
        f._write_cache(url, "vieux")
        check(f._read_cache(url) == "vieux", "cache frais relu")
        old = time.time() - 7200  # 2h -> au-delà du TTL de 1h
        os.utime(f._cache_path(url), (old, old))
        check(f._read_cache(url) is None, "cache expiré -> None")


# --- etsy_parser (cas variés) ------------------------------------------------

def test_parser_variants():
    print("\n[etsy_parser : variantes]")
    from src.etsy_parser import parse_shop_page

    # Prix bornés (500 exclu car > 80), prix barré via <del>
    html = ('<html><body><del>$20.00</del> <span>$12.00</span> '
            '<span>$500.00</span></body></html>')
    d = parse_shop_page(html, "S", "com", "u")
    check(d.has_strikethrough_price is True, "prix barré détecté via <del>")
    # Prix plausibles retenus (20, 12) ; 500 exclu car hors bornes (> 80 €).
    check(d.price_max_eur == 20.0 and d.price_min_eur == 12.0,
          "prix aberrant (500) exclu, bornes 12-20 retenues")

    # JSON-LD avec liste d'offres
    html2 = ('<html><body><script type="application/ld+json">'
             '{"offers":[{"price":"5.00"},{"price":"9.00"}]}</script>'
             '<h3>Boho Terracotta Printable Set of 3 Neutral</h3></body></html>')
    d2 = parse_shop_page(html2, "S", "com", "u")
    check(abs(d2.avg_price_eur - 7.0) < 0.01, "moyenne JSON-LD liste (5,9)->7")
    check(len(d2.sample_titles) >= 1, "titre de fiche collecté")


# --- analysis (compléments) --------------------------------------------------

def test_analysis_extras():
    print("\n[analysis : compléments]")
    from src.analysis import (ai_inference, build_profile, estimate_revenue,
                              rank_competitors, _formats_label)
    from src.etsy_parser import ShopData

    # rank : None en dernier
    a = ShopData("A", "com", "u", total_sales=100)
    b = ShopData("B", "com", "u", total_sales=None)
    c = ShopData("C", "com", "u", total_sales=500)
    ranked = rank_competitors([build_profile(s, {}, {}, {}) for s in (a, b, c)])
    check([p.shop.slug for p in ranked] == ["C", "A", "B"],
          "classement par ventes, None en dernier")

    # estimate_revenue avec prix de repli
    rev = {"fallback_avg_price_eur_low": 4, "fallback_avg_price_eur_high": 12,
           "recent_sales_share_low": 0.02, "recent_sales_share_high": 0.08}
    e = estimate_revenue(ShopData("X", "com", "u", total_sales=1000), rev)
    check(e.available and e.lifetime_low_eur == 4000 and e.lifetime_high_eur == 12000,
          "CA avec fourchette de prix de repli (4-12)")

    # ai_inference désactivée
    off = ai_inference(ShopData("X", "com", "u"), {"enabled": False})
    check(not off.probably_ai and "désactivée" in off.signals[0],
          "heuristique IA désactivable")

    # _formats_label détecte les sets
    lab = _formats_label(ShopData("X", "com", "u",
                                  sample_titles=["Wabi Set of 3 art"]))
    check("sets" in lab, "_formats_label détecte sets/bundles")

    # faille : catalogue étroit
    narrow = ShopData("N", "com", "u", total_sales=100, active_listings=20,
                      avg_price_eur=10.0, has_strikethrough_price=True)
    prof = build_profile(narrow, {"total_sales": 1, "active_listings": 16,
                                  "reviews": 1}, rev, {"enabled": True,
                         "threshold": 99, "weights": {}})
    check("traîne" in prof.exploitable_gap or "étroit" in prof.exploitable_gap,
          "faille 'catalogue étroit' identifiée")


# --- trends ------------------------------------------------------------------

def test_trends():
    print("\n[trends : direction, absent, succès simulé]")
    import src.trends as trends_mod
    from src.trends import _trend_direction, fetch_trends

    check(_trend_direction([10, 10, 30, 40]) == "montant", "direction montante")
    check(_trend_direction([40, 30, 10, 5]) == "déclin", "direction déclin")
    check(_trend_direction([20, 21, 19, 20]) == "stable", "direction stable")

    # Absent -> tout indisponible
    saved = trends_mod._safe_import_pytrends
    trends_mod._safe_import_pytrends = lambda: None
    try:
        res = fetch_trends(["japandi wall art"])
        check(len(res) == 1 and not res[0].available, "pytrends absent -> indisponible")
    finally:
        trends_mod._safe_import_pytrends = saved

    # Succès simulé via faux TrendReq (avec pandas)
    try:
        import pandas as pd

        class FakeTrendReq:
            def __init__(self, *a, **k):
                self.batch = []
            def build_payload(self, batch, timeframe="", geo=""):
                self.batch = batch
            def interest_over_time(self):
                data = {kw: [10, 20, 30, 40] for kw in self.batch}
                data["isPartial"] = [False] * 4
                return pd.DataFrame(data)
        trends_mod._safe_import_pytrends = lambda: FakeTrendReq
        res = fetch_trends(["japandi wall art"])
        check(res[0].available and res[0].direction == "montant",
              "succès simulé -> tendance montante détectée")
        check(res[0].relative_interest == 25.0, "intérêt relatif moyen calculé (25)")
    except ImportError:
        check(True, "pandas absent -> test succès Trends ignoré (OK)")
    finally:
        trends_mod._safe_import_pytrends = saved


# --- seo ---------------------------------------------------------------------

def test_seo_extras():
    print("\n[seo : saturation, matching]")
    from src.seo import build_opportunities
    niche = {"emerging_subniches": ["boho rainbow generic art"],
             "pillars": ["japandi wall art"],
             "saturated_topics": ["boho rainbow generic"]}
    ops = build_opportunities(niche, [])
    sat = next(o for o in ops if "rainbow" in o.keyword)
    check(sat.saturated and sat.confirmation == "à valider",
          "sujet saturé -> marqué et rétrogradé 'à valider'")


# --- prompt_generator --------------------------------------------------------

def test_prompts_extras():
    print("\n[brief visuel : repli config vide, rotation des recettes par date]")
    from datetime import date
    from src.prompt_generator import generate_daily_brief
    from src.seo import SeoOpportunity

    ops = [SeoOpportunity("neutral wall art", "à valider", "x", ["cfg"])]
    # Config vide -> recette de repli, jamais de crash
    b = generate_daily_brief({}, {"saturated_topics": []}, ops)
    check(len(b.raw_prompts) == 3 and len(b.mockup_prompts) == 4,
          "config vide -> recette de repli (3 images + 4 mockups)")

    # Rotation : 2 recettes -> dates consécutives donnent des thèmes différents
    grok = {"palette": ["a", "b"], "mockup_rooms": ["r1", "r2"], "set_recipes": [
        {"name": "Theme A", "keyword": "a", "format": "2:3 vertical",
         "designs": ["d1", "d2", "d3"]},
        {"name": "Theme B", "keyword": "b", "format": "16:9 horizontal",
         "designs": ["e1", "e2", "e3"]}]}
    d1 = generate_daily_brief(grok, {"saturated_topics": []}, ops, date(2026, 6, 1))
    d2 = generate_daily_brief(grok, {"saturated_topics": []}, ops, date(2026, 6, 2))
    check(d1.theme != d2.theme, "rotation quotidienne des recettes (thème différent)")
    check("rainbow" in d1.raw_prompts[0].prompt_text.lower(),
          "negative anti-arc-en-ciel présent dans l'image brute")


# --- report_generator --------------------------------------------------------

def test_reports():
    print("\n[report_generator : sections des 3 rapports]")
    from src.analysis import build_profile
    from src.etsy_parser import ShopData
    from src.prompt_generator import generate_daily_brief
    from src.report_generator import (_render_deltas_section,
                                      render_competitors, render_grok_prompts,
                                      render_guidelines)
    from src.seo import build_opportunities
    from src.storage import CompetitorDelta

    shop = ShopData("Riv", "com", "u", fetched=True, total_sales=3000,
                    active_listings=50, reviews=400, avg_price_eur=12.0)
    prof = build_profile(shop, {"total_sales": 1, "active_listings": 16,
                                "reviews": 1}, {}, {"enabled": True,
                        "threshold": 4, "weights": {}})
    comp = render_competitors([prof], {}, degraded=False)
    check("Top concurrents" in comp and "Estimation de CA" in comp,
          "veille : sections clés présentes")
    check("Évolution depuis le dernier run" in comp, "veille : section évolution")

    # Deltas : 3 variantes
    check("Premier run" in _render_deltas_section({}), "deltas : premier run")
    nochange = {"A": CompetitorDelta("A", "2026-05-30")}
    check("Aucun changement" in _render_deltas_section(nochange),
          "deltas : aucun changement")
    changed = {"A": CompetitorDelta("A", "2026-05-30", sales_delta=120,
                                    listings_delta=3)}
    out = _render_deltas_section(changed)
    check("Δ ventes" in out and "+120" in out, "deltas : variation affichée")

    ops = build_opportunities({"emerging_subniches": ["x"], "pillars": [],
                               "saturated_topics": []}, [])
    brief = generate_daily_brief({"palette": ["a"], "mockup_rooms": ["r"]},
                                 {"saturated_topics": ["nursery"]}, ops)
    pm = render_grok_prompts(brief)
    check("Images BRUTES" in pm and "MOCKUPS" in pm and "VIDÉO" in pm,
          "brief : 3 sections (images / mockups / vidéo)")
    check("COVER" in pm and "~/Downloads" in pm,
          "brief : cover identifiée + sortie ~/Downloads")

    gm = render_guidelines([prof], ops, {"avg_price_eur": 6.0},
                           {"target_net_eur_per_month": 5000}, degraded=False)
    for section in ("Roadmap vers 5000", "Pinterest", "Publicité",
                    "Opportunités SEO"):
        check(section in gm, f"guidelines : section '{section}' présente")

    # Bloc unique pour Claude chat : mission QC+fiche en tête, prompts, puis
    # veille (Annexe A) et stratégie (Annexe B) en référence.
    from src.report_generator import build_merged_guidelines
    merged = build_merged_guidelines(gm, comp, pm)
    check("BLOC À COLLER DANS CLAUDE CHAT" in merged,
          "fusion : mène par la mission du jour (bloc à coller)")
    check("Fiche Etsy complète" in merged and "13 tags" in merged
          and "6,90" in merged,
          "fusion : livrables fiche Etsy (titre/tags/prix) demandés")
    check("Prompts Grok du jour" in merged and "MOCKUPS" in merged,
          "fusion : prompts du jour intégrés")
    check("ANNEXE A" in merged and "Top concurrents" in merged,
          "fusion : veille en annexe A")
    check("ANNEXE B" in merged and "Roadmap vers 5000" in merged,
          "fusion : stratégie de référence en annexe B")
    # Les fichiers séparés restent intacts (pas d'annexe dedans)
    check("ANNEXE A" not in comp and "ANNEXE A" not in pm,
          "fusion : veille et prompts restent autonomes (pas d'annexe injectée)")

    # Veille hebdo IA (Annexe C) : ne liste que les miroirs IA, exclut handmade
    from src.report_generator import render_weekly_ai_watch
    from src.storage import CompetitorDelta
    mirror = ShopData("MyAestheticAlley", "com", "u", fetched=True,
                      total_sales=1200, reviews=81, avg_price_eur=14.0,
                      ai_mirror=True)
    handmade = ShopData("MusingsOfMeiMei", "com", "u", fetched=True,
                        total_sales=28300, declared_handmade=True)
    profs = [build_profile(mirror, {}, {}, {"enabled": True, "threshold": 4,
                                            "weights": {}}),
             build_profile(handmade, {}, {}, {"enabled": True, "threshold": 4,
                                              "weights": {}})]
    wk = {"MyAestheticAlley": CompetitorDelta("MyAestheticAlley", "2026-05-30",
                                              sales_delta=40, reviews_delta=5)}
    watch = render_weekly_ai_watch(profs, wk)
    check("Veille hebdo" in watch and "MyAestheticAlley" in watch,
          "veille hebdo : miroir IA listé")
    check("| MusingsOfMeiMei |" not in watch,
          "veille hebdo : fait-main (MeiMei) absent du tableau IA")
    check("+40" in watch, "veille hebdo : Δ7j ventes affiché")
    merged2 = build_merged_guidelines(gm, comp, pm, watch)
    check("ANNEXE C" in merged2 and "Veille hebdo" in merged2,
          "fusion : veille hebdo intégrée en Annexe C quand fournie")


def test_automation_scripts():
    print("\n[automation : scripts launchd valides]")
    import subprocess
    base = Path(__file__).resolve().parent.parent / "automation"
    for name in ("run_daily.sh", "install_daily.sh", "uninstall_daily.sh"):
        p = base / name
        check(p.exists(), f"script présent : {name}")
        rc = subprocess.run(["bash", "-n", str(p)], capture_output=True).returncode
        check(rc == 0, f"syntaxe bash valide : {name}")
    # Le script d'install doit programmer 7h00 et viser le bon dossier.
    txt = (base / "install_daily.sh").read_text(encoding="utf-8")
    check('HOUR="${1:-5}"' in txt, "install : heure réglable (défaut 5h)")
    check('MINUTE="${2:-0}"' in txt, "install : minute réglable (ex. 5 30 -> 5h30)")
    check("run_daily.sh" in txt, "install : pointe vers run_daily.sh")
    rd = (base / "run_daily.sh").read_text(encoding="utf-8")
    check(".grok/bin" in rd, "run_daily : ajoute ~/.grok/bin au PATH (grok en launchd)")


def test_image_pipeline():
    print("\n[image_pipeline : profils set/single, naming, JPEG, ABORT (spec Claude Chat)]")
    try:
        from PIL import Image
    except Exception:
        check(True, "Pillow absent -> test ignoré (OK)")
        return
    from src.image_pipeline import (RATIOS, export_ratio, jpeg_info, profile_for,
                                    upscale_x4, validate_input_stem)

    # 1) Dimensions de PRODUCTION (calcul pur, sans rendu lourd)
    set_p = profile_for("set", {})
    sng_p = profile_for("single", {})
    set_dims = {rk: (round(6912 * w / h), 6912) for rk, (w, h) in RATIOS.items()}
    check(set_dims["2x3"] == (4608, 6912) and set_dims["4x5"] == (5530, 6912)
          and set_dims["11x14"] == (5431, 6912), "SET : ancrage hauteur 6912 (dims exactes)")
    sng_2x3 = (4608, round(4608 * 3 / 2))
    sng_3x4 = (4608, round(4608 * 4 / 3))
    check(sng_2x3 == (4608, 6912) and sng_3x4 == (4608, 6144),
          "SINGLE : ancrage largeur 4608 -> 2x3=4608x6912, 3x4=4608x6144")
    check(set_p["ratios"] == ["2x3", "3x4", "4x5", "5x7", "11x14"]
          and sng_p["ratios"] == ["2x3", "3x4"], "ratios par profil")

    # 2) Validation du nommage NWD
    validate_input_stem("NWD_T1_WarmShapes_Dune", "set")
    validate_input_stem("NWD_T2_OliveBranch", "single")
    for bad, kind in [("grok_design_1", "set"), ("NWD_T1_OliveBranch", "set"),
                      ("NWD_T1_A_B", "single")]:
        try:
            validate_input_stem(bad, kind); ok = False
        except ValueError:
            ok = True
        check(ok, f"nom invalide rejeté : {bad} ({kind})")

    # 3) Upscale : absent + fallback false -> ABORT ; fallback true -> Lanczos ×4
    tmp = tempfile.mkdtemp()
    src = Path(tmp) / "in.png"
    Image.new("RGB", (40, 60), (181, 117, 79)).save(src)
    up = Path(tmp) / "up.png"
    try:
        upscale_x4(str(src), str(up), command="", fallback_lanczos=False); ok = False
    except RuntimeError:
        ok = True
    check(ok, "upscaler absent + fallback_lanczos=false -> ABORT")
    mode = upscale_x4(str(src), str(up), command="", fallback_lanczos=True)
    check(mode == "lanczos" and Image.open(up).size == (160, 240),
          "fallback Lanczos ×4 (40x60 -> 160x240)")

    # 4) export_ratio : math + JPEG metadata (petit anchor pour rester léger)
    master = Image.new("RGB", (300, 450), (181, 117, 79))
    d = Path(tmp) / "NWD_T1_WS_Dune_2x3.jpg"
    w, h = export_ratio(master, "2x3", "height", 90, str(d), {"quality": 90})
    check((w, h) == (60, 90), "export ancrage hauteur (2x3 @90 -> 60x90)")
    info = jpeg_info(str(d))
    check(info["dpi"] == (300, 300), "JPEG : 300 DPI")
    check(info["mode"] == "RGB", "JPEG : mode RGB")
    check(info["icc"], "JPEG : profil sRGB intégré")
    w2, h2 = export_ratio(master, "3x4", "width", 90, str(Path(tmp) / "s_3x4.jpg"))
    check((w2, h2) == (90, 120), "export ancrage largeur (single 3x4 @90 -> 90x120)")

    # 5) ABORT si master trop petit (jamais d'agrandissement)
    tiny = Image.new("RGB", (50, 50))
    try:
        export_ratio(tiny, "2x3", "height", 6912, str(Path(tmp) / "x.jpg")); ok = False
    except ValueError:
        ok = True
    check(ok, "master trop petit -> ABORT (pas de ré-upscale au resize)")


def test_upscale_cli_any_name():
    print("\n[upscale_and_export : upscale TOUT fichier (nom quelconque)]")
    try:
        from PIL import Image
    except Exception:
        check(True, "Pillow absent -> test ignoré (OK)")
        return
    import importlib.util
    from datetime import date
    import yaml

    repo = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "upscale_and_export", repo / "automation" / "upscale_and_export.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["upscale_and_export"] = mod
    spec.loader.exec_module(mod)

    tmp = tempfile.mkdtemp()
    with open(repo / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["image_pipeline"] = {
        "downloads_dir": tmp, "to_upscale_dir": "In", "output_root": f"{tmp}/Out",
        "date_subdir": True, "masters_subdir": "Upscaled",
        "crops_by_ratio_subdirs": True, "default_type": "set",
        "validate_naming": False,
        "profiles": {"set": {"anchor": "height", "anchor_px": 90,
                             "ratios": ["2x3", "3x4"], "min_master_width": 100}},
        "jpeg": {"quality": 90, "subsampling": 0, "optimize": True, "dpi": [300, 300]},
        "upscale": {"command": "", "fallback_lanczos": True}}
    day = date.today().strftime("%d-%m-%Y")
    indir = Path(tmp) / "In" / day
    indir.mkdir(parents=True)
    Image.new("RGB", (40, 60), (180, 120, 90)).save(indir / "random name 123.png")
    cfgp = Path(tmp) / "c.yaml"
    with open(cfgp, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)

    rc = mod.main(["--type", "set", "--config", str(cfgp)])
    check(rc == 0, "CLI traite un fichier au nom quelconque (validate_naming=false)")
    jpgs = list((Path(tmp) / "Out" / day).glob("Final/**/*.jpg"))
    check(len(jpgs) == 2, "2 ratios exportés depuis un nom non-NWD")
    check(any(p.name == "random name 123_2x3.jpg" for p in jpgs),
          "sortie nommée <nom_du_fichier>_<ratio>.jpg")
    check((Path(tmp) / "Out" / day / "Upscaled" /
           "random name 123_upscaled.png").exists(), "master _upscaled.png présent")


def test_zip_outputs():
    print("\n[grok_generate : ZIP des images brutes]")
    import importlib.util
    base = Path(__file__).resolve().parent.parent / "automation"
    spec = importlib.util.spec_from_file_location("grok_generate",
                                                  base / "grok_generate.py")
    gg = importlib.util.module_from_spec(spec)
    sys.modules["grok_generate"] = gg
    spec.loader.exec_module(gg)
    import zipfile
    tmp = tempfile.mkdtemp()
    files = []
    for i in range(3):
        f = Path(tmp) / f"img_{i}.png"
        f.write_bytes(b"PNGDATA")
        files.append(f)
    files.append(Path(tmp) / "missing.png")   # inexistant -> ignoré
    zp = Path(tmp) / "24images_grok_brut.zip"
    n = gg.zip_outputs(files, zp)
    check(n == 3 and zp.exists(), "ZIP créé avec les 3 images existantes")
    with zipfile.ZipFile(zp) as z:
        check(sorted(z.namelist()) == ["img_0.png", "img_1.png", "img_2.png"],
              "ZIP contient les bons fichiers (noms à plat)")


def test_mockup_compositor():
    print("\n[mockup_compositor : compositing exact dans une zone chroma]")
    try:
        from PIL import Image
    except Exception:
        check(True, "Pillow absent -> test compositing ignoré (OK)")
        return
    from src.mockup_compositor import (composite_into_template,
                                       find_placeholder_quad)

    import numpy as np
    tmp = tempfile.mkdtemp()
    tpl = Path(tmp) / "tpl.png"
    design = Path(tmp) / "design.png"
    out = Path(tmp) / "out.png"

    # Gabarit : décor non uni (pour tester l'intégrité hors-zone) + rectangle
    # vert "sale" RGB(9,187,13) comme le vrai green-screen mesuré par Claude Chat.
    t = Image.new("RGB", (240, 180), (200, 180, 160))
    t.putpixel((3, 3), (123, 45, 67))     # pixel témoin hors-zone (couleur unique)
    for x in range(60, 180):
        for y in range(40, 140):
            t.putpixel((x, y), (9, 187, 13))
    t.save(tpl)
    Image.new("RGB", (120, 100), (220, 30, 30)).save(design)   # design rouge

    quad = find_placeholder_quad(str(tpl))
    check(quad is not None and len(quad) == 4,
          "zone chroma détectée (vert 'sale' RGB 9,187,13)")

    before = np.asarray(Image.open(tpl).convert("RGB"))
    ok = composite_into_template(str(design), str(tpl), str(out))
    check(ok and out.exists(), "compositing réussi, fichier écrit")
    after = np.asarray(Image.open(out).convert("RGB"))

    r, g, b = [int(v) for v in after[90, 120]]      # centre ancienne zone verte
    check(r > 150 and g < 100 and b < 100, "design (rouge) collé dans la zone")
    check(not (g > 150 and r < 100), "le vert chroma a été recouvert")

    # GARANTIE clé : hors de la zone verte, le gabarit est IDENTIQUE au pixel.
    mask = (before[:, :, 1] > 110) & (before[:, :, 1] - before[:, :, 0] > 35) \
        & (before[:, :, 1] - before[:, :, 2] > 35)
    non_green_identical = np.array_equal(after[~mask], before[~mask])
    check(non_green_identical, "hors-zone-verte : gabarit STRICTEMENT identique")
    check(tuple(int(v) for v in after[3, 3]) == (123, 45, 67),
          "pixel témoin hors-zone inchangé")


def test_make_mockups_helpers():
    print("\n[make_mockups : construction des commandes vidéo/ffmpeg]")
    import importlib.util
    base = Path(__file__).resolve().parent.parent / "automation"
    spec = importlib.util.spec_from_file_location("make_mockups",
                                                  base / "make_mockups.py")
    mm = importlib.util.module_from_spec(spec)
    sys.modules["make_mockups"] = mm
    spec.loader.exec_module(mm)

    check(mm._ratio_tag("16:9 horizontal") == "16x9", "ratio tag 16:9 -> 16x9")
    check(mm._ratio_tag("2:3 vertical") == "2x3", "ratio tag 2:3 -> 2x3")

    vc = mm.video_cmd("grok", "anim prompt", "/d/Cover.png", "/d/V.mp4")
    check(vc[0] == "grok" and "Cover.png" in vc[2] and "MP4 file" in vc[2],
          "video_cmd : source = cover composite + sortie MP4")
    fc = mm.ffmpeg_strip_cmd("/d/raw.mp4", "/d/V.mp4")
    check("-an" in fc and "ffmpeg" in fc[0], "ffmpeg : audio retiré (-an)")


def test_grok_runner():
    print("\n[grok_generate : jobs + orchestration (runner simulé, sans grok)]")
    import importlib.util
    from datetime import date
    from src.prompt_generator import generate_daily_brief

    base = Path(__file__).resolve().parent.parent / "automation"
    spec = importlib.util.spec_from_file_location("grok_generate",
                                                  base / "grok_generate.py")
    gg = importlib.util.module_from_spec(spec)
    sys.modules["grok_generate"] = gg  # requis pour résoudre les annotations dataclass
    spec.loader.exec_module(gg)

    import re as _re

    def ok_runner(cmd, timeout):
        # crée TOUS les fichiers cités dans la commande (batch ou unitaire)
        for p in _re.findall(r"(/[^\s,]+\.(?:png|mp4|jpg))", cmd[2]):
            Path(p).write_bytes(b"x")
        class R: returncode = 0
        return R()

    def noop_runner(cmd, timeout):
        class R: returncode = 0
        return R()

    tmp = tempfile.mkdtemp()
    grok_cfg = {"output_dir": tmp, "variations_per_design": 2, "palette": ["a"],
                "mockup_rooms": ["r1", "r2", "r3", "r4"], "grok_command": "grok"}
    brief = generate_daily_brief(grok_cfg, {"saturated_topics": []}, [],
                                 date(2026, 6, 6))

    # Mode BATCH (défaut) : 1 appel par design, 2 fichiers attendus chacun
    djobs = gg.build_design_jobs(brief, grok_cfg)
    check(len(djobs) == 3, "batch : 3 jobs (1 appel par design)")
    check(len(djobs[0].outs) == 2, "batch : 2 variations attendues par appel")
    check(djobs[0].cmd[0] == "grok" and djobs[0].cmd[1] == "-p", "commande `grok -p`")
    check("save them as exactly these 2 PNG files" in djobs[0].cmd[2],
          "batch : demande les 2 variations en un seul appel")

    # Mode NON-batch : 1 appel par variation = 6 jobs
    nb = gg.build_design_jobs(brief, dict(grok_cfg, batch_variations=False))
    check(len(nb) == 6, "non-batch : 6 jobs (1 par variation)")
    check("Save the result as a PNG file at" in nb[0].cmd[2], "non-batch : clause PNG")

    # Ancienne voie mockups DÉSACTIVÉE -> redirige vers make_mockups.py
    rc = gg.main(["--mockups", "a.png", "b.png", "c.png", "--config",
                  "config.yaml"])
    check(rc == 0, "`--mockups` renvoie 0 (désactivé, pas de génération Grok)")
    check(not hasattr(gg, "build_mockup_jobs"),
          "build_mockup_jobs supprimé (plus de mockups via Grok)")

    # Orchestration batch : runner qui crée les fichiers -> 3 OK (6 fichiers)
    recap = gg.run_jobs(djobs, 5, runner=ok_runner)
    check(len(recap["ok"]) == 3 and not recap["failed"],
          "batch : runner crée les fichiers -> 3 jobs OK")

    # Parallèle : 2 workers, runner OK -> toujours 3 OK (dossier neuf)
    tmpp = tempfile.mkdtemp()
    briefp = generate_daily_brief(dict(grok_cfg, output_dir=tmpp),
                                  {"saturated_topics": []}, [], date(2026, 6, 6))
    recapp = gg.run_jobs(gg.build_design_jobs(briefp, dict(grok_cfg,
                         output_dir=tmpp)), 5, runner=ok_runner, workers=2)
    check(len(recapp["ok"]) == 3, "parallèle (2 workers) : 3 jobs OK")

    # Runner qui ne produit rien -> 'failed', pas de crash (dossier neuf)
    tmp2 = tempfile.mkdtemp()
    brief2 = generate_daily_brief(dict(grok_cfg, output_dir=tmp2),
                                  {"saturated_topics": []}, [], date(2026, 6, 6))
    recap2 = gg.run_jobs(gg.build_design_jobs(brief2, dict(grok_cfg,
                         output_dir=tmp2)), 5, runner=noop_runner)
    check(len(recap2["failed"]) == 3 and not recap2["ok"],
          "aucun fichier produit -> jobs à refaire, sans crash")


# --- storage (compléments) ---------------------------------------------------

def test_storage_extras():
    print("\n[storage : snapshot le plus récent, base indisponible]")
    from src.etsy_parser import ShopData
    from src.storage import HistoryStore

    with tempfile.TemporaryDirectory() as tmp:
        store = HistoryStore(str(Path(tmp) / "h.sqlite3"))
        store.save_snapshot("2026-05-20", [ShopData("A", "com", "u", total_sales=100)])
        store.save_snapshot("2026-05-30", [ShopData("A", "com", "u", total_sales=200)])
        deltas = store.compute_deltas([ShopData("A", "com", "u", total_sales=260)],
                                      "2026-06-01")
        check(deltas["A"].prev_date == "2026-05-30" and deltas["A"].sales_delta == 60,
              "diff calculé vs le snapshot le PLUS RÉCENT antérieur")
        # Évolution HEBDO : cutoff à 7 j -> compare au snapshot du 2026-05-20
        wk = store.compute_deltas([ShopData("A", "com", "u", total_sales=260)],
                                  "2026-06-01", cutoff="2026-05-25")
        check(wk["A"].prev_date == "2026-05-20" and wk["A"].sales_delta == 160,
              "diff hebdo via cutoff (vs snapshot <= cutoff)")
        store.close()

    # Base impossible (chemin = dossier) -> dégradation, pas de crash
    with tempfile.TemporaryDirectory() as tmp:
        bad = HistoryStore(tmp)  # un dossier, pas un fichier
        check(not bad.available, "base SQLite impossible -> available=False (dégradé)")
        bad.save_snapshot("2026-06-01", [])  # ne doit pas crasher
        check(bad.compute_deltas([], "2026-06-01") == {}, "diffs vides si base KO")


# --- currency (compléments) --------------------------------------------------

def test_currency_extras():
    print("\n[currency : fetch simulé, cache, devise inconnue]")
    import src.currency as cur
    from src.currency import CurrencyConverter, convert_shop_prices
    from src.etsy_parser import ShopData

    # Fetch en ligne simulé (monkeypatch requests.get)
    saved_get = cur.requests.get
    cur.requests.get = lambda url, params=None, timeout=None: FakeResponse(
        200, json_data={"date": "2026-05-30", "rates": {"USD": 1.1, "GBP": 0.85}})
    try:
        with tempfile.TemporaryDirectory() as tmp:
            cache = str(Path(tmp) / "fx.json")
            conv = CurrencyConverter(cache_path=cache, allow_network=True)
            val, note = conv.to_eur(110, "USD")
            check(abs(val - 100.0) < 0.01 and "API" in note,
                  "fetch en ligne simulé -> 110 USD = 100 € (taux 1.1)")
            check(Path(cache).exists(), "taux mis en cache après fetch")
            # Nouveau convertisseur lit le cache (pas de fetch)
            cur.requests.get = lambda *a, **k: FakeResponse(500)
            conv2 = CurrencyConverter(cache_path=cache, allow_network=True)
            v2, _ = conv2.to_eur(110, "USD")
            check(abs(v2 - 100.0) < 0.01, "2e convertisseur sert le cache")
    finally:
        cur.requests.get = saved_get

    # Devise inconnue -> pas de conversion inventée
    conv = CurrencyConverter(cache_path=tempfile.mktemp(), allow_network=False)
    shop = ShopData("S", "com", "u", avg_price_eur=10.0, currency="XYZ")
    convert_shop_prices(shop, conv)
    check(shop.avg_price_eur == 10.0 and shop.fx_note is not None,
          "devise inconnue -> prix inchangé + note explicative")

    # Pas de devise -> no-op total
    shop2 = ShopData("S", "com", "u", avg_price_eur=10.0, currency=None)
    convert_shop_prices(shop2, conv)
    check(shop2.avg_price_eur == 10.0 and shop2.fx_note is None,
          "pas de devise -> aucune modification")


# --- etsy_api (couche HTTP) --------------------------------------------------

def test_etsy_api_http():
    print("\n[etsy_api : couche HTTP simulée]")
    from src.etsy_api import EtsyApiClient

    check(not EtsyApiClient(api_key=None).available, "sans clé -> inactif")

    client = EtsyApiClient(api_key="K", backoff_base=0.0, min_delay=0)
    shop_json = {"results": [{"shop_id": 7, "shop_name": "CoolShop",
                 "transaction_sold_count": 4200, "listing_active_count": 88,
                 "review_count": 510, "review_average": 4.9,
                 "currency_code": "USD"}]}
    listings_json = {"results": [
        {"title": "Japandi Set of 3", "price": {"amount": 1100, "divisor": 100}}]}

    def handler(method, url, params, data, n):
        if "listings/active" in url:
            return FakeResponse(200, json_data=listings_json)
        if url.endswith("/shops"):
            return FakeResponse(200, json_data=shop_json)
        return FakeResponse(404)
    client._session = FakeSession(handler)
    sd = client.get_shop("CoolShop", "fr")
    check(sd is not None and sd.total_sales == 4200, "get_shop via HTTP -> ventes")
    check(sd.currency == "USD" and abs(sd.avg_price_eur - 11.0) < 0.01,
          "prix moyen depuis fiches (11.0) + devise")

    # 403 -> None
    client2 = EtsyApiClient(api_key="K", backoff_base=0.0, min_delay=0)
    client2._session = FakeSession(lambda *a: FakeResponse(403))
    check(client2.get_shop("X") is None, "HTTP 403 sur l'API -> None")

    # panne puis succès sur _get
    client3 = EtsyApiClient(api_key="K", backoff_base=0.0, min_delay=0)

    def flaky(method, url, params, data, n):
        if n == 1:
            raise RequestException("net")
        return FakeResponse(200, json_data={"results": []})
    client3._session = FakeSession(flaky)
    check(client3._get("/shops") == {"results": []}, "panne réseau -> retry réussi")


# --- keywords_api (couche HTTP) ----------------------------------------------

def test_keywords_api_http():
    print("\n[keywords_api : couche HTTP simulée]")
    from src.keywords_api import KeywordsEverywhereClient

    client = KeywordsEverywhereClient(api_key="K", backoff_base=0.0)
    client._session = FakeSession(lambda *a: FakeResponse(200, json_data={"data": [
        {"keyword": "japandi wall art", "vol": 2400,
         "cpc": {"value": "0.4"}, "competition": 0.2}]}))
    vols = client.get_volumes(["japandi wall art"])
    check(vols["japandi wall art"].volume == 2400, "volumes via HTTP simulé")

    # 402 crédits épuisés -> {}
    c2 = KeywordsEverywhereClient(api_key="K", backoff_base=0.0)
    c2._session = FakeSession(lambda *a: FakeResponse(402))
    check(c2.get_volumes(["x"]) == {}, "HTTP 402 (crédits) -> {} sans crash")

    # 401 clé invalide -> {}
    c3 = KeywordsEverywhereClient(api_key="K", backoff_base=0.0)
    c3._session = FakeSession(lambda *a: FakeResponse(401))
    check(c3.get_volumes(["x"]) == {}, "HTTP 401 (clé) -> {} sans crash")


# --- main (câblage) ----------------------------------------------------------

def test_main_wiring():
    print("\n[main : shop_url, discover, collect (offline + données manuelles)]")
    import main as cli

    check(cli.shop_url("X", "com") == "https://www.etsy.com/shop/X", "shop_url .com")
    check(cli.shop_url("X", "fr") == "https://www.etsy.com/fr/shop/X", "shop_url .fr")
    check(cli.shop_url("X", None) == "https://www.etsy.com/shop/X", "shop_url devise nulle")

    import logging
    lg = logging.getLogger("market_intel")
    lg.addHandler(logging.NullHandler())

    # discover désactivé -> []
    check(cli.discover_competitors({"discovery": {"enabled": False}}, None, lg) == [],
          "discover désactivé -> liste vide")

    # collect hors-ligne SANS donnée manuelle -> dégradé
    cfg_off = {"competitors": [{"slug": "A", "market": "com"}], "shop": {},
               "revenue_estimation": {}, "ai_inference": {}}
    profs, degraded = cli.collect_competitors(cfg_off, None, lg, allow_network=False)
    check(degraded and len(profs) == 1 and not profs[0].shop.fetched,
          "collect --no-network sans data -> dégradé, profil non récupéré")

    # collect avec DONNÉES MANUELLES (config) -> non dégradé, analyse complète,
    # même sans réseau ni API (voie conforme aux CGU). + conversion en EUR.
    from src.currency import CurrencyConverter
    conv = CurrencyConverter(cache_path=tempfile.mktemp(suffix=".json"),
                             allow_network=False)
    cfg_manual = {"shop": {"total_sales": 1, "active_listings": 16, "reviews": 1},
                  "revenue_estimation": {}, "ai_inference": {"enabled": True,
                  "threshold": 4, "weights": {}},
                  "competitors": [{"slug": "MeiMei", "market": "com",
                                   "data": {"sales": 28300, "reviews": 3800,
                                            "rating": 5.0, "price": 8.64,
                                            "currency": "USD", "strikethrough": True,
                                            "since_year": 2016,
                                            "titles": ["Boho Nursery Set of 3"]}}]}
    profs2, degraded2 = cli.collect_competitors(cfg_manual, None, lg,
                                               allow_network=False, converter=conv)
    p = profs2[0].shop
    check(not degraded2, "données manuelles -> pipeline NON dégradé (sans API)")
    check(p.total_sales == 28300 and p.reviews == 3800, "chiffres manuels chargés")
    check(abs(p.avg_price_eur - 8.0) < 0.01, "prix manuel USD converti en EUR (8.64->8)")
    check(profs2[0].revenue.available and profs2[0].revenue.lifetime_low_eur == 226400,
          "CA estimé depuis données manuelles (28300 x 8)")


def run() -> int:
    print("=== TESTS ÉTENDUS — couverture exhaustive ===")
    test_config_errors()
    test_config_defaults()
    test_fetcher_robots_block()
    test_fetcher_cache_and_status()
    test_fetcher_cache_expiry()
    test_parser_variants()
    test_analysis_extras()
    test_trends()
    test_seo_extras()
    test_prompts_extras()
    test_reports()
    test_automation_scripts()
    test_grok_runner()
    test_zip_outputs()
    test_image_pipeline()
    test_upscale_cli_any_name()
    test_mockup_compositor()
    test_make_mockups_helpers()
    test_storage_extras()
    test_currency_extras()
    test_etsy_api_http()
    test_keywords_api_http()
    test_main_wiring()
    print(f"\n{'='*46}")
    if _FAILURES:
        print(f"❌ {len(_FAILURES)} test(s) étendu(s) en échec :")
        for f in _FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ Tous les tests étendus passent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
