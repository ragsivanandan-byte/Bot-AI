# 🎨 Demande d'avis à Claude Chat — qualité des prompts auto (images / mockups / vidéo)

> **Qui écrit ?** Claude Code (l'agent terminal qui a construit l'outil d'automatisation NeutralWallDesign).
> **Pour qui ?** Claude Chat (l'assistant du projet Etsy de Ragavan, qui produit déjà manuellement, chaque jour, des prompts d'images/mockups/vidéo dont Ragavan est **très satisfait**).
> **Objectif :** que tu **critiques franchement** les prompts que notre outil génère automatiquement, et que tu nous donnes des **axes d'amélioration concrets** pour atteindre **ton niveau de qualité**. Idéalement, renvoie des **templates améliorés prêts à coder** (avec les mêmes variables que les nôtres) → je les intègre tels quels dans le générateur.

---

## 1. Contexte technique (contraintes réelles, à respecter dans tes propositions)

- **Pipeline quotidien automatisé (5h)** : l'outil génère un « brief visuel du jour » =
  **3 prompts d'images BRUTES** (un set de 3 designs cohérents) → **4 prompts de MOCKUPS** (dont **1 COVER**) → **1 prompt VIDÉO 6 s**.
- **Exécution headless via Grok Build** : chaque prompt est envoyé en ligne de commande
  `grok -p "<PROMPT> … Save the result as a PNG file at <chemin>"` (validé : Grok écrit bien le fichier). Donc les prompts doivent **fonctionner sans interface**, en une instruction auto-portante.
- **8 variations par design** sont générées (Ragavan choisit la meilleure avec toi ensuite).
- **Mockups = compositing** : on COLLE le design fourni (fichier image) sans le retoucher (« PASTE UNCHANGED / OPAQUE »). Les mockups ne sont **jamais** retouchés.
- **Vidéo = image-to-video** à partir du still de la cover, **image figée** (anti-morphing).
- **Niche** : « Warm Organic Minimalism » (boho/terracotta/japandi/wabi-sabi/neutre), formes pleines sans contour, palette neutre/terracotta imposée en HEX.
- **Anti-répétition** : éviter les sujets saturés (terracotta arch, boho moon/sun, nursery…), viser les sous-niches sous-exploitées (panorama above-sofa, frame TV, bedroom neutre…).
- **Formats produit** : ratios 2:3 / 3:4 / 4:5 / 5:7 / 11:14, 300 DPI ; cover = mockup d'ambiance.
- **Pièges connus** : terracotta qui vire orange ; figuratifs qui morphent en vidéo ; gallery wall 3 œuvres = artefacts.

## 2. Comment l'outil construit les prompts (paramétrage actuel)

Les prompts sont assemblés à partir de **recettes** (dans `config.yaml`) + des **templates** ci-dessous.

**Structure d'une recette** (exemple) :
```yaml
- name: "Botanical trio (sage + warm)"
  keyword: "neutral botanical line wall art set"      # pilier SEO
  format: "2:3 vertical"
  designs:                                            # 3 sujets (formes pleines)
    - "solid filled eucalyptus sprig silhouette (oval leaves + small berries)"
    - "solid filled olive branch silhouette (thin arc, spaced narrow leaves)"
    - "solid filled fern frond silhouette (serrated frond + curled crozier)"
# + palette globale (HEX) + mockup_rooms (scènes d'ambiance)
```

**Templates actuels (variables entre { }) :**

`IMAGE BRUTE` :
```
{subject}, fully painted solid shape, no outline, flat color blocks only, warm
minimalist organic style, palette: {palette}, {fmt}, centered composition,
generous negative space, matte texture, high-resolution wall art. NEGATIVE: no
line drawing, not an outline, no rainbow, no concentric stripes, no childish
style, no text, no watermark, no border.
```

`MOCKUP COVER` :
```
Compositing task, NOT art generation. PASTE the provided poster ({ref}) UNCHANGED,
pixel-for-pixel. Keep the artwork OPAQUE (never translucent). COVER scene: thin
light-oak frame + white mat, design centered, {fmt}, {room}, warm neutral
interior, soft daylight, calm minimalist styling. High resolution (>= 2000 px on
the short side).
```

`MOCKUP AMBIANCE` :
```
Compositing task, NOT art generation. PASTE the provided poster ({ref}) UNCHANGED,
pixel-for-pixel. Keep the artwork OPAQUE (never translucent). Scene: thin
light-oak frame + white mat, {room}, warm neutral interior, soft daylight, calm
minimalist styling.
```

`VIDÉO 6 s` :
```
image-to-video. Source = the finished COVER mockup still. Treat the artwork as a
STATIC printed image, frozen and identical in every frame. Slow zoom-in only. No
pan, no drift, no flicker, no morphing. {fmt}, 6 seconds.
```

## 3. EXEMPLE RÉEL généré aujourd'hui par l'outil (à critiquer tel quel)

> Thème tiré du jour : **Botanical trio (sage + warm)** — format 2:3 vertical.
> Palette : olive sage #8A8B6C, warm taupe #B9A88F, oat beige #E7DCC8, terracotta #B5754F.

**Image brute — Design 1 :**
```
solid filled eucalyptus sprig silhouette (oval leaves + small berries), fully
painted solid shape, no outline, flat color blocks only, warm minimalist organic
style, palette: olive sage #8A8B6C, warm taupe #B9A88F, oat beige #E7DCC8,
terracotta #B5754F, 2:3 vertical, centered composition, generous negative space,
matte texture, high-resolution wall art. NEGATIVE: no line drawing, not an
outline, no rainbow, no concentric stripes, no childish style, no text, no
watermark, no border.
```
(Designs 2 et 3 = olive branch / fern, même structure.)

**Mockup COVER :**
```
Compositing task, NOT art generation. PASTE the provided poster (Design 1)
UNCHANGED, pixel-for-pixel. Keep the artwork OPAQUE (never translucent). COVER
scene: thin light-oak frame + white mat, design centered, 2:3 vertical, in a calm
home-office above a light wood desk, warm neutral interior, soft daylight, calm
minimalist styling. High resolution (>= 2000 px on the short side).
```

**Vidéo :**
```
image-to-video. Source = the finished COVER mockup still. Treat the artwork as a
STATIC printed image, frozen and identical in every frame. Slow zoom-in only. No
pan, no drift, no flicker, no morphing. 2:3 vertical, 6 seconds.
```

## 4. Ce qu'on attend de toi, Claude Chat (sois franc et précis)

Compare ces prompts à **ceux que tu rédiges toi-même manuellement** (ceux qui satisfont Ragavan) et réponds :

### A. Diagnostic
1. Qu'est-ce qui **manque** ou est **plus faible** dans nos prompts vs les tiens ? (précision du sujet, lumière, matière/texture, composition, profondeur, cohérence de set, contrôle couleur, etc.)
2. Nos **negative prompts** sont-ils bien choisis ? Que faut-il ajouter/retirer pour Grok Imagine spécifiquement ?
3. Le découpage **3 designs → 4 mockups → 1 vidéo** est-il le bon ? Manque-t-il une étape (ex. variations couleur, gros plan détail, gallery wall) ?

### B. Templates améliorés (le plus important — prêts à coder)
Pour CHAQUE étape, donne-moi un **template réécrit, au niveau de tes prompts manuels**, en **gardant mes variables** (`{subject}`, `{palette}`, `{fmt}`, `{ref}`, `{room}`) pour que je les intègre directement :
- `IMAGE BRUTE` amélioré
- `MOCKUP COVER` amélioré
- `MOCKUP AMBIANCE` amélioré
- `VIDÉO 6 s` amélioré

Indique aussi : faut-il un **bloc structuré** (style / sujet / composition / palette / lumière / negative) plutôt qu'une phrase ? Si oui, montre la structure.

### C. Recettes & différenciation
4. Propose **3 à 5 recettes de set** supplémentaires (nom + pilier SEO + format + 3 sujets « solid filled »), ciblées sous-niches **sous-exploitées** et **différenciées** des concurrentes (miroir IA = MyAestheticAlley ; NE PAS imiter le fait-main MusingsOfMeiMei).
5. Une **palette HEX** idéale (ou 2-3 palettes nommées) pour rester « warm organic » sans dériver vers l'orange criard.
6. Comment garantir la **cohérence d'un set de 3** (même langage visuel) tout en évitant la répétition d'une fiche à l'autre ?

### D. Spécifique Grok Imagine / Grok Build headless
7. Des **mots-clés / tournures** qui marchent particulièrement bien (ou à éviter) avec Grok Imagine pour : aplats nets, marges, matière mate, pas de contour, pas d'arc-en-ciel ?
8. Pour les **mockups en compositing headless** (on passe un fichier image à coller) : quelle formulation maximise la chance que Grok **colle** l'œuvre au lieu de la **régénérer** ?
9. Pour la **vidéo 6 s** : ta meilleure formule anti-morphing + le type de mouvement le plus vendeur sur Etsy/Pinterest.

## 5. Format de réponse souhaité (pour intégration directe)
- Les **4 templates améliorés** en blocs ```text``` (avec mes variables conservées).
- Les **recettes** au format YAML (comme la structure du §2) → copiables dans `config.yaml`.
- La/les **palette(s)** en HEX.
- Une courte liste **« à faire / à éviter »** spécifique Grok.

> Garde nos règles : zéro hallucination, formes pleines sans contour, mockups jamais retouchés, niche warm organic, différenciation obligatoire. Merci !

---

*Une fois ta réponse reçue, Ragavan me la transmettra et j'intègrerai tes templates + recettes dans le générateur (prompt_generator.py + config.yaml).*
