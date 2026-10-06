// Tests de l'extraction audio (docs/audio/mp4audio.js) sur de VRAIS fichiers
// générés par ffmpeg : MP4 classique, faststart, MOV, MP4 fragmentés (3 variantes
// d'offsets), HLS-fMP4 recollé (comme yt-dlp), M4A, multi-pistes, cas d'erreur.
// Vérifie que les paquets audio de sortie sont IDENTIQUES (hash) à la source.
//
//   node test_audio_extract.mjs        (nécessite ffmpeg + ffprobe)

import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, readdirSync, readFileSync, rmSync, openAsBlob } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const { extractAudio, looksLikeMp4 } = require("./docs/audio/mp4audio.js");

let fail = 0;
const ok = (c, m) => { if (!c) { console.log("  ✗ " + m); fail++; } };

const dir = mkdtempSync(join(tmpdir(), "lecons-audio-"));
const f = (name) => join(dir, name);
const ff = (...args) => execFileSync("ffmpeg", ["-v", "error", "-y", ...args], { stdio: ["ignore", "pipe", "pipe"] });
const probe = (file) => JSON.parse(execFileSync("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", file]));
// Hash des paquets audio (sans décodage) : identique <=> copie bit à bit.
const audioHash = (file, idx = 0) =>
  execFileSync("ffmpeg", ["-v", "error", "-i", file, "-map", `0:a:${idx}`, "-c", "copy", "-f", "hash", "-hash", "md5", "-"]).toString().trim();
const decodeErrors = (file) =>
  execFileSync("ffmpeg", ["-v", "error", "-i", file, "-f", "null", "-"], { stdio: ["ignore", "pipe", "pipe"] }).toString();

// Types des boîtes de premier niveau d'un fichier MP4.
function topTypes(buf) {
  const out = [];
  for (let p = 0; p + 8 <= buf.length; p += buf.readUInt32BE(p)) out.push(buf.toString("latin1", p + 4, p + 8));
  return out;
}

const SRC = ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=25", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"];
const VENC = ["-t", "12", "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-pix_fmt", "yuv420p"];
const ENC = [...VENC, "-c:a", "aac", "-b:a", "96k"];

// --- Fixtures ---------------------------------------------------------------
ff(...SRC, ...ENC, f("plain.mp4"));
ff(...SRC, ...ENC, "-movflags", "+faststart", f("faststart.mp4"));
ff(...SRC, ...ENC, "-f", "mov", f("quicktime.mov"));
ff(...SRC, ...ENC, "-movflags", "frag_keyframe+empty_moov+default_base_moof", f("frag_moof.mp4"));
ff(...SRC, ...ENC, "-movflags", "frag_keyframe+empty_moov", f("frag_explicit.mp4"));
// Ni base explicite ni default-base-is-moof : base = fin du traf précédent.
ff(...SRC, ...ENC, "-movflags", "frag_keyframe+empty_moov+omit_tfhd_offset", f("frag_implicit.mp4"));
ff("-f", "lavfi", "-i", "sine=frequency=660:sample_rate=48000", "-t", "12", "-ac", "1", "-c:a", "aac", f("audio.m4a"));
ff(...SRC.slice(0, 4), ...VENC, f("video_only.mp4"));
ff(...SRC, "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100", ...ENC, "-map", "0:v", "-map", "1:a", "-map", "2:a", f("two_audio.mp4"));
// HLS en fMP4 audio seul (rendu « audio » de Vimeo/HLS), recollé init + segments
// exactement comme le fait yt-dlp sans ffmpeg.
ff("-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000", "-t", "12", "-c:a", "aac", "-b:a", "128k",
  "-f", "hls", "-hls_segment_type", "fmp4", "-hls_time", "2", "-hls_playlist_type", "vod",
  "-hls_fmp4_init_filename", "init.mp4", "-hls_segment_filename", f("seg%03d.m4s"), f("hls.m3u8"));
{
  const segs = readdirSync(dir).filter((n) => n.endsWith(".m4s")).sort();
  writeFileSync(f("hls_joined.mp4"), Buffer.concat([readFileSync(f("init.mp4")), ...segs.map((s) => readFileSync(f(s)))]));
}
ff("-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-c:a", "libmp3lame", f("song.mp3"));

async function run(name, title) {
  const blob = await openAsBlob(f(name));
  const res = await extractAudio(blob, { title });
  const out = f(name + ".out.m4a");
  writeFileSync(out, Buffer.from(await res.blob.arrayBuffer()));
  return { res, out };
}

// --- Cas nominaux : paquets identiques, 1 seule piste audio, décodage propre ---
const cases = [
  ["plain.mp4", 0, false],
  ["faststart.mp4", 0, false],
  ["quicktime.mov", 0, false],
  ["frag_moof.mp4", 0, true],
  ["frag_explicit.mp4", 0, true],
  ["frag_implicit.mp4", 0, true],
  ["audio.m4a", 0, false],
  ["two_audio.mp4", 0, false],
  ["hls_joined.mp4", 0, true],
];
for (const [name, idx, fragmented] of cases) {
  const { res, out } = await run(name, "Leçon test " + name);
  const p = probe(out);
  const src = probe(f(name)).streams.filter((s) => s.codec_type === "audio")[idx];
  ok(p.streams.length === 1 && p.streams[0].codec_type === "audio", `${name} : une seule piste, audio`);
  ok(p.streams[0].codec_name === "aac", `${name} : codec AAC conservé`);
  ok(audioHash(out) === audioHash(f(name), idx), `${name} : paquets audio identiques à la source`);
  ok(decodeErrors(out) === "", `${name} : décodage sans erreur`);
  ok(Math.abs(Number(p.format.duration) - 12) < 0.15, `${name} : durée ≈ 12 s (${p.format.duration})`);
  ok(Math.abs(res.duration - 12) < 0.15, `${name} : durée calculée ≈ 12 s (${res.duration})`);
  ok(res.fragmented === fragmented, `${name} : fragmented=${fragmented}`);
  ok(res.codec === "mp4a", `${name} : codec mp4a détecté`);
  ok(p.format.tags && p.format.tags.title === "Leçon test " + name, `${name} : titre écrit dans les métadonnées`);
  ok(res.blob.size < (await openAsBlob(f(name))).size || name.endsWith(".m4a") || name.startsWith("hls"), `${name} : plus léger que la vidéo`);
  // Le fichier de sortie ne doit plus être fragmenté (lecture/seek fiables partout).
  ok(topTypes(readFileSync(out)).join(",") === "ftyp,moov,mdat", `${name} : sortie « à plat » ftyp+moov+mdat (${topTypes(readFileSync(out))})`);
}
// Mono 48 kHz : métadonnées remontées.
{
  const { res } = await run("audio.m4a");
  ok(res.channels === 1 && res.sampleRate === 48000, "audio.m4a : mono 48 kHz détecté");
}
// Multi-pistes : on prend bien la 1re (440 Hz) et pas la 2e (880 Hz).
{
  const { out } = await run("two_audio.mp4");
  ok(audioHash(out) !== audioHash(f("two_audio.mp4"), 1), "two_audio : ne prend pas la 2e piste");
}

// --- Cas d'erreur -------------------------------------------------------------
async function expectError(blob, code, label) {
  try { await extractAudio(blob); ok(false, `${label} : aurait dû échouer (${code})`); }
  catch (e) { ok(e.code === code, `${label} : erreur ${code} (reçu ${e.code} — ${e.message})`); }
}
await expectError(await openAsBlob(f("video_only.mp4")), "no_audio", "vidéo sans son");
await expectError(await openAsBlob(f("song.mp3")), "not_mp4", "fichier MP3");
await expectError(new Blob(["<html>pas une vidéo</html>"]), "not_mp4", "page HTML");
{
  const full = readFileSync(f("faststart.mp4"));
  await expectError(new Blob([full.subarray(0, Math.floor(full.length / 2))]), "truncated", "vidéo tronquée");
  const plain = readFileSync(f("plain.mp4")); // moov en fin de fichier -> perdu si tronqué
  await expectError(new Blob([plain.subarray(0, Math.floor(plain.length / 2))]), "no_moov", "vidéo tronquée (moov en fin)");
}
ok(await looksLikeMp4(await openAsBlob(f("plain.mp4"))), "looksLikeMp4 : MP4");
ok(await looksLikeMp4(await openAsBlob(f("quicktime.mov"))), "looksLikeMp4 : MOV");
ok(!(await looksLikeMp4(await openAsBlob(f("song.mp3")))), "looksLikeMp4 : MP3 = non");

// --- Outils de réécriture de fichiers MP4 (cas difficiles à produire avec ffmpeg)
const CONT = new Set(["moov", "trak", "mdia", "minf", "stbl", "edts", "dinf"]);
function tree(buf, s = 0, e = buf.length) {
  const out = [];
  for (let p = s; p + 8 <= e;) {
    const size = buf.readUInt32BE(p), type = buf.toString("latin1", p + 4, p + 8);
    out.push(CONT.has(type) ? { type, kids: tree(buf, p + 8, p + size) } : { type, raw: buf.subarray(p, p + size) });
    p += size;
  }
  return out;
}
function ser(n) {
  if (n.raw) return n.raw;
  const body = Buffer.concat(n.kids.map(ser));
  const h = Buffer.alloc(8);
  h.writeUInt32BE(body.length + 8);
  h.write(n.type, 4, "latin1");
  return Buffer.concat([h, body]);
}
const mapTree = (nodes, fn) => nodes.map((n) => fn(n.kids ? { ...n, kids: mapTree(n.kids, fn) } : n));
const findAfter = (buf, what, after) => buf.indexOf(Buffer.from(what, "latin1"), buf.indexOf(Buffer.from(after, "latin1")));

// QuickTime : la description audio v1 (esds dans « wave ») devient ISO v0 (esds direct).
{
  const { out } = await run("quicktime.mov");
  const b = readFileSync(out);
  const e = findAfter(b, "mp4a", "stsd") - 4;
  ok(b.readUInt16BE(e + 16) === 0, "MOV : description audio convertie en ISO v0");
  ok(b.toString("latin1", e + 40, e + 44) === "esds", "MOV : esds directement dans mp4a (plus de « wave »)");
  ok(!b.includes(Buffer.from("wave")), "MOV : bloc QuickTime « wave » retiré");
}

// Vidéo > 4 Go : offsets 64 bits (co64) et mdat à taille 64 bits en ENTRÉE.
{
  const src = readFileSync(f("plain.mp4"));
  const top = tree(src);
  const SHIFT = 8; // l'en-tête de mdat passe de 8 à 16 octets
  const moov = mapTree(top.filter((n) => n.type === "moov"), (n) => {
    if (n.type !== "stco") return n;
    const count = n.raw.readUInt32BE(12);
    const co = Buffer.alloc(16 + 8 * count);
    co.writeUInt32BE(co.length); co.write("co64", 4, "latin1"); co.writeUInt32BE(count, 12);
    for (let i = 0; i < count; i++) co.writeBigUInt64BE(BigInt(n.raw.readUInt32BE(16 + 4 * i) + SHIFT), 16 + 8 * i);
    return { type: "co64", raw: co };
  });
  const parts = top.map((n) => {
    if (n.type === "moov") return ser(moov[0]);
    if (n.type !== "mdat") return ser(n);
    const h = Buffer.alloc(16);
    h.writeUInt32BE(1); h.write("mdat", 4, "latin1"); h.writeBigUInt64BE(BigInt(n.raw.length - 8 + 16), 8);
    return Buffer.concat([h, n.raw.subarray(8)]);
  });
  writeFileSync(f("big64.mp4"), Buffer.concat(parts));
  ok(audioHash(f("big64.mp4")) === audioHash(f("plain.mp4")), "fichier 64 bits valide pour ffmpeg (contrôle)");
  const { out } = await run("big64.mp4", "64 bits");
  ok(audioHash(out) === audioHash(f("plain.mp4")), "co64 + mdat 64 bits en entrée : paquets identiques");
}

// Piste désactivée en premier : on prend la piste audio ACTIVÉE (2e, 880 Hz).
{
  ff(...SRC, "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100", ...ENC, "-map", "0:v", "-map", "1:a", "-map", "2:a",
    "-disposition:a:0", "0", "-disposition:a:1", "default", f("second_enabled.mp4"));
  const { out } = await run("second_enabled.mp4");
  ok(audioHash(out) === audioHash(f("second_enabled.mp4"), 1), "piste activée choisie plutôt que la 1re désactivée");
}

// Nouveaux cas d'erreur : moov coupé, DRM, codec non pris en charge, table géante.
{
  const plain = readFileSync(f("plain.mp4"));
  await expectError(new Blob([plain.subarray(0, plain.length - 50)]), "truncated", "moov coupé en fin de fichier");
  const patch = (name, what, after, by) => {
    const b = Buffer.from(readFileSync(f(name)));
    b.write(by, findAfter(b, what, after), "latin1");
    return new Blob([b]);
  };
  await expectError(patch("audio.m4a", "mp4a", "stsd", "enca"), "drm", "audio chiffré (DRM)");
  await expectError(patch("audio.m4a", "mp4a", "stsd", "sowt"), "codec", "PCM QuickTime refusé (sinon son corrompu)");
  const b = Buffer.from(readFileSync(f("faststart.mp4")));
  const stsz = b.indexOf(Buffer.from("stsz"), b.indexOf(Buffer.from("stsz")) + 4); // 2e = piste audio
  b.writeUInt32BE(0x7fffffff, stsz + 12);
  await expectError(new Blob([b]), "corrupt", "nombre d'échantillons absurde (pas d'allocation géante)");
}

// Fuzzing : des fichiers corrompus au hasard ne doivent JAMAIS planter, seulement
// produire une Mp4Error (ou réussir), et rapidement.
{
  let seed = 2026;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  let bad = 0, slow = 0, runs = 0;
  for (const name of ["faststart.mp4", "frag_moof.mp4", "quicktime.mov", "hls_joined.mp4"]) {
    const src = readFileSync(f(name));
    const moov = src.indexOf(Buffer.from("moov")) - 4;
    for (let it = 0; it < 250; it++) {
      const b = Buffer.from(src);
      for (let k = 0, n = 1 + Math.floor(rnd() * 4); k < n; k++) {
        const at = rnd() < 0.8 ? moov + Math.floor(rnd() * 4000) : Math.floor(rnd() * b.length);
        if (at < b.length) b[at] = rnd() < 0.5 ? 0xff : Math.floor(rnd() * 256);
      }
      const t0 = Date.now();
      try { await extractAudio(new Blob([b])); } catch (e) { if (!e.code) { bad++; if (bad < 4) console.log("   ", e); } }
      if (Date.now() - t0 > 1000) slow++;
      runs++;
    }
  }
  ok(bad === 0, `fuzzing : ${bad} erreur(s) non contrôlée(s) sur ${runs} fichiers corrompus`);
  ok(slow === 0, `fuzzing : ${slow} analyse(s) > 1 s`);
}

// Performance : 10 min en fragments d'1 s (600 moof) analysées vite.
{
  ff("-f", "lavfi", "-i", "sine=frequency=500:sample_rate=48000", "-t", "600", "-c:a", "aac", "-b:a", "64k",
    "-movflags", "frag_keyframe+empty_moov+default_base_moof", "-frag_duration", "1000000", f("long_frag.mp4"));
  const t0 = Date.now();
  const { out, res } = await run("long_frag.mp4");
  const ms = Date.now() - t0;
  ok(ms < 3000, `600 fragments analysés en ${ms} ms`);
  ok(Math.abs(res.duration - 600) < 0.2 && audioHash(out) === audioHash(f("long_frag.mp4")), "10 min fragmentées : durée et paquets exacts");
}

rmSync(dir, { recursive: true, force: true });
if (fail) { console.log(`✗ ${fail} échec(s)`); process.exit(1); }
console.log("✓ test_audio_extract : extraction audio OK (MP4, MOV, fMP4, HLS, M4A, 64 bits, DRM, fuzzing, perf)");
