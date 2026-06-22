"use strict";

// ---------------------------------------------------------------------------
// STRC DCA — Closing-Price Edition (logique portée depuis strc_dca.py)
// Tous les calculs sont refaits dans le navigateur à partir de data/strc.json.
// ---------------------------------------------------------------------------

let DATA = null;

const $ = (id) => document.getElementById(id);
const fmtUSD = (x) =>
  (x < 0 ? "-$" : "$") + Math.abs(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtNum = (x, d = 4) => x.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtPct = (x) => (x >= 0 ? "+" : "") + x.toFixed(2) + "%";

// Logique de simulation : fournie par sim.js (STRCsim), partagée avec les tests Node.
const { simulate } = STRCsim;

// --- Lecture des contrôles --------------------------------------------------
function readParams() {
  const dividendsOn = $("dividends").checked;
  return {
    weekly: Math.max(0, parseFloat($("weekly").value) || 0),
    start: $("start").value,
    end: $("end").value,
    dividendsOn,
    reinvest: $("reinvest").checked,
    apy: dividendsOn ? (parseFloat($("apy").value) || 0) / 100 : 0,
  };
}

function filteredCloses(p) {
  return DATA.weekly_closes.filter(
    (c) => (!p.start || c.date >= p.start) && (!p.end || c.date <= p.end)
  );
}

// --- Rendu ------------------------------------------------------------------
function render() {
  const p = readParams();
  const closes = filteredCloses(p);
  if (!closes.length) {
    $("compare").querySelector("tbody").innerHTML =
      '<tr><td colspan="3">Aucune semaine dans l\'intervalle.</td></tr>';
    return;
  }
  const par = DATA.par;
  const schedule = p.dividendsOn ? DATA.dividends : [];
  const apy = p.dividendsOn ? p.apy : 0;

  const parRes = simulate(closes, p.weekly, "par", schedule, apy, p.reinvest, par);
  const clRes = simulate(closes, p.weekly, "closing", schedule, apy, p.reinvest, par);

  renderKPIs(clRes, parRes);
  renderTable(parRes, clRes, p.dividendsOn);
  renderImpact(parRes, clRes);
  renderPortfolioChart(parRes, clRes);
  renderPriceChart(closes, par);
}

function renderKPIs(cl, par) {
  const cards = [
    { label: "Total investi", value: fmtUSD(cl.invested) },
    { label: "Valeur (closing réel)", value: fmtUSD(cl.totalValue) },
    {
      label: "P/L total (closing)",
      value: fmtUSD(cl.totalPL),
      cls: cl.totalPL >= 0 ? "pos" : "neg",
      hint: fmtPct(cl.totalPLpct),
    },
    {
      label: "Perte/gain en capital",
      value: fmtUSD(cl.capitalPL),
      cls: cl.capitalPL >= 0 ? "pos" : "neg",
      hint: "ignoré en Mode Par (" + fmtPct(par.capitalPLpct) + ")",
    },
    {
      label: "Écart vs Mode Par",
      value: fmtUSD(cl.totalValue - par.totalValue),
      cls: cl.totalValue - par.totalValue >= 0 ? "pos" : "neg",
      hint: "surestimation corrigée",
    },
  ];
  $("kpis").innerHTML = cards
    .map(
      (c) =>
        `<div class="kpi"><div class="label">${c.label}</div>` +
        `<div class="value ${c.cls || ""}">${c.value}</div>` +
        `<div class="hint">${c.hint || "&nbsp;"}</div></div>`
    )
    .join("");
}

function renderTable(par, cl, dividendsOn) {
  const sign = (v, base) => (v < 0 ? "neg" : v > 0 ? "pos" : "");
  let rows = [
    ["Total investi", fmtUSD(par.invested), fmtUSD(cl.invested), "", ""],
    ["Actions STRC", fmtNum(par.shares), fmtNum(cl.shares), "", ""],
    ["Coût moyen / action", fmtUSD(par.avgCost), fmtUSD(cl.avgCost), "", ""],
    ["Dernier closing", fmtUSD(par.latestClose), fmtUSD(cl.latestClose), "", ""],
    ["Valeur de marché", fmtUSD(par.marketValue), fmtUSD(cl.marketValue), "", ""],
    ["+/- value capital", fmtUSD(par.capitalPL), fmtUSD(cl.capitalPL), sign(par.capitalPL), sign(cl.capitalPL)],
    ["  (en %)", fmtPct(par.capitalPLpct), fmtPct(cl.capitalPLpct), sign(par.capitalPL), sign(cl.capitalPL)],
  ];
  if (dividendsOn) {
    rows.push(["Dividendes perçus", fmtUSD(par.dividends), fmtUSD(cl.dividends), "", ""]);
    rows.push(["Yield on cost", fmtPct(par.yieldOnCost), fmtPct(cl.yieldOnCost), "pos", "pos"]);
  }
  const tbody = $("compare").querySelector("tbody");
  tbody.innerHTML = rows
    .map(
      (r) =>
        `<tr><td>${r[0]}</td><td class="${r[3]}">${r[1]}</td>` +
        `<td class="${r[4]}">${r[2]}</td></tr>`
    )
    .join("");
  // Lignes totales
  tbody.innerHTML +=
    `<tr class="total"><td>VALEUR TOTALE</td><td>${fmtUSD(par.totalValue)}</td>` +
    `<td>${fmtUSD(cl.totalValue)}</td></tr>` +
    `<tr class="total"><td>P/L TOTAL</td>` +
    `<td class="${sign(par.totalPL)}">${fmtUSD(par.totalPL)} (${fmtPct(par.totalPLpct)})</td>` +
    `<td class="${sign(cl.totalPL)}">${fmtUSD(cl.totalPL)} (${fmtPct(cl.totalPLpct)})</td></tr>`;
}

function renderImpact(par, cl) {
  const dShares = cl.shares - par.shares;
  const dValue = cl.totalValue - par.totalValue;
  const capLine =
    cl.capitalPL < 0
      ? `<span class="neg">Perte en capital intégrée : ${fmtUSD(cl.capitalPL)}</span> — STRC sous le par 100 $ au dernier closing.`
      : `<span class="pos">Plus-value en capital intégrée : ${fmtUSD(cl.capitalPL)}</span>.`;
  $("impact").innerHTML =
    `<strong>Impact de la modification (closing réel vs par 100 $)</strong><br/>` +
    `Actions supplémentaires acquises sous le par : <strong>${fmtNum(dShares)}</strong><br/>` +
    `Écart de valeur totale : <strong class="${dValue < 0 ? "neg" : "pos"}">${fmtUSD(dValue)}</strong> ` +
    `(${fmtPct(par.totalValue ? (dValue / par.totalValue) * 100 : 0)})<br/>` +
    capLine;
}

// --- Graphiques SVG (sans dépendance) --------------------------------------
function lineChart(container, series, opts) {
  // series: [{name, color, dashed, points:[{x:Date->idx, y}]}], x partagé par index
  const W = 920, H = 320, padL = 70, padR = 16, padT = 16, padB = 34;
  const labels = opts.labels;
  const n = labels.length;
  let yMin = opts.yMin, yMax = opts.yMax;
  if (yMin === undefined || yMax === undefined) {
    const ys = series.flatMap((s) => s.points);
    yMin = Math.min(...ys); yMax = Math.max(...ys);
  }
  if (yMin === yMax) { yMax = yMin + 1; }
  const padY = (yMax - yMin) * 0.08;
  yMin -= padY; yMax += padY;
  const x = (i) => padL + (i / Math.max(1, n - 1)) * (W - padL - padR);
  const y = (v) => padT + (1 - (v - yMin) / (yMax - yMin)) * (H - padT - padB);

  const grid = [];
  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const v = yMin + (t / ticks) * (yMax - yMin);
    const yy = y(v);
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}" stroke="#232b3a" stroke-width="1"/>`);
    grid.push(`<text x="${padL - 8}" y="${yy + 4}" fill="#8b97a7" font-size="11" text-anchor="end">${opts.fmtY(v)}</text>`);
  }
  // étiquettes X (~6)
  const xlabels = [];
  const step = Math.max(1, Math.floor(n / 6));
  for (let i = 0; i < n; i += step) {
    xlabels.push(`<text x="${x(i)}" y="${H - 12}" fill="#8b97a7" font-size="11" text-anchor="middle">${labels[i]}</text>`);
  }

  // zones estimées (bandes grises)
  const bands = (opts.estimated || [])
    .map((e, i) => (e ? `<rect x="${x(i) - (W - padL - padR) / (2 * Math.max(1, n - 1))}" y="${padT}" width="${(W - padL - padR) / Math.max(1, n - 1)}" height="${H - padT - padB}" fill="#ffffff" opacity="0.03"/>` : ""))
    .join("");

  const paths = series
    .map((s) => {
      const d = s.points.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
      const dash = s.dashed ? ` stroke-dasharray="5 5"` : "";
      return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2"${dash}/>`;
    })
    .join("");

  container.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img">` +
    bands + grid.join("") + xlabels.join("") + paths + `</svg>`;
}

function renderPortfolioChart(par, cl) {
  const labels = cl.history.map((h) => h.date.slice(2, 7)); // YY-MM
  lineChart($("chart-portfolio"), [
    { name: "Mode Closing (réel)", color: "#f7931a", points: cl.history.map((h) => h.value) },
    { name: "Mode Par ($100)", color: "#5aa9ff", points: par.history.map((h) => h.value) },
    { name: "Total investi", color: "#8b97a7", dashed: true, points: cl.history.map((h) => h.invested) },
  ], { labels, fmtY: (v) => "$" + (v / 1000).toFixed(0) + "k" });

  $("legend-portfolio").innerHTML = [
    ["#f7931a", "Mode Closing (réel)"],
    ["#5aa9ff", "Mode Par ($100)"],
    ["#8b97a7", "Total investi"],
  ].map(([c, t]) => `<span class="item"><span class="swatch" style="background:${c}"></span>${t}</span>`).join("");
}

function renderPriceChart(closes, par) {
  const labels = closes.map((c) => c.date.slice(2, 7));
  lineChart($("chart-price"), [
    { name: "Closing STRC", color: "#f7931a", points: closes.map((c) => c.close) },
    { name: "Par", color: "#8b97a7", dashed: true, points: closes.map(() => par) },
  ], {
    labels,
    estimated: closes.map((c) => c.estimated),
    fmtY: (v) => "$" + v.toFixed(0),
  });
}

// --- Init -------------------------------------------------------------------
function setDefaults() {
  const w = DATA.weekly_closes;
  $("start").min = w[0].date;
  $("start").max = w[w.length - 1].date;
  $("end").min = w[0].date;
  $("end").max = w[w.length - 1].date;
  $("start").value = w[0].date;
  $("end").value = w[w.length - 1].date;
  $("apy").value = (DATA.default_apy * 100).toString();
  const src = DATA.live ? "LIVE (" + DATA.source + ")" : "SNAPSHOT embarqué";
  $("datameta").innerHTML =
    `Source : <strong>${src}</strong> · généré le ${DATA.generated_utc} · ` +
    `${DATA.weeks} semaines · ${DATA.interpolated_weeks} estimées · ` +
    `dernier closing ${fmtUSD(DATA.latest_close)} (par ${fmtUSD(DATA.par)}).`;
}

function bind() {
  ["weekly", "start", "end", "apy"].forEach((id) => $(id).addEventListener("input", render));
  ["dividends", "reinvest"].forEach((id) => $(id).addEventListener("change", render));
  $("reset").addEventListener("click", () => {
    $("weekly").value = 1000;
    $("dividends").checked = true;
    $("reinvest").checked = false;
    setDefaults();
    render();
  });
}

fetch("data/strc.json", { cache: "no-store" })
  .then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  })
  .then((d) => {
    DATA = d;
    setDefaults();
    bind();
    render();
  })
  .catch((e) => {
    document.querySelector("main").innerHTML =
      `<section class="panel"><h2>Erreur de chargement des données</h2>` +
      `<p class="muted">Impossible de charger <code>data/strc.json</code> (${e.message}).</p></section>`;
  });
