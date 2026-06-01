# NeutralWallDesign — Outil d'intelligence marché Etsy

Outil Python (CLI + rapports markdown) qui, lancé quotidiennement, produit
trois livrables pour piloter la boutique Etsy **NeutralWallDesign** (wall art
printable, niche « Warm Organic Minimalism ») :

1. **`veille_concurrents.md`** — veille concurrentielle : ventes publiques,
   fiches, avis, prix, **CA estimé (calcul transparent)**, inférence
   « probablement IA », et pour chaque concurrent « 3 choses qu'ils font mieux
   + 1 faille exploitable ».
2. **`prompts_grok_du_jour.md`** — 5 prompts Grok prêts à copier-coller, ciblant
   des demandes confirmées, au format « formes pleines / solid filled / no
   outline » imposé.
3. **`guidelines_claude_chat.md`** — brief stratégique (SEO, Pinterest, pricing,
   pub, roadmap 5000 €/mois) destiné à un assistant en chat.

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

---

## Utilisation

```bash
python main.py                 # run complet (récupère les concurrents live)
python main.py --discover      # + découverte de nouveaux concurrents via recherche
python main.py --no-network    # mode hors-ligne (rapports dégradés, aucune requête)
python main.py --demo          # rapport de DÉMONSTRATION avec données FICTIVES
python main.py --verbose       # logs détaillés (utile pour diagnostiquer)
```

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

## Planifier un lancement quotidien

### macOS (recommandé : `launchd`)

Crée `~/Library/LaunchAgents/com.neutralwall.marketintel.plist` :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.neutralwall.marketintel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/CHEMIN/VERS/Bot-AI/.venv/bin/python</string>
    <string>/CHEMIN/VERS/Bot-AI/main.py</string>
  </array>
  <key>WorkingDirectory</key><string>/CHEMIN/VERS/Bot-AI</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/CHEMIN/VERS/Bot-AI/logs/launchd.out.log</string>
  <key>StandardErrorPath</key><string>/CHEMIN/VERS/Bot-AI/logs/launchd.err.log</string>
</dict>
</plist>
```

Puis :

```bash
launchctl load ~/Library/LaunchAgents/com.neutralwall.marketintel.plist
```

### Linux / macOS (alternative : `cron`)

```bash
crontab -e
# Tous les jours à 8h00 :
0 8 * * * cd /CHEMIN/VERS/Bot-AI && .venv/bin/python main.py >> logs/cron.log 2>&1
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
