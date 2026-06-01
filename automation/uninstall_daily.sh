#!/bin/bash
# =============================================================================
# uninstall_daily.sh — Désactive le lancement automatique quotidien.
#     bash automation/uninstall_daily.sh
# =============================================================================
set -u

LABEL="com.neutralwalldesign.marketintel"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "🗑️  Automatisation désactivée (le plist a été retiré)."
echo "    Tu peux toujours lancer l'outil à la main : "
echo "    cd ~/Bot-AI && source .venv/bin/activate && python main.py"
