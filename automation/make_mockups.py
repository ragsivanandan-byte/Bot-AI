#!/usr/bin/env python3
"""
make_mockups.py — Mockups EXACTS par compositing Python (pas de régénération IA).

Insère tes designs GAGNANTS, inchangés, dans tes gabarits de pièces
(`mockup_templates/*.png`, chacun avec un rectangle vert là où va l'œuvre) et
écrit les mockups dans ~/Downloads. La cover = 1er gabarit + 1er design.

Préparer les gabarits (UNE fois) : voir README (prompt Grok « cadre vide +
rectangle vert ») ou mets-y tes propres photos de pièces avec un cadre vide
rempli d'un aplat vert vif (#00FF00).

Usage :
    python automation/make_mockups.py D1.png [D2.png D3.png]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config            # noqa: E402
from src.mockup_compositor import composite_into_template  # noqa: E402
from src.prompt_generator import generate_daily_brief  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Mockups exacts par compositing Python.")
    ap.add_argument("designs", nargs="+", help="Fichiers designs gagnants (1 à 3).")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--templates", default=None,
                    help="Dossier des gabarits (défaut : config ou ./mockup_templates).")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    grok_cfg = cfg["grok_prompts"]
    out_dir = Path(grok_cfg.get("output_dir", "~/Downloads")).expanduser()
    tpl_dir = Path(args.templates or grok_cfg.get("mockup_templates_dir",
                                                  "mockup_templates")).expanduser()
    brief = generate_daily_brief(grok_cfg, cfg["niche"], [])
    slug = brief.slug

    if not tpl_dir.is_dir():
        print(f"⚠️ Dossier de gabarits introuvable : {tpl_dir}")
        print("   Crée-le et ajoutes-y des images de pièces avec un rectangle "
              "vert (#00FF00) à l'emplacement du cadre. Voir README.")
        return 0
    templates = sorted(p for p in tpl_dir.iterdir()
                       if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not templates:
        print(f"⚠️ Aucun gabarit dans {tpl_dir}.")
        return 0

    designs = [str(Path(d).expanduser()) for d in args.designs]
    print(f"== Mockups exacts (compositing) — {len(templates)} gabarit(s) ==")
    ok = fail = 0
    for i, tpl in enumerate(templates):
        design = designs[i % len(designs)]          # 1er gabarit -> 1er design
        is_cover = (i == 0)
        name = f"{slug}_Cover.png" if is_cover else f"{slug}_Mockup_{i + 1:02d}.png"
        dest = out_dir / name
        if composite_into_template(design, str(tpl), str(dest)):
            print(f"  ✅ {name}  ({Path(design).name} dans {tpl.name})")
            ok += 1
        else:
            print(f"  ⚠️ échec sur {tpl.name} (zone verte introuvable ?)")
            fail += 1
    print(f"\nTerminé : {ok} OK, {fail} en échec. Sortie : {out_dir}")
    print("⚠️ QC humain conseillé. L'œuvre est collée EXACTEMENT (pixel-for-pixel).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
