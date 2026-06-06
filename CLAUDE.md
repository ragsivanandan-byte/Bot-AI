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

## 🆕 Production visuelle Grok (réponse Claude Chat intégrée 06/06)
- **Grok Build = agent CLI de code xAI** (comme Claude Code) avec `/imagine`
  natif ; **API Grok Imagine** = endpoints HTTP payants (clé `xai-...`).
  Génération headless qui écrit un fichier = **NON confirmée** → ne PAS coder un
  cron qui appelle Grok. Génération + QC + publication restent **MANUELS**.
- **Corrections boutique** : URL sans `/au/` ; ~20 fiches, 2 ventes, 1 avis ;
  prix single 6,90 € / set 3 13,90 € / set 6 26,90 €.
- **MusingsOfMeiMei = dessin MAIN (pas IA)** → `handmade: true`, exclue du label
  IA. Miroir IA réel = **MyAestheticAlley**.
- **Flux quotidien 7h** (déjà branché sur l'automatisation) : l'outil écrit dans
  `prompts_grok_du_jour.md` → **3 prompts images BRUTES** (set de 3, formes
  pleines + negative anti-arc-en-ciel) → **4 mockups** (compositing « PASTE
  UNCHANGED/OPAQUE », dont **1 COVER**) → **1 vidéo 6 s** (« frozen every frame »).
  Sortie imposée `~/Downloads`, conventions de nommage `NWD_*`. ⚠️ Mockups JAMAIS
  retouchés.
- Recettes de sets dans `config.yaml > grok_prompts.set_recipes` (sous-niches
  sous-exploitées : panorama above-sofa, frame TV, bedroom neutre…), rotation/jour,
  évite `niche.saturated_topics` (terracotta arch, boho moon/sun, nursery…).

### ✅ Fait
1. Nouveau format 3 images→4 mockups(+cover)+vidéo 6 s (`prompt_generator.py`).
2. Sortie `~/Downloads` + nommage imposés dans le brief.
3. Anti-répétition (recettes sous-exploitées + évitement des sujets saturés).
4. Branché sur l'automatisation 7h (main.py inchangé côté planif).

### ⏳ À faire
- Ingestion fine de la **liste réelle des ~20 fiches** (carte NWD_T*) pour
  durcir l'anti-répétition (Claude Chat doit transmettre la liste à jour).
- **Rapport de veille hebdo « boutiques IA »** (miroir MyAestheticAlley ; exclure
  MeiMei du label IA).
- Détails Grok Build (`[À TESTER]`) : valider si `/imagine` headless écrit un
  fichier ; sinon, option API Imagine (payante) en dossier de staging.
> Voir BRIEF_POUR_CLAUDE_CHAT.md + la réponse de Claude Chat (06/06) pour specs,
> formules de prompts éprouvées et pièges.

## Rôles
- Claude Code : outillage terminal (prompts, génération via Grok Build, sortie
  Downloads, automatisation, veille, anti-répétition, tests).
- Claude Chat : stratégie + jugement des images Grok + savoir Grok Build.
- Grok Build / Imagine : exécution images/mockups/vidéos.
- Ragavan : validation, mise en ligne, saisie chiffres concurrents, screenshots.
