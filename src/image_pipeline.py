"""
image_pipeline.py — Upscale ×4 + export multi-ratios (équivalent Photopea).

Deux briques pures (testables, sans réseau) :
  * upscale_x4()  : agrandit ×4 une image. Utilise un upscaler externe
    (Upscayl / Real-ESRGAN) si configuré ET présent ; sinon repli Lanczos ×4
    (très propre pour des aplats de couleur, le style NWD).
  * export_ratios() : pour une image, produit les 5 ratios fixes en JPG.
    Spécif. confirmées par Claude Chat : hauteur FIXE (6912 px), largeur = ratio,
    JPG qualité 90 (jamais 100 — sinon fichiers trop lourds, refusés par Etsy).

Dépendance : Pillow (importée paresseusement ; si absente, on le signale).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("market_intel")

# Ratios d'export standard NWD (largeur:hauteur).
DEFAULT_RATIOS = [(2, 3), (3, 4), (4, 5), (5, 7), (11, 14)]


def _pil():
    try:
        from PIL import Image
        return Image
    except Exception as e:
        logger.warning("Pillow manquant (%s) : pip install -r requirements.txt", e)
        return None


def parse_ratios(ratios) -> list[tuple[int, int]]:
    """Convertit ['2:3','3:4'...] en [(2,3),(3,4)...]. Tolère déjà des tuples."""
    out = []
    for r in ratios or []:
        if isinstance(r, (tuple, list)) and len(r) == 2:
            out.append((int(r[0]), int(r[1])))
        else:
            w, h = str(r).split(":")
            out.append((int(w), int(h)))
    return out or list(DEFAULT_RATIOS)


def upscale_x4(in_path: str, out_path: str, command: str = "") -> bool:
    """
    Agrandit ×4. Si `command` (template avec {input}/{output}) cible un binaire
    présent, on l'utilise ; sinon repli Lanczos ×4. Renvoie True si un fichier de
    sortie a été produit.
    """
    Image = _pil()
    if Image is None:
        return False
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    binary = command.split()[0] if command.strip() else ""
    if binary and shutil.which(binary):
        # On remplace les jetons {input}/{output} sans casser les chemins à espaces.
        cmd = [in_path if p == "{input}" else (out_path if p == "{output}" else p)
               for p in command.split()]
        try:
            subprocess.run(cmd, capture_output=True, timeout=900)
            if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
                logger.info("Upscale externe OK : %s", out_path)
                return True
            logger.warning("Upscaler externe sans sortie -> repli Lanczos.")
        except Exception as e:
            logger.warning("Upscaler externe en échec (%s) -> repli Lanczos.", e)

    try:
        img = Image.open(in_path).convert("RGB")
        img = img.resize((img.width * 4, img.height * 4), Image.LANCZOS)
        img.save(out_path)
        logger.info("Upscale Lanczos ×4 : %s", out_path)
        return True
    except Exception as e:
        logger.warning("Upscale impossible (%s) : %s", in_path, e)
        return False


def _center_crop_to_ratio(img, rw: int, rh: int):
    """Recadre au centre à l'aspect rw:rh (garde le sujet centré)."""
    W, H = img.size
    target = rw / rh
    if W / H > target:                    # trop large -> on rogne la largeur
        new_w = int(round(H * target))
        x = (W - new_w) // 2
        return img.crop((x, 0, x + new_w, H))
    new_h = int(round(W / target))        # trop haut -> on rogne la hauteur
    y = (H - new_h) // 2
    return img.crop((0, y, W, y + new_h))


def export_ratios(src_path: str, out_dir: str, stem: str,
                  target_height: int = 6912, quality: int = 90,
                  ratios=None) -> list[Path]:
    """
    Exporte `src_path` en plusieurs ratios JPG (hauteur fixe `target_height`,
    largeur = ratio, qualité `quality`). Renvoie la liste des fichiers écrits.
    """
    Image = _pil()
    if Image is None:
        return []
    ratios = parse_ratios(ratios) if ratios else list(DEFAULT_RATIOS)
    quality = min(int(quality), 95)       # garde-fou : jamais 100
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        base = Image.open(src_path).convert("RGB")
    except Exception as e:
        logger.warning("Image illisible (%s) : %s", src_path, e)
        return []

    written = []
    for rw, rh in ratios:
        cropped = _center_crop_to_ratio(base, rw, rh)
        w = int(round(target_height * rw / rh))
        resized = cropped.resize((w, target_height), Image.LANCZOS)
        dest = out / f"{stem}_{rw}x{rh}.jpg"
        resized.save(dest, "JPEG", quality=quality)
        written.append(dest)
    logger.info("Export %d ratios depuis %s -> %s", len(written), stem, out_dir)
    return written
