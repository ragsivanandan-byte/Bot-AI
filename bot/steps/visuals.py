"""
Étape VISUELS — récupère les images du Short.

Deux modes (auto-détectés) :
  1. API xAI Grok Imagine  (si XAI_API_KEY est défini)  -> $0.02/image
  2. Dossier manuel         -> tu déposes tes images générées dans
                               bot/assets/visuals/short<N>/  (depuis l'app Grok)

Retourne la liste des chemins d'images (au moins 1).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import requests


def _natural_key(p: Path) -> list:
    """Tri naturel : img2 avant img10 (pas l'ordre lexical img10 < img2)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]

XAI_IMAGE_URL = "https://api.x.ai/v1/images/generations"
XAI_MODEL = os.getenv("XAI_IMAGE_MODEL", "grok-2-image")  # ou "grok-imagine-image" ($0.02)


def _manual_dir(short_number: int, assets_dir: Path) -> Path:
    return assets_dir / "visuals" / f"short{short_number}"


def _load_manual(short_number: int, assets_dir: Path) -> list[Path]:
    d = _manual_dir(short_number, assets_dir)
    if not d.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    imgs = [p for p in d.iterdir()
            if p.suffix.lower() in exts and not p.name.startswith(".")]  # ignore .DS_Store etc.
    return sorted(imgs, key=_natural_key)


def _generate_xai(prompts: list[str], out_dir: Path) -> list[Path]:
    api_key = os.getenv("XAI_API_KEY")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, prompt in enumerate(prompts, 1):
        # Suffixe vertical pour coller au format Short 9:16.
        full_prompt = f"{prompt}, vertical 9:16 composition, cinematic, ultra realistic, 4k"
        resp = requests.post(
            XAI_IMAGE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": XAI_MODEL, "prompt": full_prompt, "n": 1},
            timeout=120,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"xAI image a échoué ({resp.status_code}) : {resp.text[:300]}")
        data = resp.json()["data"][0]
        img_path = out_dir / f"img{i:02d}.png"
        if data.get("url"):
            img_path.write_bytes(requests.get(data["url"], timeout=120).content)
        elif data.get("b64_json"):
            import base64
            img_path.write_bytes(base64.b64decode(data["b64_json"]))
        else:
            raise RuntimeError(f"Réponse xAI inattendue : {list(data)}")
        paths.append(img_path)
    return paths


def get_visuals(short_number: int, prompts: list[str], work_dir: Path, assets_dir: Path) -> list[Path]:
    """Mode manuel prioritaire (gratuit) ; sinon API xAI si clé dispo."""
    manual = _load_manual(short_number, assets_dir)
    if manual:
        print(f"  → {len(manual)} image(s) trouvée(s) dans le dossier manuel")
        return manual

    if os.getenv("XAI_API_KEY"):
        print(f"  → Génération de {len(prompts)} image(s) via l'API xAI…")
        return _generate_xai(prompts, work_dir / "visuals")

    raise RuntimeError(
        f"Aucun visuel pour le Short #{short_number}.\n"
        f"   Option A : ajoute XAI_API_KEY dans bot/.env (génération auto).\n"
        f"   Option B : dépose tes images Grok dans "
        f"{_manual_dir(short_number, assets_dir)}/"
    )
