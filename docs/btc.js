"use strict";
// Graphique BTC/EUR depuis 2015 + moyenne mobile 200 semaines, et tableau des
// périodes sous la 200 WMA. Données réelles, sans clé API : fichier committé,
// puis CryptoCompare (indice EUR) et Kraken XBT/EUR (bourse) en direct. Aucun
// prix n'est codé en dur — 0 hallucination.
(function () {
  const PRICE_COLOR = "#f7931a"; // orange = prix BTC
  const WMA_COLOR = "#5aa9ff";   // bleu = 200 WMA
  const START = "2015-01-01";

  const { resampleWeekly, computeSeries, belowPeriods, zoom1D } = BTCcore;

  // Géométrie du graphique (coordonnées du viewBox SVG).
  const W = 960, H = 380, padL = 70, padR = 14, padT = 14, padB = 30;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  // État du graphique (données + fenêtre de vue zoomable).
  let G = null;
  const $ = (id) => document.getElementById(id);
  const status = (msg) => { const e = $("btc-status"); if (e) e.textContent = msg; };

  const eur = (x) =>
    "€" + Math.round(x).toLocaleString("fr-FR");
  const pct = (x) => (x >= 0 ? "+" : "") + x.toFixed(1) + "%";

  // --- Sources de données (réelles, sans clé API) -------------------------
  // 1) Fichier committé (le plus fiable, généré par build_btc_data.py / l'Action).
  async function fromCommitted() {
    const r = await fetch("data/btc_eur.json", { cache: "no-store" });
    if (!r.ok) throw new Error("btc_eur.json HTTP " + r.status);
    const j = await r.json();
    if (!j.weekly || !j.weekly.length) throw new Error("btc_eur.json vide");
    return {
      series: j.weekly.map((w) => ({ date: w.date, close: w.close, wma200: w.wma200 })),
      source: (j.source || "fichier local") + " · généré le " + (j.generated_utc || "?"),
    };
  }

  // 2) CryptoCompare CCCAGG (indice EUR agrégé) — sans clé, historique long.
  async function fromCryptoCompare() {
    const url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=EUR&allData=true";
    const r = await fetch(url);
    if (!r.ok) throw new Error("CryptoCompare HTTP " + r.status);
    const j = await r.json();
    const data = (j.Data && j.Data.Data) || [];
    if (!data.length) throw new Error("CryptoCompare vide");
    const pts = data.filter((d) => d.close > 0).map((d) => [d.time * 1000, d.close]);
    return {
      series: computeSeries(resampleWeekly(pts), 200),
      source: "CryptoCompare CCCAGG · BTC/EUR (indice agrégé en euros), chargé en direct",
    };
  }

  // 3) Kraken XBT/EUR (bourse réglementée) — sans clé ; ~720 semaines (depuis 2015).
  async function fromKraken() {
    const url = "https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval=10080";
    const r = await fetch(url);
    if (!r.ok) throw new Error("Kraken HTTP " + r.status);
    const j = await r.json();
    if (j.error && j.error.length) throw new Error("Kraken: " + j.error.join(","));
    const key = Object.keys(j.result || {}).find((k) => k !== "last");
    const rows = (key && j.result[key]) || [];
    if (!rows.length) throw new Error("Kraken vide");
    const pts = rows.map((row) => [row[0] * 1000, parseFloat(row[4])]);
    return {
      series: computeSeries(resampleWeekly(pts), 200),
      source: "Kraken · XBT/EUR (bourse), chargé en direct",
    };
  }

  // --- Rendu --------------------------------------------------------------
  function render(all, source) {
    const series = all.filter((p) => p.date >= START);
    if (!series.length) { status("Aucune donnée à afficher."); return; }
    status("");
    $("btc-source").textContent =
      "Source : " + source + ". 200 WMA = moyenne mobile sur 200 semaines " +
      "(définie à partir de ~200 semaines de données). Écart = (prix − 200WMA) / 200WMA.";
    setupChart(series);
    renderLegend();
    renderTable(belowPeriods(series));
  }

  function renderLegend() {
    $("btc-legend").innerHTML = [
      [PRICE_COLOR, "Prix BTC/EUR (clôture hebdo)"],
      [WMA_COLOR, "200 WMA (moyenne mobile 200 sem.)"],
    ].map(([c, t]) => `<span class="item"><span class="swatch" style="background:${c}"></span>${t}</span>`).join("");
  }

  function logTicks(min, max) {
    const ticks = [];
    for (let p = Math.floor(Math.log10(min)); p <= Math.ceil(Math.log10(max)); p++) {
      for (const m of [1, 2, 5]) {
        const v = m * Math.pow(10, p);
        if (v >= min * 0.85 && v <= max * 1.15) ticks.push(v);
      }
    }
    return ticks;
  }

  // --- Graphique zoomable -------------------------------------------------
  // G.view = { i0, i1 } (indices visibles) et { lmin, lmax } (bornes prix en log10).
  function setupChart(series) {
    const n = series.length;
    const vals = series.flatMap((p) => (p.wma200 != null ? [p.close, p.wma200] : [p.close])).filter((v) => v > 0);
    const dataLmin = Math.log10(Math.min(...vals));
    const dataLmax = Math.log10(Math.max(...vals));
    G = {
      pts: series, n,
      dataLmin, dataLmax,
      view: { i0: 0, i1: n - 1, lmin: dataLmin - 0.03, lmax: dataLmax + 0.03 },
    };
    draw();
    attachInteractions();
  }

  function resetView() {
    if (!G) return;
    G.view = { i0: 0, i1: G.n - 1, lmin: G.dataLmin - 0.03, lmax: G.dataLmax + 0.03 };
    draw();
  }

  function clampX() {
    const v = G.view, minW = 2;
    if (v.i1 - v.i0 < minW) { const c = (v.i0 + v.i1) / 2; v.i0 = c - minW / 2; v.i1 = c + minW / 2; }
    if (v.i0 < 0) { v.i1 -= v.i0; v.i0 = 0; }
    if (v.i1 > G.n - 1) { v.i0 -= (v.i1 - (G.n - 1)); v.i1 = G.n - 1; }
    v.i0 = Math.max(0, v.i0); v.i1 = Math.min(G.n - 1, v.i1);
  }
  function clampY() {
    const v = G.view, lo = G.dataLmin - 0.05, hi = G.dataLmax + 0.05, minH = 0.04;
    if (v.lmax - v.lmin < minH) { const c = (v.lmin + v.lmax) / 2; v.lmin = c - minH / 2; v.lmax = c + minH / 2; }
    v.lmin = Math.max(lo, v.lmin); v.lmax = Math.min(hi, v.lmax);
    if (v.lmax - v.lmin < minH) { v.lmin = lo; v.lmax = hi; }
  }

  const X = (i) => padL + ((i - G.view.i0) / (G.view.i1 - G.view.i0)) * plotW;
  const Y = (val) => padT + (1 - (Math.log10(val) - G.view.lmin) / (G.view.lmax - G.view.lmin)) * plotH;
  const idxAtX = (x) => G.view.i0 + ((x - padL) / plotW) * (G.view.i1 - G.view.i0);
  const lvalAtY = (y) => G.view.lmin + (G.view.lmax - G.view.lmin) * (1 - (y - padT) / plotH);

  function pathOf(arr) {
    let d = "", pen = false;
    for (let i = 0; i < arr.length; i++) {
      const val = arr[i];
      if (val == null || !(val > 0)) { pen = false; continue; }
      d += (pen ? "L" : "M") + X(i).toFixed(1) + "," + Y(val).toFixed(1) + " ";
      pen = true;
    }
    return d.trim();
  }

  function draw() {
    const v = G.view, pts = G.pts;
    const grid = [];
    for (const val of logTicks(Math.pow(10, v.lmin), Math.pow(10, v.lmax))) {
      const yy = Y(val);
      if (yy < padT - 1 || yy > H - padB + 1) continue;
      grid.push(`<line x1="${padL}" y1="${yy.toFixed(1)}" x2="${W - padR}" y2="${yy.toFixed(1)}" stroke="#232b3a" stroke-width="1"/>`);
      const lbl = val >= 1000 ? "€" + (Math.round(val / 100) / 10) + "k" : "€" + Math.round(val);
      grid.push(`<text x="${padL - 8}" y="${(yy + 4).toFixed(1)}" fill="#8b97a7" font-size="11" text-anchor="end">${lbl}</text>`);
    }
    // étiquettes X : années visibles (sinon bornes de la fenêtre)
    const i0c = Math.max(0, Math.ceil(v.i0)), i1c = Math.min(G.n - 1, Math.floor(v.i1));
    const xlabels = [];
    let prevYear = null;
    for (let i = i0c; i <= i1c; i++) {
      const yr = pts[i].date.slice(0, 4);
      if (yr !== prevYear) { prevYear = yr; xlabels.push(`<text x="${X(i).toFixed(1)}" y="${H - 10}" fill="#8b97a7" font-size="11" text-anchor="middle">${yr}</text>`); }
    }
    if (xlabels.length <= 1 && i1c >= i0c) {
      const mk = (i) => `<text x="${X(i).toFixed(1)}" y="${H - 10}" fill="#8b97a7" font-size="11" text-anchor="middle">${pts[i].date.slice(0, 7)}</text>`;
      xlabels.length = 0; xlabels.push(mk(i0c), mk(i1c));
    }

    $("btc-chart").innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="BTC/EUR et 200 WMA">` +
      `<defs><clipPath id="btcclip"><rect x="${padL}" y="${padT}" width="${plotW}" height="${plotH}"/></clipPath></defs>` +
      grid.join("") + xlabels.join("") +
      `<rect x="${padL}" y="${padT}" width="${plotW}" height="${plotH}" fill="transparent"/>` +
      `<g clip-path="url(#btcclip)">` +
      `<path d="${pathOf(pts.map((p) => p.wma200))}" fill="none" stroke="${WMA_COLOR}" stroke-width="2"/>` +
      `<path d="${pathOf(pts.map((p) => p.close))}" fill="none" stroke="${PRICE_COLOR}" stroke-width="1.6"/>` +
      `</g></svg>`;
  }

  // --- Interactions (zoom molette par axe, glisser-déplacer, double-clic) --
  let interactionsBound = false;
  function localCoords(e) {
    const svg = $("btc-chart").querySelector("svg");
    const r = svg.getBoundingClientRect();
    return { x: (e.clientX - r.left) * (W / r.width), y: (e.clientY - r.top) * (H / r.height) };
  }
  // Zone : 'y' (axe gauche -> prix), 'x' (axe bas -> temps), 'both' (graphe).
  function zoneAt(x, y) {
    if (x < padL) return "y";
    if (y > H - padB) return "x";
    return "both";
  }

  function attachInteractions() {
    if (interactionsBound) return;
    interactionsBound = true;
    const host = $("btc-chart");

    host.addEventListener("wheel", (e) => {
      if (!G) return;
      e.preventDefault();
      const { x, y } = localCoords(e);
      const zone = zoneAt(x, y);
      const factor = e.deltaY < 0 ? 0.85 : 1 / 0.85; // molette haut = zoom avant
      const cx = Math.min(W - padR, Math.max(padL, x));
      const cy = Math.min(H - padB, Math.max(padT, y));
      if (zone !== "y") { [G.view.i0, G.view.i1] = zoom1D(G.view.i0, G.view.i1, idxAtX(cx), factor); clampX(); }
      if (zone !== "x") { [G.view.lmin, G.view.lmax] = zoom1D(G.view.lmin, G.view.lmax, lvalAtY(cy), factor); clampY(); }
      draw();
    }, { passive: false });

    let drag = null;
    host.addEventListener("mousedown", (e) => {
      if (!G) return;
      const { x, y } = localCoords(e);
      drag = { x, y, view: { ...G.view } };
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
      if (!drag || !G) return;
      const { x, y } = localCoords(e);
      const dvX = (drag.view.i1 - drag.view.i0);
      const di = -((x - drag.x) / plotW) * dvX;
      G.view.i0 = drag.view.i0 + di; G.view.i1 = drag.view.i1 + di; clampX();
      const dvY = (drag.view.lmax - drag.view.lmin);
      const dl = ((y - drag.y) / plotH) * dvY;
      G.view.lmin = drag.view.lmin + dl; G.view.lmax = drag.view.lmax + dl; clampY();
      draw();
    });
    window.addEventListener("mouseup", () => { drag = null; });
    host.addEventListener("dblclick", (e) => { e.preventDefault(); resetView(); });

    const rb = $("btc-reset");
    if (rb) rb.addEventListener("click", resetView);
    const zi = $("btc-zoom-in"), zo = $("btc-zoom-out");
    const stepZoom = (factor) => {
      if (!G) return;
      const cx = (G.view.i0 + G.view.i1) / 2, cy = (G.view.lmin + G.view.lmax) / 2;
      [G.view.i0, G.view.i1] = zoom1D(G.view.i0, G.view.i1, cx, factor); clampX();
      [G.view.lmin, G.view.lmax] = zoom1D(G.view.lmin, G.view.lmax, cy, factor); clampY();
      draw();
    };
    if (zi) zi.addEventListener("click", () => stepZoom(0.7));
    if (zo) zo.addEventListener("click", () => stepZoom(1 / 0.7));
  }

  function renderTable(periods) {
    const tb = $("btc-below").querySelector("tbody");
    if (!periods.length) {
      tb.innerHTML = '<tr><td colspan="5">Aucune période sous la 200 WMA sur l\'intervalle.</td></tr>';
      return;
    }
    tb.innerHTML = periods
      .map((p) =>
        `<tr><td>${p.start}</td><td>${p.end}</td>` +
        `<td>${p.weeks} sem.</td>` +
        `<td class="neg">${pct(p.maxDev)}<span class="muted small"> (${p.maxDevDate})</span></td>` +
        `<td class="neg">${pct(p.avgDev)}</td></tr>`
      )
      .join("");
  }

  // --- Démarrage : essaie chaque source dans l'ordre ----------------------
  (async function () {
    const attempts = [
      ["fichier local", fromCommitted],
      ["CryptoCompare", fromCryptoCompare],
      ["Kraken", fromKraken],
    ];
    const errors = [];
    for (const [label, fn] of attempts) {
      try {
        status("Chargement des données BTC/EUR (" + label + ")…");
        const { series, source } = await fn();
        render(series, source);
        return;
      } catch (e) {
        errors.push(label + ": " + e.message);
      }
    }
    status("Impossible de charger les données BTC/EUR (" + errors.join(" · ") +
      "). Lancez « python3 build_btc_data.py » puis poussez pour générer data/btc_eur.json.");
  })();
})();
