# LIMITS.md — Ce que cet outil NE PEUT PAS faire (lecture obligatoire)

Honnêteté brutale, comme demandé. Lis ceci avant de prendre une décision sur la
base des rapports.

## 1. Le CA réel des boutiques n'est PAS accessible
- Etsy **ne publie pas** le chiffre d'affaires des boutiques.
- L'outil **estime** un CA = `ventes_publiques × prix_moyen × part_des_ventes_sur_30j`.
- Les ventes publiques sont un **cumul depuis l'ouverture** (lifetime), pas un
  rythme mensuel. La conversion en run-rate mensuel repose sur une **hypothèse
  grossière** (2-8 % des ventes sur 30 j) → **marge d'erreur énorme**.
- ➡️ Traite tout CA comme un **ordre de grandeur**, jamais un chiffre fiable.

## 2. La détection « boutique 100 % IA » est impossible avec certitude
- Aucune méthode publique ne prouve qu'une boutique est générée par IA.
- L'outil produit une **inférence** (faisceau d'indices : prix bas, catalogue
  massif, titres empilés…) marquée « INFÉRENCE, non confirmée ».
- ➡️ Un faux positif est possible (un humain prolifique). Ne diffame personne.

## 3. Pas de vrais volumes de recherche
- Les volumes de recherche Etsy/Google **exacts** ne sont pas publics sans outil
  payant (eRank, Marmalead, Keyword Planner avec budget).
- Google Trends (si `pytrends` installé et accessible) donne un **intérêt
  relatif (0-100)**, PAS un volume absolu.
- ➡️ « Volume estimé » dans les prompts = intérêt relatif ou « à valider ».
  Croise toujours avec eRank avant d'investir du temps de production.

## 4. Accès Etsy = dépendant de l'environnement
- Etsy peut renvoyer **403 / bloquer** l'accès automatisé (c'est le cas dans
  l'environnement de build de cet outil → rapports en **mode dégradé**).
- L'outil **respecte robots.txt et ne contourne rien**. S'il est bloqué, il le
  note et marque les données « indisponible ».
- ➡️ Lance l'outil **depuis ta machine** (réseau résidentiel) pour de
  meilleures chances de récupérer les pages publiques. Même là, le succès n'est
  pas garanti et peut varier dans le temps.

## 5. Le parsing dépend de la structure HTML d'Etsy
- Etsy change régulièrement son HTML. Les sélecteurs/regex de `etsy_parser.py`
  peuvent **cesser de fonctionner** sans préavis (un champ tombe à « indisponible »).
- ➡️ Si plusieurs champs passent « indisponible » en mode live, c'est
  probablement un changement de structure : il faut ajuster `etsy_parser.py`.

## 6. Données à renseigner / valider à la main
- Tes propres chiffres de boutique (`config.yaml > shop`) ne sont pas
  auto-scrapés (pour éviter une donnée périmée) — **tiens-les à jour**.
- Les concurrents de départ sont des **placeholders** (`EXAMPLE_*`) à remplacer.
- **Pinterest Trends**, **eRank**, le détail des **sections/ratios** d'un
  concurrent : à consulter manuellement (pas d'API gratuite fiable ici).

## 6bis. Précisions sur les connecteurs API (si tu les actives)
- **Conversion en EUR** : les prix de l'API Etsy (devise de la boutique) sont
  désormais **convertis automatiquement en EUR**. Taux récupérés via une source
  gratuite (BCE/Frankfurter), mis en cache 24 h. Si le réseau est indisponible,
  l'outil utilise une **table de repli statique APPROXIMATIVE et datée** (≈ janv.
  2026) — la conversion est alors un ordre de grandeur, pas un taux du jour. La
  devise et le prix d'origine restent affichés entre crochets pour transparence.
- ⚠️ Les prix récupérés par **scraping HTML** (mode sans clé API) ne sont PAS
  convertis de façon fiable : la devise n'y est pas toujours identifiable. La
  conversion en EUR est garantie surtout via l'**API Etsy** (devise connue).
- **API Etsy** : nécessite une clé validée par Etsy, soumise à des quotas
  (≈ 10 req/s, 10 000 req/jour). Sur de longues listes de concurrents, le run
  prend plus de temps.
- **Keywords Everywhere** : les volumes sont d'origine **Google**, pas Etsy. Ils
  approchent l'intention de recherche mais ne sont **pas** le volume Etsy exact.
  Le seul volume Etsy « officieux » reste celui d'eRank/Marmalead, sans API
  (consultation manuelle). Chaque appel **consomme des crédits payants**.

## 7. Ce que l'outil ne fait pas (volontairement)
- Il ne crée pas d'images (il génère des **prompts** pour Grok, à toi de lancer).
- Il ne publie rien sur Etsy/Pinterest.
- Il ne garantit aucun revenu : la roadmap 5000 €/mois est un **scénario**, pas
  une promesse (compter typiquement **12-36 mois** en printables).

## En résumé
Cet outil est un **assistant de décision honnête**, pas un oracle. Il sépare
clairement le **vérifié** (ventes publiques, nb fiches, avis quand lisibles) de
l'**estimé** (CA), de l'**inféré** (profil IA) et de l'**indisponible**. Utilise-le
comme un point de départ d'analyse, pas comme une source de vérité absolue.
