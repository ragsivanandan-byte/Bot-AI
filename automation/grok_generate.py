#!/usr/bin/env python3
"""
grok_generate.py — Pilote Grok Build (headless) pour générer les visuels du jour.

Validé : `grok -p "<prompt>. Save the result as a PNG file at <path>"` génère ET
écrit le fichier en mode headless. Ce script industrialise ça.

Deux phases (QC humain obligatoire entre les deux) :
  * `--designs` (défaut) : génère N variations de chacun des 3 designs bruts du
    jour → ~/Downloads. (lancé automatiquement à 7h)
  * `--mockups D1 D2 D3` : à partir des designs GAGNANTS (choisis au QC avec
    Claude chat), génère 4 mockups (dont 1 cover) + 1 vidéo 6 s → ~/Downloads.

Robuste : si une génération échoue, on continue, on journalise, on ne publie
RIEN. Si `grok` n'est pas installé ou auto_generate=false, on s'arrête proprement.

Usage :
    python automation/grok_generate.py --designs
    python automation/grok_generate.py --mockups ~/Downloads/A.png ~/Downloads/B.png ~/Downloads/C.png
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Rendre le paquet `src` importable quel que soit le dossier de lancement.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_config          # noqa: E402
from src.prompt_generator import generate_daily_brief  # noqa: E402


@dataclass
class Job:
    label: str
    cmd: list[str]
    out: Path


def _out_dir(grok_cfg: dict) -> Path:
    return Path(grok_cfg.get("output_dir", "~/Downloads")).expanduser()


def _save_clause(path: Path, kind: str = "PNG") -> str:
    return f" Save the result as a {kind} file at {path}."


def build_design_jobs(brief, grok_cfg: dict) -> list[Job]:
    """N variations par design brut → fichiers _NN_vK.png."""
    out = _out_dir(grok_cfg)
    n = int(grok_cfg.get("variations_per_design", 4))
    jobs: list[Job] = []
    for i, design in enumerate(brief.raw_prompts, 1):
        for v in range(1, n + 1):
            path = out / f"{brief.slug}_{i:02d}_v{v}.png"
            jobs.append(Job(label=f"Design {i} — variation {v}",
                            cmd=[grok_cfg.get("grok_command", "grok"), "-p",
                                 design.prompt_text + _save_clause(path)],
                            out=path))
    return jobs


def build_mockup_jobs(brief, grok_cfg: dict, design_files: list[str]) -> list[Job]:
    """4 mockups (1 cover + 3 ambiance) à partir des designs GAGNANTS fournis."""
    out = _out_dir(grok_cfg)
    grok = grok_cfg.get("grok_command", "grok")
    jobs: list[Job] = []
    for k, mk in enumerate(brief.mockup_prompts):
        # Le mockup k référence "Design (k)" ; on mappe sur le fichier fourni.
        ref_idx = 0 if mk.is_cover else (k - 1)
        ref_idx = max(0, min(ref_idx, len(design_files) - 1))
        ref_file = str(Path(design_files[ref_idx]).expanduser())
        path = out / mk.filename
        prompt = (mk.prompt_text +
                  f" Use the existing image file at {ref_file} as the poster — "
                  f"paste it UNCHANGED (pixel-for-pixel, opaque)." +
                  _save_clause(path))
        jobs.append(Job(label=mk.label, cmd=[grok, "-p", prompt], out=path))
    return jobs


def build_video_job(brief, grok_cfg: dict, cover_file: str) -> Job:
    out = _out_dir(grok_cfg)
    grok = grok_cfg.get("grok_command", "grok")
    cover = str(Path(cover_file).expanduser())
    path = out / f"{brief.slug}_Video.mp4"
    prompt = (brief.video_prompt +
              f" Source still image file: {cover}." + _save_clause(path, "MP4"))
    return Job(label="Vidéo 6 s", cmd=[grok, "-p", prompt], out=path)


def _default_runner(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def run_jobs(jobs: list[Job], timeout: int, runner=_default_runner) -> dict:
    """Exécute les jobs séquentiellement. Renvoie un récap {ok, failed}."""
    ok, failed = [], []
    for j in jobs:
        j.out.parent.mkdir(parents=True, exist_ok=True)
        print(f"→ {j.label} …", flush=True)
        try:
            runner(j.cmd, timeout)
        except Exception as e:  # timeout, binaire absent, etc. : on continue
            print(f"  ⚠️ échec génération ({type(e).__name__}: {e})")
            failed.append(j.label)
            continue
        if j.out.exists() and j.out.stat().st_size > 0:
            print(f"  ✅ {j.out}")
            ok.append(j.label)
        else:
            print("  ⚠️ aucun fichier produit (à refaire / QC)")
            failed.append(j.label)
    return {"ok": ok, "failed": failed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Génération visuelle Grok Build.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--designs", action="store_true",
                    help="Génère les variations des 3 designs bruts (défaut).")
    ap.add_argument("--mockups", nargs=3, metavar=("D1", "D2", "D3"),
                    help="Génère 4 mockups + vidéo depuis les 3 designs gagnants.")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    grok_cfg = cfg["grok_prompts"]

    if not grok_cfg.get("auto_generate", True) and not args.mockups:
        print("auto_generate=false dans la config → rien à faire.")
        return 0
    if shutil.which(grok_cfg.get("grok_command", "grok")) is None:
        print("⚠️ Grok Build (`grok`) introuvable dans le PATH — étape ignorée.")
        return 0

    brief = generate_daily_brief(grok_cfg, cfg["niche"], [])
    timeout = int(grok_cfg.get("per_call_timeout_s", 300))

    if args.mockups:
        jobs = build_mockup_jobs(brief, grok_cfg, args.mockups)
        jobs.append(build_video_job(brief, grok_cfg, args.mockups[0]))
        print(f"== Mockups + vidéo ({brief.theme}) ==")
    else:
        jobs = build_design_jobs(brief, grok_cfg)
        print(f"== Designs bruts ({brief.theme}) — "
              f"{grok_cfg.get('variations_per_design', 4)} variations/design ==")

    recap = run_jobs(jobs, timeout)
    print(f"\nTerminé : {len(recap['ok'])} OK, {len(recap['failed'])} à refaire.")
    if recap["failed"]:
        print("À refaire :", ", ".join(recap["failed"]))
    print("⚠️ QC humain obligatoire avant publication. Rien n'a été publié.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
