#!/usr/bin/env bash
# Phase 2 du jour (APRÈS le QC) — ZÉRO saisie de noms :
#   1. Dépose tes images gagnantes (3 ou plus) dans  ~/Downloads/Pre_phase_2/
#   2. Lance simplement :   ./run_phase2.sh        (ajoute --single pour 2 ratios)
#
# Le script : mockups exacts + vidéo 6 s depuis ces images, puis les DÉPLACE dans
# ~/Downloads/To Upscale/<jour>/, puis upscale Upscayl + export ratios -> .../Final/.
# (Tu peux aussi passer des fichiers en arguments pour court-circuiter le dossier.)
set -u
PY="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="${PRE_PHASE2_DIR:-$HOME/Downloads/Pre_phase_2}"

TYPE="set"
if [ "${1:-}" = "--single" ]; then TYPE="single"; shift; fi

# --- Récupère la liste des designs : arguments explicites, sinon le dossier de dépôt
ABS=()
FROM_DROP=0
if [ "$#" -ge 1 ]; then
  for f in "$@"; do
    case "$f" in /*) p="$f" ;; *) p="$PWD/$f" ;; esac
    [ -f "$p" ] || { echo "❌ Fichier introuvable : $f"; exit 2; }
    ABS+=("$p")
  done
else
  FROM_DROP=1
  mkdir -p "$SRC"
  shopt -s nullglob nocaseglob
  for p in "$SRC"/*.png "$SRC"/*.jpg "$SRC"/*.jpeg; do ABS+=("$p"); done
  shopt -u nullglob nocaseglob
  if [ "${#ABS[@]}" -eq 0 ]; then
    echo "❌ Aucune image dans : $SRC"
    echo "   Dépose-y tes gagnants (.png/.jpg) puis relance ./run_phase2.sh"
    exit 2
  fi
fi

echo "== ${#ABS[@]} design(s) gagnant(s) =="
for p in "${ABS[@]}"; do echo "   • $(basename "$p")"; done

cd "$SCRIPT_DIR"

# --- [1/2] Mockups exacts (+ vidéo) ------------------------------------------
echo ""
echo "== [1/2] Mockups exacts (+ vidéo 6 s) =="
"$PY" automation/make_mockups.py "${ABS[@]}" --video \
  || echo "⚠️ Mockups en échec (gabarits mockup_templates/ ? 'grok' dispo ?) — on continue vers l'export."

# --- Placement des gagnants là où l'export va les lire -----------------------
# Cohérent avec image_pipeline.to_upscale_date_subdir : avec dossier daté ou non.
DAY="$(date +%d-%m-%Y)"
SUBDIR="$("$PY" -c "from src.config_loader import load_config; print('1' if load_config()['image_pipeline'].get('to_upscale_date_subdir', True) else '0')" 2>/dev/null || echo 1)"
if [ "$SUBDIR" = "1" ]; then
  DEST="$HOME/Downloads/To Upscale/$DAY"
else
  DEST="$HOME/Downloads/To Upscale"
fi
mkdir -p "$DEST"
for p in "${ABS[@]}"; do
  if [ "$FROM_DROP" -eq 1 ]; then
    mv -f "$p" "$DEST/"; echo "  -> déplacé dans ${DEST#$HOME/} : $(basename "$p")"
  else
    cp -f "$p" "$DEST/"; echo "  -> copié dans ${DEST#$HOME/} : $(basename "$p")"
  fi
done

# --- [2/2] Upscale + export ---------------------------------------------------
echo ""
echo "== [2/2] Upscale Upscayl + export ($TYPE) =="
"$PY" automation/upscale_and_export.py --type "$TYPE" \
  || { echo "❌ upscale/export a échoué. (Tes images sont dans To Upscale/$DAY/ — relançable.)"; exit 1; }

echo ""
echo "✅ Phase 2 terminée."
echo "   Mockups + vidéo : ~/Downloads"
echo "   JPG $TYPE ratios : ~/Downloads/Upscaled_add_export_5_ratios/$DAY/Final/"
[ "$FROM_DROP" -eq 1 ] && echo "   (Pre_phase_2 est de nouveau vide pour demain.)"
