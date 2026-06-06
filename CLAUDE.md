# CLAUDE.md — Mémoire projet (à lire par Claude Code à chaque session)

Projet : outil d'intelligence marché + production de contenu pour la boutique
Etsy **NeutralWallDesign** (wall art printables, niche Warm Organic Minimalism).
Opérateur : Ragavan (France). Objectif : 5000 €/mois net (12-36 mois).

## Règles non négociables
- **Zéro hallucination** : CA = ESTIMATION étiquetée + calcul ; « 100% IA » =
  INFÉRENCE ; toute donnée non vérifiable est marquée + sourcée.
- **CGU respectées** : pas de scraping agressif ni de contournement.
- **Différenciation** : chaque visuel/fiche doit être unique vs concurrents ET
  vs les fiches déjà publiées (ne pas se répéter).
- **Dév sur la branche** `claude/etsy-market-intelligence-tool-oq4UV`, commit+push.

## État des sources (important)
- Scraping HTML Etsy : bloqué (403). API Etsy : **bannie** (CGU interdisent la
  collecte sur d'autres boutiques) → **abandonnée**.
- Veille concurrents = **données publiques saisies à la main** dans `config.yaml`
  (bloc `data:`), rafraîchies ~1×/semaine.
- Google Trends : fonctionne sur le Mac. Conversion devises→€ : OK. Historique
  SQLite + diffs : OK. Keywords Everywhere : optionnel (pas de clé).

## Ce qui tourne dans le terminal
`python main.py` (3 rapports/jour), `--selftest`, `--demo`, `tests/run_all.py`
(142 tests verts), `automation/install_daily.sh` (launchd 7h), `run_daily.sh`.
`guidelines_claude_chat.md` = sur-ensemble (stratégie + Annexe A veille + Annexe B
prompts) destiné à Claude chat.

## 🆕 Direction en cours : production visuelle via Grok Build / Grok Imagine
Objectif : générer automatiquement images, **mockups** et **vidéos** pour chaque
future fiche Etsy, piloté depuis le terminal du Mac.
- **Sortie imposée vers `~/Downloads` (Téléchargements)** pour images/mockups/vidéos.
- **Flux quotidien cible 7h (heure FR), automatisé :**
  `3 prompts images BRUTES` → alimentent `4 prompts mockups` (dont **1 cover**
  fiche du jour) → **+ 1 vidéo de 6 s**. ⚠️ **Mockups JAMAIS retouchés.**
- Prompts calés sur l'**analyse de la boutique existante** (anti-répétition) et
  différenciés des concurrents.
- **Veille hebdo** des boutiques **IA positionnées comme nous**, avec Claude chat
  + Grok via Grok Build.

### À FAIRE (en attente des réponses de Claude chat sur Grok Build — voir
### BRIEF_POUR_CLAUDE_CHAT.md §9 : commande terminal exacte, format de prompts,
### redirection sortie Downloads, erreurs à éviter, liste des 16 fiches existantes)
1. Remplacer les 5 prompts génériques par le format 3 images→4 mockups(+cover)+vidéo 6 s.
2. Imposer la sortie Grok Build vers `~/Downloads`.
3. Module anti-répétition basé sur les fiches existantes.
4. Brancher sur l'automatisation 7h.
5. Rapport de veille hebdo « boutiques IA ».
> Ne pas inventer le fonctionnement de Grok Build : attendre les réponses.

## Rôles
- Claude Code : outillage terminal (prompts, génération via Grok Build, sortie
  Downloads, automatisation, veille, anti-répétition, tests).
- Claude Chat : stratégie + jugement des images Grok + savoir Grok Build.
- Grok Build / Imagine : exécution images/mockups/vidéos.
- Ragavan : validation, mise en ligne, saisie chiffres concurrents, screenshots.
