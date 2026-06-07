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
# NB : render_grok_prompts reçoit un DailyVisualBrief (défini dans prompt_generator).
from .seo import SeoOpportunity
from .utils import (UNAVAILABLE, fmt_eur, fmt_price, now_iso, report_dir,
                    today_display)

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
    lines.append(f"# Veille concurrentielle — {today_display()}")
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


# --- OUTPUT 2 : brief visuel Grok du jour ------------------------------------

def render_grok_prompts(brief) -> str:
    """Rend le brief visuel du jour : 3 images brutes -> 4 mockups (dont 1 cover)
    -> 1 vidéo 6 s, avec consignes de sortie et de nommage."""
    b = brief
    out: list[str] = []
    out.append(f"# Brief visuel Grok du jour — {today_display()}")
    out.append(f"_Généré le {now_iso()}_\n")
    out.append(f"> **Thème du jour** : {b.theme}  ·  **Format** : {b.fmt}")
    out.append(f"> **Pilier SEO** : `{b.seo_pillar}`  ·  **Volume** : {b.seo_volume}")
    out.append(f"> **Pourquoi** : {b.why}")
    out.append(f"> **Sources** : {', '.join(b.sources)}")
    out.append(f"> **Anti-répétition** : {b.avoid_note}\n")
    out.append("> ⚙️ **Mode d'emploi** : génère dans **Grok Imagine / Grok Build "
               "`/imagine`**. **Enregistre toutes les sorties dans "
               f"`{b.output_dir}`** avec les noms indiqués. **QC humain** sur "
               "chaque rendu (GARDER / REFAIRE / JETER). **Mockups JAMAIS "
               "retouchés.** Génération + publication Etsy **manuelles**.\n")
    out.append("> ⚠️ Volume = intérêt **relatif** (Trends) ou volume réel "
               "(Keywords Everywhere) ou « à valider » — jamais un chiffre Etsy "
               "absolu (non public).\n")

    out.append("## 1) Images BRUTES (set de 3 designs)\n")
    for p in b.raw_prompts:
        out.append(f"### {p.label}  →  `{p.filename}`")
        out.append("```text")
        out.append(p.prompt_text)
        out.append("```")
        if p.variation_files:
            files = ", ".join(f"`{f}`" for f in p.variation_files)
            out.append(f"_Variations générées dans `~/Downloads` (à joindre à "
                       f"Claude chat pour qu'il choisisse la meilleure) : {files}_\n")
        else:
            out.append("")

    out.append("## 2) MOCKUPS d'ambiance (compositing — image collée, jamais "
               "retouchée)\n")
    for m in b.mockup_prompts:
        tag = " ⭐ COVER (slot 1 de la fiche)" if m.is_cover else ""
        out.append(f"### {m.label}{tag}  →  `{m.filename}`")
        out.append("```text")
        out.append(m.prompt_text)
        out.append("```\n")

    if b.gallery_prompt:
        out.append("### ⭐ (Bonus set) Gallery wall — cover IDÉALE d'un set  →  "
                   f"`{b.slug}_Cover_Gallery.png`")
        out.append("> ⚠️ Cas le plus DUR en headless (artefacts) : à faire de "
                   "préférence en **interactif** ou via **API édition-image** "
                   "(3 réf.). Si ça rate, garde la cover single ci-dessus.")
        out.append("```text")
        out.append(b.gallery_prompt)
        out.append("```\n")

    out.append("## 3) VIDÉO 6 s (image-to-video, image figée)\n")
    out.append(f"→  `{b.slug}_Video.mp4`")
    out.append("```text")
    out.append(b.video_prompt)
    out.append("```\n")

    out.append("## Rappels production")
    out.append("- **Designs** livrés : set = 5 ratios (2:3, 3:4, 4:5, 5:7, 11:14) "
               "→ 1 ZIP < 20 Mo (sinon PDF + lien Drive) ; single = 2 ratios "
               "(2:3 + 3:4). Export 90 %, **300 DPI vérifié**.")
    out.append("- **Ordre photos fiche** : COVER → [vidéo placée tôt par Etsy] → "
               "autres mockups → design(s) seul(s) → « What You Get » → « Print "
               "Sizes Guide ».")
    out.append("- **Pièges** : terracotta qui vire orange (refaire) ; figuratifs "
               "qui morphent en vidéo (formule « frozen every frame ») ; gallery "
               "wall 3 œuvres = artefacts (retries).")
    out.append("")
    return "\n".join(out) + "\n"


# --- OUTPUT 3 : guidelines pour Claude Chat ----------------------------------

def render_guidelines(profiles: list[CompetitorProfile],
                      opportunities: list[SeoOpportunity],
                      my_shop: dict, goals: dict, degraded: bool) -> str:
    lines: list[str] = []
    lines.append(f"# Guidelines stratégiques pour Claude Chat (projet Etsy) — {today_display()}")
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


def render_weekly_ai_watch(profiles: list[CompetitorProfile],
                           weekly_deltas: dict | None = None) -> str:
    """
    Veille hebdo focalisée sur les boutiques **IA positionnées comme nous**
    (miroir = MyAestheticAlley). On EXCLUT le fait-main déclaré (ex. MeiMei).
    Montre l'évolution sur ~7 jours (si l'historique le permet) pour que Claude
    chat affine ses décisions au fil du temps.
    """
    weekly_deltas = weekly_deltas or {}
    mirrors = [p for p in profiles
               if (p.shop.ai_mirror or p.ai.probably_ai)
               and not p.shop.declared_handmade]

    out = ["## Veille hebdo — boutiques IA positionnées comme nous\n"]
    out.append("_Miroir prioritaire : **MyAestheticAlley**. Le fait-main déclaré "
               "(ex. MusingsOfMeiMei) est EXCLU de ce panel IA._\n")
    if not mirrors:
        out.append("_Aucune boutique IA-miroir renseignée (ajoute `ai_mirror: true` "
                   "dans `config.yaml` sur les concurrentes IA pertinentes)._\n")
        return "\n".join(out) + "\n"

    out.append("| Boutique | Ventes | Δ7j ventes | Δ7j avis | Prix | Profil |")
    out.append("|----------|--------|-----------|----------|------|--------|")
    for p in mirrors:
        s = p.shop
        d = weekly_deltas.get(s.slug)
        dv = _signed(d.sales_delta) if d else "—"
        dr = _signed(d.reviews_delta) if d else "—"
        sales = s.total_sales if s.total_sales is not None else UNAVAILABLE
        price = fmt_price(s.avg_price_eur) if s.avg_price_eur else UNAVAILABLE
        prof = "INFÉRENCE IA" if p.ai.probably_ai else "IA-miroir (déclaré config)"
        out.append(f"| {s.slug} | {sales} | {dv} | {dr} | {price} | {prof} |")
    out.append("")
    out.append("**À faire apprendre à Claude chat (décisions à affiner) :**")
    out.append("- Quels formats/sets/prix de ces miroirs progressent le plus vite "
               "(Δ7j) → s'en inspirer, puis **faire mieux** (qualité, curation).")
    out.append("- Repérer leurs angles SEO/visuels récurrents → produire des "
               "alternatives **différenciées** (pas de copie).")
    out.append("- ⚠️ Données publiques cumulées : ventes ≠ CA mensuel ; « IA » = "
               "inférence, jamais une certitude.")
    out.append("")
    return "\n".join(out) + "\n"


def build_merged_guidelines(guidelines_md: str, competitors_md: str,
                            prompts_md: str, weekly_md: str = "") -> str:
    """
    Construit le BLOC UNIQUE à coller dans Claude chat. Il mène par la mission du
    jour (QC des rendus Grok + fiche Etsy complète), suivi des prompts du jour,
    puis — en annexes de référence — la stratégie et la veille complète. Un seul
    copier-coller suffit ; tu attaches en plus tes captures d'images Grok.
    """
    mission = (
        "# 🎯 BLOC À COLLER DANS CLAUDE CHAT — mission du jour\n\n"
        "_Colle ce bloc en entier dans Claude chat, **puis attache les captures "
        "d'écran de tes rendus Grok** (les variations générées pour chaque design "
        "+ les mockups). Tu as tout le contexte ci-dessous : pas besoin d'un autre "
        "fichier._\n\n"
        "## Ce que je te demande, Claude chat\n"
        "À partir des **captures que je joins** (les variations générées par "
        "design brut + les mockups réalisés par Grok Imagine) et des **prompts du "
        "jour** (section suivante), fais :\n\n"
        "1. **Sélection** — pour **chaque design brut**, dis **quelle variation "
        "GARDER** (1 gagnante) + 1 phrase de justification ; marque les autres "
        "REFAIRE/JETER.\n"
        "2. **Mockups** — indique quels **mockups one-shot Grok Imagine sont "
        "réussis** (cover comprise) et lesquels refaire (cadre coloré, "
        "translucidité, artefacts…).\n"
        "3. **Fiche Etsy complète prête à publier** :\n"
        "   - **Titre** (≤ 140 caractères, SEO, sans bourrage)\n"
        "   - **Description** (accroche + ce qui est inclus : nb de fichiers, "
        "ratios, 300 DPI, livraison ; usage perso)\n"
        "   - **13 tags** (≤ 20 caractères chacun, sur **une seule ligne**, "
        "séparés par « , »)\n"
        "   - **Couleur(s)** principale(s)\n"
        "   - **Prix** : single **6,90 €** · set de 3 **13,90 €** · set de 6 "
        "**26,90 €** (choisis le format adapté et justifie)\n\n"
        "**Critères de sélection** : warm organic minimalism, palette neutre/"
        "terracotta, formes pleines sans contour ; **différenciation** vs "
        "concurrentes (Annexe A) et vs mes fiches existantes (anti-répétition) ; "
        "qualité imprimable ; déclinable en set + multi-ratios. **Mockups jamais "
        "retouchés.** Aucune donnée inventée (CA = estimation ; pas de label IA "
        "sans preuve).\n"
    )
    sep = "\n\n---\n\n"
    doc = (
        mission
        + sep + "# 📎 Prompts Grok du jour (ce qui a été demandé à Grok)\n\n"
        + prompts_md.rstrip()
        + sep + "# 📎 ANNEXE A — Veille concurrentielle (contexte)\n\n"
        + competitors_md.rstrip()
    )
    if weekly_md.strip():
        doc += (sep + "# 📎 ANNEXE C — Veille hebdo boutiques IA "
                "(pour affiner tes décisions)\n\n" + weekly_md.rstrip())
    doc += (sep + "# 📎 ANNEXE B — Stratégie de référence (SEO, Pinterest, "
            "pricing, roadmap)\n\n" + guidelines_md.rstrip() + "\n")
    return doc


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
