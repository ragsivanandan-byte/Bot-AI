# Gabarits de mockups — compositing EXACT (toutes les recos Claude Chat)

Le compositeur (`automation/make_mockups.py`) insère **ton fichier exact** dans la
**zone verte** d'un gabarit → mockup pixel-pour-pixel (aucune régénération). Il ne
remplace **que les pixels verts** ; tout le reste du gabarit reste intact.

## Organisation par RATIO (important)
Range tes gabarits dans le sous-dossier du bon ratio — le compositeur choisit
automatiquement le bon dossier selon le **format du thème du jour** :
```
mockup_templates/
├── 2x3/    # sets portrait (recettes 2:3)
├── 3x1/    # panorama above-sofa
└── 16x9/   # Frame TV
```
(Si un sous-dossier est vide, il prend les gabarits à la racine.)

## Règles (mesurées par Claude Chat sur tes rendus)
- **Vert** : un aplat **plein et net** (le code gère même un vert « sale » type
  `RGB(9,187,13)`). **Pas d'autre vert vif** ailleurs dans la scène.
- **Résolution** : gabarits en **4K (3840×2160)** → mockups ≥ 2000 px côté court
  (exigence Etsy). Évite les gabarits 720p.
- **Le 1er fichier (ordre alphabétique) = la COVER** → nomme-les `01_...`, `02_...`.
- **Ratio du slot ≈ ratio du design** (sinon léger étirement). Pour Frame TV, le
  slot ≈ 16:9.

---

## 1) Gabarits PORTRAIT 2:3 (sets) — `mockup_templates/2x3/`
À coller **une commande à la fois** dans le terminal (Grok génère + enregistre) :
```bash
mkdir -p ~/Bot-AI/mockup_templates/2x3
```
```bash
grok -p "Photorealistic cozy warm-neutral living room, a thin light-oak wood frame with a white mat hanging above a beige linen sofa, soft daylight, minimalist styling, 4K. The frame is PORTRAIT 2:3. IMPORTANT: the inside of the frame (art area) is ONE perfectly flat solid pure green rectangle #00FF00, evenly filled, no artwork, no texture, sharp straight edges. Save the result as a PNG file at ~/Bot-AI/mockup_templates/2x3/01_cover_sofa.png"
```
```bash
grok -p "Photorealistic warm-neutral bedroom, a thin light-oak frame with white mat above the headboard, soft daylight, minimalist, 4K. Frame is PORTRAIT 2:3. IMPORTANT: inside the frame is ONE perfectly flat solid pure green rectangle #00FF00, evenly filled, no art, sharp edges. Save the result as a PNG file at ~/Bot-AI/mockup_templates/2x3/02_bedroom.png"
```
```bash
grok -p "Photorealistic calm home office, a thin light-oak frame with white mat above a light wood desk with a small vase, soft daylight, minimalist, 4K. Frame is PORTRAIT 2:3. IMPORTANT: inside the frame is ONE perfectly flat solid pure green rectangle #00FF00, evenly filled, no art, sharp edges. Save the result as a PNG file at ~/Bot-AI/mockup_templates/2x3/03_office.png"
```
```bash
grok -p "Photorealistic close-up of a thin light-oak frame corner with white mat on a warm neutral wall, shallow depth of field, soft daylight, 4K. Frame is PORTRAIT 2:3. IMPORTANT: the visible art area inside the frame is a perfectly flat solid pure green rectangle #00FF00, evenly filled, no art, sharp edges. Save the result as a PNG file at ~/Bot-AI/mockup_templates/2x3/04_closeup.png"
```

## 2) Gabarits FRAME TV authentiques 16:9 — `mockup_templates/16x9/`
⚠️ Reco Claude Chat : pour le mot-clé « samsung frame tv art », il faut un rendu
de **télé** (bezel fin, **art bord-à-bord**, posée sur un meuble), PAS un cadre
photo + passe-partout.
```bash
mkdir -p ~/Bot-AI/mockup_templates/16x9
```
```bash
grok -p "Photorealistic modern living room with a Samsung Frame TV mounted on a warm neutral wall above a low wood TV console with decor, soft daylight, cozy minimalist styling, 4K. The TV has a VERY THIN black bezel and the screen shows art EDGE-TO-EDGE (no white mat). IMPORTANT: the entire SCREEN area is ONE perfectly flat solid pure green rectangle #00FF00, edge-to-edge, evenly filled, no artwork, no reflection, sharp straight edges, 16:9. Save the result as a PNG file at ~/Bot-AI/mockup_templates/16x9/01_cover_frametv_console.png"
```
```bash
grok -p "Photorealistic Samsung Frame TV on a console in a warm neutral living room, slightly angled side view, soft daylight, 4K. Thin black bezel, art EDGE-TO-EDGE, no mat. IMPORTANT: the whole SCREEN is ONE perfectly flat solid pure green rectangle #00FF00, edge-to-edge, evenly filled, no reflection, sharp edges, 16:9. Save the result as a PNG file at ~/Bot-AI/mockup_templates/16x9/02_frametv_angle.png"
```
```bash
grok -p "Photorealistic close-up of a Samsung Frame TV thin bezel corner on a neutral wall, shallow depth of field, soft daylight, 4K. Art edge-to-edge, no mat. IMPORTANT: the visible screen area is a perfectly flat solid pure green rectangle #00FF00, evenly filled, no reflection, sharp edges. Save the result as a PNG file at ~/Bot-AI/mockup_templates/16x9/03_frametv_closeup.png"
```

## 3) Gabarits PANORAMA 3:1 — `mockup_templates/3x1/`
```bash
mkdir -p ~/Bot-AI/mockup_templates/3x1
```
```bash
grok -p "Photorealistic warm-neutral living room, a thin light-oak PANORAMIC frame (very wide 3:1) with a white mat hanging above a long beige linen sofa, wide shot, soft daylight, minimalist, 4K. IMPORTANT: inside the frame is ONE perfectly flat solid pure green rectangle #00FF00, very wide 3:1, evenly filled, no art, sharp edges. Save the result as a PNG file at ~/Bot-AI/mockup_templates/3x1/01_cover_panorama_sofa.png"
```

---

## Lancer le compositing
```bash
cd ~/Bot-AI && source .venv/bin/activate
python automation/make_mockups.py ~/Downloads/<g1>.png ~/Downloads/<g2>.png ~/Downloads/<g3>.png --video
```
→ mockups exacts + vidéo (zoom lent, sans balayage de lumière, audio retiré) dans
`~/Downloads`. Le bon dossier de gabarits (2x3 / 3x1 / 16x9) est choisi selon le
thème du jour.

## Après vérif (QC)
- Ouvre chaque gabarit : le **vert est bien plein/net** ? (sinon régénère-le)
- Ouvre un mockup : l'œuvre est **strictement** ton fichier (mêmes formes) ?

## Fichiers de VENTE (rappel résolution)
Les bruts Grok sont **sous** la spec NWD (4608 px côté long). Avant de vendre,
**agrandis le design gagnant avec Upscayl ×4** (modèle Standard), puis découpe aux
5 ratios à **300 DPI**. Le mockup, lui, peut rester en 4K (taille du gabarit).
