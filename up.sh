#!/usr/bin/env bash
# up.sh — Upscale SEUL, sans prise de tête : active le venv puis upscale tous les
# fichiers de 'To Upscale/' (masters dans ~/Downloads selon ta config.local).
# Usage :  ./up.sh            (profil set, upscale-only)
#          ./up.sh --single   (profil single)
#          ./up.sh --ratios-only   (exporte les ratios depuis les masters)
set -u
cd "$(cd "$(dirname "$0")" && pwd)"
# Active l'environnement Python du projet s'il existe (sinon python3 global).
if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
PY="$(command -v python || command -v python3)"

TYPE="set"
EXTRA=("--upscale-only")
for a in "$@"; do
  case "$a" in
    --single) TYPE="single" ;;
    --ratios-only) EXTRA=("--ratios-only") ;;
    --full) EXTRA=() ;;                     # upscale + ratios + zip
    *) echo "Option inconnue : $a (attendu : --single, --ratios-only, --full)"; exit 2 ;;
  esac
done

exec "$PY" automation/upscale_and_export.py --type "$TYPE" "${EXTRA[@]}"
