"""
prompt_generator.py — Brief visuel quotidien pour Grok (Imagine / Build).

Produit le flux validé par Claude Chat :
  * 3 prompts d'IMAGES BRUTES (un set de 3 designs cohérents, formes pleines) ;
  * 4 prompts de MOCKUPS d'ambiance dont 1 COVER (compositing, jamais retouché) ;
  * 1 prompt VIDÉO 6 s (image-to-video, image figée à chaque frame).

Les formules de prompt sont ÉPROUVÉES (session de prod manuelle) :
  - images : « fully painted solid shape / no outline », negative anti-arc-en-ciel ;
  - mockups : « Compositing task, NOT art generation / PASTE UNCHANGED / OPAQUE » ;
  - vidéo : « frozen and identical in every frame, slow zoom-in only ».

Sélection : déterministe par DATE (rotation des recettes/jour), en priorisant les
sous-niches sous-exploitées et en évitant les sujets saturés (anti-répétition).

⚠️ Ce module ne GÉNÈRE pas d'images : il rédige les prompts. La génération
(Grok), le QC (humain/Claude Chat) et la publication Etsy restent MANUELS.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from .seo import SeoOpportunity
from .utils import UNAVAILABLE

logger = logging.getLogger("market_intel")

# --- Templates de prompts (formules éprouvées) -------------------------------

_RAW_TEMPLATE = (
    "{subject}, fully painted solid shape, no outline, flat color blocks only, "
    "warm minimalist organic style, palette: {palette}, {fmt}, centered "
    "composition, generous negative space, matte texture, high-resolution wall "
    "art. NEGATIVE: no line drawing, not an outline, no rainbow, no concentric "
    "stripes, no childish style, no text, no watermark, no border."
)

_COVER_TEMPLATE = (
    "Compositing task, NOT art generation. PASTE the provided poster ({ref}) "
    "UNCHANGED, pixel-for-pixel. Keep the artwork OPAQUE (never translucent). "
    "COVER scene: thin light-oak frame + white mat, design centered, {fmt}, "
    "{room}, warm neutral interior, soft daylight, calm minimalist styling. "
    "High resolution (>= 2000 px on the short side)."
)

_MOCKUP_TEMPLATE = (
    "Compositing task, NOT art generation. PASTE the provided poster ({ref}) "
    "UNCHANGED, pixel-for-pixel. Keep the artwork OPAQUE (never translucent). "
    "Scene: thin light-oak frame + white mat, {room}, warm neutral interior, "
    "soft daylight, calm minimalist styling."
)

_VIDEO_TEMPLATE = (
    "image-to-video. Source = the finished COVER mockup still. Treat the artwork "
    "as a STATIC printed image, frozen and identical in every frame. Slow "
    "zoom-in only. No pan, no drift, no flicker, no morphing. {fmt}, 6 seconds."
)

# Recette de repli si la config n'en fournit pas.
_FALLBACK_RECIPE = {
    "name": "Warm organic shapes",
    "keyword": "neutral organic shapes wall art set",
    "format": "2:3 vertical",
    "designs": [
        "ONE large bold solid arch + ONE solid circle, two flat color blocks only",
        "solid filled rolling dune ridge silhouette, layered flat horizontal bands",
        "solid filled organic pebble cluster, three flat color blocks",
    ],
}


# --- Modèle de données -------------------------------------------------------

@dataclass
class ImagePrompt:
    label: str
    filename: str
    prompt_text: str


@dataclass
class MockupPrompt:
    label: str
    is_cover: bool
    filename: str
    prompt_text: str


@dataclass
class DailyVisualBrief:
    date: str
    theme: str
    fmt: str
    seo_pillar: str
    seo_volume: str
    why: str
    sources: list[str] = field(default_factory=list)
    palette: list[str] = field(default_factory=list)
    avoid_note: str = ""
    raw_prompts: list[ImagePrompt] = field(default_factory=list)
    mockup_prompts: list[MockupPrompt] = field(default_factory=list)
    video_prompt: str = ""
    output_dir: str = "~/Downloads"
    slug: str = "NWD_Set"


def _slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "", name.title())
    return s[:24] or "Set"


def _rotating(items: list, start: int, n: int) -> list:
    if not items:
        return []
    return [items[(start + j) % len(items)] for j in range(n)]


def generate_daily_brief(grok_cfg: dict, niche_cfg: dict,
                         opportunities: list[SeoOpportunity],
                         seed_date: date | None = None) -> DailyVisualBrief:
    """Construit le brief visuel du jour (3 images -> 4 mockups+cover -> 1 vidéo)."""
    seed_date = seed_date or date.today()
    ordinal = seed_date.toordinal()  # rotation déterministe par jour

    recipes = list(grok_cfg.get("set_recipes") or []) or [_FALLBACK_RECIPE]
    recipe = recipes[ordinal % len(recipes)]
    designs = list(recipe.get("designs") or _FALLBACK_RECIPE["designs"])[:3]
    fmt = recipe.get("format", "2:3 vertical")
    theme = recipe.get("name", "Set")
    keyword = recipe.get("keyword", theme)
    slug = "NWD_" + _slugify(theme)

    palette_all = list(grok_cfg.get("palette") or ["warm neutral tones"])
    palette = _rotating(palette_all, ordinal, min(4, len(palette_all)))
    palette_str = ", ".join(palette)

    rooms_all = list(grok_cfg.get("mockup_rooms") or
                     ["a calm warm neutral interior, light-oak frame"])
    output_dir = grok_cfg.get("output_dir", "~/Downloads")

    # --- SEO : volume réel / intérêt relatif / à valider --------------------
    op = _match_opportunity(keyword, opportunities)
    if op and getattr(op, "search_volume", None) is not None:
        seo_volume = (f"{op.search_volume} recherches/mois (volume réel "
                      f"Keywords Everywhere)")
        why = op.rationale
        sources = op.sources
    elif op and op.relative_interest is not None:
        seo_volume = (f"intérêt relatif Google Trends ≈ {op.relative_interest}/100 "
                      f"({op.direction})")
        why = op.rationale
        sources = op.sources
    else:
        seo_volume = f"{UNAVAILABLE} (à valider eRank)"
        why = "sous-niche sous-exploitée (carte anti-répétition) à confirmer SEO"
        sources = ["config.yaml (recette)"]

    # --- Anti-répétition -----------------------------------------------------
    saturated = [s for s in niche_cfg.get("saturated_topics", [])]
    avoid_note = ("Éviter (saturé / déjà couvert) : " + ", ".join(saturated)
                  if saturated else "—")

    # --- 3 images brutes -----------------------------------------------------
    raw_prompts = []
    for i, subject in enumerate(designs, 1):
        raw_prompts.append(ImagePrompt(
            label=f"Design {i}",
            filename=f"{slug}_{i:02d}_<ratio>.jpg",
            prompt_text=_RAW_TEMPLATE.format(subject=subject,
                                             palette=palette_str, fmt=fmt)))

    # --- 4 mockups (1 cover + 3 ambiance), 1 design par mockup ---------------
    rooms = _rotating(rooms_all, ordinal, 4)
    mockup_prompts = [MockupPrompt(
        label="COVER (Design 1)", is_cover=True, filename=f"{slug}_Cover.png",
        prompt_text=_COVER_TEMPLATE.format(ref="Design 1", fmt=fmt, room=rooms[0]))]
    for k in range(3):
        ref = f"Design {k + 1}"
        mockup_prompts.append(MockupPrompt(
            label=f"Mockup {k + 2} ({ref})", is_cover=False,
            filename=f"{slug}_Mockup_{k + 2:02d}.png",
            prompt_text=_MOCKUP_TEMPLATE.format(ref=ref, room=rooms[k + 1])))

    # --- vidéo 6 s -----------------------------------------------------------
    video_fmt = fmt if "vertical" in fmt or "1:1" in fmt else "2:3 vertical"
    video_prompt = _VIDEO_TEMPLATE.format(fmt=video_fmt)

    logger.info("Brief visuel du jour : recette « %s » (%s), pilier SEO « %s ».",
                theme, fmt, keyword)
    return DailyVisualBrief(
        date=seed_date.isoformat(), theme=theme, fmt=fmt, seo_pillar=keyword,
        seo_volume=seo_volume, why=why, sources=sources, palette=palette,
        avoid_note=avoid_note, raw_prompts=raw_prompts,
        mockup_prompts=mockup_prompts, video_prompt=video_prompt,
        output_dir=output_dir, slug=slug)


def _match_opportunity(keyword: str,
                       opportunities: list[SeoOpportunity]) -> SeoOpportunity | None:
    """Trouve l'opportunité SEO qui recouvre le mieux le mot-clé de la recette."""
    kw = set(keyword.lower().split())
    best, best_overlap = None, 0
    for o in opportunities:
        overlap = len(kw & set(o.keyword.lower().split()))
        if overlap > best_overlap:
            best, best_overlap = o, overlap
    return best if best_overlap >= 1 else None
