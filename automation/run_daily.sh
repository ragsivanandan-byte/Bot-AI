#!/bin/bash
# =============================================================================
# run_daily.sh — Script lancé automatiquement chaque matin par launchd.
# Génère les rapports du jour, puis ouvre le dossier (best-effort).
# Tu n'as PAS besoin de lancer ce script à la main : install_daily.sh le
# programme pour 7h00.
# =============================================================================
set -u

# Se placer dans le dossier du projet (indépendamment d'où launchd démarre).
cd "$HOME/Bot-AI" || { echo "Dossier ~/Bot-AI introuvable"; exit 1; }

# Activer l'environnement Python du projet.
# shellcheck disable=SC1091
source .venv/bin/activate

# Étape critique : générer les rapports. On loggue tout dans logs/.
python main.py >> logs/launchd.out.log 2>&1

# Génération auto des DESIGNS bruts via Grok Build (headless), si `grok` présent
# et auto_generate=true. Best-effort : ne bloque jamais le run. Les mockups +
# vidéo se génèrent APRÈS ton QC, via :
#   python automation/grok_generate.py --mockups <gagnant1> <gagnant2> <gagnant3>
python automation/grok_generate.py --designs >> logs/grok.out.log 2>&1 || true

# Étape best-effort : ouvrir le dossier du jour si une session graphique est
# active. Les rapports sont écrits dans ~/Downloads/reports/AAAA-MM-JJ/ (cf.
# output.reports_dir de config.yaml). En cas d'échec, on n'échoue pas : les
# rapports sont déjà générés, c'est l'essentiel.
open "$HOME/Downloads/reports/$(date +%Y-%m-%d)/" 2>/dev/null || true
