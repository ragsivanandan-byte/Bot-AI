#!/usr/bin/env bash
#
# Installateur tout-en-un — Quiet Capital (macOS / Linux)
# Usage :  ./bot/setup.sh
#
set -euo pipefail
cd "$(dirname "$0")"   # se place dans bot/

echo ""
echo "🤖  Quiet Capital — installation automatique"
echo "═══════════════════════════════════════════"

# 1. Python -------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌  Python 3 n'est pas installé. Installe-le : https://www.python.org/downloads/"
  exit 1
fi
echo "✓  Python : $(python3 --version)"

# 2. Environnement isolé (.venv) ---------------------------------------------
echo "📦  Création de l'environnement Python (.venv)…"
if ! python3 -m venv .venv 2>/dev/null; then
  echo "❌  Le module venv manque. Sur Debian/Ubuntu :  sudo apt install python3-venv"
  echo "    Puis relance ./bot/setup.sh"
  exit 1
fi
./.venv/bin/python -m pip install --upgrade pip >/dev/null
echo "📦  Installation des dépendances…"
./.venv/bin/python -m pip install -r requirements.txt

# 3. ffmpeg -------------------------------------------------------------------
if command -v ffmpeg >/dev/null 2>&1; then
  echo "✓  ffmpeg déjà installé"
else
  echo "🎬  ffmpeg manquant, tentative d'installation…"
  if command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y ffmpeg
  else
    echo "⚠️   Installe ffmpeg à la main : https://ffmpeg.org/download.html"
  fi
fi

# 4. Fichier .env -------------------------------------------------------------
[ -f .env ] || cp .env.example .env

set_key() {  # set_key CLE VALEUR  → écrit/MAJ dans .env
  local key="$1" val="$2" tmp
  tmp=$(mktemp)
  if grep -q "^${key}=" .env; then
    sed "s|^${key}=.*|${key}=${val}|" .env > "$tmp" && mv "$tmp" .env
  else
    cp .env "$tmp"; printf '%s=%s\n' "$key" "$val" >> "$tmp"; mv "$tmp" .env
  fi
}

# 5. Clés API (saisie masquée) ------------------------------------------------
echo ""
echo "🔑  Tes clés API  (laisse vide + Entrée pour configurer plus tard dans bot/.env)"
printf "    ElevenLabs (obligatoire) : "
read -rs EL; echo
[ -n "${EL:-}" ] && set_key ELEVENLABS_API_KEY "$EL" && echo "    ✓ enregistrée"
printf "    xAI Grok   (optionnel)   : "
read -rs XA; echo
[ -n "${XA:-}" ] && set_key XAI_API_KEY "$XA" && echo "    ✓ enregistrée"

# 6. Vérification -------------------------------------------------------------
echo ""
echo "🔎  Vérification du contenu…"
./.venv/bin/python pipeline.py list

echo ""
echo "✅  Installation terminée !"
echo "═══════════════════════════════════════════"
echo "👉  Produis ta 1re vidéo :   ./bot/run.sh make 1"
echo "    (ou plusieurs :          ./bot/run.sh make 1 2 3)"
echo ""
