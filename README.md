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

Les rapports sont écrits dans **`reports/AAAA-MM-JJ/`** (un dossier par jour).
Les logs vont dans `logs/run_AAAA-MM-JJ.log`.

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

Un script tout prêt installe le lancement automatique **chaque jour à 7h00**
(heure locale du Mac) via `launchd`. À lancer **une seule fois** :

```bash
cd ~/Bot-AI
bash automation/install_daily.sh
```

- L'outil se lancera seul tous les matins, générera les rapports du jour et
  ouvrira le dossier (si une session graphique est active).
- Si le Mac est en veille à 7h, le run se fait au réveil.
- ⚠️ L'heure est l'heure **locale du Mac** : pour « 7h heure française », assure-toi
  que ton Mac est sur le fuseau **Europe/Paris** (Réglages > Général > Date et heure).
- Logs : `logs/launchd.out.log`.

Tester immédiatement sans attendre 7h :
```bash
bash automation/run_daily.sh
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
├── reports/AAAA-MM-JJ/      # sorties quotidiennes
├── cache/                   # cache HTTP (gitignored)
└── logs/                    # logs de run (gitignored)
```

---

## Limites connues

Voir **[`LIMITS.md`](LIMITS.md)** (lecture obligatoire) et **[`DECISIONS.md`](DECISIONS.md)**
pour les choix d'architecture et les contraintes rencontrées.
