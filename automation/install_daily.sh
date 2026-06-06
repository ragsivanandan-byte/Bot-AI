#!/bin/bash
# =============================================================================
# install_daily.sh — Programme l'outil pour qu'il tourne TOUS LES JOURS à 7h00.
#
# À lancer UNE SEULE FOIS sur ton Mac :
#     bash automation/install_daily.sh
#
# ⚠️ L'heure est l'heure LOCALE de ton Mac. Comme tu es en France, vérifie que
# ton Mac est réglé sur le fuseau « Europe/Paris » (Réglages Système > Général >
# Date et heure) -> 7h00 local = 7h00 heure française.
# =============================================================================
set -e

LABEL="com.neutralwalldesign.marketintel"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO="$HOME/Bot-AI"
# Heure de lancement (heure LOCALE du Mac). Défaut 5h00.
# Réglable : `install_daily.sh 7`     -> 7h00
#            `install_daily.sh 5 30`  -> 5h30
HOUR="${1:-5}"
MINUTE="${2:-0}"
TIMESTR=$(printf '%dh%02d' "$HOUR" "$MINUTE")

if [ ! -d "$REPO" ]; then
  echo "❌ $REPO introuvable. Clone d'abord le projet dans ton dossier perso."
  exit 1
fi
if [ ! -d "$REPO/.venv" ]; then
  echo "❌ $REPO/.venv introuvable. Crée d'abord l'environnement :"
  echo "   cd ~/Bot-AI && python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$REPO/logs"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO/automation/run_daily.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$HOUR</integer>
    <key>Minute</key><integer>$MINUTE</integer>
  </dict>
  <key>StandardOutPath</key><string>$REPO/logs/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$REPO/logs/launchd.err.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
PLISTEOF

# Recharge proprement (unload silencieux si déjà chargé, puis load).
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ Automatisation installée."
echo "   -> Rapports + génération des designs TOUS LES JOURS à ${TIMESTR} (heure locale du Mac)."
echo "   -> Vérifie que ton Mac est réglé sur l'heure française (Europe/Paris)."
echo "   -> ⚠️ Le Mac doit être ALLUMÉ + SESSION OUVERTE (verrouillée OK) + NON"
echo "      ENDORMI à ${TIMESTR}. launchd ne réveille/n'allume PAS le Mac."
echo "      (Pour rester éveillé : voir le README, section veille.)"
echo "   -> Logs : $REPO/logs/launchd.out.log + logs/grok.out.log"
echo ""
echo "Pour tester tout de suite :"
echo "   bash automation/run_daily.sh"
echo "Pour désactiver plus tard :"
echo "   bash automation/uninstall_daily.sh"
