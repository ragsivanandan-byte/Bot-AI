# STRC DCA Simulator — Closing-Price Edition

Reproduction en local (terminal Mac) du **« STRC Mode »** du
[Bitcoin Intelligence Report](https://btcintelligencereport.com/portfolio) —
avec **une modification** :

> L'outil d'origine fait :
> **« Weekly DCA deploys into STRC at $100 par. »**
> (chaque DCA hebdomadaire achète STRC au **par de 100 $**, traité comme stable).

> **Cette version** utilise à la place le **closing price hebdomadaire RÉEL de
> STRC** depuis son lancement (IPO réglée le 29/07/2025, première cotation
> Nasdaq ~30/07/2025). La **perte (ou le gain) de valeur en capital** par
> rapport au par 100 $ est donc désormais **intégrée**, et toutes les autres
> métriques sont **recalculées** au closing réel.

## Pourquoi c'est important

STRC est conçu pour rester proche de 100 $ via un dividende variable mensuel,
mais ça n'a pas tenu :

- ATH **100,42 $** le 13/01/2026
- puis chute sous le par → plus-bas record **82,53 $** le 18/06/2026
  (Strategy a vendu du BTC pour financer les dividendes, ATM suspendu car
  cotation sous le par).

L'hypothèse « 100 $ par » de l'outil d'origine **surestime** donc le
portefeuille et **masque** la perte en capital. Cette version la montre.

## Lancer sur votre Mac

Aucune installation : Python 3 (livré avec macOS) suffit, **zéro dépendance**.

```bash
cd Bot-AI

# DCA de 1000 $/semaine depuis le lancement de STRC (données LIVE)
python3 strc_dca.py --weekly-amount 1000

# Avec réinvestissement des dividendes (DRIP)
python3 strc_dca.py --weekly-amount 1000 --reinvest-dividends

# Comparer au même DCA déployé en Bitcoin
python3 strc_dca.py --weekly-amount 1000 --btc-benchmark

# Sortie JSON (pour scripts) / export CSV semaine par semaine
python3 strc_dca.py --json
python3 strc_dca.py --csv-out historique_strc.csv
```

Par défaut l'outil récupère **en direct** les closing prices hebdo réels de
STRC depuis **Yahoo Finance** (fallback **Stooq**). Si vous êtes hors-ligne,
ajoutez `--no-live` pour utiliser le snapshot embarqué.

> ⚠ Le snapshot `data/strc_weekly_closes.csv` n'est qu'un **fallback
> approximatif** (quelques points vérifiés + interpolation). Pour des chiffres
> exacts, lancez **sans** `--no-live` sur votre Mac : la série hebdo complète et
> exacte est alors téléchargée.

## Ce que l'outil calcule

Pour chaque semaine depuis le lancement, il déploie le montant DCA et compare
deux modes côte à côte :

| | **Mode Par (100 $)** | **Mode Closing (réel)** |
|---|---|---|
| Prix d'achat | 100 $ fixe | closing hebdo réel |
| Valorisation | 100 $ (stable) | dernier closing réel |
| Perte/gain en capital | toujours 0 | **intégré** |

Métriques recalculées : total investi, actions STRC accumulées, coût moyen,
valeur de marché, **+/- value en capital**, dividendes perçus (rendement
variable, réinvestis ou non), yield on cost, valeur totale et P/L total —
plus l'**impact de la modification** (actions supplémentaires acquises sous le
par, écart de valeur, perte en capital intégrée).

## Options principales

| Option | Effet |
|---|---|
| `--weekly-amount N` | Montant DCA hebdomadaire en USD (défaut 1000) |
| `--start / --end` | Bornes de période (YYYY-MM-DD) |
| `--reinvest-dividends` | Réinvestir les dividendes (DRIP) |
| `--no-dividends` | Ignorer le rendement de STRC |
| `--apy 0.115` | Rendement annualisé de repli (si pas de calendrier) |
| `--btc-benchmark` | Comparer au même DCA déployé en BTC |
| `--no-live` | Mode hors-ligne (snapshot embarqué) |
| `--json` / `--csv-out F` | Sorties machine / export CSV |

## Données

- `data/strc_weekly_closes.csv` — snapshot de secours (closes hebdo).
- `data/strc_dividends.csv` — calendrier de dividendes mensuels variables
  (montants approximatifs ; remplaçables par les montants déclarés exacts
  depuis <https://www.strategy.com/strc/dividends>).

Les dividendes des préférentielles sont calculés sur le **par 100 $**,
indépendamment du prix d'achat.

## Site web en ligne (GitHub Pages)

En plus du terminal, l'outil est disponible comme **site interactif**
(dossier `docs/`). Le navigateur ne pouvant pas interroger Yahoo (CORS), une
**GitHub Action** (`.github/workflows/pages.yml`) exécute le script Python,
récupère les vrais closing prices STRC, écrit `docs/data/strc.json` et déploie
le site. Tous les calculs sont ensuite refaits **côté navigateur** (Mode Par vs
Mode Closing, KPIs, tableau, graphiques) — instantané et interactif.

### Activer le site (une seule fois)

1. Poussez la branche sur GitHub (déjà fait).
2. Dépôt → **Settings → Pages → Build and deployment → Source : « GitHub Actions »**.
3. L'Action se déclenche au push, chaque lundi, ou via **Run workflow**.
   > Note : les exécutions programmées (`schedule`) ne tournent que sur la
   > branche par défaut — fusionnez sur `main` pour le rafraîchissement hebdo
   > automatique.
4. L'URL publique sera du type `https://ragsivanandan-byte.github.io/bot-ai/`.

### Prévisualiser en local sur votre Mac

```bash
python3 build_web_data.py        # génère docs/data/strc.json (données live)
cd docs && python3 -m http.server 8000
# puis ouvrez http://localhost:8000
```

### Tests du site

```bash
node test_web_parity.mjs   # le JS donne EXACTEMENT les mêmes chiffres que Python
node test_web_render.mjs   # app.js s'exécute et peuple l'UI sans erreur
```

## Avertissement

Outil pédagogique / d'analyse. Les chiffres dépendent des données de marché
récupérées et des hypothèses de dividende. Ce n'est pas un conseil en
investissement.
