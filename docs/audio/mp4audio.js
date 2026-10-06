"use strict";
// Extraction de la piste audio d'une vidéo MP4 / MOV / M4V -> fichier .m4a,
// SANS ré-encodage (copie bit à bit des échantillons AAC) et SANS charger la
// vidéo en mémoire : seuls les en-têtes (moov/moof) sont lus, l'audio final est
// un Blob composé de tranches du fichier d'origine. Indispensable sur iPhone
// où une vidéo d'1 h pèse plusieurs centaines de Mo.
//
// Gère : MP4 classique (moov au début ou à la fin), MOV QuickTime (vidéos
// iPhone, enregistrements d'écran), MP4 fragmenté (DASH/HLS-fMP4, fichiers
// téléchargés par yt-dlp), fichiers déjà audio (M4A), tailles 64 bits (> 4 Go).
// Un fichier corrompu produit toujours une Mp4Error (jamais de plantage ni
// d'allocation géante).
//
// Partagé navigateur + Node (tests) : extractAudio(blob, { title, onProgress }).
(function (global) {
  class Mp4Error extends Error {
    constructor(code, message) { super(message); this.name = "Mp4Error"; this.code = code; }
  }
  const printable = (t) => t.replace(/[^\x20-\x7e]/g, "?");
  const corrupt = (what) => new Mp4Error("corrupt", "Fichier vidéo endommagé (" + what + ").");
  const truncated = () => new Mp4Error("truncated", "La vidéo semble incomplète (téléchargement interrompu ?).");
  function check(cond, what) { if (!cond) throw corrupt(what); }

  // Garde-fous contre les fichiers corrompus.
  const MAX_SAMPLES = 20e6; // ~120 h d'AAC à 48 kHz
  const MAX_INDEX = 256 * 1024 * 1024; // taille max d'un moov / moof
  const MAX_TOP_BOXES = 2e6;
  const MAX_DEPTH = 16;

  // Types de boîtes acceptés en tête de fichier (détection « est-ce un MP4 ? »).
  const TOP_TYPES = new Set(["ftyp", "moov", "mdat", "free", "skip", "wide", "pnot", "styp", "sidx", "moof", "uuid", "junk", "pdin"]);
  // Boîtes dont on parcourt les enfants (udta/meta volontairement exclus :
  // formats QuickTime hétérogènes, et on ne les recopie pas).
  const CONTAINERS = new Set(["moov", "trak", "mdia", "minf", "stbl", "edts", "mvex", "moof", "traf", "dinf"]);
  // Codecs chiffrés (DRM) : impossible d'en extraire un audio lisible.
  const DRM_CODECS = new Set(["enca", "drms", "drmi"]);
  // Codecs dont chaque échantillon est décrit dans stsz : copie exacte garantie.
  // (Le PCM QuickTime, décrit autrement, donnerait un son corrompu : refusé.)
  const SAFE_CODECS = new Set(["mp4a", "alac", "ac-3", "ec-3", "Opus", "fLaC", ".mp3", "mp3 "]);
  // Tables liées au chiffrement, aux offsets absolus : jamais recopiées.
  const DROP_FROM_STBL = new Set(["saio", "saiz", "senc"]);

  const u16 = (b, o) => (b[o] << 8) | b[o + 1];
  const u32 = (b, o) => ((b[o] << 24) >>> 0) + (b[o + 1] << 16) + (b[o + 2] << 8) + b[o + 3];
  const i32 = (b, o) => u32(b, o) | 0;
  const u64 = (b, o) => u32(b, o) * 4294967296 + u32(b, o + 4);
  const fourcc = (b, o) => String.fromCharCode(b[o], b[o + 1], b[o + 2], b[o + 3]);
  const flagsOf = (p) => (p[1] << 16) | (p[2] << 8) | p[3];

  function w16(b, o, v) { b[o] = (v >>> 8) & 255; b[o + 1] = v & 255; }
  function w32(b, o, v) { b[o] = (v >>> 24) & 255; b[o + 1] = (v >>> 16) & 255; b[o + 2] = (v >>> 8) & 255; b[o + 3] = v & 255; }
  function w64(b, o, v) { w32(b, o, Math.floor(v / 4294967296)); w32(b, o + 4, v >>> 0); }

  // Lecture avec fenêtre d'avance de 64 Ko : les en-têtes et les petits moof
  // qui se suivent sont servis par un seul accès au fichier.
  function makeReader(blob) {
    let winStart = 0, win = new Uint8Array(0);
    return async function read(start, len) {
      if (start >= winStart && start + len <= winStart + win.length) {
        return win.subarray(start - winStart, start - winStart + len);
      }
      const end = Math.min(blob.size, start + Math.max(len, 65536));
      win = new Uint8Array(await blob.slice(start, end).arrayBuffer());
      winStart = start;
      return win.subarray(0, Math.min(len, win.length));
    };
  }

  // --- Lecture de la structure ------------------------------------------------

  // Boîtes de premier niveau (en-têtes seulement ; les moof sont lus au passage).
  async function scanTopLevel(blob, read, onProgress) {
    const boxes = [];
    let pos = 0;
    while (pos + 8 <= blob.size) {
      const h = await read(pos, 16);
      let size = u32(h, 0), hdr = 8;
      const type = fourcc(h, 4);
      if (!boxes.length && !TOP_TYPES.has(type)) {
        throw new Mp4Error("not_mp4", "Ce fichier n'est pas une vidéo MP4/MOV.");
      }
      if (size === 1) {
        if (h.length < 16) break;
        size = u64(h, 8); hdr = 16;
      } else if (size === 0) {
        size = blob.size - pos;
      }
      if (size < hdr) {
        // Octets parasites en fin de fichier : on s'arrête si on a l'essentiel.
        if (boxes.some((b) => b.type === "moov")) break;
        throw corrupt("boîte « " + printable(type) + " » invalide");
      }
      const b = { type, start: pos, size, hdr };
      if (type === "moof" && size <= MAX_INDEX && pos + size <= blob.size) {
        b.buf = (await read(pos, size)).slice(); // copie : libère la fenêtre
      }
      boxes.push(b);
      check(boxes.length <= MAX_TOP_BOXES, "trop de boîtes");
      pos += size;
      if (onProgress && boxes.length % 256 === 0) onProgress(Math.min(1, pos / blob.size));
    }
    if (!boxes.length) throw new Mp4Error("not_mp4", "Ce fichier n'est pas une vidéo MP4/MOV.");
    return boxes;
  }

  // Analyse récursive d'un tampon déjà en mémoire.
  function parseBoxes(buf, start, end, depth = 0) {
    check(depth <= MAX_DEPTH, "imbrication");
    const out = [];
    let p = start;
    while (p + 8 <= end) {
      let size = u32(buf, p), hdr = 8;
      const type = fourcc(buf, p + 4);
      if (size === 1) { size = u64(buf, p + 8); hdr = 16; }
      else if (size === 0) break; // terminateur QuickTime
      if (size < hdr || p + size > end) throw corrupt("boîte « " + printable(type) + " » invalide");
      const box = { type, start: p, size, hdr, buf };
      if (CONTAINERS.has(type)) box.children = parseBoxes(buf, p + hdr, p + size, depth + 1);
      out.push(box);
      p += size;
    }
    return out;
  }

  const child = (box, type) => (box && box.children ? box.children.find((c) => c.type === type) : undefined);
  const childrenOf = (box, type) => (box && box.children ? box.children.filter((c) => c.type === type) : []);
  const path = (box, ...types) => types.reduce((b, t) => child(b, t), box);
  const payload = (box) => box.buf.subarray(box.start + box.hdr, box.start + box.size);
  const raw = (box) => box.buf.subarray(box.start, box.start + box.size);

  // mvhd / mdhd ont la même disposition : timescale + durée (v0 32 bits, v1 64 bits).
  function readTimes(box) {
    const p = payload(box);
    check(p.length >= (p[0] === 1 ? 32 : 20), box.type);
    return p[0] === 1 ? { timescale: u32(p, 20), duration: u64(p, 24) } : { timescale: u32(p, 12), duration: u32(p, 16) };
  }
  function patchedTimes(box, duration) {
    const out = raw(box).slice();
    const p = out.subarray(box.hdr);
    if (p[0] === 1) w64(p, 24, duration); else w32(p, 16, Math.min(duration, 0xffffffff));
    return out;
  }
  // tkhd : track_ID et durée (dans l'échelle de temps du film).
  function readTkhd(box) {
    const p = payload(box);
    check(p.length >= (p[0] === 1 ? 36 : 24), "tkhd");
    return p[0] === 1
      ? { flags: flagsOf(p), trackId: u32(p, 20), duration: u64(p, 28) }
      : { flags: flagsOf(p), trackId: u32(p, 12), duration: u32(p, 20) };
  }
  function patchedTkhd(box, duration) {
    const out = raw(box).slice();
    const p = out.subarray(box.hdr);
    p[3] |= 0x03; // piste activée + utilisée dans le film
    if (p[0] === 1) w64(p, 28, duration); else w32(p, 20, Math.min(duration, 0xffffffff));
    return out;
  }

  function handlerOf(trak) {
    const hdlr = path(trak, "mdia", "hdlr");
    return hdlr && payload(hdlr).length >= 12 ? fourcc(payload(hdlr), 8) : "";
  }

  // Codec + canaux de la première entrée de stsd.
  function sampleEntryInfo(stsd) {
    const p = payload(stsd);
    if (p.length < 16 || u32(p, 4) < 1) return { codec: "????", channels: 0 };
    const e = 8; // début de la 1re entrée dans le payload
    const codec = fourcc(p, e + 4);
    const version = p.length >= e + 18 ? u16(p, e + 16) : 0;
    const channels = version < 2 && p.length >= e + 26 ? u16(p, e + 24) : 0;
    return { codec, channels };
  }

  // Description audio QuickTime (v1/v2, esds rangé dans « wave ») -> description
  // ISO standard (v0, esds direct) : le .m4a est alors lisible partout, pas
  // seulement par les lecteurs Apple. Toute autre entrée est recopiée telle quelle.
  function isoStsd(stsdBox) {
    const p = payload(stsdBox);
    if (p.length < 16 || u32(p, 4) < 1) return raw(stsdBox);
    const size = u32(p, 8);
    if (size < 36 || 8 + size > p.length) return raw(stsdBox);
    const entry = p.subarray(8, 8 + size);
    const version = u16(entry, 16);
    if (fourcc(entry, 4) !== "mp4a" || (version !== 1 && version !== 2)) return raw(stsdBox);
    const fieldsEnd = version === 1 ? 52 : 72;
    if (size < fieldsEnd) return raw(stsdBox);
    let channels = u16(entry, 24), rate = u32(entry, 32);
    if (version === 2) {
      const sr = new DataView(entry.buffer, entry.byteOffset + 40, 8).getFloat64(0);
      channels = u32(entry, 48);
      rate = sr > 0 && sr < 65536 ? Math.round(sr) * 65536 : 0;
    }
    let kids, esds;
    try {
      kids = parseBoxes(entry, fieldsEnd, size);
      esds = kids.find((k) => k.type === "esds");
      const wave = kids.find((k) => k.type === "wave");
      if (!esds && wave) esds = parseBoxes(entry, wave.start + wave.hdr, wave.start + wave.size).find((k) => k.type === "esds");
    } catch (e) {
      return raw(stsdBox);
    }
    if (!esds) return raw(stsdBox);
    const fields = new Uint8Array(28);
    fields.set(entry.subarray(8, 16), 0); // réservé + data_reference_index
    w16(fields, 16, Math.min(channels, 0xffff) || 2);
    w16(fields, 18, 16); // taille d'échantillon (valeur ISO par défaut)
    w32(fields, 24, rate);
    const others = kids.filter((k) => k.type !== "wave" && k.type !== "esds").map(raw);
    const mp4a = box("mp4a", fields, raw(esds), ...others);
    return fullBox("stsd", p[0], flagsOf(p), concat([u32Array([u32(p, 4)]), mp4a, p.subarray(8 + size)]));
  }

  // Refuse les fichiers dont les données sont dans un AUTRE fichier (rare).
  function checkSelfContained(trak) {
    const dref = path(trak, "mdia", "minf", "dinf", "dref");
    if (!dref) return;
    const p = payload(dref);
    if (p.length < 8) return;
    const n = u32(p, 4);
    let o = 8;
    for (let i = 0; i < n && o + 12 <= p.length; i++) {
      const size = u32(p, o);
      if (!(p[o + 11] & 1)) throw new Mp4Error("external", "L'audio de cette vidéo est stocké dans un autre fichier.");
      o += Math.max(size, 12);
    }
  }

  // --- Tables d'échantillons (MP4 non fragmenté) -----------------------------

  function sampleSizes(stbl, fileSize) {
    const stsz = child(stbl, "stsz");
    if (stsz) {
      const p = payload(stsz);
      check(p.length >= 12, "stsz");
      const fixed = u32(p, 4), count = u32(p, 8);
      check(count <= MAX_SAMPLES, "stsz");
      if (fixed && fixed * count > fileSize) throw truncated();
      check(fixed || p.length >= 12 + 4 * count, "stsz");
      const sizes = new Uint32Array(count);
      if (fixed) sizes.fill(fixed);
      else for (let i = 0; i < count; i++) sizes[i] = u32(p, 12 + 4 * i);
      return sizes;
    }
    const stz2 = child(stbl, "stz2");
    if (stz2) {
      const p = payload(stz2);
      check(p.length >= 12, "stz2");
      const bits = p[7], count = u32(p, 8);
      check((bits === 4 || bits === 8 || bits === 16) && count <= MAX_SAMPLES && p.length >= 12 + Math.ceil((count * bits) / 8), "stz2");
      const sizes = new Uint32Array(count);
      for (let i = 0; i < count; i++) {
        if (bits === 4) sizes[i] = (p[12 + (i >> 1)] >> (i & 1 ? 0 : 4)) & 15;
        else if (bits === 8) sizes[i] = p[12 + i];
        else sizes[i] = u16(p, 12 + 2 * i);
      }
      return sizes;
    }
    return new Uint32Array(0);
  }

  function chunkOffsets(stbl) {
    const stco = child(stbl, "stco"), co64 = child(stbl, "co64");
    if (!stco && !co64) return [];
    const p = payload(stco || co64);
    check(p.length >= 8, "stco");
    const n = u32(p, 4), w = stco ? 4 : 8;
    check(p.length >= 8 + w * n, "stco");
    const out = new Array(n);
    for (let i = 0; i < n; i++) out[i] = stco ? u32(p, 8 + 4 * i) : u64(p, 8 + 8 * i);
    return out;
  }

  // Position + taille de chaque chunk (un chunk = échantillons contigus), dans
  // l'ordre de stco : il y a exactement un élément par entrée de stco.
  function chunkLayout(stbl, fileSize) {
    const sizes = sampleSizes(stbl, fileSize);
    const offsets = chunkOffsets(stbl);
    const stsc = child(stbl, "stsc");
    const chunks = [];
    if (!stsc || !offsets.length || !sizes.length) return { chunks, sizes };
    const p = payload(stsc);
    check(p.length >= 8, "stsc");
    const n = u32(p, 4);
    check(n >= 1 && p.length >= 8 + 12 * n && u32(p, 8) === 1, "stsc");
    let sample = 0;
    for (let e = 0; e < n; e++) {
      const first = u32(p, 8 + 12 * e) - 1;
      const perChunk = u32(p, 12 + 12 * e);
      const last = e + 1 < n ? u32(p, 8 + 12 * (e + 1)) - 1 : offsets.length;
      if (last <= first) continue; // entrée redondante : ignorée
      for (let c = first; c < Math.min(last, offsets.length); c++) {
        let bytes = 0, k = 0;
        for (; k < perChunk && sample < sizes.length; k++) bytes += sizes[sample++];
        if (offsets[c] + bytes > fileSize) throw truncated();
        chunks.push({ offset: offsets[c], size: bytes, samples: k });
      }
    }
    check(chunks.length === offsets.length, "stsc/stco");
    return { chunks, sizes };
  }

  // Échantillons individuels (offset, taille, durée) d'une stbl : sert quand un
  // MP4 fragmenté a aussi des échantillons dans moov.
  function stblSamples(stbl, fileSize) {
    const { chunks, sizes } = chunkLayout(stbl, fileSize);
    const out = { offsets: [], sizes: [], durations: [] };
    let s = 0;
    for (const ch of chunks) {
      let off = ch.offset;
      for (let k = 0; k < ch.samples; k++, s++) {
        out.offsets.push(off); out.sizes.push(sizes[s]); off += sizes[s];
      }
    }
    const stts = child(stbl, "stts");
    if (stts) {
      const p = payload(stts);
      const n = p.length >= 8 ? u32(p, 4) : 0;
      check(p.length >= 8 + 8 * n, "stts");
      for (let e = 0; e < n && out.durations.length < out.sizes.length; e++) {
        const count = u32(p, 8 + 8 * e), delta = u32(p, 12 + 8 * e);
        for (let k = 0; k < count && out.durations.length < out.sizes.length; k++) out.durations.push(delta);
      }
    }
    while (out.durations.length < out.sizes.length) out.durations.push(0);
    return out;
  }

  // --- MP4 fragmenté (moof/traf/trun) ----------------------------------------

  function trexFor(moov, trackId) {
    for (const trex of childrenOf(child(moov, "mvex"), "trex")) {
      const p = payload(trex);
      if (p.length >= 20 && u32(p, 4) === trackId) return { duration: u32(p, 12), size: u32(p, 16) };
    }
    return { duration: 0, size: 0 };
  }

  function fragmentSamples(blob, tops, trackId, trex) {
    const out = { offsets: [], sizes: [], durations: [] };
    for (const box of tops) {
      if (box.type !== "moof") continue;
      if (!box.buf) {
        if (box.start + box.size > blob.size) throw truncated();
        throw corrupt("moof");
      }
      const moof = parseBoxes(box.buf, 0, box.buf.length)[0];
      check(moof && moof.type === "moof", "moof");
      let prevEnd = box.start;
      for (const traf of childrenOf(moof, "traf")) {
        const tfhdBox = child(traf, "tfhd");
        if (!tfhdBox) continue;
        const t = payload(tfhdBox);
        check(t.length >= 8, "tfhd");
        const tf = flagsOf(t);
        const id = u32(t, 4);
        const optLen = (tf & 0x1 ? 8 : 0) + (tf & 0x2 ? 4 : 0) + (tf & 0x8 ? 4 : 0) + (tf & 0x10 ? 4 : 0) + (tf & 0x20 ? 4 : 0);
        check(t.length >= 8 + optLen, "tfhd");
        let q = 8, base = null;
        let defDur = trex.duration, defSize = trex.size;
        if (tf & 0x1) { base = u64(t, q); q += 8; }
        if (tf & 0x2) q += 4;
        if (tf & 0x8) { defDur = u32(t, q); q += 4; }
        if (tf & 0x10) { defSize = u32(t, q); q += 4; }
        // Base des offsets : explicite, sinon début du moof (default-base-is-moof
        // ou 1er traf), sinon fin des données du traf précédent.
        if (base === null) base = tf & 0x20000 ? box.start : prevEnd;
        let cursor = base;
        for (const trun of childrenOf(traf, "trun")) {
          const r = payload(trun);
          check(r.length >= 8, "trun");
          const rf = flagsOf(r);
          const count = u32(r, 4);
          const perSample = (rf & 0x100 ? 4 : 0) + (rf & 0x200 ? 4 : 0) + (rf & 0x400 ? 4 : 0) + (rf & 0x800 ? 4 : 0);
          let o = 8 + (rf & 0x1 ? 4 : 0) + (rf & 0x4 ? 4 : 0);
          check(r.length >= o + perSample * count && out.sizes.length + count <= MAX_SAMPLES, "trun");
          if (rf & 0x1) cursor = base + i32(r, 8);
          for (let i = 0; i < count; i++) {
            let dur = defDur, size = defSize;
            if (rf & 0x100) { dur = u32(r, o); o += 4; }
            if (rf & 0x200) { size = u32(r, o); o += 4; }
            if (rf & 0x400) o += 4;
            if (rf & 0x800) o += 4;
            if (id === trackId) {
              check(cursor >= 0, "trun");
              if (cursor + size > blob.size) throw truncated();
              out.offsets.push(cursor); out.sizes.push(size); out.durations.push(dur);
            }
            cursor += size;
          }
        }
        prevEnd = cursor;
      }
    }
    return out;
  }

  // --- Écriture --------------------------------------------------------------

  const typeBytes = (t) => Uint8Array.from(t, (c) => c.charCodeAt(0) & 255);

  function box(type, ...parts) {
    let len = 8;
    for (const p of parts) len += p.length;
    const out = new Uint8Array(len);
    w32(out, 0, len);
    out.set(typeBytes(type), 4);
    let o = 8;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }
  const fullBox = (type, version, flags, body) => box(type, Uint8Array.of(version, (flags >> 16) & 255, (flags >> 8) & 255, flags & 255), body);

  // Valeurs 32 bits consécutives (en-tête + table), sans tableau intermédiaire.
  function u32Array(head, table) {
    const n = head.length + (table ? table.length : 0);
    const b = new Uint8Array(4 * n);
    let o = 0;
    for (const v of head) { w32(b, o, v); o += 4; }
    if (table) for (let i = 0; i < table.length; i++) { w32(b, o, table[i]); o += 4; }
    return b;
  }

  function concat(parts) {
    const len = parts.reduce((s, p) => s + p.length, 0);
    const out = new Uint8Array(len);
    let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }

  function ftypBox() {
    return box("ftyp", typeBytes("M4A "), new Uint8Array(4), typeBytes("M4A mp42isom"));
  }

  // Titre iTunes (©nam) — affiché par la plupart des lecteurs.
  const NAM = String.fromCharCode(0xa9) + "nam";
  function titleBox(title) {
    if (!title) return null;
    const text = new TextEncoder().encode(String(title).slice(0, 200));
    const data = box("data", u32Array([1, 0]), text);
    const hdlr = fullBox("hdlr", 0, 0, concat([new Uint8Array(4), typeBytes("mdir"), typeBytes("appl"), new Uint8Array(9)]));
    return box("udta", fullBox("meta", 0, 0, concat([hdlr, box("ilst", box(NAM, data))])));
  }

  function chunkOffsetBox(offsets) {
    const big = offsets.length > 0 && offsets[offsets.length - 1] > 0xffffffff;
    const body = new Uint8Array(4 + (big ? 8 : 4) * offsets.length);
    w32(body, 0, offsets.length);
    offsets.forEach((v, i) => (big ? w64(body, 4 + 8 * i, v) : w32(body, 4 + 4 * i, v)));
    return fullBox(big ? "co64" : "stco", 0, 0, body);
  }

  // Regroupe des échantillons contigus en chunks + tables stts/stsc/stsz.
  function tablesFromSamples(s) {
    const chunks = [];
    for (let i = 0; i < s.sizes.length; i++) {
      const last = chunks[chunks.length - 1];
      if (last && last.offset + last.size === s.offsets[i] && last.samples < 4096) {
        last.size += s.sizes[i]; last.samples++;
      } else {
        chunks.push({ offset: s.offsets[i], size: s.sizes[i], samples: 1 });
      }
    }
    const stts = [];
    for (const d of s.durations) {
      const n = stts.length;
      if (n && stts[n - 1] === d) stts[n - 2]++; else stts.push(1, d);
    }
    const stsc = [];
    chunks.forEach((c, i) => {
      if (!stsc.length || stsc[stsc.length - 2] !== c.samples) stsc.push(i + 1, c.samples, 1);
    });
    const allSame = s.sizes.every((v) => v === s.sizes[0]);
    const boxes = {
      stts: fullBox("stts", 0, 0, u32Array([stts.length / 2], stts)),
      stsc: fullBox("stsc", 0, 0, u32Array([stsc.length / 3], stsc)),
      stsz: fullBox("stsz", 0, 0, allSame ? u32Array([s.sizes[0] || 0, s.sizes.length]) : u32Array([0, s.sizes.length], s.sizes)),
    };
    return { chunks, boxes };
  }

  // Assemble ftyp + moov + mdat. buildMoov(offsets) -> octets du moov.
  function assemble(blob, chunks, buildMoov) {
    const ftyp = ftypBox();
    const total = chunks.reduce((n, c) => n + c.size, 0);
    const bigMdat = total + 8 > 0xffffffff;
    const mdatHdr = new Uint8Array(bigMdat ? 16 : 8);
    if (bigMdat) { w32(mdatHdr, 0, 1); mdatHdr.set(typeBytes("mdat"), 4); w64(mdatHdr, 8, total + 16); }
    else { w32(mdatHdr, 0, total + 8); mdatHdr.set(typeBytes("mdat"), 4); }

    const offsetsFrom = (dataStart) => {
      const out = new Array(chunks.length);
      let o = dataStart;
      chunks.forEach((c, i) => { out[i] = o; o += c.size; });
      return out;
    };
    // Le moov précède les données : sa taille (stco ou co64) fixe leurs offsets.
    let moov = buildMoov(offsetsFrom(0));
    for (let pass = 0; pass < 3; pass++) {
      const next = buildMoov(offsetsFrom(ftyp.length + moov.length + mdatHdr.length));
      const stable = next.length === moov.length;
      moov = next;
      if (stable) break;
    }

    // Tranches du fichier source, fusionnées quand elles se suivent.
    const parts = [ftyp, moov, mdatHdr];
    let runStart = -1, runEnd = -1;
    for (const c of chunks) {
      if (c.offset === runEnd) { runEnd += c.size; continue; }
      if (runStart >= 0) parts.push(blob.slice(runStart, runEnd));
      runStart = c.offset; runEnd = c.offset + c.size;
    }
    if (runStart >= 0) parts.push(blob.slice(runStart, runEnd));
    return new Blob(parts, { type: "audio/mp4" });
  }

  // --- Choix de la piste audio ------------------------------------------------

  function sampleCount(stbl) {
    const s = child(stbl, "stsz") || child(stbl, "stz2");
    return s && payload(s).length >= 12 ? u32(payload(s), 8) : 0;
  }

  // Piste activée > AAC > avec échantillons ; à égalité, la première du fichier.
  function pickAudioTrack(moov) {
    let best = null, bestScore = -1;
    for (const trak of childrenOf(moov, "trak")) {
      if (handlerOf(trak) !== "soun") continue;
      const tkhd = child(trak, "tkhd");
      const stsd = path(trak, "mdia", "minf", "stbl", "stsd");
      if (!tkhd || !stsd || !path(trak, "mdia", "mdhd")) continue;
      let score;
      try {
        score = (readTkhd(tkhd).flags & 1 ? 4 : 0) + (sampleEntryInfo(stsd).codec === "mp4a" ? 2 : 0) +
          (sampleCount(path(trak, "mdia", "minf", "stbl")) > 0 ? 1 : 0);
      } catch (e) {
        continue; // piste illisible : on essaie les autres
      }
      if (score > bestScore) { best = trak; bestScore = score; }
    }
    return best;
  }

  // --- Point d'entrée --------------------------------------------------------

  async function extract(blob, opts) {
    const onProgress = opts.onProgress || null;
    const read = makeReader(blob);
    const tops = await scanTopLevel(blob, read, onProgress);
    const moovTop = tops.find((b) => b.type === "moov");
    if (!moovTop) throw new Mp4Error("no_moov", "Vidéo incomplète ou illisible (index « moov » absent).");
    if (moovTop.start + moovTop.size > blob.size) throw truncated();
    check(moovTop.size <= MAX_INDEX, "index anormalement gros");
    const moovBuf = new Uint8Array(await blob.slice(moovTop.start, moovTop.start + moovTop.size).arrayBuffer());
    const moov = parseBoxes(moovBuf, 0, moovBuf.length)[0];
    check(moov && moov.type === "moov", "moov");

    const hasAudio = childrenOf(moov, "trak").some((t) => handlerOf(t) === "soun");
    if (!hasAudio) throw new Mp4Error("no_audio", "Aucune piste audio dans cette vidéo.");
    const trak = pickAudioTrack(moov);
    check(trak, "piste audio");
    checkSelfContained(trak);

    const tkhd = child(trak, "tkhd");
    const mdia = child(trak, "mdia");
    const mdhd = child(mdia, "mdhd");
    const minf = child(mdia, "minf");
    const stbl = child(minf, "stbl");
    const stsd = child(stbl, "stsd");
    const mvhd = child(moov, "mvhd");
    check(mvhd, "mvhd");
    const info = sampleEntryInfo(stsd);
    if (DRM_CODECS.has(info.codec)) {
      throw new Mp4Error("drm", "Cette vidéo est protégée contre la copie (DRM) : impossible d'en extraire l'audio.");
    }
    if (!SAFE_CODECS.has(info.codec)) {
      throw new Mp4Error("codec", "Format audio « " + printable(info.codec) + " » non pris en charge (AAC attendu).");
    }
    const media = readTimes(mdhd);
    check(media.timescale > 0, "mdhd");
    const movieScale = readTimes(mvhd).timescale || media.timescale;
    const udta = titleBox(opts.title);
    const stsdOut = isoStsd(stsd);

    const fragmented = !!child(moov, "mvex") || tops.some((b) => b.type === "moof");
    let out, mediaDuration;

    if (!fragmented) {
      // Cas courant : on garde les tables d'origine, seuls stco et stsd changent.
      const { chunks } = chunkLayout(stbl, blob.size);
      if (!chunks.length || !chunks.some((c) => c.size > 0)) throw new Mp4Error("empty", "La piste audio est vide.");
      mediaDuration = media.duration;
      const trackDuration = readTkhd(tkhd).duration || Math.round((mediaDuration * movieScale) / media.timescale);
      out = assemble(blob, chunks, (offsets) => {
        const stblOut = box("stbl", ...stbl.children.filter((c) => !DROP_FROM_STBL.has(c.type)).map((c) =>
          c.type === "stco" || c.type === "co64" ? chunkOffsetBox(offsets) : c.type === "stsd" ? stsdOut : raw(c)));
        const minfOut = box("minf", ...minf.children.map((c) => (c.type === "stbl" ? stblOut : raw(c))));
        const mdiaOut = box("mdia", ...mdia.children.map((c) => (c.type === "minf" ? minfOut : raw(c))));
        const keep = trak.children.filter((c) => c.type === "edts").map(raw);
        const trakOut = box("trak", patchedTkhd(tkhd, trackDuration), ...keep, mdiaOut);
        return box("moov", patchedTimes(mvhd, trackDuration), trakOut, ...(udta ? [udta] : []));
      });
    } else {
      // MP4 fragmenté : on reconstruit des tables classiques (fichier « à plat »).
      const trackId = readTkhd(tkhd).trackId;
      const samples = stblSamples(stbl, blob.size);
      const frag = fragmentSamples(blob, tops, trackId, trexFor(moov, trackId));
      for (const k of ["offsets", "sizes", "durations"]) samples[k] = samples[k].concat(frag[k]);
      check(samples.sizes.length <= MAX_SAMPLES, "trop d'échantillons");
      if (!samples.sizes.length) throw new Mp4Error("empty", "La piste audio est vide.");
      mediaDuration = samples.durations.reduce((a, b) => a + b, 0);
      check(mediaDuration > 0, "durées d'échantillons manquantes");
      const trackDuration = Math.round((mediaDuration * movieScale) / media.timescale);
      const { chunks, boxes } = tablesFromSamples(samples);
      out = assemble(blob, chunks, (offsets) => {
        const stblOut = box("stbl", stsdOut, boxes.stts, boxes.stsc, boxes.stsz, chunkOffsetBox(offsets));
        const minfOut = box("minf", ...minf.children.map((c) => (c.type === "stbl" ? stblOut : raw(c))));
        const mdiaOut = box("mdia", ...mdia.children.map((c) =>
          c.type === "minf" ? minfOut : c.type === "mdhd" ? patchedTimes(mdhd, mediaDuration) : raw(c)));
        const trakOut = box("trak", patchedTkhd(tkhd, trackDuration), mdiaOut);
        return box("moov", patchedTimes(mvhd, trackDuration), trakOut, ...(udta ? [udta] : []));
      });
    }

    if (onProgress) onProgress(1);
    return {
      blob: out,
      duration: mediaDuration / media.timescale,
      codec: info.codec,
      channels: info.channels,
      sampleRate: media.timescale,
      fragmented,
    };
  }

  // Toute erreur inattendue devient une Mp4Error au message compréhensible.
  async function extractAudio(blob, opts = {}) {
    try {
      return await extract(blob, opts);
    } catch (e) {
      if (e instanceof Mp4Error) throw e;
      const readError = e && /NotReadable|NotFound|Security/.test(e.name || "");
      const err = readError
        ? new Mp4Error("read", "Impossible de lire ce fichier (déplacé ou supprimé ?).")
        : new Mp4Error("corrupt", "Vidéo illisible ou endommagée.");
      err.cause = e;
      throw err;
    }
  }

  // Détection rapide : le fichier commence-t-il comme un MP4/MOV ?
  async function looksLikeMp4(blob) {
    if (blob.size < 8) return false;
    const h = new Uint8Array(await blob.slice(0, 8).arrayBuffer());
    return TOP_TYPES.has(fourcc(h, 4));
  }

  const api = { extractAudio, looksLikeMp4, Mp4Error };
  global.Mp4Audio = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
