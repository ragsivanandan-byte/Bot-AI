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
import zipfile
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
    ap.add_argument("--upscale-only", action="store_true",
                    help="Upscale seul (masters dans Upscaled/), AUCUN ratio généré.")
    ap.add_argument("--ratios-only", action="store_true",
                    help="Exporte les ratios depuis les masters existants (pas d'upscale).")
    args = ap.parse_args(argv)
    if args.upscale_only and args.ratios_only:
        print("❌ --upscale-only et --ratios-only sont exclusifs.")
        return 2
    do_upscale = not args.ratios_only
    do_export = not args.upscale_only

    cfg = load_config(args.config)
    ip = cfg.get("image_pipeline", {})
    kind = args.type or ip.get("default_type", "set")
    profile = profile_for(kind, ip)
    jpeg = ip.get("jpeg", {})
    up = ip.get("upscale", {})

    downloads = Path(ip.get("downloads_dir", "~/Downloads")).expanduser()
    day = args.date or date.today().strftime("%d-%m-%Y")
    # Entrée : par défaut 'To Upscale/<jj-mm-aaaa>/'. Si to_upscale_date_subdir=false,
    # on lit TOUS les fichiers directement dans 'To Upscale/' (sans dossier daté).
    in_dir = downloads / ip.get("to_upscale_dir", "To Upscale")
    if ip.get("to_upscale_date_subdir", True):
        in_dir = in_dir / day

    base = Path(ip.get("output_root", str(downloads / "Upscaled_add_export_5_ratios"))
                ).expanduser()
    if ip.get("date_subdir", True):
        base = base / day
    # Masters : par défaut <base>/Upscaled/. Si image_pipeline.masters_dir est
    # renseigné (ex. "~/Downloads"), les masters _upscaled.png y vont directement.
    if ip.get("masters_dir"):
        masters_dir = Path(ip["masters_dir"]).expanduser()
    else:
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

    title = ("Upscale SEUL" if args.upscale_only else
             "Export ratios SEUL" if args.ratios_only else "Upscale + export")
    print(f"== {title} ({kind}) — {day} — {len(images)} image(s) ==")
    from PIL import Image
    all_jpgs: list[Path] = []
    try:
        for img in images:
            stem = img.stem
            master_path = masters_dir / f"{stem}_upscaled.png"
            print(f"→ {img.name}")
            if do_upscale:
                mode = upscale_x4(str(img), str(master_path),
                                  command=up.get("command", ""),
                                  fallback_lanczos=bool(up.get("fallback_lanczos", False)),
                                  min_master_width=int(profile.get("min_master_width", 0)),
                                  passes=int(up.get("passes", 1)),
                                  target_width=int(up.get("target_width", 0)))
                # Archive l'entrée traitée -> To Upscale/_fait/ (pas de re-upscale
                # au prochain run). _fait/ est ignoré (iterdir non récursif + dossier).
                if ip.get("to_upscale_archive_done", False):
                    arch = in_dir / "_fait"
                    arch.mkdir(exist_ok=True)
                    img.replace(arch / img.name)
            else:
                if not master_path.exists():
                    raise FileNotFoundError(
                        f"master manquant : {master_path.name} (lance d'abord "
                        "--upscale-only, ou sans flag).")
                mode = "master existant"
            if not do_export:
                print(f"  ✅ upscalé ({mode}) — master : {master_path.name}")
                continue
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
            print(f"  ✅ {mode} + {len(ratios)} ratios JPG")
    except Exception as e:  # noqa: BLE001 — CLI : un échec (timeout upscaler,
        # PNG corrompu, I/O, master trop petit...) doit donner un ABORT lisible,
        # jamais une stacktrace. KeyboardInterrupt (BaseException) reste propagé.
        print(f"❌ ABORT : {type(e).__name__}: {e}")
        return 1

    if not do_export:
        print(f"\n✅ {len(images)} master(s) upscalé(s) dans : {masters_dir}")
        print("   (aucun ratio généré — relance avec --ratios-only pour les exporter.)")
        return 0

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

    # --- Archive ZIP des ratios, dans le même dossier Final/ ----------------
    if all_jpgs and ip.get("zip_final", True):
        zip_path = (base / "Final" / f"NWD_{kind}_{day}_ratios.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in all_jpgs:
                zf.write(p, arcname=p.name)        # noms à plat (sans chemin)
        mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"🗜️  ZIP : {zip_path.name} ({len(all_jpgs)} JPG, {mb:.1f} Mo) -> {zip_path.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
