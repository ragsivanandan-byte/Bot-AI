# 📨 Brief de passation — Claude Code → Claude Chat (projet Etsy NeutralWallDesign)

> **Qui écrit ?** Claude Code (l'assistant qui a construit l'outil en ligne de
> commande sur le Mac de Ragavan).
> **Pour qui ?** Claude Chat (l'assistant stratégie SEO/trafic/ventes + pilote du
> workflow Grok Build).
> **But du document :** te donner TOUT le contexte d'un coup, te dire ce qui
> marche réellement aujourd'hui, t'expliquer la nouvelle direction (génération
> automatique images/mockups/vidéos via Grok Build), et **te poser des questions
> précises** auxquelles tu dois répondre pour que je puisse coder la suite sans
> me tromper.

---

## 1. Contexte boutique & objectif

- Boutique : **NeutralWallDesign** — https://www.etsy.com/au/shop/NeutralWallDesign
- Produit : **wall art printables** (téléchargements numériques), niche
  « Warm Organic Minimalism » (boho, terracotta, céleste, japandi, wabi-sabi,
  nursery neutre).
- État : ~16 fiches, 1 vente, 1 avis 5★, boutique de ~2 mois.
- Objectif : **5000 €/mois net** (horizon réaliste 12-36 mois, via la montée de
  l'AOV par bundles plutôt que par volume pur).
- Budget pub : 100-250 €/mois. Dispo opérateur : 4-5h/jour.
- Opérateur : Ragavan (France, micro-entreprise).

## 2. Règles NON négociables (à respecter par nous deux)

1. **Zéro hallucination.** Le CA réel d'une boutique Etsy n'est pas public →
   uniquement des **ESTIMATIONS** étiquetées avec calcul montré. « Boutique 100% IA »
   = **INFÉRENCE** (faisceau d'indices), jamais une certitude.
2. **Respect des CGU.** Pas de scraping agressif, pas de contournement. (C'est
   d'ailleurs pour ça que l'API Etsy a échoué, cf. §5.)
3. **Toute donnée non vérifiable est marquée comme telle** + source citée.
4. **Différenciation obligatoire.** Chaque future fiche/visuel doit être UNIQUE
   et différencié des concurrents ET de ce que la boutique fait déjà (ne pas se
   répéter) — analyse de la boutique existante à l'appui.

## 3. Ce que j'ai construit (l'outil, en Python, sur le Mac)

Dépôt : `~/Bot-AI` (branche `claude/etsy-market-intelligence-tool-oq4UV`).
Outil modulaire qui produit **3 rapports markdown horodatés** par jour dans
`reports/AAAA-MM-JJ/` :

1. `veille_concurrents.md` — pour chaque concurrent : ventes, fiches, avis, prix
   (convertis en €), **CA estimé (calcul transparent)**, inférence IA, « 3 forces
   / 1 faille », + section « Évolution depuis le dernier run » (historique SQLite).
2. `prompts_grok_du_jour.md` — prompts d'images prêts pour Grok (format formes
   pleines : *solid filled / no outline / negative prompt*), chacun rattaché à un
   pilier SEO + source.
3. `guidelines_claude_chat.md` — **C'EST TON FICHIER.** C'est un **sur-ensemble** :
   stratégie (SEO, Pinterest, pricing/AOV, pub, roadmap 5000 €) **+ Annexe A**
   (toute la veille) **+ Annexe B** (les prompts du jour) **+ une section
   « juger les images Grok »**. Donc en collant CE seul fichier, tu as tout le
   contexte pour évaluer les captures d'images que Ragavan t'enverra.

Briques techniques : fetch respectueux (robots.txt, rate-limit, retries, cache),
estimation CA, inférence IA, conversion devises→EUR (BCE + repli statique),
historisation SQLite + diffs, connecteurs API optionnels, génération de prompts,
**142 tests automatisés** (tous verts), automatisation launchd 7h.

## 4. ✅ Ce qui MARCHE aujourd'hui dans le terminal (état réel, vérifié)

Commandes opérationnelles sur le Mac de Ragavan :

| Commande | État |
|---|---|
| `python main.py` | ✅ génère les 3 rapports du jour |
| `python main.py --selftest` | ✅ diagnostic environnement |
| `python main.py --demo` | ✅ rapport de démonstration (données fictives) |
| `python tests/run_all.py` | ✅ 142 assertions, toutes vertes |
| `bash automation/install_daily.sh` | ✅ programme un lancement auto **chaque jour à 7h00** (heure locale du Mac → régler le Mac sur Europe/Paris) |
| `bash automation/run_daily.sh` | ✅ lance tout de suite (génère + ouvre le dossier) |

Sources de données, état réel :
- **Google Trends : ✅ fonctionne** sur le Mac (vraies tendances dans les rapports).
- **Conversion devises → € : ✅** (taux BCE, cache, repli statique hors-ligne).
- **Veille concurrents : ✅ via données PUBLIQUES saisies à la main** dans
  `config.yaml` (voir §5 et §6).
- **Historique/évolution : ✅**.

## 5. État des sources de données (important)

- **Scraping HTML d'Etsy : ❌ bloqué** (HTTP 403 depuis le Mac et depuis mon
  environnement). On ne force pas.
- **API officielle Etsy : ❌ ABANDONNÉE.** L'app a été **bannie** par Etsy : ses
  CGU interdisent largement de collecter des données sur **d'autres** boutiques.
  → On ne réessaie pas (risque pour le compte vendeur).
- **Solution retenue (100% conforme) :** Ragavan note lui-même les **chiffres
  publics** (ventes, avis, note, prix) de chaque concurrent dans `config.yaml`
  (bloc `data:`), et l'outil fait toute l'analyse à partir de ça. À rafraîchir
  ~1×/semaine.
- **Keywords Everywhere (volumes réels, ~10-15 €/mois) : optionnel, pas encore
  activé** (pas de clé). Sans lui, on utilise Google Trends (intérêt relatif).

## 6. Concurrents actuellement suivis (chiffres publics, certains « à vérifier »)

| Boutique | Ventes | Avis | Note | Prix | Note de fiabilité |
|---|---|---|---|---|---|
| DigivitesPrints | ~47 900 | ~6 600 | 4.9 | à compléter | ventes via recherche web, à confirmer |
| MusingsOfMeiMei | 28 300 | 3 800 | 5.0 | 7,56 € | fourni par Ragavan |
| ZegaStudio | ~3 200 | 210 | 5.0 | à compléter | via recherche web, à confirmer |
| MyAestheticAlley | 1 200 | 81 | 4.9 | 12,96 € | fourni par Ragavan ; **IA-assumée, UE, 2 ans = notre miroir** |
| EmaParaschivArt | à compléter | 530 | 4.9 | à compléter | Bucarest/UE, 292 fiches |
| NeutralWallDesign (nous) | 1 | 1 | 5.0 | 6,00 € | référence |

Prix manquants : introuvables via recherche web (Etsy les masque) → Ragavan les
saisira. En attendant, l'outil utilise une fourchette de repli marquée
« estimation ».

## 7. 🆕 Nouvelle direction : Grok Build / Grok Imagine (ce que Ragavan veut)

Ragavan veut industrialiser la **production de contenu visuel** via **Grok Build**
(piloté depuis le terminal du Mac) et **Grok Imagine** :

- Génération **automatique** d'images, de mockups et de vidéos pour **chaque
  future fiche Etsy** (nouvelles fiches + déclinaisons).
- **Sortie redirigée vers le dossier `Téléchargements` (`~/Downloads`)** :
  images, mockups ET vidéos doivent atterrir là, imposé via le terminal.
- **Flux quotidien cible, 7h00 (heure française), automatisé :**
  1. **3 prompts ultra-détaillés** pour des **images brutes**.
  2. Ces images alimentent **4 prompts ultra-détaillés** pour que Grok Build
     **construise les mockups** (⚠️ **les images sur les mockups ne sont JAMAIS
     retouchées**).
  3. Dont **1 cover principale** pour la fiche Etsy du jour.
  4. **+ 1 vidéo de 6 secondes** générée automatiquement par Grok Build à partir
     du prompt que j'aurai rédigé.
- Les prompts sont calés sur une **analyse de la boutique existante**
  (NeutralWallDesign) pour **ne pas se répéter**, et différenciés des concurrents.
- **Veille concurrentielle + marché Etsy hebdomadaire**, en particulier les
  **boutiques IA positionnées comme nous**, en s'appuyant sur toi (Claude chat)
  et sur Grok via Grok Build.

## 8. Ce que je (Claude Code) vais construire ensuite

Une fois que tu m'auras répondu (§9), je prévois de faire évoluer l'outil pour :
1. Produire chaque matin **le format exact demandé** : 3 prompts d'images brutes
   → 4 prompts de mockups (dont 1 cover) → 1 prompt vidéo 6 s — au lieu des
   5 prompts génériques actuels.
2. **Rediriger toutes les sorties Grok Build vers `~/Downloads`** (paramètre/flag
   imposé via le terminal).
3. Intégrer une **analyse de la boutique existante** (liste des fiches/visuels
   déjà publiés) pour **interdire les répétitions** dans les nouveaux prompts.
4. Brancher tout ça sur l'**automatisation 7h** déjà en place.
5. Mettre en place la **veille hebdo des boutiques IA** (rapport dédié).

⚠️ Je ne code rien sur Grok Build tant que je n'ai pas tes réponses ci-dessous,
pour ne pas inventer son fonctionnement.

## 9. ❓ Ce dont j'ai besoin de TOI, Claude Chat (réponds point par point)

Ragavan m'a dit que tu viens de travailler sur Grok Build ces dernières heures et
que tu peux m'expliquer **ce qui a été fait dans l'ordre + les erreurs à ne pas
commettre**. Merci de me préciser :

1. **Lien terminal ↔ Grok Build** : par quelle commande/CLI/API exacte déclenche-
   t-on Grok Build depuis le terminal du Mac ? (nom de la commande, arguments,
   fichier de config, clé/API éventuelle, dépendances installées)
2. **Format des prompts qui marche** : quelle structure exacte pour (a) les 3
   prompts d'images brutes, (b) les 4 prompts de mockups, (c) le prompt vidéo 6 s ?
   Donne un exemple réel qui a fonctionné.
3. **Redirection de sortie vers `~/Downloads`** : comment force-t-on Grok Build à
   écrire images/mockups/vidéos dans Téléchargements ? (flag, variable d'env,
   paramètre ?) Quels noms/formats de fichiers en sortie (png/jpg/mp4, dimensions) ?
4. **Règle « mockups jamais retouchés »** : comment est-ce garanti techniquement
   dans votre flux ? Qu'est-ce qui a cassé cette règle par le passé ?
5. **Erreurs déjà commises à éviter** : liste-les (formats, ratios, longueur de
   prompt, limites de génération, quotas, blocages, étapes dans le mauvais ordre…).
6. **Cover & vidéo** : specs précises attendues par Etsy (dimensions cover,
   durée/format/ratio vidéo 6 s, poids max).
7. **Anti-répétition** : as-tu déjà la **liste des 16 fiches existantes** de
   NeutralWallDesign (titres + thèmes + palettes) ? Si oui, transmets-la : j'en ai
   besoin pour interdire les répétitions dans les prompts.
8. **Cadence & ordre** : confirme l'enchaînement quotidien idéal de bout en bout
   (de la génération des prompts à la fiche Etsy prête), et ce qui doit rester
   manuel vs automatisé.

## 10. Répartition des rôles proposée

- **Claude Code (moi)** : l'outillage terminal — génération des prompts du jour
  (images brutes → mockups → cover → vidéo), redirection vers `~/Downloads`,
  automatisation 7h, veille concurrents (données publiques manuelles), analyse
  anti-répétition, tests.
- **Claude Chat (toi)** : stratégie SEO/trafic/ventes, jugement des images Grok
  (GARDER/RETRAVAILLER/JETER + titre Etsy + tags), pilotage créatif, et
  transmission du savoir Grok Build (ce document §9).
- **Grok Build / Grok Imagine** : exécution de la génération images/mockups/vidéos.
- **Ragavan** : validation finale, mise en ligne des fiches, saisie des chiffres
  publics concurrents (~1×/semaine), screenshots des images à juger.

---

**Action immédiate demandée à Claude Chat :** réponds aux 8 questions du §9
(surtout 1, 2, 3, 5, 7). Dès que Ragavan me transmet tes réponses, je code le
nouveau flux quotidien (3 images brutes → 4 mockups dont 1 cover → 1 vidéo 6 s →
sortie `~/Downloads`) et je le branche sur l'automatisation de 7h.
