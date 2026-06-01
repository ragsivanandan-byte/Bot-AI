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

# Étape best-effort : ouvrir le dossier du jour si une session graphique est
# active. En cas d'échec (Mac verrouillé, pas de bureau), on n'échoue pas : les
# rapports sont déjà générés, c'est l'essentiel.
open "reports/$(date +%Y-%m-%d)/" 2>/dev/null || true
