// Tests de la logique BTC/EUR pure (docs/btc_core.js) avec des données
// synthétiques aux résultats vérifiables à la main. Aucune dépendance réseau.
//   node test_btc_core.mjs

import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { resampleWeekly, computeSeries, belowPeriods, mondayOf } = require("./docs/btc_core.js");

let fail = 0;
const ok = (c, m) => { if (!c) { console.log("  ✗ " + m); fail++; } };
const approx = (a, b, t = 1e-9) => Math.abs(a - b) <= t;

const DAY = 86400000;
const d = (s) => Date.parse(s + "T00:00:00Z");

// 1) mondayOf : un mercredi -> lundi de la même semaine
ok(mondayOf(d("2015-01-07")).toISOString().slice(0, 10) === "2015-01-05", "mondayOf mercredi -> lundi");
ok(mondayOf(d("2015-01-05")).toISOString().slice(0, 10) === "2015-01-05", "mondayOf lundi -> lundi");

// 2) resampleWeekly : prend le DERNIER prix de chaque semaine
{
  const prices = [
    [d("2015-01-05"), 100], [d("2015-01-07"), 110], [d("2015-01-11"), 120], // semaine du 05/01 -> 120 (dim 11)
    [d("2015-01-12"), 130], [d("2015-01-14"), 140],                          // semaine du 12/01 -> 140
  ];
  const w = resampleWeekly(prices);
  ok(w.length === 2, "resample : 2 semaines");
  ok(w[0].date === "2015-01-05" && w[0].close === 120, "resample : clôture = dernier prix (120)");
  ok(w[1].date === "2015-01-12" && w[1].close === 140, "resample : 2e semaine (140)");
}

// 3) computeSeries : wma null avant 200 points, = moyenne ensuite
{
  const weekly = Array.from({ length: 205 }, (_, i) => ({ date: "w" + i, close: 100 }));
  const s = computeSeries(weekly, 200);
  ok(s[198].wma200 === null, "wma null à 199 semaines");
  ok(approx(s[199].wma200, 100), "wma = 100 à 200 semaines constantes");
  // moyenne mobile correcte avec une rampe
  const ramp = Array.from({ length: 200 }, (_, i) => ({ date: "r" + i, close: i + 1 })); // 1..200
  const sr = computeSeries(ramp, 200);
  ok(approx(sr[199].wma200, (1 + 200) / 2), "wma rampe = moyenne 1..200 = 100.5");
}

// 4) belowPeriods : une période sous la WMA détectée avec écart correct
{
  // 200 semaines à 100 (wma=100 à i=199), puis 3 semaines à 80, puis 2 à 120.
  const closes = [];
  for (let i = 0; i < 200; i++) closes.push(100);
  closes.push(80, 80, 80, 120, 120);
  const weekly = closes.map((c, i) => ({ date: "2020-01-" + String(i + 1).padStart(2, "0"), close: c }));
  const series = computeSeries(weekly, 200);
  // À i=200 (1er 80) : wma = moyenne des semaines 1..200 (200 valeurs : 199×100 + 1×80)/200 = 99.9
  ok(approx(series[200].wma200, 99.9), "wma au 1er creux = 99.9");
  const periods = belowPeriods(series);
  ok(periods.length === 1, "1 seule période sous la WMA");
  if (periods.length) {
    ok(periods[0].weeks === 3, "période = 3 semaines");
    // La WMA descend à mesure que les 80 entrent dans la fenêtre, donc l'écart
    // le PLUS négatif est à la 1re semaine sous la WMA (i=200), pas la dernière.
    const expectedMax = (80 / series[200].wma200 - 1) * 100;
    ok(approx(periods[0].maxDev, expectedMax), "écart max = creux le plus profond (1re semaine)");
    ok(periods[0].maxDevDate === series[200].date, "date du creux = 1re semaine sous la WMA");
    ok(periods[0].maxDev < 0 && periods[0].avgDev < 0, "écarts négatifs (sous la WMA)");
  }
}

// 5) Pas de période quand tout est au-dessus
{
  const weekly = Array.from({ length: 210 }, (_, i) => ({ date: "x" + i, close: 100 + i })); // toujours croissant
  const periods = belowPeriods(computeSeries(weekly, 200));
  ok(periods.length === 0, "aucune période quand le prix est toujours >= wma");
}

console.log(fail === 0 ? "✓ BTC core OK — resample, 200WMA et périodes sous la WMA validés." : `✗ ${fail} échec(s).`);
process.exit(fail ? 1 : 0);
