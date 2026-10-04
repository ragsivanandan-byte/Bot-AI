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
import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { mkdtempSync, readFileSync, writeFileSync, chmodSync, rmSync, readdirSync, openAsBlob } from "node:fs";
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
let MEDIA = null; // fichiers de test servis sous /media/ (chaîne yt-dlp)
const server = createServer((req, res) => {
  const pathname = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const root = MEDIA && pathname.startsWith("/media/") ? MEDIA : DOCS;
  let p = join(root, root === MEDIA ? pathname.slice(7) : pathname);
  if (p.endsWith("/")) p += "index.html";
  if (!p.startsWith(root)) { res.writeHead(403).end(); return; }
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
{
  // Même vidéo Vimeo en double (attribut sans hash autour de l'iframe avec hash,
  // plus grand) : on doit garder le hash, sinon une vidéo non listée échoue.
  const { command, candidates } = await detect(`<body><div data-vimeo-id="76979871" style="width:900px;height:520px">
    <iframe src="https://player.vimeo.com/video/76979871?h=abc123&amp;badge=0" style="width:800px;height:450px"></iframe></div></body>`);
  ok(urlArg(shellArgs(command)) === "https://player.vimeo.com/video/76979871?h=abc123", "Vimeo : hash conservé malgré le doublon");
  ok(candidates.length === 1, `Vimeo : doublon fusionné (${candidates.length})`);
}
{
  const { command } = await detect(`<body><div class="lesson" data-video-url="https://vimeo.com/1012345678/9f8e7d6c5b" style="width:640px;height:360px"></div></body>`);
  ok(urlArg(shellArgs(command)) === "https://player.vimeo.com/video/1012345678?h=9f8e7d6c5b", "data-video-url vimeo.com/ID/HASH -> lecteur intégré");
}
{
  // Lecteur HLS en JavaScript (src « blob: ») : le .m3u8 chargé l'emporte sur un petit YouTube.
  const setup = async () => {
    const v = document.createElement("video");
    v.controls = true;
    v.style.cssText = "width:800px;height:450px";
    v.src = URL.createObjectURL(new MediaSource());
    document.body.appendChild(v);
    await fetch("https://stream.example.net/v/abc/master.m3u8?token=xyz", { mode: "no-cors" });
  };
  const { command } = await detect(`<body><aside><iframe src="https://www.youtube.com/embed/BBBBBBBBBBB" style="width:300px;height:170px"></iframe></aside></body>`, { setup });
  ok(urlArg(shellArgs(command)) === "https://stream.example.net/v/abc/master.m3u8?token=xyz", "vidéo HLS en blob: -> flux .m3u8 chargé choisi");
}
{
  const { command } = await detect(`<head><script src="https://player.vimeo.com/api/player.js"></script></head>
    <body><a href="https://vimeo.com/">Vimeo</a><iframe src="https://www.youtube.com/embed/videoseries?list=PL123" style="width:640px;height:360px"></iframe></body>`);
  ok(/^echo /.test(command), "ni player.js de Vimeo ni playlist YouTube pris pour une vidéo");
}
{
  // Une erreur inattendue ne doit jamais bloquer le raccourci : completion() est appelée.
  const setup = () => { Document.prototype.querySelectorAll = () => { throw new Error("boom"); }; };
  const { command } = await detect(`<body><iframe src="https://player.vimeo.com/video/1"></iframe></body>`, { setup });
  ok(/^echo /.test(command) && execFileSync("bash", ["-c", command]).toString().includes("Erreur du script Lecons Audio : boom"), "erreur du script -> message, raccourci débloqué");
}
ok(/^[\x00-\x7f]*$/.test(detectSrc.replace(/\/\/.*$/gm, "").replace(/\/\*.*?\*\//g, "")), "script du raccourci en ASCII (hors commentaires) : copier-coller sûr");

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

// « Enregistrer dans Fichiers » : sans partage natif -> téléchargement du bon fichier.
await page.evaluate(() => { navigator.canShare = undefined; });
await page.click('.track:has-text("Bitcoin Talk") .t-more');
{
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click('#menu [data-act="share"]')]);
  ok(dl.suggestedFilename() === "2026-09-20 Bitcoin Talk - 20 sept.m4a", `nom du fichier enregistré : ${dl.suggestedFilename()}`);
  const saved = readFileSync(await dl.path());
  ok(createHash("sha256").update(saved).digest("hex") === expectedHash, "fichier enregistré = audio de la bibliothèque");
}
// Marquer comme écoutée / fermer le menu en touchant à côté.
await page.click('.track:has-text("Lecon test") .t-more');
await page.click('#menu [data-act="done"]');
await page.waitForFunction(() => document.querySelector(".track.done") !== null);
ok((await page.textContent('.track:has-text("Lecon test") .t-meta')).includes("écoutée ✓"), "marquée comme écoutée");
await page.click('.track:has-text("Lecon test") .t-more');
await page.mouse.click(5, 5);
ok(await page.evaluate(() => !document.getElementById("menu").open), "menu fermé en touchant à côté");

await page.click('.track:has-text("Bitcoin Talk") .t-more');
page.once("dialog", (d) => d.accept());
await page.click('#menu [data-act="delete"]');
await page.waitForFunction(() => document.querySelectorAll(".track").length === 1);
ok((await readDb()).length === 1, "suppression (bibliothèque + fichier)");

// Vitesses : cycle complet 1,5 → 1,75 → 2 → 0,75 → 1 → 1,25.
{
  const labels = [];
  for (let i = 0; i < 6; i++) { await page.click("#p-speed"); labels.push(await page.textContent("#p-speed")); }
  ok(labels.join(" ") === "1,5× 1,75× 2× 0,75× 1× 1,25×", `cycle des vitesses : ${labels.join(" ")}`);
}
await page.click("#p-close");
ok(await page.isHidden("#player"), "lecteur fermé");

// Doublon refusé ; import multiple ; fichier illisible -> message (pas de silence).
await page.click("#tab-add");
await page.setInputFiles("#file", mp3);
await page.waitForFunction(() => document.querySelector(".job.err .j-state") && [...document.querySelectorAll(".job.err .j-state")].some((e) => e.textContent.includes("Déjà dans la bibliothèque")));
ok(true, "doublon refusé");
const broken = join(tmp, "fichier-abime.mp3");
writeFileSync(broken, Buffer.alloc(4096, 7));
await page.setInputFiles("#file", [mp4, broken]);
await page.waitForFunction(() => document.querySelectorAll(".track").length === 3);
ok((await readDb()).length === 3, "import multiple (2 fichiers d'un coup)");
await page.click('.track:has-text("Fichier abime") .track-main');
await page.waitForFunction(() => document.getElementById("toast").textContent.includes("Lecture impossible"));
ok(true, "fichier illisible -> message « Lecture impossible »");

ok(errors.length === 0, "aucune erreur JavaScript : " + errors.join(" | "));

// ---------------------------------------------------------------------------
// 3) Chaîne complète du raccourci avec le VRAI yt-dlp (facultatif) :
//    YT_DLP="python3 -m yt_dlp" ou yt-dlp dans le PATH.
// ---------------------------------------------------------------------------
const YTDLP = process.env.YT_DLP || (() => { try { execFileSync("yt-dlp", ["--version"]); return "yt-dlp"; } catch (e) { return null; } })();
if (!YTDLP) {
  console.log("↷ chaîne yt-dlp ignorée (yt-dlp absent ; YT_DLP=\"python3 -m yt_dlp\" pour la tester)");
} else {
  MEDIA = join(tmp, "media");
  execFileSync("mkdir", ["-p", join(MEDIA, "hls"), join(tmp, "home")]);
  // Source audio AAC, puis HLS « à la Vimeo » : vidéo et audio en pistes séparées.
  const srcAudio = join(MEDIA, "source.m4a");
  ff("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "20", "-c:a", "aac", "-b:a", "128k", srcAudio);
  ff("-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-i", srcAudio, "-t", "20", "-map", "0:v", "-map", "1:a",
    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "copy",
    "-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod", "-hls_segment_type", "fmp4",
    "-master_pl_name", "master.m3u8", "-var_stream_map", "v:0,agroup:aud a:0,agroup:aud,default:yes",
    "-hls_segment_filename", join(MEDIA, "hls", "stream_%v", "seg%03d.m4s"), join(MEDIA, "hls", "stream_%v", "index.m3u8"));
  execFileSync("cp", [mp4, join(MEDIA, "talk.mp4")]);
  writeFileSync(join(fakeBin, "yt-dlp"), `#!/bin/sh\nexec ${YTDLP} --proxy "" "$@"\n`);
  chmodSync(join(fakeBin, "yt-dlp"), 0o755);
  const hash = (file) => execFileSync("ffmpeg", ["-v", "error", "-i", file, "-map", "0:a:0", "-c", "copy", "-f", "hash", "-"]).toString().trim();
  const cases = [
    ["HLS audio séparé (type Vimeo)", "2026-09-20-bitcoin-talk-life-discord", BASE + "/media/hls/master.m3u8", hash(srcAudio)],
    ["MP4 progressif (auto-hébergé)", "2026-09-27-autre-lecon", BASE + "/media/talk.mp4", hash(mp4)],
  ];
  for (const [label, slug, mediaUrl, expectedAudio] of cases) {
    const { command } = await detect(`<body><video controls style="width:640px;height:360px" src="${mediaUrl}"></video></body>`,
      { url: `https://academiaolivervelez.com/lecciones/${slug}/` });
    // « ~ » entre apostrophes : prouve que yt-dlp le développe lui-même (si a-Shell ne le fait pas).
    const cmd = command.replace("-P ~/Documents/Lecons-Audio", "-P '~/Documents/Lecons-Audio'");
    ok(cmd !== command, `${label} : commande avec dossier ~/Documents/Lecons-Audio`);
    // Asynchrone : le serveur de test tourne dans ce même processus Node.
    await promisify(execFile)("bash", ["-c", cmd], { env: { ...process.env, HOME: join(tmp, "home"), PATH: fakeBin + ":" + process.env.PATH }, timeout: 120000 });
    const dir = join(tmp, "home", "Documents", "Lecons-Audio");
    const file = readdirSync(dir).find((n) => n.startsWith(slug + "."));
    ok(!!file, `${label} : fichier « ${file} » dans ~/Documents/Lecons-Audio`);
    if (!file) continue;
    const streams = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-show_streams", "-of", "json", join(dir, file)])).streams;
    if (label.startsWith("HLS")) ok(streams.length === 1 && streams[0].codec_type === "audio", `${label} : seule la piste audio est téléchargée`);
    const r = await extractAudio(await openAsBlob(join(dir, file)), { title: slug });
    const outFile = join(tmp, slug + ".m4a");
    writeFileSync(outFile, Buffer.from(await r.blob.arrayBuffer()));
    ok(hash(outFile) === expectedAudio, `${label} : audio final identique à la source (bit à bit)`);
  }
}

await browser.close();
server.close();
if (process.env.KEEP_SCREENSHOTS) console.log("captures :", tmp); else rmSync(tmp, { recursive: true, force: true });
if (fail) { console.log(`✗ ${fail} échec(s)`); process.exit(1); }
console.log(`✓ test_audio_browser : détection + app (import, lecture, reprise, hors ligne, menu)${YTDLP ? " + chaîne yt-dlp réelle" : ""} OK`);
