"""
prompt_generator.py — Génère les 5 prompts Grok du jour.

Contraintes du brief, appliquées telles quelles :
  * 5 prompts/jour, prêts à copier-coller.
  * Structure imposée pour formes pleines/solides :
      description forme + "solid filled [forme] silhouette"
      + "fully painted solid shape no outline"
      + negative prompt "no line drawing, not an outline"
      + palette précise + style.
  * Chaque prompt cible une demande CONFIRMÉE (issue de seo.py), pas au hasard.
  * Évite les sujets saturés ; vise les sous-niches montantes.
  * Indique le pilier SEO, le volume estimé (honnête : intérêt relatif ou
    "à valider"), et POURQUOI la demande est confirmée + source.

Déterminisme : la sélection est seedée par la DATE -> reproductible pour un jour
donné, mais varie de jour en jour (rotation des sujets et palettes).
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import date

from .seo import SeoOpportunity
from .utils import UNAVAILABLE

logger = logging.getLogger("market_intel")


@dataclass
class GrokPrompt:
    index: int
    shape: str
    seo_pillar: str
    demand_confirmation: str
    estimated_volume: str
    why_confirmed: str
    sources: list[str]
    palette: list[str]
    style: str
    prompt_text: str = ""

    def build_text(self) -> None:
        """Assemble le prompt final selon la structure imposée."""
        palette_str = ", ".join(self.palette)
        article = "An" if self.shape[:1].lower() in "aeiou" else "A"
        # Évite "silhouette silhouette" si la forme contient déjà le mot.
        shape_core = self.shape
        if shape_core.lower().endswith("silhouette"):
            shape_core = shape_core[: -len("silhouette")].strip()
        self.prompt_text = (
            f"{article} {self.shape}, solid filled {shape_core} silhouette, "
            f"fully painted solid shape no outline, flat {self.style} style, "
            f"warm organic minimalism, color palette: {palette_str}, "
            f"centered composition, generous negative space, matte texture, "
            f"high-resolution wall art print. "
            f"Negative prompt: no line drawing, not an outline, no outlines, "
            f"no text, no watermark, no border, no photorealism."
        )


def _daily_rng(seed_date: date) -> random.Random:
    """RNG déterministe pour la date (reproductible le même jour)."""
    return random.Random(seed_date.toordinal())


def generate_daily_prompts(grok_cfg: dict, niche_cfg: dict,
                           opportunities: list[SeoOpportunity],
                           seed_date: date | None = None) -> list[GrokPrompt]:
    """
    Produit `count_per_day` prompts Grok ciblant les meilleures opportunités SEO
    non saturées, en rotation quotidienne.
    """
    seed_date = seed_date or date.today()
    rng = _daily_rng(seed_date)

    count = int(grok_cfg.get("count_per_day", 5))
    palette = list(grok_cfg.get("palette", []))
    styles = list(grok_cfg.get("styles", ["gouache flat graphic"]))
    shapes = list(grok_cfg.get("shape_pool", []))

    # On privilégie les opportunités les plus confirmées et NON saturées.
    ranked_ops = [o for o in opportunities if not o.saturated] or opportunities
    if not ranked_ops:
        # Repli total : on construit des opportunités fictives "à valider".
        ranked_ops = [SeoOpportunity(kw, "à valider",
                      "repli : aucune opportunité fournie", ["config.yaml"])
                      for kw in niche_cfg.get("pillars", ["neutral wall art"])]

    # Rotation des formes selon le jour pour éviter la répétition.
    rng.shuffle(shapes)
    if not shapes:
        shapes = ["abstract organic shape"]

    prompts: list[GrokPrompt] = []
    for i in range(count):
        op = ranked_ops[i % len(ranked_ops)]
        shape = shapes[i % len(shapes)]
        # Palette : 3 couleurs tournantes pour la cohérence visuelle.
        chosen_palette = _rotating_slice(palette, start=i * 2, n=3,
                                         rng=rng) or ["warm neutral tones"]
        style = styles[i % len(styles)]

        # Priorité au volume RÉEL (Keywords Everywhere) s'il existe, sinon
        # intérêt relatif Trends, sinon « à valider ».
        if getattr(op, "search_volume", None) is not None:
            comp_txt = (f", concurrence {op.competition:.2f}/1"
                        if op.competition is not None else "")
            vol = (f"{op.search_volume} recherches/mois (volume RÉEL, source "
                   f"Keywords Everywhere — proxy Google){comp_txt}")
        elif op.relative_interest is not None:
            vol = (f"intérêt relatif Google Trends ≈ {op.relative_interest}/100 "
                   f"({op.direction})")
        else:
            vol = f"{UNAVAILABLE} (volume absolu non public — à valider eRank)"

        gp = GrokPrompt(
            index=i + 1,
            shape=shape,
            seo_pillar=op.keyword,
            demand_confirmation=op.confirmation,
            estimated_volume=vol,
            why_confirmed=op.rationale,
            sources=op.sources,
            palette=chosen_palette,
            style=style,
        )
        gp.build_text()
        prompts.append(gp)

    # Avertissement de sécurité si on a dû taper dans des sujets non confirmés.
    n_confirmed = sum(1 for p in prompts if p.demand_confirmation == "confirmée")
    logger.info("Prompts Grok générés : %d (dont %d sur demande confirmée).",
                len(prompts), n_confirmed)
    return prompts


def _rotating_slice(items: list[str], start: int, n: int,
                    rng: random.Random) -> list[str]:
    """Prend n éléments en boucle à partir de `start` (palette tournante)."""
    if not items:
        return []
    return [items[(start + j) % len(items)] for j in range(min(n, len(items)))]
