# NeutralWallDesign — Outil d'intelligence marché Etsy

Outil Python (CLI + rapports markdown) qui, lancé quotidiennement, produit
trois livrables pour piloter la boutique Etsy **NeutralWallDesign** (wall art
printable, niche « Warm Organic Minimalism ») :

1. **`veille_concurrents.md`** — veille concurrentielle : ventes publiques,
   fiches, avis, prix, **CA estimé (calcul transparent)**, inférence
   « probablement IA », et pour chaque concurrent « 3 choses qu'ils font mieux
   + 1 faille exploitable ».
2. **`prompts_grok_du_jour.md`** — **brief visuel du jour** : 3 prompts d'images
   brutes (set de 3, formes pleines + negative anti-arc-en-ciel) → 4 prompts de
   mockups (compositing « PASTE UNCHANGED / OPAQUE », dont **1 cover**) → 1 prompt
   vidéo 6 s (« frozen every frame »). Sortie imposée `~/Downloads` + nommage
   `NWD_*`. Génération (Grok Imagine / Grok Build), QC et publication **manuels**.
3. **`guidelines_claude_chat.md`** — brief stratégique (SEO, Pinterest, pricing,
   pub, roadmap 5000 €/mois) destiné à un assistant en chat. **C'est un
   sur-ensemble** : il intègre aussi, en annexes, le contenu complet de la veille
   (Annexe A) et des prompts Grok (Annexe B), pour que Claude chat reçoive **tout
   le contexte en un seul copier-coller** et puisse juger les images Grok. Les
   fichiers 1 et 2 restent générés séparément.

> ⚠️ **Lis [`LIMITS.md`](LIMITS.md) avant de te fier aux chiffres.** Le CA réel
> d'une boutique Etsy n'est pas public (tout CA est une **estimation**), et la
> détection « 100 % IA » est une **inférence**, jamais une certitude.

---

## Installation

Prérequis : **Python 3.11+**.

```bash
# 1. Cloner / se placer dans le dossier
cd Bot-AI

# 2. (Recommandé) créer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux

# 3. Installer les dépendances
pip install -r requirements.txt
```

`pytrends` (Google Trends) est **optionnel** : s'il n'est pas installé, l'outil
fonctionne quand même, les signaux de tendance sont alors marqués « à valider ».

### Connecteurs API (optionnels, pour des données « ultra connectées »)

L'outil sait utiliser deux sources de données via API. **Sans clé, il fonctionne
exactement comme avant** (parsing HTML public + Google Trends). Les clés ne se
mettent **jamais** dans le code ni dans `config.yaml` : elles se lisent dans des
**variables d'environnement**.

**1. API officielle Etsy (GRATUITE) — recommandée**
Données concurrents fiables et autorisées (ventes, fiches, avis, prix), sans
scraping. Mise en place :
1. Crée un compte sur le portail développeur Etsy et déclare une app
   (https://www.etsy.com/developers) → tu obtiens une **keystring** (clé d'API).
   La validation est gratuite mais peut prendre quelques jours.
2. Exporte la clé avant de lancer l'outil :
   ```bash
   export ETSY_API_KEY="ta_keystring_ici"
   ```
   Pour la rendre permanente, ajoute cette ligne à `~/.zshrc` (macOS récent).

**2. Keywords Everywhere (PAYANT, ~10-15€/mois en crédits) — volumes réels**
Vrais volumes de recherche par mot-clé (source Google, proxy de l'intention
d'achat). Mise en place :
1. Crée un compte sur keywordseverywhere.com, achète des crédits, récupère ta
   clé API dans ton tableau de bord.
2. Exporte la clé :
   ```bash
   export KEYWORDS_EVERYWHERE_API_KEY="ta_cle_ici"
   ```

Quand une clé est présente, l'outil bascule automatiquement dessus ; sinon il
retombe sur le mode public. Vérifie l'état avec `python main.py --selftest`
(lignes « clé API Etsy » et « clé Keywords Everywhere »).

> 🔒 Les clés vivent uniquement dans ton environnement shell. Elles ne sont ni
> écrites dans les rapports, ni commitées, ni loggées.

---

## Utilisation

```bash
python main.py                 # run complet (récupère les concurrents live)
python main.py --selftest      # diagnostic : config, modules, accès Etsy/Trends
python main.py --discover      # + découverte de nouveaux concurrents via recherche
python main.py --no-network    # mode hors-ligne (rapports dégradés, aucune requête)
python main.py --demo          # rapport de DÉMONSTRATION avec données FICTIVES
python main.py --verbose       # logs détaillés (utile pour diagnostiquer)
```

> 💡 **Lance d'abord `python main.py --selftest`** sur ta machine : il te dira en
> quelques secondes si Etsy et Google Trends sont joignables depuis ton réseau,
> et si tout est prêt pour un run complet.

### Génération visuelle via Grok Build (headless)

L'outil pilote Grok Build pour générer les visuels, en **2 phases** (QC humain
entre les deux ; rien n'est publié automatiquement) :

```bash
# Phase 1 (auto à 5h) : variations des designs bruts -> ~/Downloads
# (+ un ZIP `24images_grok_brut.zip` regroupant toutes les images : 1 seul
#  fichier à envoyer à Claude chat, qui limite à 20 fichiers/upload)
python automation/grok_generate.py --designs

# (tu choisis les gagnants avec Claude chat à partir des captures)

# Phase 2 : 4 mockups (1 cover) + vidéo 6 s, depuis les designs gagnants
python automation/grok_generate.py --mockups ~/Downloads/<g1>.png ~/Downloads/<g2>.png ~/Downloads/<g3>.png
```

Réglages dans `config.yaml > grok_prompts` : `auto_generate`, `variations_per_design`,
`grok_command`, `per_call_timeout_s`. Si `grok` n'est pas installé, l'étape est
ignorée proprement.

**Vitesse** : `batch_variations: true` (défaut) demande les N variations d'un
design en **un seul appel** `grok` (au lieu de N) → beaucoup plus rapide.
`parallel_workers: 3` lance plusieurs designs **en parallèle** (plus rapide,
consomme plus de quota simultanément).

### Mockups EXACTS par compositing Python (recommandé)

Demander à Grok de « coller » l'œuvre en headless **régénère souvent** une œuvre
proche au lieu de coller la tienne. Pour des mockups **pixel-pour-pixel** (la
cover montre EXACTEMENT le fichier vendu), utilise le compositeur Python :

1. Prépare une fois des **gabarits** de pièces dans `mockup_templates/` (photo
   avec un cadre dont l'intérieur est un **rectangle vert `#00FF00`**). Voir
   `mockup_templates/README_TEMPLATES.md` (inclut un prompt Grok pour les créer).
2. Lance le compositing avec tes designs gagnants :
   ```bash
   python automation/make_mockups.py ~/Downloads/<g1>.png ~/Downloads/<g2>.png ~/Downloads/<g3>.png
   ```
   → mockups exacts dans `~/Downloads` (le code détecte le vert et y plaque ton
   design, perspective comprise ; **seuls les pixels verts sont remplacés**, le
   reste du gabarit reste identique). Gratuit, instantané, déterministe.
   Gabarits par ratio : `mockup_templates/2x3/`, `/3x1/`, `/16x9/` (le bon dossier
   est choisi selon le format du jour ; sinon dossier à plat).
   Ajoute `--video` pour générer aussi la vidéo 6 s **depuis la cover composite**
   (zoom lent, sans balayage de lumière) et retirer l'audio via ffmpeg.

### Upscale ×4 + export 5 ratios (commande indépendante)

Process **séparé** du flux quotidien, à lancer à la main. Il traite le dossier
**du jour** dans `~/Downloads/To Upscale/<jj-mm-aaaa>/` :
```bash
python automation/upscale_and_export.py            # dossier du jour
python automation/upscale_and_export.py --date 07-06-2026
```
1. **upscale ×4** chaque image (Upscayl/Real-ESRGAN si `image_pipeline.upscale_command`
   est configuré et présent ; sinon **Lanczos ×4**, très propre pour des aplats) ;
2. **exporte** chaque image en **5 ratios JPG** (2:3, 3:4, 4:5, 5:7, 11:14),
   hauteur fixe **6912 px**, **qualité 90** (jamais 100).
Sortie : `~/Downloads/Upscaled_add_export_5_ratios/<jj-mm-aaaa>/` (créé auto) —
ex. 3 images → 3 PNG upscalées + 15 JPG.

> Pour un vrai upscale IA (au lieu de Lanczos), installe Upscayl/Real-ESRGAN et
> renseigne `image_pipeline.upscale_command` dans `config.yaml` (placeholders
> `{input}`/`{output}`).

### Veille jour à jour (historisation)

À chaque run, l'état public des concurrents est enregistré dans une base SQLite
locale (`cache/history.sqlite3`). Le rapport de veille affiche alors une section
**« Évolution depuis le dernier run »** (Δ ventes, Δ fiches, Δ avis, Δ prix) — le
meilleur signal pour repérer la fiche/le set d'un concurrent qui décolle.

### Tests

```bash
python tests/run_all.py        # TOUTES les suites (128 assertions, sans réseau)
# ou individuellement :
python tests/test_core.py      # cœur métier
python tests/test_extended.py  # couverture exhaustive (réseau simulé)
```

Les tests couvrent config, fetcher (robots/cache/retry/403/panne), parsing,
analyse, tendances, SEO, prompts, rapports, historique, conversion de devises,
les connecteurs API (succès + erreurs simulés) et le pipeline complet — sans
aucun accès réseau réel.

Les rapports sont écrits dans **`~/Downloads/reports/JJ-MM-AAAA/`** (un dossier
par jour, dans ton dossier Téléchargements ; chemin réglable via
`output.reports_dir` dans `config.yaml`). Les logs vont dans `logs/run_AAAA-MM-JJ.log`
(format ISO en interne).

### Première utilisation — checklist

1. Ouvre **`config.yaml`** et vérifie le bloc `shop` (tes propres chiffres).
2. Les concurrents de départ sont des **placeholders à remplacer** (`EXAMPLE_*`).
   Lance `python main.py --discover` depuis ta machine (réseau ouvert) pour
   récupérer des slugs réels, puis ajoute-les dans `config.yaml`.
3. Lance `python main.py` et lis les 3 rapports du jour.

---

## Configuration (`config.yaml`)

Tout est paramétrable **sans toucher au code** :

| Section | À quoi ça sert |
|---------|----------------|
| `shop` | Tes propres chiffres (référentiel de comparaison). |
| `niche.pillars` | Mots-clés socle de la niche. |
| `niche.emerging_subniches` | Sous-niches montantes à privilégier. |
| `niche.saturated_topics` | Sujets à **éviter** dans les prompts. |
| `competitors` | Boutiques à suivre (slug + marché). |
| `discovery` | Requêtes de recherche pour découvrir des concurrents. |
| `revenue_estimation` | Hypothèses de l'estimation de CA. |
| `ai_inference` | Pondérations de l'heuristique « probablement IA ». |
| `network` | Rate limiting, retries, user-agent, cache, robots.txt. |
| `grok_prompts` | Palette, styles, formes, nombre de prompts/jour. |
| `goals` | Objectif de revenu, budget pub. |

---

## Planifier un lancement quotidien (macOS, automatique)

Un script tout prêt installe le lancement automatique **chaque jour** (heure
locale du Mac) via `launchd`. Il génère les rapports **et** les designs (24
images). À lancer **une seule fois** — l'heure est réglable en argument :

```bash
cd ~/Bot-AI
bash automation/install_daily.sh       # 5h00 (défaut) ; `... 7` -> 7h00 ; `... 5 30` -> 5h30
```

### Conditions de déclenchement (à lire — important)
`launchd` lance le job à l'heure prévue **uniquement si** :
- le Mac est **allumé** (PAS éteint) ;
- ta **session est ouverte** (écran **verrouillé = OK**, mais pas déconnecté) ;
- le Mac est **éveillé** (PAS en veille) à cet instant.

| État du Mac à l'heure prévue | Résultat |
|------------------------------|----------|
| Allumé + session ouverte + éveillé (même verrouillé) | ✅ se déclenche à l'heure |
| Allumé + en **veille** | ⏳ se déclenche **au réveil** (pas à l'heure) |
| **Éteint** | ❌ rien ; se déclenchera au prochain démarrage + login |

> ⚠️ **`launchd` ne réveille ni n'allume le Mac.** Sur les Mac **Apple Silicon**
> (M1/M2/M3/M4), le réveil/allumage programmé (`pmset schedule/repeat wake`) n'est
> **plus supporté** par Apple. Pour que ça se déclenche pile à l'heure, la méthode
> fiable = **laisser le Mac allumé, branché, et l'empêcher de dormir** :
> ```bash
> sudo pmset -c disablesleep 1     # plus de veille quand branché (annuler : ... 0)
> ```
> Le Mac peut rester **verrouillé** (écran éteint), ça fonctionne quand même.
> Vérifie ta puce : `uname -m` (`arm64` = Apple Silicon, `x86_64` = Intel).

- ⚠️ Heure = **locale du Mac** : pour « heure française », mets le fuseau
  **Europe/Paris** (Réglages > Général > Date et heure).
- Logs : `logs/launchd.out.log` + `logs/grok.out.log`.

### Vérifier que c'est bien armé
```bash
launchctl list | grep neutralwall                 # doit afficher une ligne
launchctl print gui/$(id -u)/com.neutralwalldesign.marketintel | grep -A3 -i calendar
```

### Tester sans attendre
```bash
bash automation/run_daily.sh          # lance tout de suite le run complet
```

Désactiver l'automatisation :
```bash
bash automation/uninstall_daily.sh
```

---

## Respect des CGU et éthique

- Respect de **robots.txt** (ne pas désactiver dans la config).
- **Rate limiting** strict + jitter entre requêtes.
- **User-agent honnête** et identifiable (personnalise l'email dans `config.yaml`).
- **Aucun contournement** de protection : si Etsy renvoie 403/bloque, l'outil
  s'abstient, note l'échec et dégrade gracieusement (cache ou « indisponible »).

---

## Structure du projet

```
Bot-AI/
├── main.py                  # orchestrateur CLI
├── config.yaml              # toute la configuration
├── requirements.txt
├── README.md / DECISIONS.md / LIMITS.md
├── src/
│   ├── config_loader.py     # chargement + validation config
│   ├── fetcher.py           # HTTP respectueux (robots, rate limit, cache, retries)
│   ├── etsy_parser.py       # parsing des pages boutiques -> ShopData
│   ├── analysis.py          # estimation CA, inférence IA, comparaison
│   ├── trends.py            # Google Trends (optionnel, dégrade)
│   ├── seo.py               # opportunités SEO
│   ├── prompt_generator.py  # 5 prompts Grok/jour
│   ├── report_generator.py  # rendu des 3 rapports markdown
│   ├── demo_fixtures.py     # données FICTIVES pour --demo
│   └── utils.py             # logging, dates, marqueurs de fiabilité
│   (sorties -> ~/Downloads/reports/JJ-MM-AAAA/ par défaut)
├── cache/                   # cache HTTP (gitignored)
└── logs/                    # logs de run (gitignored)
```

---

## Limites connues

Voir **[`LIMITS.md`](LIMITS.md)** (lecture obligatoire) et **[`DECISIONS.md`](DECISIONS.md)**
pour les choix d'architecture et les contraintes rencontrées.
