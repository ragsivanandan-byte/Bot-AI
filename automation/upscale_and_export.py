#!/usr/bin/env python3
"""
upscale_and_export.py — Commande INDÉPENDANTE (à lancer à la main).

Pour le dossier du JOUR `~/Downloads/To Upscale/<jj-mm-aaaa>/` :
  1. upscale ×4 (Upscayl/Real-ESRGAN ; sinon ABORT — pas de Lanczos muet) ;
  2. export multi-ratios JPEG selon le profil (set/single), specs Claude Chat
     (center-crop, downscale only, q90/4:4:4/300DPI/sRGB).

Sortie : `<output_root>/<jj-mm-aaaa>/Upscaled/` (masters) + `.../Final/` (JPG à
plat, ratio dans le nom ; `Final/<ratio>/` si crops_by_ratio_subdirs: true).

⚠️ Les bruts doivent être nommés à la convention NWD :
   SET    : NWD_T#_{SetName}_{DesignName}.png   (ex. NWD_T1_WarmShapes_Dune.png)
   SINGLE : NWD_T#_{DesignName}.png             (ex. NWD_T1_OliveBranch.png)

Usage :
    python automation/upscale_and_export.py --type set
    python automation/upscale_and_export.py --type single --date 07-06-2026
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config                       # noqa: E402
from src.image_pipeline import (export_ratio, jpeg_info, profile_for,  # noqa: E402
                                upscale_x4, validate_input_stem)

_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _verify(jpgs: list[Path], expected_dims: dict) -> list[str]:
    """Checklist d'audit (§11) ; renvoie la liste des problèmes (vide = OK)."""
    problems = []
    for p in jpgs:
        ratio = p.stem.split("_")[-1]
        info = jpeg_info(str(p))
        if ratio in expected_dims and info["size"] != expected_dims[ratio]:
            problems.append(f"{p.name}: dim {info['size']} ≠ {expected_dims[ratio]}")
        if info["mode"] != "RGB":
            problems.append(f"{p.name}: mode {info['mode']} (attendu RGB)")
        if info["dpi"] != (300, 300):
            problems.append(f"{p.name}: dpi {info['dpi']} (attendu 300,300)")
        if not info["icc"]:
            problems.append(f"{p.name}: profil sRGB absent")
        mb = info["bytes"] / 1e6
        if mb > 2.5:
            problems.append(f"{p.name}: {mb:.1f} Mo (> 2.5 Mo)")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Upscale ×4 + export ratios (jour).")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--type", choices=["set", "single"], default=None,
                    help="set (5 ratios, ancrage hauteur) ou single (2 ratios, "
                         "ancrage largeur). Défaut : config.")
    ap.add_argument("--date", default=None, help="Dossier daté (jj-mm-aaaa).")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    ip = cfg.get("image_pipeline", {})
    kind = args.type or ip.get("default_type", "set")
    profile = profile_for(kind, ip)
    jpeg = ip.get("jpeg", {})
    up = ip.get("upscale", {})

    downloads = Path(ip.get("downloads_dir", "~/Downloads")).expanduser()
    day = args.date or date.today().strftime("%d-%m-%Y")
    in_dir = downloads / ip.get("to_upscale_dir", "To Upscale") / day

    base = Path(ip.get("output_root", str(downloads / "Upscaled_add_export_5_ratios"))
                ).expanduser()
    if ip.get("date_subdir", True):
        base = base / day
    masters_dir = base / ip.get("masters_subdir", "Upscaled")

    if not in_dir.is_dir():
        print(f"⚠️ Dossier introuvable : {in_dir}")
        return 0
    images = sorted(p for p in in_dir.iterdir() if p.suffix.lower() in _EXTS)
    if not images:
        print(f"⚠️ Aucune image dans {in_dir}.")
        return 0

    # Validation des noms (OPTIONNELLE) : par défaut on upscale TOUT fichier, quel
    # que soit son nom (sortie = <nom>_<ratio>.jpg). Active validate_naming pour
    # imposer la convention NWD_T#_... (ABORT sinon).
    if ip.get("validate_naming", False):
        try:
            for img in images:
                validate_input_stem(img.stem, kind)
        except ValueError as e:
            print(f"❌ ABORT (nommage) : {e}")
            return 1

    anchor, anchor_px = profile["anchor"], int(profile["anchor_px"])
    ratios = profile["ratios"]
    expected = {}
    for rk in ratios:
        from src.image_pipeline import RATIOS
        rw, rh = RATIOS[rk]
        if anchor == "height":
            expected[rk] = (round(anchor_px * rw / rh), anchor_px)
        else:
            expected[rk] = (anchor_px, round(anchor_px * rh / rw))

    print(f"== Upscale ×4 + export ({kind}) — {day} — {len(images)} image(s) ==")
    from PIL import Image
    all_jpgs: list[Path] = []
    try:
        for img in images:
            stem = img.stem
            master_path = masters_dir / f"{stem}_upscaled.png"
            print(f"→ {img.name}")
            mode = upscale_x4(str(img), str(master_path),
                              command=up.get("command", ""),
                              fallback_lanczos=bool(up.get("fallback_lanczos", False)),
                              min_master_width=int(profile.get("min_master_width", 0)),
                              passes=int(up.get("passes", 1)),
                              target_width=int(up.get("target_width", 0)))
            master = Image.open(master_path)
            for rk in ratios:
                # Par défaut : tous les JPG à plat dans Final/ (le ratio est déjà
                # dans le nom -> pas de sous-dossiers). Mets crops_by_ratio_subdirs:
                # true pour revenir à Final/<ratio>/.
                crops_dir = (base / "Final" / rk
                             if ip.get("crops_by_ratio_subdirs", False)
                             else base / "Final")
                dest = crops_dir / f"{stem}_{rk}.jpg"
                export_ratio(master, rk, anchor, anchor_px, str(dest), jpeg)
                all_jpgs.append(dest)
            print(f"  ✅ upscalé ({mode}) + {len(ratios)} ratios JPG")
    except Exception as e:  # noqa: BLE001 — CLI : un échec (timeout upscaler,
        # PNG corrompu, I/O, master trop petit...) doit donner un ABORT lisible,
        # jamais une stacktrace. KeyboardInterrupt (BaseException) reste propagé.
        print(f"❌ ABORT : {type(e).__name__}: {e}")
        return 1

    # --- verify (§11) -------------------------------------------------------
    problems = _verify(all_jpgs, expected)
    print(f"\n== Vérification ({len(all_jpgs)} JPG) ==")
    if problems:
        print("⚠️ Problèmes :")
        for p in problems:
            print(f"   - {p}")
    else:
        print("✅ Dimensions, 300 DPI, sRGB, mode RGB, poids — tout conforme.")
    print(f"Masters : {masters_dir}\nCrops   : {base}/Final/"
          + ("<ratio>/" if ip.get("crops_by_ratio_subdirs", False) else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
