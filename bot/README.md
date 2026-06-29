# 🤖 Quiet Capital — Bot de production faceless

Transforme un script déjà écrit (dans [`../content/`](../content/)) en **vidéo Short prête à publier**, automatiquement :

```
script  →  voix (ElevenLabs)  →  visuels (Grok Imagine / manuel)  →  montage (ffmpeg)  →  MP4 + métadonnées
```

**Objectif : passer de ~1h à ~5 min par vidéo.** Le bot fait 95 % ; toi tu revois 30 s et tu publies.

> ⚠️ **Pourquoi tu publies à la main (par défaut) ?** La politique YouTube de juillet 2026 démonétise le contenu IA "inauthentique" publié en masse sans contrôle. Garder un humain dans la boucle = la chaîne survit. L'upload auto existe (`--upload`) mais est désactivé par défaut.

---

## ⚡ Installation un-clic (une seule fois)

**macOS / Linux :**
```bash
./bot/setup.sh
```
**Windows (PowerShell) :**
```powershell
.\bot\setup.ps1
```

Le script fait TOUT : environnement Python isolé, dépendances, ffmpeg, fichier `.env`, et il te demande tes clés API à la fin :
- **ElevenLabs** (obligatoire) → elevenlabs.io > API Keys
- **xAI Grok** (optionnel) → console.x.ai > API Keys

> Installation manuelle possible si tu préfères : `pip install -r bot/requirements.txt`, installe ffmpeg, puis `cp bot/.env.example bot/.env`.

---

## 🚀 Utilisation quotidienne

```bash
./bot/run.sh list           # voir Shorts + long-form     (Windows: .\bot\run.ps1 list)
./bot/run.sh make 1         # produire le Short #1 (9:16)
./bot/run.sh make 1 2 3     # produire plusieurs d'un coup
./bot/run.sh make all       # produire les 10 Shorts

# LONG-FORM (16:9) — le moteur de revenu (RPM finance 100× les Shorts)
./bot/run.sh make-long 1    # produire le long-form #1 (8 min)
./bot/run.sh make-long all  # produire les 4 long-forms
```

**Long-form :** dépose 15-25 images dans `bot/assets/visuals/long<N>/` (le bot recycle si moins).
Sortie 16:9 dans `bot/output/long<N>/`. Sous-titres via YouTube auto-captions (son activé).

## 💸 Monétisation auto (liens d'affiliation)
```bash
cp bot/links.txt.example bot/links.txt   # puis mets TES liens dedans
```
Le contenu de `links.txt` est ajouté automatiquement à la description de **chaque** vidéo
(Shorts + long-form). C'est un de tes leviers de revenu directs.

Résultat dans `bot/output/short1/` :
- `short1.mp4` — la vidéo 9:16 finie (voix + visuels + sous-titres + zoom)
- `metadata.txt` — titre, description, hashtags à copier-coller

Tu revois le MP4, tu l'uploades depuis l'app YouTube (en cochant **"contenu IA"**), tu copies les métadonnées. Fini.

---

## 🎨 Les visuels : 2 modes

| Mode | Quand | Comment |
|------|-------|---------|
| **Auto (xAI)** | tu as mis `XAI_API_KEY` | le bot génère les images via l'API Grok ($0.02–0.07/image) |
| **Manuel (gratuit)** | pas de clé xAI | tu déposes tes images Grok Imagine dans `bot/assets/visuals/short<N>/` et le bot les utilise |

Le mode manuel est **prioritaire** : si le dossier contient des images, le bot les prend (utile si tu préfères choisir tes visuels à la main dans l'app Grok).

🎵 **Musique** (optionnelle) : dépose un `bot/assets/music.mp3` libre de droits, il sera mixé en fond à bas volume.

---

## 💰 Coût par Short
- Voix ElevenLabs : ~**$0.04**
- Visuels (si API xAI) : ~**$0.10–0.40** (5 images)
- **Total : ~$0.15–0.45 / Short** → ~**5–15 $/mois** pour 30 Shorts. (0 $ si tu fournis les visuels en manuel.)

---

## 📤 Upload automatique (optionnel, avancé)
```bash
pip install google-auth-oauthlib google-api-python-client
# Google Cloud Console : active "YouTube Data API v3", crée un OAuth Desktop,
# télécharge client_secret.json dans bot/
python bot/pipeline.py make 1 --upload    # met en ligne en PRIVÉ (tu passes en public après revue)
```

---

## 🗂️ Structure
```
bot/
  pipeline.py            # orchestrateur (le cerveau)
  steps/
    parse_content.py     # lit tes scripts -> données structurées
    voiceover.py         # ElevenLabs
    visuals.py           # xAI Grok Imagine + fallback manuel
    assemble.py          # montage ffmpeg (Ken Burns, sous-titres, musique)
    youtube_upload.py    # upload YouTube (optionnel)
  assets/
    visuals/short<N>/    # (mode manuel) tes images Grok ici
    music.mp3            # (optionnel) musique de fond
  output/short<N>/       # vidéos finies + métadonnées
  .env                   # tes clés (privé, jamais committé)
```
