"use strict";
// Logique pure BTC/EUR (sans DOM, sans réseau) — partagée navigateur + Node + tests.
// Aucune donnée de prix codée en dur : tout est calculé à partir des prix réels
// fournis en entrée (récupérés en direct depuis CoinGecko).
(function (global) {
  // Lundi (UTC) de la semaine d'un timestamp ms — ancre de regroupement hebdo.
  function mondayOf(ms) {
    const x = new Date(ms);
    const day = (x.getUTCDay() + 6) % 7; // 0 = lundi
    x.setUTCDate(x.getUTCDate() - day);
    x.setUTCHours(0, 0, 0, 0);
    return x;
  }

  // prices : [[ms, prix_eur], ...] quotidiens -> clôtures HEBDOMADAIRES
  // (dernier prix disponible de chaque semaine).
  function resampleWeekly(prices) {
    const map = new Map();
    for (const row of prices) {
      const ms = row[0], price = row[1];
      if (price == null || !isFinite(price)) continue;
      const key = mondayOf(ms).toISOString().slice(0, 10);
      const prev = map.get(key);
      if (!prev || ms >= prev.ms) map.set(key, { ms, price });
    }
    return [...map.entries()]
      .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
      .map(([date, v]) => ({ date, close: v.price }));
  }

  // Ajoute la moyenne mobile sur `win` semaines (null tant que < win points).
  function computeSeries(weekly, win) {
    win = win || 200;
    const closes = weekly.map((w) => w.close);
    return weekly.map((w, i) => {
      let wma = null;
      if (i >= win - 1) {
        let s = 0;
        for (let k = i - win + 1; k <= i; k++) s += closes[k];
        wma = s / win;
      }
      return { date: w.date, close: w.close, wma200: wma };
    });
  }

  // Périodes contiguës où close < wma200. Pour chacune : bornes, nb de semaines,
  // écart le plus bas (le plus négatif) + sa date, et écart moyen. % = (close/wma - 1)*100.
  function belowPeriods(series) {
    const out = [];
    let cur = null;
    for (const p of series) {
      const below = p.wma200 != null && p.close < p.wma200;
      if (below) {
        const dev = (p.close / p.wma200 - 1) * 100;
        if (!cur) cur = { start: p.date, end: p.date, weeks: 0, maxDev: 0, maxDevDate: p.date, sum: 0 };
        cur.end = p.date;
        cur.weeks += 1;
        cur.sum += dev;
        if (dev < cur.maxDev) { cur.maxDev = dev; cur.maxDevDate = p.date; }
      } else if (cur) {
        cur.avgDev = cur.sum / cur.weeks;
        delete cur.sum;
        out.push(cur);
        cur = null;
      }
    }
    if (cur) { cur.avgDev = cur.sum / cur.weeks; delete cur.sum; out.push(cur); }
    return out;
  }

  const api = { mondayOf, resampleWeekly, computeSeries, belowPeriods };
  global.BTCcore = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
