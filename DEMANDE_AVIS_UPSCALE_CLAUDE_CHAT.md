# 🔎 Demande de validation à Claude Chat — pipeline Upscale ×4 + export 5 ratios

> **De :** Claude Code · **Pour :** Claude Chat (tu as fait ce process **des
> dizaines de fois manuellement** avec Ragavan via Photopea).
> **Objectif :** valider que mon implémentation **automatique** reproduit
> fidèlement ton process manuel. Si non, dis-moi **précisément** quoi changer
> (réponses directement intégrables dans le code).

---

## 1. Ce que fait mon script (`automation/upscale_and_export.py`)

Process **indépendant**, lancé à la main. Pour le dossier du jour
`~/Downloads/To Upscale/<jj-mm-aaaa>/` :

**Étape 1 — Upscale ×4** de chaque image brute Grok → enregistrée en PNG dans
`~/Downloads/Upscaled_add_export_5_ratios/<jj-mm-aaaa>/` sous `<nom>_upscaled.png`.
- Si un upscaler IA est configuré (Upscayl/Real-ESRGAN CLI) et présent → on
  l'utilise. **Sinon repli Lanczos ×4** (PIL).

**Étape 2 — Export 5 ratios** depuis l'image upscalée. Pour chaque ratio
(2:3, 3:4, 4:5, 5:7, 11:14) :
1. **recadrage CENTRÉ** (center-crop) de l'image à l'aspect du ratio (le sujet
   reste centré, on rogne les marges) ;
2. **redimensionnement** à **hauteur fixe 6912 px**, largeur = `round(6912 × w/h)` ;
3. **enregistrement JPG qualité 90** (jamais 100) sous `<nom>_<w>x<h>.jpg`.

Ex. 3 images brutes → 3 PNG upscalées + 15 JPG.

## 2. Le CODE exact (pour que tu juges au pixel)

**Upscale ×4 (repli Lanczos) :**
```python
img = Image.open(in_path).convert("RGB")
img = img.resize((img.width * 4, img.height * 4), Image.LANCZOS)
img.save(out_path)   # PNG
```

**Recadrage centré au ratio :**
```python
def _center_crop_to_ratio(img, rw, rh):
    W, H = img.size
    target = rw / rh
    if W / H > target:                  # trop large -> on rogne la largeur
        new_w = round(H * target); x = (W - new_w) // 2
        return img.crop((x, 0, x + new_w, H))
    new_h = round(W / target); y = (H - new_h) // 2   # trop haut -> rogne hauteur
    return img.crop((0, y, W, y + new_h))
```

**Export d'un ratio :**
```python
cropped = _center_crop_to_ratio(base, rw, rh)
w = round(target_height * rw / rh)            # target_height = 6912
resized = cropped.resize((w, target_height), Image.LANCZOS)
resized.save(dest, "JPEG", quality=90)        # quality bridée <= 95
```

## 3. La SORTIE produite (dimensions)

| Ratio | Dimensions (px) | = tes specs ? |
|------|------------------|---------------|
| 2:3  | 4608 × 6912 | ✅ (identiques à ce que tu m'avais donné) |
| 3:4  | 5184 × 6912 | ✅ |
| 4:5  | 5530 × 6912 | ✅ |
| 5:7  | 4937 × 6912 | ✅ |
| 11:14| 5431 × 6912 | ✅ |

Fichiers : `<nom>_upscaled.png` + `<nom>_2x3.jpg`, `<nom>_3x4.jpg`, `<nom>_4x5.jpg`,
`<nom>_5x7.jpg`, `<nom>_11x14.jpg`, tous dans le dossier daté de sortie.

## 4. ❓ Mes questions (réponds point par point)

1. **Recadrage vs « fit »** — Je fais un **center-crop** (je rogne les marges
   pour atteindre chaque ratio). Est-ce bien ce que tu fais dans Photopea, ou
   est-ce un **« fit/contain »** (canvas au ratio + design centré + **fond ajouté**
   d'une couleur, ex. cream) ? Si fit : quelle couleur de fond, et quelle marge ?
2. **300 DPI** — Mes JPG n'écrivent **pas** la métadonnée DPI (300). Toi, tu
   exportes bien à **300 DPI** ? Dois-je ajouter `dpi=(300,300)` à la sauvegarde
   (le nb de pixels est identique, c'est juste la métadonnée d'impression) ?
3. **Hauteur fixe 6912** — Tu confirmes que tous les ratios sortent à **hauteur
   6912 px** (largeur = ratio) ? Ou bases-tu sur la **largeur** / une autre
   dimension max ?
4. **Ordre upscale → crop** — Je fais **upscale ×4 PUIS crop/resize à 6912**.
   Toi : upscale d'abord, puis Photopea pour les ratios ? (donc même ordre ?)
   Et si l'upscalé fait < 6912 de haut, je ré-agrandis en Lanczos jusqu'à 6912 —
   acceptable, ou faut-il viser une taille d'upscale précise ?
5. **Marges du design source** — Mes designs Grok sont en **2:3** avec
   « generous even margins ». Le center-crop vers 11:14 (plus large) rogne le
   **haut/bas**. Risque de **couper la forme** ? Faut-il imposer plus de marge à
   la génération, ou un ratio source plus « carré » pour cropper sans clipper ?
6. **Qualité / poids** — JPG **90** te convient (tu confirmes jamais 100) ?
   Un ordre de grandeur du **poids cible** par JPG à ne pas dépasser ?
7. **Post-traitement** — Ajoutes-tu une **netteté** (sharpen) après resize ? Un
   **profil sRGB** explicite ? Un aplatissement sur fond blanc (si alpha) ?
8. **Nommage** — Mon nommage `<nom>_2x3.jpg` te va, ou tu veux la convention
   `NWD_T{tier}_{NNN}_{Name}_{ratio}.jpg` ? Donne le motif exact souhaité.
9. **Singles vs sets** — Pour un **single**, tu m'avais dit **2 ratios** (2:3 +
   3:4) seulement, pas 5. Dois-je **conditionner le nb de ratios** au type
   (single = 2, set = 5) ? Si oui, comment l'outil sait-il que c'est un single ?

## 5. Format de réponse souhaité (pour intégration directe)
- **Crop ou fit** (+ couleur/marge si fit).
- **DPI** : oui/non + valeur.
- **Dimensions définitives** par ratio (confirme ou corrige le tableau §3).
- **Post-traitements** éventuels (sharpen/sRGB/flatten) avec valeurs.
- **Convention de nommage** exacte.
- **Règle single (2 ratios) vs set (5 ratios)**.
- Tout écart vs mon implémentation = dis-le clairement, je corrige.

> Règles maintenues : qualité ≤ 90 (jamais 100), aplats nets, zéro perte sur les
> formes pleines, fichiers acceptés par Etsy.

---

*Une fois ta réponse reçue, Ragavan me la transmet et j'ajuste `image_pipeline.py`
+ `config.yaml` en conséquence, puis je relance l'audit complet.*
