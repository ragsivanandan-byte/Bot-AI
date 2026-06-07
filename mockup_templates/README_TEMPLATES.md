# Gabarits de mockups (compositing EXACT)

Mets ici des **images de pièces** (PNG/JPG) où l'emplacement du cadre est rempli
d'un **rectangle vert vif `#00FF00`** (couleur « chroma »). Le compositeur
(`automation/make_mockups.py`) détecte ce vert et y colle ton design **pixel pour
pixel** → le mockup montre EXACTEMENT le fichier vendu (aucune régénération).

## Comment créer un gabarit (une fois par scène)

**Option A — via Grok (recommandé)** : génère une scène avec un cadre vide dont
l'intérieur est un aplat vert. Exemple de prompt :
```
A cozy warm-neutral living room, a thin light-oak frame with a white mat hanging
on the wall above a beige linen sofa, soft daylight, minimalist styling. IMPORTANT:
the INSIDE of the frame (the artwork area) is a perfectly flat solid pure green
rectangle (#00FF00), evenly filled, no art, no texture. Photorealistic interior.
Save as a PNG.
```
Génère-en 3-4 (salon au-dessus du canapé, chambre, bureau, gros plan). Vérifie
que le **rectangle vert est bien plein et net**.

**Option B — tes propres photos** : prends une photo de cadre vide et peins un
aplat vert `#00FF00` à l'intérieur (Aperçu/Photopea).

## Conseils
- Le rectangle vert peut être légèrement **de biais** (perspective gérée).
- Évite tout autre vert vif dans l'image (ça fausserait la détection).
- 1er fichier (ordre alphabétique) = utilisé pour la **COVER**. Nomme-les par ex.
  `01_cover_sofa.png`, `02_bedroom.png`, `03_office.png`, `04_closeup.png`.

## Lancer
```bash
python automation/make_mockups.py ~/Downloads/<gagnant1>.png ~/Downloads/<gagnant2>.png ~/Downloads/<gagnant3>.png
```
→ mockups exacts écrits dans `~/Downloads` (`NWD_*_Cover.png`, `NWD_*_Mockup_02.png`…).
