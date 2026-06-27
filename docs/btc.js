"use strict";
// Graphique BTC/EUR depuis 2015 + moyenne mobile 200 semaines, et tableau des
// périodes sous la 200 WMA. Données réelles, sans clé API : fichier committé,
// puis CryptoCompare (indice EUR) et Kraken XBT/EUR (bourse) en direct. Aucun
// prix n'est codé en dur — 0 hallucination.
(function () {
  const PRICE_COLOR = "#f7931a"; // orange = prix BTC
  const WMA_COLOR = "#5aa9ff";   // bleu = 200 WMA
  const START = "2015-01-01";

  const { resampleWeekly, computeSeries, belowPeriods } = BTCcore;
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
    renderChart(series);
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

  function renderChart(series) {
    const W = 960, H = 380, padL = 70, padR = 14, padT = 14, padB = 30;
    const n = series.length;
    const vals = series.flatMap((p) => (p.wma200 != null ? [p.close, p.wma200] : [p.close])).filter((v) => v > 0);
    const min = Math.min(...vals), max = Math.max(...vals);
    const lmin = Math.log10(min), lmax = Math.log10(max);
    const X = (i) => padL + (i / Math.max(1, n - 1)) * (W - padL - padR);
    const Y = (v) => padT + (1 - (Math.log10(v) - lmin) / (lmax - lmin)) * (H - padT - padB);

    const grid = [];
    for (const v of logTicks(min, max)) {
      const yy = Y(v);
      grid.push(`<line x1="${padL}" y1="${yy.toFixed(1)}" x2="${W - padR}" y2="${yy.toFixed(1)}" stroke="#232b3a" stroke-width="1"/>`);
      const lbl = v >= 1000 ? "€" + (v / 1000) + "k" : "€" + v;
      grid.push(`<text x="${padL - 8}" y="${(yy + 4).toFixed(1)}" fill="#8b97a7" font-size="11" text-anchor="end">${lbl}</text>`);
    }
    // étiquettes d'années (changement d'année)
    const xlabels = [];
    let prevYear = null;
    series.forEach((p, i) => {
      const y = p.date.slice(0, 4);
      if (y !== prevYear) {
        prevYear = y;
        xlabels.push(`<text x="${X(i).toFixed(1)}" y="${H - 10}" fill="#8b97a7" font-size="11" text-anchor="middle">${y}</text>`);
      }
    });

    const pricePath = pathOf(series.map((p) => p.close), X, Y);
    const wmaPath = pathOf(series.map((p) => p.wma200), X, Y);

    $("btc-chart").innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="BTC/EUR et 200 WMA">` +
      grid.join("") + xlabels.join("") +
      `<path d="${wmaPath}" fill="none" stroke="${WMA_COLOR}" stroke-width="2"/>` +
      `<path d="${pricePath}" fill="none" stroke="${PRICE_COLOR}" stroke-width="1.6"/>` +
      `</svg>`;
  }

  // Construit un path SVG en sautant les valeurs null (segments séparés).
  function pathOf(arr, X, Y) {
    let d = "", pen = false;
    for (let i = 0; i < arr.length; i++) {
      const v = arr[i];
      if (v == null || !(v > 0)) { pen = false; continue; }
      d += (pen ? "L" : "M") + X(i).toFixed(1) + "," + Y(v).toFixed(1) + " ";
      pen = true;
    }
    return d.trim();
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
