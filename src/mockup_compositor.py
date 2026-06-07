"""
mockup_compositor.py — Compositing EXACT (pixel-for-pixel) sans IA.

Insère TON fichier design, inchangé, dans un gabarit de mockup (photo de pièce
avec un emplacement marqué par un rectangle de couleur « chroma » — vert vif par
défaut). Le code détecte la zone chroma et y plaque le design (avec perspective
si le cadre est légèrement de biais). Résultat : la cover/le mockup montre
EXACTEMENT le fichier vendu — jamais une régénération approximative.

Dépendances : Pillow + numpy (importées paresseusement ; si absentes, le module
le signale et ne plante pas).

Pourquoi un gabarit « chroma » ? On génère UNE fois des scènes (cadre vide
contenant un rectangle vert) — via Grok ou stock — puis Pillow colle le vrai
design dans le vert. AI pour l'ambiance, Python pour l'exactitude.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("market_intel")

# Couleur "chroma" par défaut du placeholder dans les gabarits (vert vif pur).
DEFAULT_KEY = (0, 255, 0)
DEFAULT_TOL = 90  # tolérance de distance couleur


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


def find_placeholder_quad(template_path: str, key=DEFAULT_KEY, tol=DEFAULT_TOL):
    """
    Détecte la zone chroma dans le gabarit et renvoie ses 4 coins
    (TL, TR, BR, BL) ou None si introuvable.
    """
    Image, np = _imports()
    if Image is None:
        return None
    try:
        img = Image.open(template_path).convert("RGB")
    except Exception as e:
        logger.warning("Gabarit illisible (%s) : %s", template_path, e)
        return None
    arr = np.asarray(img, dtype=np.int16)
    kr, kg, kb = key
    dist = ((arr[:, :, 0] - kr) ** 2 + (arr[:, :, 1] - kg) ** 2
            + (arr[:, :, 2] - kb) ** 2) ** 0.5
    mask = dist <= tol
    ys, xs = np.where(mask)
    if len(xs) < 50:  # pas (assez) de zone chroma
        logger.warning("Aucune zone chroma détectée dans %s", template_path)
        return None
    s = xs + ys
    d = xs - ys
    tl = (int(xs[np.argmin(s)]), int(ys[np.argmin(s)]))
    br = (int(xs[np.argmax(s)]), int(ys[np.argmax(s)]))
    tr = (int(xs[np.argmax(d)]), int(ys[np.argmax(d)]))
    bl = (int(xs[np.argmin(d)]), int(ys[np.argmin(d)]))
    return [tl, tr, br, bl]


def _find_coeffs(dest_quad, source_rect, np):
    """
    Coefficients PIL pour Image.transform(..., PERSPECTIVE) : la transform mappe
    chaque pixel de SORTIE vers la SOURCE. On veut que le quad de SORTIE (dans le
    gabarit) corresponde au rectangle SOURCE (le design). Convention canonique
    PIL : matrice sur les points de destination, B = points source.
    """
    matrix = []
    for d, s in zip(dest_quad, source_rect):
        matrix.append([d[0], d[1], 1, 0, 0, 0, -s[0] * d[0], -s[0] * d[1]])
        matrix.append([0, 0, 0, d[0], d[1], 1, -s[1] * d[0], -s[1] * d[1]])
    A = np.array(matrix, dtype=float)
    B = np.array(source_rect, dtype=float).reshape(8)
    res = np.linalg.solve(A, B)
    return list(res)


def composite_into_template(design_path: str, template_path: str, out_path: str,
                            key=DEFAULT_KEY, tol=DEFAULT_TOL) -> bool:
    """
    Colle `design_path` (inchangé) dans la zone chroma de `template_path` et écrit
    `out_path`. Renvoie True si réussi, False sinon (jamais d'exception).
    """
    Image, np = _imports()
    if Image is None:
        return False
    quad = find_placeholder_quad(template_path, key, tol)
    if quad is None:
        return False
    try:
        template = Image.open(template_path).convert("RGBA")
        design = Image.open(design_path).convert("RGBA")
    except Exception as e:
        logger.warning("Image illisible (%s) : %s", e, design_path)
        return False

    w, h = design.size
    source_rect = [(0, 0), (w, 0), (w, h), (0, h)]   # TL,TR,BR,BL du design
    try:
        coeffs = _find_coeffs(quad, source_rect, np)
        warped = design.transform(template.size, Image.PERSPECTIVE, coeffs,
                                  Image.BICUBIC)
    except Exception as e:
        logger.warning("Échec de la transformation perspective : %s", e)
        return False

    out = Image.alpha_composite(template, warped).convert("RGB")
    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        out.save(out_path)
    except Exception as e:
        logger.warning("Écriture du mockup impossible (%s) : %s", out_path, e)
        return False
    logger.info("Mockup composité (exact) : %s", out_path)
    return True
