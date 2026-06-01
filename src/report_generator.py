"""
report_generator.py — Génère les 3 rapports markdown du jour.

  1. veille_concurrents.md      (OUTPUT 1)
  2. prompts_grok_du_jour.md     (OUTPUT 2)
  3. guidelines_claude_chat.md   (OUTPUT 3)

Tout est écrit dans reports/AAAA-MM-JJ/. Les marqueurs de fiabilité (ESTIMATION,
INFÉRENCE, donnée indisponible) sont propagés depuis les modules d'analyse pour
ne JAMAIS présenter une supposition comme un fait.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .analysis import CompetitorProfile
from .prompt_generator import GrokPrompt
from .seo import SeoOpportunity
from .utils import (UNAVAILABLE, fmt_eur, fmt_price, now_iso, report_dir,
                    today_str)

logger = logging.getLogger("market_intel")

_DISCLAIMER = (
    "> ⚠️ **Note d'honnêteté** : le CA réel d'une boutique Etsy n'est pas public ; "
    "tous les montants ci-dessous sont des **ESTIMATIONS** avec marge d'erreur "
    "élevée (calcul montré). La mention « probablement IA » est une **INFÉRENCE** "
    "(faisceau d'indices), jamais une certitude. Les champs « donnée "
    "indisponible » n'ont pas pu être lus automatiquement — voir LIMITS.md.\n"
)


# --- OUTPUT 1 : veille concurrents -------------------------------------------

def render_competitors(profiles: list[CompetitorProfile], my_shop: dict,
                       degraded: bool, deltas: dict | None = None) -> str:
    lines: list[str] = []
    lines.append(f"# Veille concurrentielle — {today_str()}")
    lines.append(f"_Généré le {now_iso()}_\n")
    lines.append(_DISCLAIMER)

    if degraded:
        lines.append("> 🔌 **MODE DÉGRADÉ** : l'accès live à Etsy a échoué (réseau "
                     "bloqué ou pages non récupérées). Les profils ci-dessous sont "
                     "donc majoritairement « donnée indisponible ». Relance l'outil "
                     "depuis ta machine (réseau ouvert) pour des données réelles.\n")

    # --- Évolution depuis le dernier run (historisation SQLite) --------------
    lines.append(_render_deltas_section(deltas or {}))

    # --- Tableau de synthèse top 10 ------------------------------------------
    lines.append("## Top concurrents (classés par ventes publiques)\n")
    lines.append("| # | Boutique | Ventes (publiques) | Fiches | Avis | Note | "
                 "Prix moyen | CA mensuel ESTIMÉ | Profil |")
    lines.append("|---|----------|-------------------|--------|------|------|"
                 "-----------|-------------------|--------|")
    for i, p in enumerate(profiles[:10], 1):
        s = p.shop
        sales = s.total_sales if s.total_sales is not None else UNAVAILABLE
        listings = s.active_listings if s.active_listings is not None else "—"
        reviews = s.reviews if s.reviews is not None else "—"
        rating = s.avg_rating if s.avg_rating is not None else "—"
        price = fmt_price(s.avg_price_eur) if s.avg_price_eur else UNAVAILABLE
        if p.revenue.available:
            ca = f"{fmt_eur(p.revenue.monthly_low_eur)}–{fmt_eur(p.revenue.monthly_high_eur)}"
        else:
            ca = UNAVAILABLE
        profil = "INFÉRENCE IA" if p.ai.probably_ai else "artisan/humain probable"
        lines.append(f"| {i} | {s.slug} | {sales} | {listings} | {reviews} | "
                     f"{rating} | {price} | {ca} | {profil} |")
    lines.append("")

    # --- Fiches détaillées ---------------------------------------------------
    lines.append("## Fiches détaillées\n")
    for i, p in enumerate(profiles, 1):
        s = p.shop
        lines.append(f"### {i}. {s.slug}  ({s.market})")
        lines.append(f"- URL : {s.url}")
        fetch_status = (f"OK — {s.source_note}" if s.fetched
                        else f"❌ échec — {s.source_note}")
        lines.append(f"- Récupération : {fetch_status}")
        lines.append(f"- Ventes publiques (cumul) : "
                     f"{s.total_sales if s.total_sales is not None else UNAVAILABLE}")
        lines.append(f"- Fiches actives : "
                     f"{s.active_listings if s.active_listings is not None else UNAVAILABLE}")
        lines.append(f"- Avis : {s.reviews if s.reviews is not None else UNAVAILABLE}"
                     f" | Note : {s.avg_rating if s.avg_rating is not None else UNAVAILABLE}")
        price_line = (f"- Prix : moyen {fmt_price(s.avg_price_eur)} "
                      f"(min {fmt_price(s.price_min_eur)} / max {fmt_price(s.price_max_eur)})")
        if s.fx_note and s.avg_price_original is not None:
            price_line += (f"  _[{s.avg_price_original:.2f} {s.currency} d'origine, "
                           f"{s.fx_note}]_")
        elif s.fx_note:
            price_line += f"  _[{s.fx_note}]_"
        lines.append(price_line)
        lines.append(f"- Prix barré (promo) : "
                     f"{_yesno(s.has_strikethrough_price)}")
        lines.append(f"- Ancienneté : {s.age_text or UNAVAILABLE}")
        lines.append(f"- Langue/marché : {', '.join(s.languages) or UNAVAILABLE}")

        # CA estimé avec calcul transparent
        lines.append("\n**Estimation de CA (transparente)**")
        if p.revenue.available:
            lines.append(f"- Méthode : {p.revenue.method}")
            lines.append("```")
            lines.append(p.revenue.calc_explanation)
            lines.append("```")
            lines.append(f"- ⚠️ {p.revenue.caveat}")
        else:
            lines.append(f"- {p.revenue.caveat}")

        # Inférence IA
        lines.append("\n**Profil de production (INFÉRENCE)**")
        lines.append(f"- Verdict : {'⚙️ PROBABLEMENT IA' if p.ai.probably_ai else 'artisan/humain probable'} "
                     f"(score {p.ai.score}/{p.ai.threshold} requis)")
        for sig in p.ai.signals:
            lines.append(f"  - {sig}")
        lines.append(f"- {p.ai.note}")

        # Forces / faille
        lines.append("\n**3 choses qu'ils font mieux que NeutralWallDesign**")
        for st in p.strengths_vs_me:
            lines.append(f"- {st}")
        lines.append(f"\n**1 faille exploitable** : {p.exploitable_gap}\n")

    return "\n".join(lines) + "\n"


def _render_deltas_section(deltas: dict) -> str:
    """Section 'évolution depuis le dernier run' à partir des diffs SQLite."""
    changed = [d for d in deltas.values() if getattr(d, "has_change", False)]
    if not deltas:
        return ("## Évolution depuis le dernier run\n\n_Premier run enregistré "
                "(ou historique indisponible) : pas encore de comparaison. "
                "Les écarts apparaîtront dès le prochain lancement._\n")
    if not changed:
        return ("## Évolution depuis le dernier run\n\n_Aucun changement détecté "
                "sur les données publiques depuis le dernier snapshot._\n")

    out = ["## Évolution depuis le dernier run\n"]
    out.append("| Boutique | Depuis | Δ ventes | Δ fiches | Δ avis | Δ prix moyen |")
    out.append("|----------|--------|----------|----------|--------|--------------|")
    for d in sorted(changed, key=lambda x: -(x.sales_delta or 0)):
        out.append(
            f"| {d.slug} | {d.prev_date} | {_signed(d.sales_delta)} | "
            f"{_signed(d.listings_delta)} | {_signed(d.reviews_delta)} | "
            f"{_signed(d.price_delta, is_money=True)} |")
    out.append("\n> 📈 Une forte hausse de ventes/avis sur un concurrent signale "
               "une fiche ou un set qui marche → à étudier et à concurrencer.\n")
    return "\n".join(out)


def _signed(v, is_money: bool = False) -> str:
    """Affiche un delta signé (+/-) ou '—' si indisponible."""
    if v is None:
        return "—"
    if v == 0:
        return "0"
    sign = "+" if v > 0 else ""
    if is_money:
        return f"{sign}{v:.2f} €"
    return f"{sign}{v}"


def _yesno(v) -> str:
    if v is True:
        return "oui (détecté)"
    if v is False:
        return "non"
    return UNAVAILABLE


# --- OUTPUT 2 : prompts Grok -------------------------------------------------

def render_grok_prompts(prompts: list[GrokPrompt]) -> str:
    lines: list[str] = []
    lines.append(f"# 5 prompts Grok du jour — {today_str()}")
    lines.append(f"_Généré le {now_iso()}_\n")
    lines.append("> Chaque prompt cible une demande issue de l'analyse "
                 "concurrentielle + tendances. Structure imposée pour formes "
                 "pleines (solid filled, no outline). Copie-colle le bloc "
                 "**Prompt** dans Grok.\n")
    lines.append("> ⚠️ « Volume estimé » = intérêt **relatif** Google Trends "
                 "(0-100) ou « à valider » : ce n'est PAS un volume de recherche "
                 "absolu (non public). Valide via eRank/Marmalead avant d'investir.\n")

    for p in prompts:
        lines.append(f"## Prompt {p.index} — forme : {p.shape}")
        lines.append(f"- **Pilier SEO visé** : `{p.seo_pillar}`")
        lines.append(f"- **Demande** : {p.demand_confirmation}")
        lines.append(f"- **Volume estimé** : {p.estimated_volume}")
        lines.append(f"- **Pourquoi confirmée** : {p.why_confirmed}")
        lines.append(f"- **Sources** : {', '.join(p.sources)}")
        lines.append(f"- **Palette** : {', '.join(p.palette)}")
        lines.append(f"- **Style** : {p.style}")
        lines.append("\n**Prompt (à copier-coller dans Grok) :**")
        lines.append("```text")
        lines.append(p.prompt_text)
        lines.append("```\n")

    return "\n".join(lines) + "\n"


# --- OUTPUT 3 : guidelines pour Claude Chat ----------------------------------

def render_guidelines(profiles: list[CompetitorProfile],
                      opportunities: list[SeoOpportunity],
                      my_shop: dict, goals: dict, degraded: bool) -> str:
    lines: list[str] = []
    lines.append(f"# Guidelines stratégiques pour Claude Chat (projet Etsy) — {today_str()}")
    lines.append(f"_Généré le {now_iso()}_\n")
    lines.append("> Brief destiné à un assistant en chat pour affiner SEO, trafic "
                 "et ventes de **NeutralWallDesign**. Données honnêtes : "
                 "estimations marquées, incertitudes assumées.\n")

    # 1. Insights du jour
    lines.append("## 1. Insights majeurs du jour")
    insights = _build_insights(profiles, opportunities, degraded)
    for ins in insights:
        lines.append(f"- {ins}")
    lines.append("")

    # 2. Opportunités SEO
    lines.append("## 2. Opportunités SEO (long-tail prioritaires)")
    lines.append("| Mot-clé | Confirmation | Intérêt relatif | Tendance | Sources |")
    lines.append("|---------|-------------|-----------------|----------|---------|")
    for o in opportunities[:12]:
        rel = o.relative_interest if o.relative_interest is not None else "—"
        lines.append(f"| {o.keyword} | {o.confirmation} | {rel} | {o.direction} "
                     f"| {', '.join(o.sources)} |")
    lines.append("\n> ⚠️ Aucun volume absolu n'est affirmé : « intérêt relatif » "
                 "vient de Google Trends (0-100). Croise avec eRank avant d'agir.\n")

    # 3. Pinterest
    lines.append("## 3. Recommandations Pinterest")
    lines.extend([
        "- Format prioritaire : épingles **2:3 (1000×1500)**, mockups en "
        "contexte (mur, cadre bois clair, intérieur japandi).",
        "- Idea Pins / vidéos courtes : démo « comment imprimer & encadrer » → "
        "fort engagement, peu de concurrence sur la niche neutre.",
        "- Tableaux thématiques par sous-niche (terracotta, wabi-sabi, nursery "
        "neutre) pour capter le SEO Pinterest.",
        "- Fréquence : 3-5 épingles/jour, recycler les top performers en "
        "nouveaux mockups.",
        f"- ⚠️ Tendances Pinterest précises : {UNAVAILABLE} en automatique "
        "(Pinterest Trends à consulter manuellement — voir LIMITS.md).",
    ])
    lines.append("")

    # 4. Pricing / bundles / AOV
    lines.append("## 4. Pricing, bundles & AOV")
    my_price = my_shop.get("avg_price_eur", 6.0)
    lines.extend([
        f"- AOV actuel estimé ≈ {fmt_eur(my_price)} (single). Levier #1 vers "
        "5000 €/mois = **monter l'AOV**, pas seulement le volume.",
        "- Créer 3 paliers : **single** (ancrage bas), **set de 3** (best-value, "
        "mis en avant), **bundle collection 6-9** (AOV max).",
        "- Prix barré sur les sets (ancrage promo) : plusieurs concurrents "
        "l'utilisent (voir veille) → +conversion perçue.",
        "- Cible AOV : passer de ~6 € à **15-25 €** via sets/bundles avant "
        "d'augmenter le trafic payant.",
        "- Toujours livrer plusieurs ratios (2:3, 3:4, 4:5, ISO/A, 11x14) → "
        "argument de valeur vs concurrents qui en livrent peu.",
    ])
    lines.append("")

    # 5. Publicité
    lines.append("## 5. Publicité (budget 100-250 €/mois)")
    lines.extend([
        "- **Seuil de prudence** : Etsy Ads sont rarement rentables sous **25 € "
        "de panier** et avec **0-2 avis**. Aujourd'hui (1 vente, 1 avis) → "
        "**ne pas pousser Etsy Ads agressivement**.",
        "- Étape 1 (maintenant) : 1-3 €/jour Etsy Ads sur tes 3-4 meilleures "
        "fiches uniquement, pour collecter de la donnée (pas pour le ROI).",
        "- Étape 2 (après 10-15 avis + sets en place) : monter à 5-8 €/jour sur "
        "les fiches qui convertissent déjà en organique.",
        "- Réinvestir le **gros du budget dans Pinterest** (organique + un peu "
        "de Pinterest Ads) : meilleur canal de découverte pour le wall art.",
        "- **Seuil de déclenchement** : n'augmente un budget que si ROAS > 2 sur "
        "14 jours glissants. Sinon, coupe et réalloue.",
        "- ROI attendu : honnêtement **incertain** au stade actuel — vise "
        "d'abord la preuve sociale (avis) et l'AOV, le payant viendra après.",
    ])
    lines.append("")

    # 6. Roadmap 5000€/mois
    lines.append("## 6. Roadmap vers 5000 €/mois (honnête)")
    lines.append(_roadmap_text(goals))

    # 7. Plan d'ajustement dynamique
    lines.append("\n## 7. Plan d'ajustement dynamique")
    lines.extend([
        "- **Hebdo** : vérifier les vues/favoris par fiche ; tuer/retravailler "
        "les fiches à 0 vue après 3 semaines.",
        "- **Bi-hebdo** : relancer cet outil, comparer l'évolution des "
        "concurrents, ajuster les tags long-tail.",
        "- **Mensuel** : recalculer l'AOV réel, décider de l'allocation pub "
        "selon le ROAS observé.",
        "- **Trigger SEO** : si une sous-niche passe « confirmée » (Trends "
        "montant), produire 3-5 fiches dessus sous 7 jours.",
    ])
    lines.append("")
    return "\n".join(lines) + "\n"


def build_merged_guidelines(guidelines_md: str, competitors_md: str,
                            prompts_md: str) -> str:
    """
    Fusionne les 3 rapports en UN seul document pour Claude chat : stratégie +
    veille concurrentielle (Annexe A) + prompts Grok du jour (Annexe B). Les
    fichiers séparés restent générés par ailleurs ; ceci est un SUR-ENSEMBLE
    pensé pour un copier-coller unique, et pour que Claude chat puisse juger les
    images Grok que tu lui enverras.
    """
    judging = (
        "## 8. Mission : juger les images Grok que je t'enverrai\n\n"
        "Ce document est **autosuffisant** : il contient ma stratégie (ci-dessus), "
        "la **veille concurrentielle complète** (Annexe A) et les **5 prompts Grok "
        "du jour** (Annexe B). Tu as donc TOUT le contexte en un seul copier-coller.\n\n"
        "Quand je t'enverrai des **captures d'écran d'images générées par Grok** "
        "(à partir des prompts de l'Annexe B), évalue rapidement lesquelles "
        "**GARDER** selon ces critères :\n"
        "- **Cohérence niche** : warm organic minimalism, palette neutre/terracotta, "
        "formes pleines sans contour.\n"
        "- **Différenciation** : se démarque-t-elle de ce que font déjà les "
        "concurrentes (Annexe A) ?\n"
        "- **Potentiel SEO/commercial** : colle au pilier SEO visé par le prompt "
        "(Annexe B) et à une demande confirmée.\n"
        "- **Qualité technique** : pas de contour/ligne, fond propre, composition "
        "centrée, marges généreuses, rendu imprimable haute résolution.\n"
        "- **Déclinable** : se prête-t-elle à un **set de 3** et à plusieurs ratios "
        "(comme les concurrentes) ?\n\n"
        "Pour **chaque image** : verdict **GARDER / RETRAVAILLER / JETER** + 1 phrase "
        "de justification. Si GARDER → propose un **titre Etsy SEO** + **3 tags "
        "long-tail**.\n"
    )
    sep = "\n\n---\n\n"
    return (
        guidelines_md.rstrip() + "\n\n" + judging
        + sep + "# 📎 ANNEXE A — Veille concurrentielle (détail complet)\n\n"
        + competitors_md.rstrip()
        + sep + "# 📎 ANNEXE B — Prompts Grok du jour (images à générer & juger)\n\n"
        + prompts_md.rstrip() + "\n"
    )


def _build_insights(profiles, opportunities, degraded) -> list[str]:
    insights = []
    if degraded:
        insights.append("🔌 Données concurrents en **mode dégradé** (réseau "
                        "bloqué) : insights ci-dessous basés sur la structure de "
                        "la niche, à confirmer en relançant depuis ta machine.")
    ai_shops = [p.shop.slug for p in profiles if p.ai.probably_ai]
    if ai_shops:
        insights.append(f"Boutiques **probablement IA** (INFÉRENCE) à étudier "
                        f"pour leurs patterns : {', '.join(ai_shops)} — copier "
                        "leur structure de sets/pricing, battre leur qualité.")
    confirmed = [o.keyword for o in opportunities if o.confirmation == "confirmée"]
    if confirmed:
        insights.append(f"Opportunités SEO **confirmées** (Trends montant) : "
                        f"{', '.join(confirmed[:5])}.")
    partial = [o.keyword for o in opportunities if o.confirmation == "partielle"]
    if partial:
        insights.append(f"Sous-niches montantes à tester : {', '.join(partial[:5])}.")
    if not insights:
        insights.append("Pas de signal fort aujourd'hui — concentrer l'effort sur "
                        "la création de sets/bundles et la collecte d'avis.")
    return insights


def _roadmap_text(goals: dict) -> str:
    target = goals.get("target_net_eur_per_month", 5000)
    return (
        f"**Objectif : {target} €/mois NET.** Rappel : CA = AOV × nb de ventes.\n\n"
        "Projection honnête : en printables, atteindre ce niveau prend "
        "**typiquement 12-36 mois**, pas quelques semaines. Voici des jalons "
        "réalistes (à AOV croissant) :\n\n"
        "| Jalon | Horizon | AOV cible | Ventes/mois | CA brut ≈ | Focus |\n"
        "|-------|---------|-----------|-------------|-----------|-------|\n"
        "| J1 | Mois 0-3 | 6 € | 5-15 | 30-90 € | 1ers avis, sets, mockups Pinterest |\n"
        "| J2 | Mois 3-6 | 12 € | 30-60 | 360-720 € | bundles, 30+ fiches, SEO long-tail |\n"
        "| J3 | Mois 6-12 | 18 € | 80-150 | 1,4-2,7 k€ | collections, Pinterest scale |\n"
        "| J4 | Mois 12-24 | 22 € | 150-250 | 3,3-5,5 k€ | catalogue mûr, pub rentable |\n"
        "| J5 | Mois 24-36 | 25 € | 200-250 | ~5 k€+ | marque établie, AOV haut |\n\n"
        "⚠️ Ces chiffres sont des **scénarios**, pas des promesses. Le facteur "
        "limitant n°1 est le trafic qualifié (Pinterest + SEO), pas le nombre de "
        "fiches. Priorité : **AOV via bundles** plutôt que volume pur."
    )


# --- Écriture sur disque -----------------------------------------------------

def write_reports(reports_base: str, competitors_md: str, prompts_md: str,
                  guidelines_md: str) -> dict[str, Path]:
    """Écrit les 3 fichiers dans reports/AAAA-MM-JJ/ et renvoie leurs chemins."""
    d = report_dir(reports_base)
    paths = {
        "veille_concurrents.md": d / "veille_concurrents.md",
        "prompts_grok_du_jour.md": d / "prompts_grok_du_jour.md",
        "guidelines_claude_chat.md": d / "guidelines_claude_chat.md",
    }
    paths["veille_concurrents.md"].write_text(competitors_md, encoding="utf-8")
    paths["prompts_grok_du_jour.md"].write_text(prompts_md, encoding="utf-8")
    paths["guidelines_claude_chat.md"].write_text(guidelines_md, encoding="utf-8")
    logger.info("Rapports écrits dans %s", d)
    return paths
