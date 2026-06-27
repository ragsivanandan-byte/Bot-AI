#!/usr/bin/env bash
#
# Lanceur quotidien — Quiet Capital (macOS / Linux)
# Utilise l'environnement .venv créé par setup.sh.
#
#   ./bot/run.sh list
#   ./bot/run.sh make 1
#   ./bot/run.sh make all
#
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$DIR/.venv/bin/python" ]; then
  echo "❌  Environnement absent. Lance d'abord :  ./bot/setup.sh"
  exit 1
fi
exec "$DIR/.venv/bin/python" "$DIR/pipeline.py" "$@"
