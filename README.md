# Bot-AI — Quiet Capital · Faceless YouTube Channel Kit

Kit complet pour lancer **Quiet Capital**, une chaîne YouTube faceless (marché US/UK) sur la finance, le luxe et les montres. Décision, scripts, visuels et planning — tout est prêt à exécuter.

## 📂 Sommaire

| Fichier | Contenu |
|---------|---------|
| [`youtube-niche-analysis-2026.md`](youtube-niche-analysis-2026.md) | Analyse des niches : top 5 CPM, fit, gap concurrentiel, revenus à 1K/10K/100K, classement |
| [`launch-kit-quiet-capital.md`](launch-kit-quiet-capital.md) | Plateforme, concept, nom de chaîne, workflow, calendrier de monétisation |
| [`content/01-shorts-scripts.md`](content/01-shorts-scripts.md) | 10 scripts Shorts complets (prêts ElevenLabs) |
| [`content/02-longform-01-rolex.md`](content/02-longform-01-rolex.md) | Long-form #1 — Why Rolex Makes You Wait Years |
| [`content/03-grok-prompts.md`](content/03-grok-prompts.md) | Tous les prompts Grok Imagine + identité visuelle |
| [`content/04-publishing-calendar-30days.md`](content/04-publishing-calendar-30days.md) | Planning de publication 30 jours |
| [`content/05-longform-02-debt.md`](content/05-longform-02-debt.md) | Long-form #2 — How the Rich Use Debt (Buy, Borrow, Die) |
| [`content/06-longform-03-patek.md`](content/06-longform-03-patek.md) | Long-form #3 — Is a Patek Philippe an Investment? |
| [`content/07-longform-04-salary.md`](content/07-longform-04-salary.md) | Long-form #4 — Why Your Salary Will Never Make You Rich |
| [`content/08-shorts-metadata.md`](content/08-shorts-metadata.md) | Titres, descriptions et hashtags des 10 Shorts |
| [`content/09-thumbnail-concepts.md`](content/09-thumbnail-concepts.md) | Concepts de miniatures pour les long-forms |
| [`bot/`](bot/) | 🤖 **Bot de production** : script → voix → visuels → montage → MP4 prêt (voir [bot/README.md](bot/README.md)) |

## 🚀 Par où commencer
1. Crée la chaîne **Quiet Capital** + logo (prompt Grok dans `03`)
2. Produis 7 Shorts d'avance : script (`01`) → voix ElevenLabs → visuels Grok (`03`) → montage CapCut
3. Suis le planning 30 jours (`04`) : 1 Short/jour + 1 long-form/dimanche
4. Vise le palier early-access (500 abos / 3M vues Shorts), puis monétisation complète (1000 abos + 4000h)

## 🤖 Automatisation (dossier `bot/`)
Un bot Python transforme tes scripts en vidéos prêtes à publier en une commande :
```bash
pip install -r bot/requirements.txt   # + ffmpeg + clés dans bot/.env
python bot/pipeline.py make 1          # -> bot/output/short1/short1.mp4 + metadata.txt
```
Coût ~$0.15–0.45/Short. Tu revois 30 s et tu publies (contrôle humain = conforme à la politique YouTube 2026). Détails : [`bot/README.md`](bot/README.md).

## ⚙️ Stack outils
Scripts : Claude · Voix : ElevenLabs (API) · Visuels : Grok Imagine (API ou manuel) · Montage : bot ffmpeg (ou CapCut) · Miniatures : Canva/CapCut

> ⚠️ Conformité YouTube 2026 : coche "contenu IA" à chaque upload, ajoute de la vraie valeur, pas de contenu répétitif "set-and-forget". Tout le contenu finance est de l'éducation/divertissement — *not financial advice*.
