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
`guidelines_claude_chat.md` = **bloc unique à coller dans Claude chat** : mène par
la mission du jour (QC des rendus Grok : garder 1 des ~8 variations/design +
mockups OK + **fiche Etsy complète** titre/description/13 tags/couleur/prix), puis
les prompts du jour, puis veille (Annexe A) et stratégie (Annexe B) en référence.

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
2. Sortie `~/Downloads` (rapports : `~/Downloads/reports/<date>/`) + nommage imposés.
3. Anti-répétition (recettes sous-exploitées + évitement des sujets saturés).
4. Branché sur l'automatisation 7h.
5. **Grok Build headless VALIDÉ** (`grok -p "...Save the result as a PNG at <path>"`
   écrit bien le fichier). Runner `automation/grok_generate.py` :
   - `--designs` (lancé à 7h) : génère `variations_per_design` variations des 3
     designs bruts → `~/Downloads` ;
   - `--mockups D1 D2 D3` (APRÈS QC) : 4 mockups (1 cover) + vidéo depuis les
     gagnants. **QC humain obligatoire entre les 2 phases ; rien n'est publié.**
6. `guidelines_claude_chat.md` = bloc unique QC + fiche Etsy (cf. plus haut).

7. **Veille hebdo boutiques IA** intégrée au bloc Claude chat (Annexe C) :
   miroir = MyAestheticAlley (`ai_mirror: true`), MeiMei exclue (fait-main),
   évolution sur 7 j via `compute_deltas(..., cutoff=J-7)`. But : Claude chat
   affine ses décisions au fil du temps.
8. Génération matinale = **8 variations/design** (`variations_per_design: 8`),
   listées (noms `_vK.png`) dans le bloc pour que Claude chat choisisse la
   meilleure à partir des images jointes.

9. **Prompts raffinés (avis Claude Chat 06/06)** : 1 `{shape_color}` + 1
   `{bg_color}` par design (anti arc-en-ciel, set cohérent), fond explicite,
   negatives courts/priorisés, cover « FILLS MOST », cadre au ratio, mockup
   « gros plan détail », palettes HEX nommées (Warm Clay/Sage Organic/Neutral
   Sand), nouvelles recettes (vessels, dunes, marks, panorama, Frame TV),
   prompt **gallery-wall bonus** pour les sets.

### ✅ Mockups EXACTS (compositing Python) — résout le piège de régénération
Test réel (feedback Claude Chat 06/06) : `grok -p` **régénère/déforme** (skew,
halo, doublon) au lieu de coller. → **compositing Pillow** (`src/mockup_compositor.py`
+ `automation/make_mockups.py`) : détection du vert par test RELATIF (robuste au
vert « sale » mesuré RGB(9,187,13)), perspective, et **np.where → seuls les pixels
verts sont remplacés** ⇒ le reste du gabarit reste IDENTIQUE au pixel (testé).
Ratio-aware (`mockup_templates/2x3|3x1|16x9/`). Gabarits gitignored.
Vidéo : `make_mockups.py --video` = image-to-video depuis la COVER composite,
prompt sans balayage de lumière, **audio retiré** via ffmpeg `-an`, 16:9 (Frame
TV) / 2:3 (Pinterest), jamais 2:1.

### ⏳ À faire / À TESTER
- Créer les **gabarits** réels (commandes `grok -p` prêtes dans
  `mockup_templates/README_TEMPLATES.md`, rangées par ratio 2x3/3x1/16x9). Inclut
  les gabarits **Frame TV authentiques** (bezel fin Samsung, art **bord-à-bord**,
  sur console, écran 100% vert) — recos Claude Chat intégrées.
- Designs livrés ≥ 4608 px (bruts Grok sous la spec → Upscayl ×4) ; mockups en 4K.
- (Optionnel) automatiser l'Upscayl ×4 du gagnant avant découpe 5 ratios/300 DPI.
- **Gallery-wall (3 œuvres)** = cas dur en headless → interactif/API ; fallback
  cover single déjà en place.
- Résolution Grok vs spec NWD (4608 px) → sinon Upscayl ×4.
- Ingestion fine de la **liste réelle des ~20 fiches** (carte NWD_T*) pour durcir
  l'anti-répétition.
> Voir BRIEF_POUR_CLAUDE_CHAT.md + la réponse de Claude Chat (06/06) pour specs,
> formules de prompts éprouvées et pièges.

## Rôles
- Claude Code : outillage terminal (prompts, génération via Grok Build, sortie
  Downloads, automatisation, veille, anti-répétition, tests).
- Claude Chat : stratégie + jugement des images Grok + savoir Grok Build.
- Grok Build / Imagine : exécution images/mockups/vidéos.
- Ragavan : validation, mise en ligne, saisie chiffres concurrents, screenshots.
