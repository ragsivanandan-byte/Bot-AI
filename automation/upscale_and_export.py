#!/usr/bin/env python3
"""
upscale_and_export.py — Commande INDÉPENDANTE (à lancer à la main).

Pour le sous-dossier du JOUR (jj-mm-aaaa) de `~/Downloads/To Upscale/` :
  1. upscale ×4 chaque image (Upscayl/Real-ESRGAN si configuré, sinon Lanczos) ;
  2. exporte chaque image upscalée en 5 ratios JPG (qualité 90, hauteur 6912).
Sortie : `~/Downloads/Upscaled_add_export_5_ratios/<jj-mm-aaaa>/` (créé auto).

N'a AUCUN lien avec le flux quotidien (grok_generate / make_mockups) : process à
part, déclenché manuellement.

Usage :
    python automation/upscale_and_export.py            # dossier du jour
    python automation/upscale_and_export.py --date 07-06-2026   # une autre date
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config             # noqa: E402
from src.image_pipeline import export_ratios, upscale_x4  # noqa: E402

_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Upscale ×4 + export 5 ratios (jour).")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--date", default=None,
                    help="Sous-dossier daté (jj-mm-aaaa). Défaut : aujourd'hui.")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    ip = cfg.get("image_pipeline", {})
    downloads = Path(ip.get("downloads_dir", "~/Downloads")).expanduser()
    day = args.date or date.today().strftime("%d-%m-%Y")

    in_dir = downloads / ip.get("to_upscale_dir", "To Upscale") / day
    out_dir = downloads / ip.get("output_dir", "Upscaled_add_export_5_ratios") / day

    if not in_dir.is_dir():
        print(f"⚠️ Dossier introuvable : {in_dir}")
        print(f"   Mets les images brutes à upscaler dans : "
              f"{downloads / ip.get('to_upscale_dir', 'To Upscale') / day}")
        return 0
    images = sorted(p for p in in_dir.iterdir() if p.suffix.lower() in _EXTS)
    if not images:
        print(f"⚠️ Aucune image dans {in_dir}.")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    command = ip.get("upscale_command", "")
    target_h = int(ip.get("target_height", 6912))
    quality = int(ip.get("jpg_quality", 90))
    ratios = ip.get("ratios")

    print(f"== Upscale ×4 + export 5 ratios — {day} — {len(images)} image(s) ==")
    if not command.strip():
        print("   (upscale : repli Lanczos ×4 — net pour des aplats ; configure "
              "image_pipeline.upscale_command pour Upscayl/Real-ESRGAN)")
    total_jpg = 0
    for img in images:
        stem = img.stem
        upscaled = out_dir / f"{stem}_upscaled.png"
        print(f"→ {img.name}")
        if not upscale_x4(str(img), str(upscaled), command):
            print("  ⚠️ upscale échoué, image ignorée")
            continue
        jpgs = export_ratios(str(upscaled), str(out_dir), stem,
                             target_height=target_h, quality=quality, ratios=ratios)
        total_jpg += len(jpgs)
        print(f"  ✅ upscalé + {len(jpgs)} ratios JPG (q{quality})")

    print(f"\nTerminé : {total_jpg} fichiers JPG (5 ratios/image) dans {out_dir}")
    print("⚠️ Vérifie les recadrages (centrés) avant mise en vente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
