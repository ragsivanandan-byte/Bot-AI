// Test de parité : la simulation JS (docs/sim.js) doit donner exactement les
// mêmes résultats que le moteur Python (strc_dca.py) sur les mêmes données.
//
//   node test_web_parity.mjs
//
// Génère les références Python via `python3 strc_dca.py --json` pour plusieurs
// scénarios, recalcule en JS depuis docs/data/strc.json, et compare.

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { simulate } = require("./docs/sim.js");

const DATA = JSON.parse(readFileSync(new URL("./docs/data/strc.json", import.meta.url)));

const scenarios = [
  { weekly: 1000, dividends: true, reinvest: false },
  { weekly: 1000, dividends: true, reinvest: true },
  { weekly: 500, dividends: false, reinvest: false },
  { weekly: 250, dividends: true, reinvest: false, start: "2026-01-01" },
];

function pyRef(s) {
  const args = ["strc_dca.py", "--no-live", "--json", "--weekly-amount", String(s.weekly)];
  if (!s.dividends) args.push("--no-dividends");
  if (s.reinvest) args.push("--reinvest-dividends");
  if (s.start) args.push("--start", s.start);
  const out = execFileSync("python3", args, { encoding: "utf-8" });
  return JSON.parse(out);
}

function jsRun(s) {
  const par = DATA.par;
  const closes = DATA.weekly_closes.filter((c) => !s.start || c.date >= s.start);
  const schedule = s.dividends ? DATA.dividends : [];
  const apy = s.dividends ? DATA.default_apy : 0;
  return {
    par: simulate(closes, s.weekly, "par", schedule, apy, s.reinvest, par),
    closing: simulate(closes, s.weekly, "closing", schedule, apy, s.reinvest, par),
  };
}

let failures = 0;
const approx = (a, b, tol = 1e-6) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(a), Math.abs(b));

function check(name, jsVal, pyVal) {
  if (!approx(jsVal, pyVal)) {
    console.log(`  ✗ ${name}: JS=${jsVal}  PY=${pyVal}`);
    failures++;
  }
}

for (const s of scenarios) {
  const tag = `weekly=${s.weekly} div=${s.dividends} reinvest=${s.reinvest}${s.start ? " start=" + s.start : ""}`;
  console.log("Scénario:", tag);
  const py = pyRef(s);
  const js = jsRun(s);

  for (const [mode, pyKey] of [["par", "par_mode"], ["closing", "closing_mode"]]) {
    check(`${mode}.invested`, js[mode].invested, py[pyKey].invested);
    check(`${mode}.shares`, js[mode].shares, py[pyKey].shares);
    check(`${mode}.market_value`, js[mode].marketValue, py[pyKey].market_value);
    check(`${mode}.capital_pl`, js[mode].capitalPL, py[pyKey].capital_pl);
    check(`${mode}.total_value`, js[mode].totalValue, py[pyKey].total_value);
    check(`${mode}.total_pl`, js[mode].totalPL, py[pyKey].total_pl);
    check(`${mode}.yield_on_cost`, js[mode].yieldOnCost, py[pyKey].yield_on_cost);
    check(`${mode}.avg_cost`, js[mode].avgCost, py[pyKey].avg_cost);
  }
}

console.log(failures === 0
  ? "\n✓ PARITÉ OK — JS et Python identiques sur tous les scénarios."
  : `\n✗ ${failures} écart(s) détecté(s).`);
process.exit(failures === 0 ? 0 : 1);
