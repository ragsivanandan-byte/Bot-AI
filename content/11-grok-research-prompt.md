# 🔎 PROMPT GROK — Recherche de demande prouvée (insights stratégiques)

> **Rôle de Grok dans Quiet Capital :** partenaire stratégique. En plus de générer les
> visuels, Grok exploite son **accès temps réel à X + web** pour trouver la **demande
> RÉELLE et actuelle** sur YouTube Shorts (ce que les blogs SEO ratent car en retard).
>
> **Comment l'utiliser :** colle le prompt ci-dessous dans Grok (mode raisonnement +
> accès web/X activé). Récupère le tableau, **colle-le à Claude** → Claude scriptera les
> meilleurs sujets. Refais cette recherche ~toutes les 2 semaines (les tendances bougent).

---

## PROMPT (à copier-coller dans Grok)

```
You are the growth & trend-research strategist for "Quiet Capital", a faceless YouTube
channel in the MONEY + STATUS space (personal finance, wealth psychology, investing, and
luxury/watches-as-assets). Audience: English-speaking US/UK, ~25-40, aspirational earners.
Format: faceless Shorts (45-60s), AI voiceover + AI b-roll, plus some long-form. Goal:
MAXIMUM views and revenue (high-CPM finance/luxury angles).

YOUR UNIQUE EDGE: use your REAL-TIME access to X (Twitter) and the web. I don't want
generic "post consistently" advice — I want PROVEN, CURRENT demand from the last ~60-90 days.

TASK
Find the 15 highest-view-potential topics for our niche on YouTube Shorts RIGHT NOW, each
backed by evidence of real demand.

WHAT COUNTS AS "PROVEN DEMAND" (cite at least one per topic)
- Recent Shorts/Reels/TikToks in our niche with unusually high views/engagement
- Spiking search queries or Google/YouTube trends
- High-engagement X threads/posts on the topic (lots of replies/bookmarks)
- Questions people repeatedly ask in comments/forums (Reddit r/personalfinance, etc.)

HARD CONSTRAINTS
- Market: US/UK English only.
- Niche must stay in: personal finance, investing, money psychology, wealth habits,
  luxury/watches/cars as assets, "old money / quiet luxury".
- Faceless + AI visuals. Brand-safe: visuals must NOT show real brand logos (we can NAME
  brands in the voiceover, but images stay generic luxury).
- Prefer EVERGREEN over fads, but flag any hot fad worth riding now.

OUTPUT — strict format, a numbered list of 15, each with:
1. Topic title (punchy, English)
2. Proven-demand evidence: the exact signal + where + roughly when (link/handle if possible)
3. Confidence: HIGH / MEDIUM / LOW  (be brutally honest; if you cannot verify it, mark LOW
   and label it "hypothesis" — DO NOT fabricate numbers, views, or sources)
4. 1-second HOOK: the on-screen text + the spoken opening line
5. Why it fits Quiet Capital + CPM note (is the advertiser intent high-value?)
6. Saturation level (low/med/high) + the specific GAP/angle to stand out
7. 6 brand-safe visual prompt ideas (9:16, "no logo, no text")

THEN, at the very end, add:
- "TOP 3 BETS": the 3 topics you'd publish first and why (1 line each).
- "FORMAT TRENDS": any current Shorts format/editing trend in our niche worth copying
  (caption style, pacing, hook pattern) — evidence-based.
- "AVOID": 2-3 topics that LOOK appealing but are saturated or low-CPM, and why.

RULES
- Zero fabrication. No invented stats or fake sources. Uncertain = mark LOW / hypothesis.
- Be specific and evidence-led, not generic. Quality over filler.
```

---

## Après avoir reçu la réponse de Grok
1. **Colle le tableau complet à Claude.**
2. Claude croise avec le `growth-playbook` (content/10) et **écrit les scripts** des 3-5
   meilleurs (hook seconde 0, 45-60s, chute satisfaisante), les ajoute à `content/01`.
3. Tu génères les visuels (prompts fournis par Grok) → `./bot/run.sh make N` → publie.
