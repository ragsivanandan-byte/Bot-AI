#!/usr/bin/env bash
# Phase 1 du jour : prompts -> designs bruts (8 variations/design), puis STOP pour QC.
# Usage : ./run_phase1.sh
set -u
PY="${PYTHON:-python3}"
cd "$(cd "$(dirname "$0")" && pwd)"

echo "== [1/2] Prompts du jour (main.py) =="
"$PY" main.py || { echo "❌ main.py a échoué."; exit 1; }

echo ""
echo "== [2/2] Génération des designs bruts via Grok Build =="
"$PY" automation/grok_generate.py --designs \
  || { echo "❌ grok_generate a échoué (la commande 'grok' de Grok Build est-elle dispo ?)."; exit 1; }

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✋ STOP — QC HUMAIN requis avant la suite."
echo "  1. Ouvre ~/Downloads (ou le ZIP 24images_grok_brut.zip)."
echo "  2. Envoie les images à Claude Chat -> garde tes gagnants (1 / design)."
echo "  3. Dépose les gagnants dans  ~/Downloads/Pre_phase_2/  puis lance :"
echo "       ./run_phase2.sh              (set, 5 ratios)"
echo "       ./run_phase2.sh --single     (single, 2 ratios)"
echo "════════════════════════════════════════════════════════════════"
