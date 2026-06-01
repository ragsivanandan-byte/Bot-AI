# DECISIONS.md — Décisions d'architecture, contraintes et récapitulatif

Document tenu en autonomie totale (l'opérateur n'était pas disponible). Il
contient : (A) le plan d'architecture, (B) les décisions prises seul + pourquoi,
(C) les contraintes/limites rencontrées, (D) le récapitulatif final.

---

## A. Plan d'architecture (décidé en début de session)

**Objectif** : un outil Python modulaire, robuste, honnête, lancé quotidiennement,
produisant 3 rapports markdown.

**Pipeline retenu** (`main.py`) :
`config → (découverte) → fetch concurrents → parse → analyse (CA/IA/comparaison)
→ tendances → opportunités SEO → prompts Grok → rendu des 3 rapports`.

**Découpage en modules** (un fichier = une responsabilité) :
| Module | Responsabilité |
|--------|----------------|
| `config_loader.py` | charge + valide `config.yaml`, applique des défauts |
| `fetcher.py` | HTTP respectueux : robots.txt, rate limit, retries, cache |
| `etsy_parser.py` | HTML → `ShopData` (défensif, champ absent = `None`) |
| `analysis.py` | estimation CA, inférence IA, comparaison/classement |
| `trends.py` | Google Trends optionnel (dégrade si absent/bloqué) |
| `seo.py` | opportunités SEO croisant config + tendances |
| `prompt_generator.py` | 5 prompts Grok/jour, déterministes par date |
| `report_generator.py` | rendu markdown des 3 livrables |
| `demo_fixtures.py` | données fictives labellisées pour `--demo` |
| `utils.py` | logging, dates, marqueurs de fiabilité |

**Principe directeur** : *robustesse > exhaustivité*. Aucune source ne doit
pouvoir crasher le run ; chaque échec dégrade gracieusement et est documenté
dans le rapport.

---

## B. Décisions prises seul (et pourquoi)

1. **Séparation stricte vérifié / estimé / inféré / indisponible.**
   Trois marqueurs centralisés dans `utils.py` (`ESTIMATION`, `INFÉRENCE`,
   `donnée indisponible`) propagés partout. Respecte les règles anti-hallucination.

2. **Estimation de CA = fourchette avec calcul affiché**, jamais un chiffre sec.
   Si les ventes publiques manquent → `available=False` (on ne devine pas).
   Choix d'hypothèses conservatrices et explicitées dans `config.yaml`.

3. **Heuristique IA = score pondéré + liste des signaux**, seuil configurable.
   Toujours étiquetée « INFÉRENCE, non confirmée ». Évite l'accusation gratuite.

4. **Respect CGU non négociable.** robots.txt respecté, pas de retry sur 403
   (on respecte le refus), rate limit + jitter, user-agent honnête avec contact.
   Décision : **ne jamais contourner** un blocage, quitte à dégrader.

5. **Concurrents de départ = placeholders explicites** (`EXAMPLE_*`).
   Je ne pouvais pas vérifier de vrais slugs (Etsy bloqué dans l'environnement,
   cf. section C). Plutôt que d'**inventer des noms de boutiques** (violation des
   règles anti-hallucination), j'ai mis des placeholders + un mode `--discover`
   qui récupérera de vrais slugs au premier run live sur la machine de l'opérateur.

6. **Mode `--demo` avec données 100 % fictives et labellisées.**
   Comme l'accès live est bloqué ici, le run réel ne produit que de
   l'« indisponible ». Pour que l'opérateur **voie les moteurs d'analyse à
   l'œuvre** (estimation CA, inférence IA, comparaison), j'ai ajouté un jeu de
   données synthétiques (`demo_fixtures.py`) avec un bandeau « DONNÉES FICTIVES »
   en tête de rapport. Décision assumée : utilité pédagogique > risque, car le
   caractère fictif est martelé.

7. **Prompts Grok déterministes par date** (`random.Random(date.toordinal())`).
   Reproductibles le même jour, mais rotation jour après jour. Priorité aux
   sous-niches montantes non saturées.

8. **`pytrends` en dépendance optionnelle.** S'il manque ou est bloqué, le module
   dégrade (« à valider ») au lieu de planter. Évite une dépendance dure à un
   service instable.

9. **Mes propres chiffres de boutique non auto-scrapés.** Renseignés dans
   `config.yaml` pour éviter une donnée périmée/erronée ; l'opérateur les met à jour.

---

## C. Contraintes / limites rencontrées pendant le build

- **🔌 Etsy bloque l'accès automatisé dans l'environnement de build (HTTP 403,
  « Host not in allowlist »).** La politique réseau de l'environnement
  d'exécution distant n'autorise pas `etsy.com`. Conséquence : impossible de
  récupérer de vraies données Etsy ici. Le run réel est donc en **mode dégradé**
  (tout « indisponible »).
- **Google Trends également bloqué** (403) dans cet environnement, et `pytrends`
  n'y est pas installé → module Trends en mode dégradé.
- **PyPI accessible** : `beautifulsoup4` + `lxml` ont pu être installés.
- ➡️ Ces blocages sont **propres à l'environnement de build**, pas à l'outil.
  Sur la machine de l'opérateur (réseau résidentiel), `python main.py` tentera
  de vraies requêtes — sans garantie, Etsy pouvant aussi bloquer selon le contexte.

---

## D. Récapitulatif final

### ✅ Ce qui marche (vérifié)
- `python main.py` tourne **de bout en bout sans crash**, y compris quand toutes
  les sources externes échouent (mode dégradé propre).
- Chargement + validation de `config.yaml` ; tout est paramétrable sans code.
- Fetcher respectueux : robots.txt, rate limit + jitter, retries 2/4/8/16 s,
  cache disque TTL, pas de contournement (vérifié : 403 Etsy → abstention + log).
- Parser défensif : champ absent = `None` (jamais inventé).
- Moteurs d'analyse opérationnels (vérifié via `--demo`) : estimation CA avec
  calcul transparent, inférence IA avec signaux détaillés, comparaison « 3 forces
  / 1 faille », classement par ventes.
- Génération des 5 prompts Grok au format imposé (solid filled / no outline /
  negative prompt), ciblant les sous-niches non saturées.
- Rendu des 3 rapports markdown horodatés dans `reports/AAAA-MM-JJ/`.
- **Historisation SQLite + diffs** (`storage.py`) : section « Évolution depuis le
  dernier run » dans la veille (Δ ventes/fiches/avis/prix). Vérifié par tests.
- **Diagnostic `--selftest`** : vérifie config, moteurs, historique, pytrends, et
  l'accès live Etsy/Trends — pour savoir en 5 s ce qui marche sur une machine.
- **Suite de tests** (`tests/test_core.py`, 24 assertions, sans réseau ni pytest) :
  config, estimation CA, inférence IA, structure des prompts, parsing HTML
  défensif, historisation/diffs. **Toutes passent.** Le test de parsing valide
  l'extraction sur du HTML réaliste (donc l'extraction marchera en live si Etsy
  est joignable).
- Documentation complète : README, LIMITS, ce fichier, requirements, config commentée.

### 🔌 Ce qui est dégradé (à cause de l'environnement, pas du code)
- Données concurrents **réelles** : indisponibles ici (Etsy 403). Le rapport
  d'exemple « réel » est donc en mode dégradé ; un rapport `--demo` populé est
  également fourni pour montrer l'analyse.
- Tendances Google : indisponibles ici (Trends 403 + pytrends absent).

### 🖐️ Ce que l'opérateur doit faire à la main
1. Installer `pip install -r requirements.txt` (dont `pytrends`) sur sa machine.
2. Remplacer les concurrents `EXAMPLE_*` par de vrais slugs (`--discover` aide).
3. Tenir à jour le bloc `shop` de `config.yaml`.
4. Consulter manuellement Pinterest Trends + eRank (pas d'API gratuite fiable).
5. Personnaliser l'email du `user_agent` dans `config.yaml`.

### 🔌 Connecteurs API ajoutés (sur demande de l'opérateur)
Décision : « ultra connecté » pour 10-20€/mois. J'ai construit deux connecteurs
**optionnels**, clé lue en variable d'environnement, **dégradation gracieuse
totale sans clé** (l'outil retombe sur le comportement HTML/Trends d'origine).
- **`etsy_api.py`** — API officielle Etsy v3 (GRATUITE). Priorité sur le scraping
  HTML quand `ETSY_API_KEY` est défini. Mappe ventes/fiches/avis/note/prix/devise
  vers `ShopData`. Path complet vérifié par test (réponse JSON simulée).
- **`keywords_api.py`** — Keywords Everywhere (payant, ~10-15€/mois). Volumes de
  recherche réels (proxy Google) injectés dans les opportunités SEO et les
  prompts quand `KEYWORDS_EVERYWHERE_API_KEY` est défini.
- Choix : ces deux-là car ce sont les **seules sources de qualité dotées d'une
  API officielle** dans le budget. eRank/Marmalead/Alura/Everbee n'ont pas d'API
  publique -> les automatiser violerait leurs CGU, donc exclus (restent manuels).
- Honnêteté ajoutée dans LIMITS.md : prix Etsy en devise réelle non convertie ;
  volumes KWE d'origine Google, pas Etsy ; crédits KWE consommés à chaque appel.

### 🧪 Audit exhaustif (sur demande de l'opérateur)
- Suite de tests portée à **128 assertions** (`tests/run_all.py` agrège
  `test_core.py` + `test_extended.py`), exécutées dans un **virtualenv neuf**
  reproduisant exactement le poste Mac (`pip install -r requirements.txt`).
- Couverture des chemins **succès ET échec** via doublures réseau
  (`tests/_fakes.py`) : robots.txt, cache, retry 5xx, 403 sans retry, pannes
  réseau, 401/402 des API, fetch de taux de change, pipeline `main()` complet
  avec connecteurs simulés.
- **Bug réel trouvé et corrigé pendant l'audit** : une liste `styles` vide dans
  `config.yaml` provoquait une division par zéro dans le générateur de prompts.
  Corrigé (repli sur un style par défaut) + test de non-régression ajouté.
- `pyflakes` : aucun import/variable inutilisé. Tous les modes CLI sortent en 0,
  y compris le scénario « clé API présente mais réseau injoignable » (dégradation
  propre, sans traceback).

### 🚀 Prochaines améliorations possibles
1. **Conversion de devises** : faite (`currency.py`). Reste : élargir la table de
   repli et ajouter une 2e source de taux en secours.
2. **Rendu HTML/PDF + envoi par e-mail** du rapport quotidien (lecture mobile).
3. **Graphe d'évolution** : à partir des snapshots SQLite, tracer la courbe des
   ventes/avis des top concurrents et de ma propre boutique (AOV, nb d'avis).
