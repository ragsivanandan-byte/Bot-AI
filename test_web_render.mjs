// Test de rendu DOM headless (sans jsdom) : exécute réellement docs/app.js
// avec un faux DOM minimal et un fetch simulé, puis vérifie que le tableau
// comparatif et l'encart d'impact sont bien peuplés sans erreur runtime.
//
//   node test_web_render.mjs

import { readFileSync } from "node:fs";
import vm from "node:vm";

const DATA = JSON.parse(readFileSync(new URL("./docs/data/strc.json", import.meta.url)));
const simSrc = readFileSync(new URL("./docs/sim.js", import.meta.url), "utf-8");
const appSrc = readFileSync(new URL("./docs/app.js", import.meta.url), "utf-8");

// --- Faux DOM minimal -------------------------------------------------------
function makeEl(id) {
  return {
    id, value: "", checked: false, min: "", max: "", innerHTML: "",
    _tbody: null,
    addEventListener() {},
    querySelector(sel) {
      if (sel === "tbody") {
        if (!this._tbody) this._tbody = makeEl(id + ":tbody");
        return this._tbody;
      }
      return makeEl(id + sel);
    },
  };
}

const els = {};
function getEl(id) { return (els[id] ||= makeEl(id)); }

// Valeurs par défaut (équivalent des attributs HTML).
getEl("weekly").value = "1000";
getEl("dividends").checked = true;
getEl("reinvest").checked = false;

const document = {
  getElementById: getEl,
  querySelector: (sel) => (sel === "main" ? getEl("main") : makeEl(sel)),
};

let fetchResolve;
const fetchPromise = new Promise((res) => (fetchResolve = res));
const fetchMock = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(DATA) });

const sandbox = { document, fetch: fetchMock, console, setTimeout, queueMicrotask };
sandbox.globalThis = sandbox;
sandbox.window = sandbox; // dans un navigateur, window EST l'objet global
vm.createContext(sandbox);
vm.runInContext(simSrc, sandbox);
vm.runInContext(appSrc, sandbox);

// Laisse les promesses (fetch.then -> render) se résoudre.
await new Promise((r) => setTimeout(r, 50));

let failures = 0;
function assert(cond, msg) { if (!cond) { console.log("  ✗ " + msg); failures++; } }

const tbody = getEl("compare")._tbody;
assert(tbody && tbody.innerHTML.includes("VALEUR TOTALE"), "tableau comparatif peuplé (VALEUR TOTALE)");
assert(tbody && tbody.innerHTML.includes("Actions STRC"), "ligne Actions STRC présente");
assert(getEl("impact").innerHTML.includes("Impact de la modification"), "encart d'impact peuplé");
assert(getEl("kpis").innerHTML.includes("kpi"), "cartes KPI peuplées");
assert(getEl("chart-portfolio").innerHTML.includes("<svg"), "graphique portefeuille rendu (SVG)");
assert(getEl("chart-price").innerHTML.includes("<svg"), "graphique prix rendu (SVG)");
assert(getEl("datameta").innerHTML.includes("SNAPSHOT") || getEl("datameta").innerHTML.includes("LIVE"),
  "métadonnées de source affichées");
assert(!getEl("main").innerHTML.includes("Erreur de chargement"), "pas d'erreur de chargement");

console.log(failures === 0
  ? "✓ RENDU OK — app.js s'exécute et peuple l'UI sans erreur."
  : `✗ ${failures} problème(s) de rendu.`);
process.exit(failures === 0 ? 0 : 1);
