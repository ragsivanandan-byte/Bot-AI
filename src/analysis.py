"""
analysis.py — Analyse concurrentielle.

Trois briques, toutes gouvernées par les règles anti-hallucination du brief :

  1. estimate_revenue() : estime une fourchette de CA en montrant TOUT le calcul.
     Le CA réel d'une boutique Etsy n'est PAS public -> on ne sort que des
     ESTIMATIONS étiquetées, avec marge d'erreur explicite.

  2. ai_inference() : score heuristique "probablement IA". JAMAIS une certitude.
     Renvoie le détail des signaux pour que tu juges toi-même.

  3. compare_to_reference() / rank_competitors() : classement par ventes
     publiques et synthèse "3 forces / 1 faille".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .etsy_parser import ShopData
from .utils import ESTIMATION, INFERENCE, UNAVAILABLE

logger = logging.getLogger("market_intel")


# --- 1. Estimation de CA -----------------------------------------------------

@dataclass
class RevenueEstimate:
    """Résultat d'estimation de CA, avec calcul et incertitude transparents."""
    available: bool
    method: str
    lifetime_low_eur: float | None = None
    lifetime_high_eur: float | None = None
    monthly_low_eur: float | None = None
    monthly_high_eur: float | None = None
    calc_explanation: str = ""
    caveat: str = ""


def estimate_revenue(shop: ShopData, rev_cfg: dict) -> RevenueEstimate:
    """
    Estime une fourchette de CA à partir des ventes publiques et du prix moyen.

    Formule (volontairement simple et transparente) :
        CA_lifetime ≈ ventes_publiques × prix_moyen
        CA_mensuel  ≈ CA_lifetime × part_des_ventes_sur_30j (heuristique)

    On renvoie une FOURCHETTE (low/high) car le prix moyen et la part récente
    sont incertains. Si les ventes publiques manquent, on ne devine PAS : on
    renvoie available=False.
    """
    if shop.total_sales is None:
        return RevenueEstimate(
            available=False,
            method="aucune (ventes publiques indisponibles)",
            caveat=f"{UNAVAILABLE} : le nombre de ventes n'a pas pu être lu sur "
                   "la page. Sans lui, toute estimation de CA serait inventée.")

    sales = shop.total_sales

    # Prix moyen : on prend celui de la page si dispo, sinon la fourchette de repli.
    if shop.avg_price_eur:
        price_low = price_high = shop.avg_price_eur
        price_src = f"prix moyen lu sur la page = {shop.avg_price_eur} €"
    else:
        price_low = float(rev_cfg.get("fallback_avg_price_eur_low", 4.0))
        price_high = float(rev_cfg.get("fallback_avg_price_eur_high", 12.0))
        price_src = (f"prix moyen INDISPONIBLE -> fourchette de repli "
                     f"{price_low}-{price_high} € (hypothèse)")

    lifetime_low = sales * price_low
    lifetime_high = sales * price_high

    share_low = float(rev_cfg.get("recent_sales_share_low", 0.02))
    share_high = float(rev_cfg.get("recent_sales_share_high", 0.08))
    monthly_low = lifetime_low * share_low
    monthly_high = lifetime_high * share_high

    # Formatage des montants avec espace comme séparateur de milliers (sans
    # toucher aux virgules de la prose).
    def _sp(x: float) -> str:
        return f"{x:,.0f}".replace(",", " ")

    calc = (
        f"Ventes publiques (cumul lifetime) = {sales}\n"
        f"  • {price_src}\n"
        f"  • CA lifetime ESTIMÉ = ventes × prix moyen "
        f"= {sales} × {price_low}–{price_high} € "
        f"= {_sp(lifetime_low)}–{_sp(lifetime_high)} €\n"
        f"  • Part des ventes supposée sur 30 j = {share_low:.0%}–{share_high:.0%} "
        f"(heuristique, marge d'erreur ÉNORME)\n"
        f"  • CA mensuel ESTIMÉ ≈ {_sp(monthly_low)}–{_sp(monthly_high)} €"
    )

    return RevenueEstimate(
        available=True,
        method=f"{ESTIMATION} = ventes_publiques × prix_moyen × part_30j",
        lifetime_low_eur=round(lifetime_low, 0),
        lifetime_high_eur=round(lifetime_high, 0),
        monthly_low_eur=round(monthly_low, 0),
        monthly_high_eur=round(monthly_high, 0),
        calc_explanation=calc,
        caveat="Les ventes publiques sont un CUMUL depuis l'ouverture, pas un "
               "rythme mensuel. La conversion en run-rate mensuel est une "
               "heuristique grossière. À traiter comme un ORDRE DE GRANDEUR, "
               "pas un chiffre fiable.")


# --- 2. Inférence "probablement IA" ------------------------------------------

@dataclass
class AiInference:
    probably_ai: bool
    score: int
    threshold: int
    signals: list[str] = field(default_factory=list)
    note: str = INFERENCE


def _looks_keyword_stuffed(titles: list[str]) -> bool:
    """Heuristique : titres très longs et bourrés de virgules/mots-clés."""
    if not titles:
        return False
    long_count = 0
    for t in titles:
        words = t.split()
        commas = t.count(",") + t.count("|")
        if len(words) >= 18 or commas >= 4:
            long_count += 1
    return long_count >= max(1, len(titles) // 2)


def ai_inference(shop: ShopData, ai_cfg: dict) -> AiInference:
    """
    Score heuristique d'une boutique sur l'axe "probablement générée par IA".
    Ce n'est JAMAIS une preuve. Chaque signal est listé pour transparence.
    """
    if not ai_cfg.get("enabled", True):
        return AiInference(False, 0, 0, ["heuristique désactivée"])

    # Dessin/fait-main DÉCLARÉ (ex. About) -> on n'attribue jamais le label IA.
    if getattr(shop, "declared_handmade", False):
        return AiInference(False, 0, int(ai_cfg.get("threshold", 4)),
                           ["dessin/fait-main déclaré (About) -> exclu du label IA"],
                           note="Déclaré fait-main : non concerné par l'inférence IA.")

    weights = ai_cfg.get("weights", {})
    threshold = int(ai_cfg.get("threshold", 4))
    score = 0
    signals: list[str] = []

    low_price_th = float(ai_cfg.get("low_price_threshold_eur", 3.5))
    if shop.avg_price_eur is not None and shop.avg_price_eur <= low_price_th:
        w = int(weights.get("low_price", 2))
        score += w
        signals.append(f"prix moyen très bas ({shop.avg_price_eur} € ≤ "
                       f"{low_price_th} €) [+{w}]")

    high_list_th = int(ai_cfg.get("high_listing_count_threshold", 150))
    if shop.active_listings is not None and shop.active_listings >= high_list_th:
        w = int(weights.get("high_listing_count", 2))
        score += w
        signals.append(f"dépôt massif de fiches ({shop.active_listings} ≥ "
                       f"{high_list_th}) [+{w}]")

    if _looks_keyword_stuffed(shop.sample_titles):
        w = int(weights.get("keyword_stuffed_titles", 2))
        score += w
        signals.append(f"titres à rallonge / mots-clés empilés [+{w}]")

    # Vélocité de ventes vs ancienneté (si on connaît l'année d'ouverture).
    if shop.age_text and shop.total_sales and shop.active_listings:
        if (shop.active_listings >= high_list_th and shop.total_sales > 1000):
            w = int(weights.get("high_sales_velocity", 1))
            score += w
            signals.append(f"volume de ventes élevé + catalogue massif [+{w}]")

    if not signals:
        signals.append("aucun signal IA détecté (ou données insuffisantes)")

    return AiInference(
        probably_ai=score >= threshold,
        score=score,
        threshold=threshold,
        signals=signals,
        note=f"{INFERENCE} — une boutique '100% IA' n'est PAS détectable avec "
             "certitude. Score = faisceau d'indices, pas une preuve.")


# --- 3. Comparaison & classement ---------------------------------------------

@dataclass
class CompetitorProfile:
    """Vue agrégée d'un concurrent, prête pour le rapport."""
    shop: ShopData
    revenue: RevenueEstimate
    ai: AiInference
    strengths_vs_me: list[str] = field(default_factory=list)
    exploitable_gap: str = ""


def _formats_label(shop: ShopData) -> str:
    """Déduit grossièrement les formats vendus depuis les titres (best-effort)."""
    titles = " ".join(shop.sample_titles).lower()
    fmts = []
    if any(w in titles for w in ("set of", "set de", "bundle", "pack", "gallery")):
        fmts.append("sets/bundles")
    if "single" in titles or not fmts:
        fmts.append("singles")
    return ", ".join(dict.fromkeys(fmts)) if fmts else UNAVAILABLE


def build_profile(shop: ShopData, my_shop: dict, rev_cfg: dict,
                  ai_cfg: dict) -> CompetitorProfile:
    """Assemble le profil complet d'un concurrent + comparaison à ma boutique."""
    revenue = estimate_revenue(shop, rev_cfg)
    ai = ai_inference(shop, ai_cfg)

    strengths: list[str] = []
    my_sales = my_shop.get("total_sales", 0) or 0
    my_listings = my_shop.get("active_listings", 0) or 0
    my_reviews = my_shop.get("reviews", 0) or 0

    if shop.total_sales and shop.total_sales > my_sales:
        strengths.append(f"Bien plus de ventes publiques ({shop.total_sales} "
                         f"vs {my_sales}) → preuve sociale & ancienneté SEO.")
    if shop.active_listings and shop.active_listings > my_listings:
        strengths.append(f"Catalogue plus large ({shop.active_listings} fiches "
                         f"vs {my_listings}) → plus de surface de recherche.")
    if shop.reviews and shop.reviews > my_reviews:
        strengths.append(f"Davantage d'avis ({shop.reviews} vs {my_reviews}) → "
                         "meilleur taux de conversion et classement Etsy.")
    if shop.has_strikethrough_price:
        strengths.append("Utilise des prix barrés (ancrage promo) → augmente la "
                         "conversion perçue.")
    if _formats_label(shop) and "sets" in _formats_label(shop):
        strengths.append("Vend des sets/bundles → panier moyen (AOV) plus élevé "
                         "que des singles seuls.")

    if not strengths:
        strengths.append(f"{UNAVAILABLE} — données insuffisantes pour comparer "
                         "(page non récupérée ou champs manquants).")
    strengths = strengths[:3]  # le brief demande "3 choses qu'ils font mieux"

    # Faille exploitable : best-effort à partir des signaux disponibles.
    gap = _find_gap(shop, ai)

    return CompetitorProfile(shop=shop, revenue=revenue, ai=ai,
                             strengths_vs_me=strengths, exploitable_gap=gap)


def _find_gap(shop: ShopData, ai: AiInference) -> str:
    """Une faille exploitable, choisie selon le profil."""
    if ai.probably_ai:
        return ("INFÉRENCE IA → souvent : descriptions génériques, peu de "
                "personnalisation, SAV faible, pas de curation. Ta faille : "
                "qualité éditoriale + cohérence de collection + branding humain.")
    if shop.has_strikethrough_price is None and shop.total_sales:
        return ("Pas de promo/ancrage prix détecté → tu peux te différencier "
                "avec un bundle 'meilleure affaire' bien mis en avant.")
    if shop.active_listings and shop.active_listings < 30:
        return ("Catalogue étroit → opportunité de couvrir plus de longue traîne "
                "SEO qu'eux sur la même sous-niche.")
    return ("Faille à confirmer manuellement (sections, ratios livrés, qualité "
            "des mockups) — données automatiques insuffisantes.")


def rank_competitors(profiles: list[CompetitorProfile]) -> list[CompetitorProfile]:
    """Classe par ventes publiques décroissantes (None en dernier)."""
    return sorted(profiles,
                  key=lambda p: (p.shop.total_sales is not None,
                                 p.shop.total_sales or 0),
                  reverse=True)
