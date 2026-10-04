// Tests navigateur (Chromium headless via Playwright) de Leçons Audio :
//  1) docs/audio/detect.js sur des pages de leçon simulées (Vimeo, lazy-load,
//     shadow DOM, Plyr, Wistia, <video>, iframe même site, rien) + la commande
//     produite, analysée par un vrai shell ;
//  2) l'app docs/audio/ : import MP4 -> audio identique à l'extraction Node,
//     lecture, vitesse, reprise après rechargement, hors ligne (service worker),
//     menu (renommer/supprimer), erreurs.
//
//   NODE_PATH=$(npm root -g) node test_audio_browser.mjs   (Playwright + ffmpeg)

import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { mkdtempSync, readFileSync, writeFileSync, chmodSync, rmSync, openAsBlob } from "node:fs";
import { tmpdir } from "node:os";
import { join, extname, resolve } from "node:path";

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require("playwright"); } catch (e) {
  console.log("↷ test_audio_browser ignoré : Playwright introuvable (NODE_PATH=$(npm root -g) ?)");
  process.exit(0);
}
const { extractAudio } = require("./docs/audio/mp4audio.js");

let fail = 0;
const ok = (c, m) => { if (!c) { console.log("  ✗ " + m); fail++; } };

const DOCS = resolve("docs");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css",
  ".png": "image/png", ".webmanifest": "application/manifest+json", ".json": "application/json" };
const server = createServer((req, res) => {
  let p = join(DOCS, decodeURIComponent(new URL(req.url, "http://x").pathname));
  if (p.endsWith("/")) p += "index.html";
  if (!p.startsWith(DOCS)) { res.writeHead(403).end(); return; }
  try { const body = readFileSync(p); res.writeHead(200, { "Content-Type": TYPES[extname(p)] || "application/octet-stream" }); res.end(body); }
  catch (e) { res.writeHead(404).end(); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

const tmp = mkdtempSync(join(tmpdir(), "lecons-audio-web-"));
const browser = await playwright.chromium.launch();

// ---------------------------------------------------------------------------
// 1) Détection de la vidéo sur la page de la leçon
// ---------------------------------------------------------------------------
const detectSrc = readFileSync("docs/audio/detect.js", "utf-8");
const LESSON = "https://academiaolivervelez.com/lecciones/2026-09-20-bitcoin-talk-life-discord/";

async function detect(html, { url = LESSON, setup, inner } = {}) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.route("**/*", (route) => {
    const u = route.request().url();
    if (u === url) return route.fulfill({ contentType: "text/html; charset=utf-8", body: html });
    if (inner && u.endsWith("/inner.html")) return route.fulfill({ contentType: "text/html; charset=utf-8", body: inner });
    return route.fulfill({ contentType: "text/html", body: "<html><body></body></html>" });
  });
  await page.goto(url);
  if (setup) await page.evaluate(setup);
  await page.waitForTimeout(100);
  const command = await page.evaluate((src) => new Promise((done) => { window.completion = done; (0, eval)(src); }), detectSrc);
  const candidates = await page.evaluate(() => window.__leconsAudio.candidates.map((c) => c.url));
  await ctx.close();
  return { command, candidates };
}

// Faux yt-dlp : affiche ses arguments tels que le shell les lui transmet.
const fakeBin = join(tmp, "bin");
execFileSync("mkdir", ["-p", fakeBin]);
writeFileSync(join(fakeBin, "yt-dlp"), "#!/usr/bin/env python3\nimport sys, json\nprint(json.dumps(sys.argv[1:]))\n");
chmodSync(join(fakeBin, "yt-dlp"), 0o755);
const shellArgs = (command) => JSON.parse(execFileSync("bash", ["-c", command], {
  env: { ...process.env, PATH: fakeBin + ":" + process.env.PATH, HOME: "/home/iphone" } }).toString());
const urlArg = (args) => args[args.length - 1];

const page1 = `<!doctype html><html><head><title>Bitcoin Talk – Academia Oliver L. Velez</title></head><body>
  <header><video autoplay muted loop playsinline src="/wp-content/uploads/hero.mp4" style="width:900px;height:300px"></video></header>
  <main><h1>2026-09-20 Bitcoin Talk Life Discord</h1>
    <div class="ld-video" data-video-progression="true" data-video-provider="vimeo">
      <iframe src="https://player.vimeo.com/video/1012345678?h=abc123def&amp;badge=0&amp;autopause=0&amp;player_id=0&amp;app_id=58479"
        width="800" height="450" allow="autoplay; fullscreen" style="width:800px;height:450px"></iframe>
    </div></main>
  <aside><iframe src="https://www.youtube.com/embed/AAAAAAAAAAA" style="width:300px;height:170px"></iframe></aside>
</body></html>`;
{
  const { command, candidates } = await detect(page1);
  const args = shellArgs(command);
  ok(urlArg(args) === "https://player.vimeo.com/video/1012345678?h=abc123def", `Vimeo choisi (le plus grand) : ${urlArg(args)}`);
  ok(!candidates.some((c) => c.includes("hero.mp4")), "vidéo décorative (autoplay muet en boucle) ignorée");
  ok(candidates.includes("https://www.youtube.com/watch?v=AAAAAAAAAAA"), "YouTube secondaire détecté mais non prioritaire");
  ok(args[args.indexOf("--referer") + 1] === LESSON, "referer = page de la leçon");
  ok(args[args.indexOf("-o") + 1] === "2026-09-20-bitcoin-talk-life-discord.%(ext)s", "nom de fichier = slug de la leçon");
  ok(args[args.indexOf("-f") + 1] === "ba[ext=m4a]/ba/b[ext=mp4]/b", "format : audio seul en priorité");
  ok(args[args.indexOf("-P") + 1] === "/home/iphone/Documents/Lecons-Audio", "dossier : ~/Documents/Lecons-Audio");
  ok(args[0] === "--no-playlist", "commande yt-dlp bien formée");
}
{
  const { command } = await detect(`<body><div><iframe data-src="https://player.vimeo.com/video/42?h=ff00" class="lazyload"></iframe></div></body>`);
  ok(urlArg(shellArgs(command)) === "https://player.vimeo.com/video/42?h=ff00", "iframe Vimeo en lazy-load (data-src)");
}
{
  const { command } = await detect(`<body><div data-plyr-provider="vimeo" data-plyr-embed-id="76979871"></div></body>`);
  ok(urlArg(shellArgs(command)) === "https://player.vimeo.com/video/76979871", "lecteur Plyr (data-plyr-*)");
}
{
  const setup = () => {
    customElements.define("presto-player", class extends HTMLElement {
      constructor() { super(); this.attachShadow({ mode: "open" }).innerHTML = '<iframe src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?rel=0" style="width:640px;height:360px"></iframe>'; }
    });
    document.body.appendChild(document.createElement("presto-player"));
  };
  const { command } = await detect(`<body></body>`, { setup });
  ok(urlArg(shellArgs(command)) === "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "iframe dans un shadow DOM (Presto Player)");
}
{
  const { command } = await detect(`<body><div class="wistia_responsive_padding"><div class="wistia_embed wistia_async_abc123xyz videoFoam=true" style="width:640px;height:360px"></div></div></body>`);
  ok(urlArg(shellArgs(command)) === "https://fast.wistia.net/embed/iframe/abc123xyz", "Wistia (classe wistia_async_)");
}
{
  const { command } = await detect(`<body><video controls style="width:640px;height:360px"><source src="/wp-content/uploads/2026/09/talk.mp4" type="video/mp4"></video></body>`);
  ok(urlArg(shellArgs(command)) === "https://academiaolivervelez.com/wp-content/uploads/2026/09/talk.mp4", "<video><source> MP4 auto-hébergé");
}
{
  const inner = `<body><video controls src="https://cdn.example.net/hls/master.m3u8"></video></body>`;
  const { command } = await detect(`<body><iframe src="/inner.html"></iframe></body>`, { inner });
  ok(urlArg(shellArgs(command)) === "https://cdn.example.net/hls/master.m3u8", "vidéo HLS dans une iframe du même site");
}
{
  const { command } = await detect(`<body><p>Pas de vidéo ici.</p><iframe src="https://www.google.com/maps/embed?pb=1"></iframe></body>`);
  ok(/^echo /.test(command), "aucune vidéo -> simple message (pas de yt-dlp)");
  ok(execFileSync("bash", ["-c", command]).toString().includes("Aucune video trouvee"), "message lisible dans a-Shell");
}
{
  // Apostrophes / caractères spéciaux : aucune injection possible dans la commande.
  const url = "https://academiaolivervelez.com/lecciones/l'%C3%A9con%20%24(rm%20-rf)%20%60x%60/";
  const { command } = await detect(`<body><iframe src="https://player.vimeo.com/video/7?h=1'2;echo%20pwned" style="width:10px;height:10px"></iframe></body>`, { url });
  const args = shellArgs(command);
  ok(args.length === 12, `apostrophes neutralisées (${args.length} arguments)`);
  ok(args[args.indexOf("-o") + 1] === "l-econ-rm-rf-x.%(ext)s", `nom de fichier assaini : ${args[args.indexOf("-o") + 1]}`);
  ok(!args.join(" ").includes("pwned\n"), "pas d'exécution de commande injectée");
}

// ---------------------------------------------------------------------------
// 2) L'application
// ---------------------------------------------------------------------------
const ff = (...a) => execFileSync("ffmpeg", ["-v", "error", "-y", ...a]);
const mp4 = join(tmp, "2026-09-20-bitcoin-talk-life-discord.mp4");
ff("-f", "lavfi", "-i", "testsrc=size=320x240:rate=25", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
  "-t", "12", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", mp4);
const mp3 = join(tmp, "lecon-test.mp3");
ff("-f", "lavfi", "-i", "sine=frequency=330:sample_rate=44100", "-t", "20", "-c:a", "libmp3lame", mp3);
const silent = join(tmp, "video-sans-son.mp4");
ff("-f", "lavfi", "-i", "testsrc=size=160x120:rate=10", "-t", "2", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", silent);
const expected = await extractAudio(await openAsBlob(mp4), { title: "Bitcoin talk life discord" });
const expectedHash = createHash("sha256").update(Buffer.from(await expected.blob.arrayBuffer())).digest("hex");

const ctx = await browser.newContext({ ...playwright.devices["iPhone 13"], serviceWorkers: "allow" });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(BASE + "/audio/");
await page.waitForSelector("#empty:not([hidden])");
ok(await page.isVisible("#install-tip"), "iPhone dans Safari : conseil « Sur l'écran d'accueil » affiché");

const readDb = () => page.evaluate(async () => {
  const db = await new Promise((res, rej) => { const r = indexedDB.open("lecons-audio"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
  const get = (store, fn) => new Promise((res) => { const r = fn(db.transaction(store).objectStore(store)); r.onsuccess = () => res(r.result); });
  const tracks = await get("tracks", (s) => s.getAll());
  const out = [];
  for (const t of tracks) {
    const blob = await get("blobs", (s) => s.get(t.id));
    const h = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
    out.push({ ...t, hash: [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("") });
  }
  db.close();
  return out;
});

// Import MP4 -> audio
await page.click("#tab-add");
await page.setInputFiles("#file", mp4);
await page.waitForSelector(".track");
{
  const db = await readDb();
  ok(db.length === 1, "1 leçon en bibliothèque");
  ok(db[0].hash === expectedHash, "audio stocké identique à l'extraction Node (octet par octet)");
  ok(db[0].mime === "audio/mp4" && Math.abs(db[0].duration - 12) < 0.2, `métadonnées : ${db[0].mime}, ${db[0].duration} s`);
  ok(db[0].title === "Bitcoin talk life discord" && db[0].date === "2026-09-20", "titre + date tirés du nom de fichier");
  const meta = await page.textContent(".track .t-meta");
  ok(meta.includes("20/09/2026") && meta.includes("12 s"), `ligne de la leçon : ${meta}`);
  ok(await page.isVisible("#library"), "retour automatique à la bibliothèque");
}

// Erreurs d'import
await page.click("#tab-add");
await page.setInputFiles("#file", { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("bonjour") });
await page.waitForSelector(".job.err");
await page.setInputFiles("#file", silent);
await page.waitForFunction(() => document.querySelectorAll(".job.err").length === 2);
{
  const errs = await page.$$eval(".job.err .j-state", (els) => els.map((e) => e.textContent));
  ok(errs.some((t) => t.includes("Aucune piste audio")), "vidéo sans son -> message clair");
  ok(errs.some((t) => t.includes("ni une vidéo")), "fichier texte -> refusé");
}

// Import MP3 + lecture (Chromium de test sans AAC : on lit le MP3)
await page.setInputFiles("#file", mp3);
await page.waitForFunction(() => document.querySelectorAll(".track").length === 2);
await page.click('.track:has-text("Lecon test") .track-main');
await page.waitForFunction(() => { const a = document.getElementById("audio"); return a.duration > 19 && a.currentTime > 0.3; }, null, { timeout: 15000 });
ok(await page.isVisible("#player"), "lecteur affiché");
ok((await page.textContent("#p-title")) === "Lecon test", "titre dans le lecteur");
await page.click("#p-speed");
ok(await page.evaluate(() => document.getElementById("audio").playbackRate) === 1.25, "vitesse 1,25×");
ok((await page.textContent("#p-speed")) === "1,25×", "libellé vitesse « 1,25× »");
await page.evaluate(() => { document.getElementById("audio").currentTime = 10; });
await page.waitForFunction(() => document.getElementById("audio").currentTime >= 10);
await page.click("#p-play"); // pause -> position enregistrée
await page.waitForTimeout(300);
{
  const t = (await readDb()).find((x) => x.title === "Lecon test");
  ok(t.position >= 10 && t.position < 12, `position enregistrée (${t.position.toFixed(1)} s)`);
}

// Hors ligne : rechargement sans réseau, bibliothèque + reprise de lecture
await page.evaluate(() => navigator.serviceWorker.ready);
await page.reload();
await page.waitForFunction(() => !!navigator.serviceWorker.controller);
await ctx.setOffline(true);
await page.reload();
await page.waitForSelector(".track");
ok((await page.$$(".track")).length === 2, "hors ligne : app + bibliothèque disponibles");
ok(await page.evaluate(() => getComputedStyle(document.querySelector(".pick")).borderStyle) === "dashed", "hors ligne : styles chargés depuis le cache");
await page.click('.track:has-text("Lecon test") .track-main');
await page.waitForFunction(() => { const a = document.getElementById("audio"); return a.duration > 19 && a.currentTime >= 10; }, null, { timeout: 15000 });
ok(await page.evaluate(() => document.getElementById("audio").playbackRate) === 1.25, "vitesse mémorisée");
ok(true, "reprise de lecture à la position enregistrée");
await page.click("#tab-help");
await page.waitForFunction(() => document.getElementById("script-code").textContent.length > 1000);
ok((await page.textContent("#script-code")) === detectSrc, "mode d'emploi : script du raccourci disponible hors ligne");
await page.screenshot({ path: join(tmp, "help.png"), fullPage: true });
await ctx.setOffline(false);

// Menu : renommer puis supprimer
await page.click("#tab-library");
await page.click('.track:has-text("Bitcoin") .t-more');
page.once("dialog", (d) => d.accept("Bitcoin Talk — 20 sept."));
await page.click('#menu [data-act="rename"]');
await page.waitForSelector('.track:has-text("Bitcoin Talk — 20 sept.")');
ok(true, "renommage");
await page.screenshot({ path: join(tmp, "library.png") });
await page.click('.track:has-text("Bitcoin Talk") .t-more');
page.once("dialog", (d) => d.accept());
await page.click('#menu [data-act="delete"]');
await page.waitForFunction(() => document.querySelectorAll(".track").length === 1);
ok((await readDb()).length === 1, "suppression (bibliothèque + fichier)");

ok(errors.length === 0, "aucune erreur JavaScript : " + errors.join(" | "));

await browser.close();
server.close();
if (process.env.KEEP_SCREENSHOTS) console.log("captures :", tmp); else rmSync(tmp, { recursive: true, force: true });
if (fail) { console.log(`✗ ${fail} échec(s)`); process.exit(1); }
console.log("✓ test_audio_browser : détection + app (import, lecture, reprise, hors ligne, menu) OK");
