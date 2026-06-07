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
import zipfile
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
    outs: list[Path]   # fichier(s) attendu(s) (plusieurs en mode batch)


def _out_dir(grok_cfg: dict) -> Path:
    return Path(grok_cfg.get("output_dir", "~/Downloads")).expanduser()


def _save_clause(path: Path, kind: str = "PNG") -> str:
    return f" Save the result as a {kind} file at {path}."


def build_design_jobs(brief, grok_cfg: dict) -> list[Job]:
    """
    N variations par design brut → fichiers _NN_vK.png.

    Mode `batch_variations` (défaut) : UN SEUL appel `grok` par design demande les
    N variations d'un coup (comme Grok Imagine) → beaucoup plus rapide que N
    appels (chaque démarrage d'agent est coûteux). Sinon : 1 appel/variation.
    """
    out = _out_dir(grok_cfg)
    n = int(grok_cfg.get("variations_per_design", 8))
    grok = grok_cfg.get("grok_command", "grok")
    batch = bool(grok_cfg.get("batch_variations", True))
    jobs: list[Job] = []
    for i, design in enumerate(brief.raw_prompts, 1):
        paths = [out / f"{brief.slug}_{i:02d}_v{v}.png" for v in range(1, n + 1)]
        if batch:
            files = ", ".join(str(p) for p in paths)
            prompt = (design.prompt_text +
                      f" Generate {n} DISTINCT variations of this image and save "
                      f"them as exactly these {n} PNG files: {files}.")
            jobs.append(Job(label=f"Design {i} — {n} variations (1 appel)",
                            cmd=[grok, "-p", prompt], outs=paths))
        else:
            for v, path in enumerate(paths, 1):
                jobs.append(Job(label=f"Design {i} — variation {v}",
                                cmd=[grok, "-p", design.prompt_text +
                                     _save_clause(path)], outs=[path]))
    return jobs


def _default_runner(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def zip_outputs(files: list[Path], zip_path: Path) -> int:
    """Compresse `files` (existants) dans `zip_path`. Renvoie le nb d'images zippées."""
    existing = [f for f in files if Path(f).exists()]
    if not existing:
        return 0
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in existing:
            z.write(f, Path(f).name)
    return len(existing)


def _run_one(job: Job, timeout: int, runner) -> tuple[Job, str, str]:
    """Exécute un job, renvoie (job, statut, détail). Ne lève jamais."""
    for o in job.outs:
        o.parent.mkdir(parents=True, exist_ok=True)
    try:
        runner(job.cmd, timeout)
    except Exception as e:  # timeout, binaire absent, etc.
        return job, "fail", f"{type(e).__name__}: {e}"
    made = [o for o in job.outs if o.exists() and o.stat().st_size > 0]
    if len(made) == len(job.outs):
        return job, "ok", f"{len(made)}/{len(job.outs)} fichier(s)"
    if made:
        return job, "partial", f"{len(made)}/{len(job.outs)} fichier(s)"
    return job, "fail", "aucun fichier produit"


def run_jobs(jobs: list[Job], timeout: int, runner=_default_runner,
             workers: int = 1) -> dict:
    """
    Exécute les jobs (séquentiel si workers=1, sinon en parallèle). Renvoie un
    récap {ok, failed}. Le parallélisme accélère le mur-à-mur mais consomme plus
    de quota/ressources simultanément.
    """
    print(f"→ {len(jobs)} job(s), {workers} en parallèle …", flush=True)
    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda j: _run_one(j, timeout, runner), jobs))
    else:
        results = [_run_one(j, timeout, runner) for j in jobs]

    ok, failed = [], []
    for job, status, detail in results:
        icon = {"ok": "✅", "partial": "🟡", "fail": "⚠️"}.get(status, "•")
        print(f"  {icon} {job.label} — {detail}")
        (ok if status == "ok" else failed).append(job.label)
    return {"ok": ok, "failed": failed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Génération des DESIGNS bruts via "
                                 "Grok Build (les mockups -> make_mockups.py).")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--designs", action="store_true",
                    help="Génère les variations des designs bruts (défaut).")
    ap.add_argument("--mockups", nargs="*", metavar="DESIGN",
                    help="(DÉSACTIVÉ) Les mockups se font par compositing exact : "
                         "utilise automation/make_mockups.py.")
    args = ap.parse_args(argv)

    # Ancienne voie mockups (régénération Grok) volontairement désactivée :
    # elle déformait l'œuvre (skew/halo/doublon). On redirige vers le compositeur.
    if args.mockups is not None:
        print("⛔ La génération des mockups par Grok est DÉSACTIVÉE (elle "
              "régénérait/déformait l'œuvre).")
        print("➡️  Utilise le compositing EXACT (pixel-for-pixel) :")
        files = " ".join(args.mockups) if args.mockups else \
            "~/Downloads/<g1>.png ~/Downloads/<g2>.png ~/Downloads/<g3>.png"
        print(f"    python automation/make_mockups.py {files} --video")
        return 0

    cfg = load_config(args.config)
    grok_cfg = cfg["grok_prompts"]

    if not grok_cfg.get("auto_generate", True):
        print("auto_generate=false dans la config → rien à faire.")
        return 0
    if shutil.which(grok_cfg.get("grok_command", "grok")) is None:
        print("⚠️ Grok Build (`grok`) introuvable dans le PATH — étape ignorée.")
        return 0

    brief = generate_daily_brief(grok_cfg, cfg["niche"], [])
    timeout = int(grok_cfg.get("per_call_timeout_s", 300))

    jobs = build_design_jobs(brief, grok_cfg)
    print(f"== Designs bruts ({brief.theme}) — "
          f"{grok_cfg.get('variations_per_design', 8)} variations/design ==")

    workers = int(grok_cfg.get("parallel_workers", 1))
    recap = run_jobs(jobs, timeout, workers=workers)
    print(f"\nTerminé : {len(recap['ok'])} OK, {len(recap['failed'])} à refaire.")
    if recap["failed"]:
        print("À refaire :", ", ".join(recap["failed"]))

    # ZIP de toutes les images brutes -> 1 seul fichier à envoyer à Claude chat
    # (contourne la limite de 20 fichiers/upload).
    all_outs = [o for j in jobs for o in j.outs]
    zip_name = grok_cfg.get("zip_name", "24images_grok_brut")
    zip_path = _out_dir(grok_cfg) / f"{zip_name}.zip"
    n = zip_outputs(all_outs, zip_path)
    if n:
        print(f"📦 ZIP créé : {zip_path} ({n} images) — à envoyer à Claude chat.")

    print("⚠️ QC humain obligatoire. Mockups -> make_mockups.py. Rien publié.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
