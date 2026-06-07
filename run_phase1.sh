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
echo "  2. Envoie les images à Claude Chat -> garde 1 variation / design (3 gagnants)."
echo "  3. Lance ensuite la phase 2 avec les 3 gagnants :"
echo "       ./run_phase2.sh ~/Downloads/NWD_T1_xxx.png ~/Downloads/NWD_T2_yyy.png ~/Downloads/NWD_T3_zzz.png"
echo "════════════════════════════════════════════════════════════════"
