"""
mockup_compositor.py — Compositing EXACT (pixel-for-pixel) sans IA.

Insère TON fichier design, inchangé, dans un gabarit de mockup (photo de pièce
avec un emplacement marqué par un rectangle de couleur « chroma » vert). Le code
détecte la zone verte (test RELATIF robuste : vert dominant, marche même sur un
vert d'écran « sale » type RGB(9,187,13)), puis :
  1. déduit le quadrilatère de l'écran ;
  2. déforme le design par perspective pour épouser ce quad ;
  3. ne REMPLACE QUE les pixels verts par le design (np.where) → tout le reste du
     gabarit (cadre, pièce, lumière) reste IDENTIQUE au pixel près.

Garantie clé (testée) : aucun pixel hors-zone-verte n'est modifié → zéro
régénération, zéro halo, zéro déformation de la scène.

Dépendances : Pillow + numpy (importées paresseusement ; si absentes, le module
le signale et ne plante pas).
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("market_intel")


def _imports():
    """Importe PIL + numpy paresseusement. Renvoie (Image, np) ou (None, None)."""
    try:
        from PIL import Image
        import numpy as np
        return Image, np
    except Exception as e:  # Pillow/numpy absents
        logger.warning("Compositing indisponible (Pillow/numpy manquant : %s). "
                       "Installe-les : pip install -r requirements.txt", e)
        return None, None


def _green_mask(arr, np):
    """Masque du vert chroma par test RELATIF (vert nettement dominant)."""
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    return (g > 110) & (g - r > 35) & (g - b > 35)


def _quad_from_mask(mask, np):
    """4 coins (TL, TR, BR, BL) de la zone verte, ou None."""
    ys, xs = np.where(mask)
    if len(xs) < 50:
        return None
    s, d = xs + ys, xs - ys
    return [(int(xs[np.argmin(s)]), int(ys[np.argmin(s)])),   # TL
            (int(xs[np.argmax(d)]), int(ys[np.argmax(d)])),   # TR
            (int(xs[np.argmax(s)]), int(ys[np.argmax(s)])),   # BR
            (int(xs[np.argmin(d)]), int(ys[np.argmin(d)]))]   # BL


def _expand_quad(quad, factor=1.012):
    """Dilate légèrement le quad depuis son centre (évite un liseré au bord)."""
    cx = sum(p[0] for p in quad) / 4.0
    cy = sum(p[1] for p in quad) / 4.0
    return [(cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in quad]


def find_placeholder_quad(template_path: str):
    """Détecte la zone chroma et renvoie ses 4 coins (TL,TR,BR,BL) ou None."""
    Image, np = _imports()
    if Image is None:
        return None
    try:
        arr = np.asarray(Image.open(template_path).convert("RGB"))
    except Exception as e:
        logger.warning("Gabarit illisible (%s) : %s", template_path, e)
        return None
    quad = _quad_from_mask(_green_mask(arr, np), np)
    if quad is None:
        logger.warning("Aucune zone chroma détectée dans %s", template_path)
    return quad


def _find_coeffs(dest_quad, source_rect, np):
    """Coefficients PIL pour Image.transform(..., PERSPECTIVE) (sortie->source)."""
    matrix = []
    for d, s in zip(dest_quad, source_rect):
        matrix.append([d[0], d[1], 1, 0, 0, 0, -s[0] * d[0], -s[0] * d[1]])
        matrix.append([0, 0, 0, d[0], d[1], 1, -s[1] * d[0], -s[1] * d[1]])
    A = np.array(matrix, dtype=float)
    B = np.array(source_rect, dtype=float).reshape(8)
    return list(np.linalg.solve(A, B))


def composite_into_template(design_path: str, template_path: str, out_path: str) -> bool:
    """
    Colle `design_path` (inchangé) dans la zone verte de `template_path` et écrit
    `out_path`. Ne remplace QUE le vert → reste du gabarit identique au pixel.
    Renvoie True si réussi, False sinon (jamais d'exception).
    """
    Image, np = _imports()
    if Image is None:
        return False
    try:
        template = Image.open(template_path).convert("RGB")
        design = Image.open(design_path).convert("RGB")
    except Exception as e:
        logger.warning("Image illisible : %s", e)
        return False

    t_arr = np.asarray(template)
    mask = _green_mask(t_arr, np)
    quad = _quad_from_mask(mask, np)
    if quad is None:
        logger.warning("Zone verte introuvable dans %s", template_path)
        return False

    w, h = design.size
    source_rect = [(0, 0), (w, 0), (w, h), (0, h)]   # TL,TR,BR,BL
    try:
        coeffs = _find_coeffs(_expand_quad(quad), source_rect, np)
        warped = design.transform(template.size, Image.PERSPECTIVE, coeffs,
                                  Image.BICUBIC)
    except Exception as e:
        logger.warning("Échec de la transformation perspective : %s", e)
        return False

    # On ne remplace QUE les pixels verts -> le reste du gabarit reste intact.
    out_arr = np.where(mask[:, :, None], np.asarray(warped), t_arr)
    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(out_arr.astype(np.uint8), "RGB").save(out_path)
    except Exception as e:
        logger.warning("Écriture du mockup impossible (%s) : %s", out_path, e)
        return False
    logger.info("Mockup composité (exact, %dx%d) : %s",
                template.size[0], template.size[1], out_path)
    return True
