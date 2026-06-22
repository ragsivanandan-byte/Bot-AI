#!/bin/bash
# Double-cliquez ce fichier pour ouvrir l'outil STRC dans votre navigateur.
# (Le .webloc est encore plus propre — celui-ci marche partout.)
URL="https://ragsivanandan-byte.github.io/bot-ai/"
echo "Ouverture de l'outil STRC…"
echo "$URL"
if command -v open >/dev/null 2>&1; then
  open "$URL"                 # macOS
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"             # Linux (au cas où)
else
  echo "Ouvrez ce lien dans votre navigateur : $URL"
fi
