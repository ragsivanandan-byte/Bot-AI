"""
image_pipeline.py — Upscale ×4 + export ratios (spec Claude Chat validée).

Invariants (non négociables) :
  * Aplats nets, zéro perte sur les formes pleines.
  * Le resize final est TOUJOURS une réduction (jamais d'agrandissement au crop).
  * Aucune dégradation silencieuse : repli/sous-taille -> ABORT avec message clair.
  * Center-crop, jamais fit/contain (aucun fond ajouté).
  * JPG qualité 90 (jamais 100), 4:4:4, 300 DPI, profil sRGB.

Profils :
  * SET    -> ancrage HAUTEUR 6912 ; ratios 2x3,3x4,4x5,5x7,11x14 ; master ≥ 5530 px.
  * SINGLE -> ancrage LARGEUR 4608 ; ratios 2x3,3x4 ; master ≥ 4608 px.

Nommage (déduit du stem du brut, AUCUN compteur) :
  SET    : NWD_T{tier}_{SetName}_{DesignName}[_{ratio}.jpg | _upscaled.png]
  SINGLE : NWD_T{tier}_{DesignName}[_{ratio}.jpg | _upscaled.png]
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("market_intel")

RATIOS = {"2x3": (2, 3), "3x4": (3, 4), "4x5": (4, 5),
          "5x7": (5, 7), "11x14": (11, 14)}
NWD_STEM_RE = re.compile(r"^NWD_T[1-4]_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)?$")

_DEFAULT_PROFILES = {
    "set": {"anchor": "height", "anchor_px": 6912,
            "ratios": ["2x3", "3x4", "4x5", "5x7", "11x14"],
            "min_master_width": 5530},
    "single": {"anchor": "width", "anchor_px": 4608,
               "ratios": ["2x3", "3x4"], "min_master_width": 4608},
}
_DEFAULT_JPEG = {"quality": 92, "subsampling": 0, "optimize": True,
                 "dpi": [300, 300], "sharpen": False,
                 "dither": True, "dither_sigma": 0.7}


# Largeur cible du master par défaut quand `target_width` n'est pas configuré :
# un peu au-dessus du minimum requis (marge pour le center-crop).
_MASTER_CAP_FACTOR = 1.08


def _pil():
    try:
        from PIL import Image
        # Nos images sont générées par nous (pas de contenu hostile) : on lève la
        # limite anti-"decompression bomb" pour pouvoir traiter de grands masters.
        Image.MAX_IMAGE_PIXELS = None
        return Image
    except Exception as e:
        logger.warning("Pillow manquant (%s) : pip install -r requirements.txt", e)
        return None


_SRGB_CACHE = "unset"


def _srgb_bytes():
    global _SRGB_CACHE
    if _SRGB_CACHE == "unset":
        try:
            from PIL import ImageCms
            _SRGB_CACHE = ImageCms.ImageCmsProfile(
                ImageCms.createProfile("sRGB")).tobytes()
        except Exception:
            _SRGB_CACHE = None
    return _SRGB_CACHE


def profile_for(kind: str, ip_cfg: dict) -> dict:
    profiles = (ip_cfg or {}).get("profiles") or _DEFAULT_PROFILES
    if kind not in profiles:
        raise ValueError(f"type inconnu : {kind!r} (attendu 'set' ou 'single')")
    return profiles[kind]


def validate_input_stem(stem: str, kind: str) -> None:
    """Vérifie le nom du brut + cohérence avec le type. Lève ValueError sinon."""
    if not NWD_STEM_RE.match(stem):
        raise ValueError(
            f"Brut mal nommé : '{stem}'. Attendu "
            "NWD_T#_{SetName}_{DesignName} (set) ou NWD_T#_{DesignName} (single), "
            "tokens PascalCase sans espace/underscore interne.")
    n_name = len(stem.split("_")) - 2          # retire NWD + tier
    if kind == "single" and n_name != 1:
        raise ValueError(f"'{stem}' : un single attend 1 token de nom, trouvé {n_name}.")
    if kind == "set" and n_name != 2:
        raise ValueError(f"'{stem}' : un set attend 2 tokens (SetName_DesignName), "
                         f"trouvé {n_name}.")


def _flatten(img):
    """RGBA/transparence -> composite sur blanc (jamais convert RGB aveugle/noir)."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        Image = _pil()
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB") if img.mode != "RGB" else img


def _dither_8bit(img, sigma: float = 0.7):
    """Anti-banding : ajoute un bruit gaussien TRÈS faible (σ≈0,7 niveau/255) en
    flottant avant la quantif 8-bit finale -> casse les marches des dégradés doux,
    invisible à l'œil. Sans effet si numpy absent ou σ<=0 (on renvoie tel quel)."""
    if sigma <= 0:
        return img
    try:
        import numpy as np
    except Exception:
        logger.warning("numpy absent : dithering anti-banding ignoré.")
        return img
    Image = _pil()
    arr = np.asarray(img, dtype=np.float32)
    arr += np.random.normal(0.0, sigma, arr.shape).astype(np.float32)
    arr = np.clip(arr, 0, 255).round().astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def upscale_x4(in_path: str, out_path: str, command: str = "",
               fallback_lanczos: bool = False, min_master_width: int = 0,
               passes: int = 1, target_width: int = 0) -> str:
    """
    Mode B (défaut, reco Claude Chat) : `passes` passe(s) d'upscale IA, puis
    FINITION Lanczos jusqu'à `target_width`. Sur des aplats/dégradés, au-delà du
    1er ×4 l'IA n'apporte rien de visible (et risque des halos) : on agrandit la
    fin en Lanczos. Renvoie 'external' ou 'lanczos'. Lève RuntimeError si :
      - upscaler IA absent ET fallback_lanczos=False (pas de dégradation muette) ;
      - master final sous `min_master_width`.
    ⚠️ `fallback_lanczos` (binaire IA absent -> repli/ABORT) est une notion
    DISTINCTE de la finition Lanczos du Mode B (toujours appliquée, assumée).
    """
    Image = _pil()
    if Image is None:
        raise RuntimeError("Pillow indisponible.")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    binary = command.split()[0] if command.strip() else ""
    target = int(target_width) or round(min_master_width * _MASTER_CAP_FACTOR)
    used = ""

    if binary and shutil.which(binary):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cur = in_path
            last = in_path
            for i in range(max(1, int(passes))):     # Mode B = 1 passe IA
                step = str(Path(td) / f"pass{i}.png")
                cmd = [cur if p == "{input}" else (step if p == "{output}" else p)
                       for p in command.split()]
                subprocess.run(cmd, capture_output=True, timeout=1800)
                if not Path(step).exists():     # certains outils ajoutent un suffixe
                    for cand in Path(td).glob("*upscayl*" + Path(step).suffix):
                        cand.rename(step)
                        break
                if not (Path(step).exists() and Path(step).stat().st_size > 0):
                    raise RuntimeError("Upscaler externe : aucune sortie produite.")
                last, cur = step, step
            # Finition Mode B : normalise la largeur du master à `target` (Lanczos
            # — agrandissement assumé sur aplats, ou réduction si passes>1).
            img = Image.open(last)
            if target and img.width != target:
                img = _flatten(img)
                new_h = round(img.height * target / img.width)
                img.resize((target, new_h), Image.LANCZOS).save(out)
            else:
                shutil.copyfile(last, out)
        used = "external"
    elif fallback_lanczos:
        logger.warning("⚠️ Upscaler IA absent -> repli Lanczos ×4 (accepté car "
                       "fallback_lanczos=true).")
        img = _flatten(Image.open(in_path))
        img.resize((img.width * 4, img.height * 4), Image.LANCZOS).save(out)
        used = "lanczos"
    else:
        raise RuntimeError(
            "Upscaler IA introuvable ET fallback_lanczos=false -> ABORT (aucune "
            "dégradation muette). Configure image_pipeline.upscale.command "
            "(Upscayl/Real-ESRGAN) ou mets image_pipeline.upscale.fallback_lanczos: true.")

    if min_master_width:
        w = Image.open(out).width
        if w < min_master_width:
            raise RuntimeError(
                f"Master trop petit ({w}px < {min_master_width}px requis) après "
                f"upscale. Régénère un brut PLUS GRAND ou augmente upscale.target_width.")
    return used


def center_crop_to_ratio(img, rw: int, rh: int):
    """Recadre au centre à l'aspect rw:rh (crop seul, aucun fond ajouté)."""
    W, H = img.size
    target = rw / rh
    if W / H > target:                          # trop large -> rogne la largeur
        nw = round(H * target)
        x = (W - nw) // 2
        return img.crop((x, 0, x + nw, H))
    nh = round(W / target)                       # trop haut -> rogne la hauteur
    y = (H - nh) // 2
    return img.crop((0, y, W, y + nh))


def export_ratio(master, ratio_key: str, anchor: str, anchor_px: int,
                 dest: str, jpeg: dict | None = None) -> tuple[int, int]:
    """
    Exporte un ratio en JPEG (downscale only). Lève ValueError si le master est
    trop petit (jamais d'agrandissement). Renvoie (largeur, hauteur).
    """
    Image = _pil()
    jpeg = {**_DEFAULT_JPEG, **(jpeg or {})}
    rw, rh = RATIOS[ratio_key]
    crop = center_crop_to_ratio(master, rw, rh)
    if anchor == "height":
        h = int(anchor_px); w = round(anchor_px * rw / rh)
    else:
        w = int(anchor_px); h = round(anchor_px * rh / rw)
    if crop.width < w or crop.height < h:
        raise ValueError(
            f"master trop petit pour {ratio_key} : crop {crop.size} < cible {(w, h)}. "
            "Régénérer un brut plus grand — NE PAS upscaler ici.")
    out = _flatten(crop.resize((w, h), Image.LANCZOS))   # toujours une réduction
    if jpeg.get("dither", True):                          # anti-banding des dégradés
        out = _dither_8bit(out, float(jpeg.get("dither_sigma", 0.7)))
    save_kwargs = dict(quality=min(int(jpeg["quality"]), 95),
                       optimize=bool(jpeg.get("optimize", True)),
                       subsampling=int(jpeg.get("subsampling", 0)),
                       dpi=tuple(jpeg.get("dpi", [300, 300])))
    icc = _srgb_bytes()
    if icc:
        save_kwargs["icc_profile"] = icc
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "JPEG", **save_kwargs)
    return (w, h)


def jpeg_info(path: str) -> dict:
    """Métadonnées d'un JPG produit (pour l'étape verify / tests)."""
    Image = _pil()
    im = Image.open(path)
    return {"size": im.size, "mode": im.mode,
            "dpi": tuple(int(v) for v in im.info.get("dpi", (0, 0))),
            "icc": bool(im.info.get("icc_profile")),
            "bytes": Path(path).stat().st_size}
