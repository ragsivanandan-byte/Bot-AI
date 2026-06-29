# 🧠 MEMORY — Quiet Capital (contexte permanent du projet)

> **À TOUTE IA QUI OUVRE CE REPO (Claude, Cowork, autre) :** lis ce fichier EN ENTIER
> avant d'agir. Il contient tout le contexte, les décisions et la stratégie. Tu n'as
> jamais besoin de redemander au propriétaire ce qui est écrit ici. Mets ce fichier à
> jour (section "Journal") à la fin de chaque session de travail, puis commit.
>
> **Dernière mise à jour : 2026-06-29.**

---

## 1. Propriétaire & objectif
- Profil : 30 ans, intérêts = finance, crypto, luxe, montres, voyages. Email : r.sivanandan@me.com.
- Basé en zone francophone (Suisse probable), **communique en français**.
- **Objectif ultime : des milliers d'€/mois** via une chaîne YouTube **faceless**.
- Vérité cadrée (rappeler si besoin) : aucun bot ne *garantit* ce revenu ; il dépend des
  vues + régularité + marché. Le bot maximise les chances et démultiplie la production.

## 2. La chaîne
- **Nom : Quiet Capital** — *money, luxury, and the quiet logic of wealth.*
- **Marché : ANGLAIS (US/UK)** — choix assumé (RPM bien plus élevé qu'en FR).
- Faceless. Voix off IA (ElevenLabs "Brian"). Visuels IA (Grok Imagine).
- Handle : `@QuietCapital-q1m` (le nom "Quiet Capital" prime).
- Niche : **finance + luxe/montres** (angle "le luxe vu par un cerveau finance").
- Compte Google perso (Ragavan) — invisible pour le public.

## 3. Stratégie (validée par recherche, juin 2026)
- **Shorts 1/jour** = moteur de **croissance** + entonnoir. (Pub quasi nulle.)
- **Long-form 1-2/sem** = moteur de **REVENU** (RPM finance $10-25 ≈ 100× les Shorts).
- **Affiliation** (liens) + **sponsors** (dès ~10k abos) = le gros du revenu réel.
- Durées : Shorts 1-2 = ~20-30s (déjà publiés) ; **Shorts 3-10 = 45-60s** (choix du proprio).
  ⚠️ Note honnête : les experts (Jenny Hoyos ~34s) penchent plus court ; à A/B tester.
- Monétisation YouTube : palier early-access 500 abos / 3M vues Shorts 90j ; complet
  1000 abos + 4000h OU 10M vues Shorts 90j.

## 4. Le BOT (dossier `bot/`) — ce qu'il fait
Pipeline : **script → voix (ElevenLabs) → visuels (Grok/manuel) → montage (ffmpeg) → MP4 + métadonnées**.
- Commandes : `./bot/run.sh make N` (Short 9:16) · `./bot/run.sh make-long N` (long-form 16:9) · `./bot/run.sh list`.
- Sous-titres : **synchronisés sur la voix** (timestamps ElevenLabs), incrustés en PNG (Pillow) car le ffmpeg du Mac n'a pas libass. Position : bas (80% hauteur).
- Images : déposées dans `bot/assets/visuals/short<N>/` ou `long<N>/`, **triées par ordre de téléchargement** (pas besoin de renommer). Le bot recycle si peu d'images (max 6s/plan Shorts, 12s/plan long).
- Monétisation : `bot/links.txt` (copié de `.example`) → ajouté à chaque description. **Reporté à ~fin juillet 2026.**
- Upload YouTube : possible (`--upload`) mais **désactivé par défaut** (revue humaine = conforme politique IA 2026).
- 84 tests passent (`python3 bot/tests/test_pipeline.py`).
- **Le rendu vidéo se fait sur le Mac du proprio** (ffmpeg + clés API), pas dans le chat.

## 5. Workflow de production quotidien
1. (si je dis "j'ai poussé") `cd ~/Desktop/Bot-AI && git pull origin claude/youtube-niche-analysis-ztb6j0`
2. Générer 6-8 images Grok (prompts `content/03`, format 9:16), télécharger dans l'ordre
3. Déposer dans `bot/assets/visuals/short<N>/`
4. `./bot/run.sh make N` → MP4 + metadata dans `bot/output/short<N>/`
5. Publier sur YouTube : titre/desc depuis `metadata.txt`, **IA = Oui**, **enfants = Non**, langue **English**, **Public**.

## 6. Fichiers clés du repo
- `MEMORY.md` (ce fichier) · `ROADMAP.md` (journal + plan 30j)
- `youtube-niche-analysis-2026.md` · `launch-kit-quiet-capital.md`
- `content/01` scripts Shorts · `02/05/06/07` long-forms · `03` prompts Grok · `04` calendrier · `08` métadonnées Shorts · `09` miniatures · **`10` growth playbook (visibilité)**
- `bot/` : pipeline + steps + tests + setup/run

## 7. Branche git
- Tout est sur **`claude/youtube-niche-analysis-ztb6j0`** (PAS `main`, qui contient un autre projet crypto du proprio).

## 8. État actuel (au 2026-06-29)
- Chaîne créée. Bot opérationnel et éprouvé.
- **Shorts produits : #1 à #6.** Publiés : au moins #1, #2 (et #3-6 en stock/publication).
- Aucun long-form encore produit (à lancer cette semaine).
- Affiliation : pas encore (reportée ~fin juillet).

## 9. Décisions notées (log)
- 2026-06-29 : marché EN ; nom Quiet Capital ; Shorts 3-10 à 45-60s ; affiliation reportée
  ~1 mois ; sous-titres synchronisés + bas ; images triées par date de téléchargement ;
  bot étendu au long-form + bloc monétisation auto.

## 10. Prochaines étapes
- Court terme : publier 1 Short/jour depuis le stock + **observer les stats** (ROADMAP).
- Cette semaine : **1er long-form** (`make-long 1`) — vrai levier revenu.
- ~Fin juillet : bilan data + brancher **affiliation** (remplir `links.txt`) ; envisager sponsors.
- En continu : appliquer le **growth playbook** (`content/10`) pour maximiser les vues.

## 11. Protocole de mise à jour (pour l'IA)
À la fin de chaque session : ajouter une ligne datée au "Journal" ci-dessous + dans `ROADMAP.md`
(chiffres si fournis : vues, abos, rétention, meilleur Short), puis `git add -A && commit && push`.

### Journal
- 2026-06-29 — Mise en place complète (chaîne, bot, 6 Shorts, mémoire, growth playbook).
