"""
prompt_generator.py — Brief visuel quotidien pour Grok (Imagine / Build).

Produit le flux validé + raffiné (retour Claude Chat 06/06) :
  * N variations par DESIGN brut (formes pleines, 1 couleur de forme + 1 fond) ;
  * 4 MOCKUPS dont 1 COVER (la cover REMPLIT l'image) + 1 gros plan DÉTAIL ;
  * 1 prompt VIDÉO 6 s (image-to-video, image figée) ;
  * + (sets) 1 prompt GALLERY WALL bonus (cover idéale, mais cas dur en headless).

Principes (Claude Chat) :
  - couleur PILOTÉE par le positif : 1 `{shape_color}` + 1 `{bg_color}` par design
    (anti arc-en-ciel + set cohérent), fond explicite ;
  - negatives COURTS et priorisés ;
  - mockups = compositing strict (« do NOT redraw / place UNCHANGED / OPAQUE »).

⚠️ Ce module rédige les prompts ; la génération (Grok), le QC (humain) et la
publication restent MANUELS.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from .seo import SeoOpportunity
from .utils import UNAVAILABLE

logger = logging.getLogger("market_intel")

# --- Templates (formules raffinées Claude Chat) ------------------------------

# Image brute avec rôles couleur explicites (1 forme + 1 fond).
_RAW_TEMPLATE = (
    "{subject}, depicted as ONE single flat solid shape in {shape_color}, fully "
    "painted, no outline, no shading, no gradient, set against a plain solid "
    "{bg_color} background. Warm minimalist organic wall-art style, matte finish. "
    "{fmt}, centered composition with generous even margins and negative space "
    "around the shape. Clean, calm, high-resolution printable poster art. "
    "NEGATIVE: outline, line drawing, stroke, rainbow, multicolor, gradient, "
    "drop shadow, 3D, photo-realistic, busy background, texture noise, frame, "
    "mat, text, watermark, border, childish, cartoon."
)

# Repli si pas de palette nommée : on borne à 2 couleurs de la liste.
_RAW_TEMPLATE_FALLBACK = (
    "{subject}, ONE flat solid shape, no outline, using at most TWO of these "
    "warm-neutral colors: {palette}, on a plain solid background in the lightest "
    "of those colors. Warm minimalist organic wall-art style, matte finish. "
    "{fmt}, centered composition with generous even margins and negative space. "
    "High-resolution printable poster art. NEGATIVE: outline, line drawing, "
    "rainbow, multicolor, gradient, drop shadow, 3D, photo-realistic, busy "
    "background, text, watermark, border, childish."
)

_COVER_TEMPLATE = (
    "Compositing task — do NOT generate, redraw or reinterpret any art. Take the "
    "PROVIDED poster image ({ref}) and place it UNCHANGED, pixel-for-pixel, "
    "inside the frame. Keep it fully OPAQUE; never recolor, restyle, blur or crop "
    "it — if unsure, reproduce it exactly. Frame: thin light-oak wood frame with "
    "a white mat, sized to the poster's {fmt} ratio so the whole artwork is fully "
    "visible and undistorted. COVER composition: the framed print is the clear "
    "focal point and FILLS MOST of the image (shot fairly close), hanging in "
    "{room}, warm neutral interior, soft natural daylight, calm minimalist "
    "styling, gentle realistic shadow. High resolution (>= 2000 px on the short "
    "side). NEGATIVE: redrawn artwork, altered colors, translucent print, extra "
    "posters, text, logo, watermark, people, clutter, colored frame, black "
    "frame, gray frame, busy decor."
)

_MOCKUP_TEMPLATE = (
    "Compositing task — do NOT generate, redraw or reinterpret any art. Take the "
    "PROVIDED poster image ({ref}) and place it UNCHANGED, pixel-for-pixel, "
    "inside the frame. Keep it fully OPAQUE; never recolor or restyle it. Frame: "
    "thin light-oak frame + white mat, sized to the poster's {fmt} ratio, artwork "
    "fully visible. Scene: {room}, warm neutral interior, soft daylight, calm "
    "minimalist styling; the framed print stays the focal point with realistic "
    "perspective and shadow. NEGATIVE: redrawn artwork, altered colors, "
    "translucent print, text, logo, watermark, people, clutter, colored frame, "
    "black frame, gray frame."
)

_DETAIL_TEMPLATE = (
    "Compositing task — do NOT generate, redraw or reinterpret any art. Take the "
    "PROVIDED poster image ({ref}) and place it UNCHANGED, pixel-for-pixel, "
    "inside a thin light-oak frame + white mat. CLOSE-UP detail shot: corner of "
    "the frame and part of the print, shallow depth of field, soft daylight, "
    "matte paper texture visible, premium minimalist feel. Keep the artwork "
    "OPAQUE and exact. NEGATIVE: redrawn artwork, altered colors, translucent "
    "print, text, logo, watermark, full room, people, clutter, colored frame."
)

_VIDEO_TEMPLATE = (
    "image-to-video from the PROVIDED still ({ref} = the finished COVER mockup in "
    "its room). Treat EVERYTHING as a STATIC photograph: the framed artwork, the "
    "frame, the room and the furniture stay frozen, sharp and identical in EVERY "
    "frame — no shape, color or content change. Camera: ONE very slow, smooth "
    "zoom-in (push-in) only — no pan, no rotation, no parallax, no drift, and "
    "absolutely NO moving light sweep or glare crossing the image. {fmt}, 6 "
    "seconds, calm premium feel, no audio. NEGATIVE: light streak, moving glare, "
    "lens flare, morphing, warping, redrawing, flicker, shape-shifting, text "
    "appearing, distortion, fast motion, camera shake."
)

_GALLERY_TEMPLATE = (
    "Compositing task — do NOT redraw any art. Arrange the THREE provided posters "
    "({refs}) as a balanced gallery wall, each inside its own thin light-oak "
    "frame + white mat, all UNCHANGED and OPAQUE, evenly spaced and aligned "
    "above {room}. Cohesive set, warm neutral interior, soft daylight. NEGATIVE: "
    "redrawn artwork, altered colors, translucent prints, mismatched frames, "
    "text, watermark, clutter."
)

# Recette de repli si la config n'en fournit pas.
_FALLBACK_RECIPE = {
    "name": "Warm organic shapes",
    "keyword": "neutral organic shapes wall art set",
    "format": "2:3 vertical",
    "designs": [
        "ONE large bold solid arch + ONE solid circle",
        "solid filled rolling dune ridge silhouette, layered flat bands",
        "solid filled organic pebble cluster",
    ],
}


# --- Modèle de données -------------------------------------------------------

@dataclass
class ImagePrompt:
    label: str
    filename: str
    prompt_text: str
    variation_files: list[str] = field(default_factory=list)


@dataclass
class MockupPrompt:
    label: str
    is_cover: bool
    filename: str
    prompt_text: str
    design_index: int = 0   # quel design (0-based) ce mockup colle


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
    gallery_prompt: str = ""    # cover gallery-wall (sets) — bonus interactif/API
    output_dir: str = "~/Downloads"
    slug: str = "NWD_Set"


def _slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "", name.title())
    return s[:24] or "Set"


def _resolve_palette(recipe: dict, grok_cfg: dict):
    """
    Renvoie (mode, data) :
      - ("roles", {"shapes": [...], "bg": "..."}) si une palette NOMMÉE existe ;
      - ("fallback", "c1, c2, ...") sinon (liste à plat de repli).
    """
    name = recipe.get("palette")
    palettes = grok_cfg.get("palettes") or {}
    if name and name in palettes:
        p = palettes[name]
        shapes = p.get("shapes") or ["warm taupe #B9A88F"]
        bg = p.get("bg", "cream #F4EBDD")
        return "roles", {"shapes": shapes, "bg": bg}
    flat = ", ".join(grok_cfg.get("palette") or ["warm neutral tones"])
    return "fallback", flat


def generate_daily_brief(grok_cfg: dict, niche_cfg: dict,
                         opportunities: list[SeoOpportunity],
                         seed_date: date | None = None) -> DailyVisualBrief:
    """Construit le brief visuel du jour (designs -> mockups+cover+détail -> vidéo)."""
    seed_date = seed_date or date.today()
    ordinal = seed_date.toordinal()

    recipes = list(grok_cfg.get("set_recipes") or []) or [_FALLBACK_RECIPE]
    recipe = recipes[ordinal % len(recipes)]
    designs = list(recipe.get("designs") or _FALLBACK_RECIPE["designs"])
    n = len(designs)
    fmt = recipe.get("format", "2:3 vertical")
    theme = recipe.get("name", "Set")
    keyword = recipe.get("keyword", theme)
    slug = "NWD_" + _slugify(theme)

    pmode, pdata = _resolve_palette(recipe, grok_cfg)
    rooms = list(recipe.get("mockup_rooms") or grok_cfg.get("mockup_rooms")
                 or ["a calm warm neutral interior"])
    output_dir = grok_cfg.get("output_dir", "~/Downloads")
    n_var = int(grok_cfg.get("variations_per_design", 8))

    # --- SEO ----------------------------------------------------------------
    op = _match_opportunity(keyword, opportunities)
    if op and getattr(op, "search_volume", None) is not None:
        seo_volume = f"{op.search_volume} recherches/mois (Keywords Everywhere)"
        why, sources = op.rationale, op.sources
    elif op and op.relative_interest is not None:
        seo_volume = (f"intérêt relatif Google Trends ≈ {op.relative_interest}/100 "
                      f"({op.direction})")
        why, sources = op.rationale, op.sources
    else:
        seo_volume = f"{UNAVAILABLE} (à valider eRank)"
        why = "sous-niche sous-exploitée (carte anti-répétition) — SEO à valider"
        sources = ["config.yaml (recette)"]

    saturated = list(niche_cfg.get("saturated_topics", []))
    avoid_note = ("Éviter (saturé) : " + ", ".join(saturated)) if saturated else "—"

    # --- Images brutes (1 couleur de forme + 1 fond par design) -------------
    raw_prompts, palette_used = [], []
    for i, subject in enumerate(designs, 1):
        if pmode == "roles":
            shape_color = pdata["shapes"][(i - 1) % len(pdata["shapes"])]
            bg_color = pdata["bg"]
            palette_used = pdata["shapes"] + [pdata["bg"]]
            text = _RAW_TEMPLATE.format(subject=subject, shape_color=shape_color,
                                        bg_color=bg_color, fmt=fmt)
        else:
            palette_used = (grok_cfg.get("palette") or [])
            text = _RAW_TEMPLATE_FALLBACK.format(subject=subject, palette=pdata,
                                                 fmt=fmt)
        variations = [f"{slug}_{i:02d}_v{k}.png" for k in range(1, n_var + 1)]
        raw_prompts.append(ImagePrompt(
            label=f"Design {i}", filename=f"{slug}_{i:02d}_<ratio>.jpg",
            prompt_text=text, variation_files=variations))

    # --- 4 mockups : cover(D1) + ambiances + 1 gros plan détail -------------
    mockups = [MockupPrompt(
        label="COVER (Design 1)", is_cover=True, filename=f"{slug}_Cover.png",
        design_index=0,
        prompt_text=_COVER_TEMPLATE.format(ref="Design 1", fmt=fmt, room=rooms[0]))]
    # 3 mockups suivants : refs selon le nb de designs, dernier = détail.
    if n >= 3:
        plan = [(1, "room"), (2, "room"), (0, "detail")]
    elif n == 2:
        plan = [(1, "room"), (0, "room"), (0, "detail")]
    else:
        plan = [(0, "room"), (0, "room"), (0, "detail")]
    for k, (di, kind) in enumerate(plan, start=2):
        ref = f"Design {di + 1}"
        room = rooms[(k - 1) % len(rooms)]
        if kind == "detail":
            text = _DETAIL_TEMPLATE.format(ref=ref)
            label = f"Mockup {k} (gros plan détail, {ref})"
        else:
            text = _MOCKUP_TEMPLATE.format(ref=ref, fmt=fmt, room=room)
            label = f"Mockup {k} ({ref})"
        mockups.append(MockupPrompt(label=label, is_cover=False,
                                    filename=f"{slug}_Mockup_{k:02d}.png",
                                    design_index=di, prompt_text=text))

    # --- Gallery wall (sets) : cover idéale, mais cas dur en headless --------
    gallery_prompt = ""
    if n >= 3:
        refs = ", ".join(f"Design {j}" for j in range(1, n + 1))
        gallery_prompt = _GALLERY_TEMPLATE.format(refs=refs, room=rooms[0])

    # --- Vidéo 6 s ----------------------------------------------------------
    # Frame TV -> 16:9 ; portrait/carré -> tel quel ; sinon (panorama 3:1) -> 2:3
    # pour Pinterest. JAMAIS du 2:1 (cf. feedback Claude Chat).
    if "16:9" in fmt:
        video_fmt = "16:9 horizontal"
    elif "vertical" in fmt or "1:1" in fmt:
        video_fmt = fmt
    else:
        video_fmt = "2:3 vertical"
    video_prompt = _VIDEO_TEMPLATE.format(ref="Cover", fmt=video_fmt)

    logger.info("Brief visuel : « %s » (%s, %d design(s)), pilier « %s ».",
                theme, fmt, n, keyword)
    return DailyVisualBrief(
        date=seed_date.isoformat(), theme=theme, fmt=fmt, seo_pillar=keyword,
        seo_volume=seo_volume, why=why, sources=sources, palette=palette_used,
        avoid_note=avoid_note, raw_prompts=raw_prompts, mockup_prompts=mockups,
        video_prompt=video_prompt, gallery_prompt=gallery_prompt,
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
