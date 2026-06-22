#!/bin/bash
# Installe l'accès le plus simple à l'outil STRC sur votre Mac :
#   1) un raccourci double-cliquable "STRC" sur le Bureau (ouvre le site),
#   2) la commande terminal 'strc'.
#
#   bash mac/install.sh
set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP="${DESKTOP_DIR:-$HOME/Desktop}"

echo "→ Dépôt   : $REPO"
echo "→ Bureau  : $DESKTOP"

# 1) Raccourci sur le Bureau : .webloc (ouvre le navigateur sans Terminal).
mkdir -p "$DESKTOP"
cp "$REPO/mac/STRC.webloc" "$DESKTOP/STRC.webloc"
cp "$REPO/mac/STRC.command" "$DESKTOP/STRC.command"
chmod +x "$DESKTOP/STRC.command"
echo "✓ Raccourcis copiés sur le Bureau (STRC.webloc + STRC.command)."

# 2) Commande terminal 'strc' (alias dans le profil shell).
chmod +x "$REPO/mac/strc"
SHELL_NAME="$(basename "${SHELL:-/bin/zsh}")"
case "$SHELL_NAME" in
  zsh)  PROFILE="$HOME/.zshrc" ;;
  bash) PROFILE="$HOME/.bash_profile" ;;
  *)    PROFILE="$HOME/.profile" ;;
esac
touch "$PROFILE"
LINE="alias strc='$REPO/mac/strc'"
if grep -qF "alias strc=" "$PROFILE" 2>/dev/null; then
  # Remplace une éventuelle ancienne définition.
  TMP="$(mktemp)"
  grep -vF "alias strc=" "$PROFILE" > "$TMP" && mv "$TMP" "$PROFILE"
fi
echo "$LINE" >> "$PROFILE"
echo "✓ Commande 'strc' ajoutée à $PROFILE"

echo
echo "TERMINÉ. Pour utiliser tout de suite la commande :  source $PROFILE"
echo "Puis :"
echo "   strc           # ouvre le site"
echo "   strc term --weekly-amount 1000   # version terminal"
echo "Ou double-cliquez 'STRC' sur le Bureau."
