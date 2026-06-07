#!/usr/bin/env bash
# Phase 2 du jour (APRÈS le QC) : mockups exacts + vidéo depuis les gagnants,
# puis upscale Upscayl + export multi-ratios JPEG (prêts Etsy).
# Usage : ./run_phase2.sh [--single] D1.png [D2.png D3.png]
#   --single  -> profil single (2 ratios). Sans option = set (5 ratios).
set -u
PY="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

TYPE="set"
if [ "${1:-}" = "--single" ]; then TYPE="single"; shift; fi

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
  echo "Usage : $0 [--single] D1.png [D2.png D3.png]   (1 à 3 fichiers gagnants)"
  exit 2
fi

# Résout les chemins en ABSOLU (avant de changer de dossier) + vérifie l'existence.
ABS=()
for f in "$@"; do
  case "$f" in /*) p="$f" ;; *) p="$PWD/$f" ;; esac
  [ -f "$p" ] || { echo "❌ Fichier introuvable : $f"; exit 2; }
  ABS+=("$p")
done

cd "$SCRIPT_DIR"

echo "== [1/2] Mockups exacts (+ vidéo 6 s) depuis les gagnants =="
"$PY" automation/make_mockups.py "${ABS[@]}" --video \
  || echo "⚠️ Mockups en échec (gabarits mockup_templates/ présents ? 'grok' dispo ?) — on continue vers l'export."

echo ""
echo "== [2/2] Upscale Upscayl + export ($TYPE) =="
DAY="$(date +%d-%m-%Y)"
DEST="$HOME/Downloads/To Upscale/$DAY"
mkdir -p "$DEST"
for p in "${ABS[@]}"; do
  cp -f "$p" "$DEST/"
  echo "  -> copié dans To Upscale/$DAY/ : $(basename "$p")"
done
"$PY" automation/upscale_and_export.py --type "$TYPE" \
  || { echo "❌ upscale/export a échoué."; exit 1; }

echo ""
echo "✅ Phase 2 terminée."
echo "   Mockups + vidéo : ~/Downloads"
echo "   JPG $TYPE ratios : ~/Downloads/Upscaled_add_export_5_ratios/$DAY/Final/"
