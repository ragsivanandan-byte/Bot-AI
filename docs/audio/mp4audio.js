"use strict";
// Extraction de la piste audio d'une vidéo MP4 / MOV / M4V -> fichier .m4a,
// SANS ré-encodage (copie bit à bit des échantillons AAC) et SANS charger la
// vidéo en mémoire : seuls les en-têtes (moov/moof) sont lus, l'audio final est
// un Blob composé de tranches du fichier d'origine. Indispensable sur iPhone
// où une vidéo d'1 h pèse plusieurs centaines de Mo.
//
// Gère : MP4 classique (moov au début ou à la fin), MOV QuickTime (vidéos
// iPhone, enregistrements d'écran), MP4 fragmenté (DASH/HLS-fMP4, fichiers
// téléchargés par yt-dlp), fichiers déjà audio (M4A).
//
// Partagé navigateur + Node (tests) : extractAudio(blob, { title }).
(function (global) {
  class Mp4Error extends Error {
    constructor(code, message) { super(message); this.code = code; }
  }

  // Types de boîtes acceptés en tête de fichier (détection « est-ce un MP4 ? »).
  const TOP_TYPES = new Set(["ftyp", "moov", "mdat", "free", "skip", "wide", "pnot", "styp", "sidx", "moof", "uuid", "junk", "pdin"]);
  // Boîtes dont on parcourt les enfants (udta/meta volontairement exclus :
  // formats QuickTime hétérogènes, et on ne les recopie pas).
  const CONTAINERS = new Set(["moov", "trak", "mdia", "minf", "stbl", "edts", "mvex", "moof", "traf", "dinf"]);

  const u16 = (b, o) => (b[o] << 8) | b[o + 1];
  const u32 = (b, o) => ((b[o] << 24) >>> 0) + (b[o + 1] << 16) + (b[o + 2] << 8) + b[o + 3];
  const i32 = (b, o) => u32(b, o) | 0;
  const u64 = (b, o) => u32(b, o) * 4294967296 + u32(b, o + 4);
  const fourcc = (b, o) => String.fromCharCode(b[o], b[o + 1], b[o + 2], b[o + 3]);
  const flagsOf = (p) => (p[1] << 16) | (p[2] << 8) | p[3];

  function w32(b, o, v) { b[o] = (v >>> 24) & 255; b[o + 1] = (v >>> 16) & 255; b[o + 2] = (v >>> 8) & 255; b[o + 3] = v & 255; }
  function w64(b, o, v) { w32(b, o, Math.floor(v / 4294967296)); w32(b, o + 4, v >>> 0); }

  async function readBytes(blob, start, len) {
    const end = Math.min(blob.size, start + len);
    return new Uint8Array(await blob.slice(start, end).arrayBuffer());
  }

  // --- Lecture de la structure ------------------------------------------------

  // Liste des boîtes de premier niveau (on ne lit que leurs en-têtes).
  async function scanTopLevel(blob) {
    const boxes = [];
    let pos = 0;
    while (pos + 8 <= blob.size) {
      const h = await readBytes(blob, pos, 16);
      let size = u32(h, 0), hdr = 8;
      const type = fourcc(h, 4);
      if (boxes.length === 0 && !TOP_TYPES.has(type)) {
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
        throw new Mp4Error("corrupt", "Fichier vidéo endommagé (boîte « " + type + " » invalide).");
      }
      boxes.push({ type, start: pos, size, hdr });
      pos += size;
    }
    if (!boxes.length) throw new Mp4Error("not_mp4", "Ce fichier n'est pas une vidéo MP4/MOV.");
    return boxes;
  }

  // Analyse récursive d'un tampon déjà en mémoire.
  function parseBoxes(buf, start, end) {
    const out = [];
    let p = start;
    while (p + 8 <= end) {
      let size = u32(buf, p), hdr = 8;
      const type = fourcc(buf, p + 4);
      if (size === 1) { size = u64(buf, p + 8); hdr = 16; }
      else if (size === 0) break; // terminateur QuickTime
      if (size < hdr || p + size > end) {
        throw new Mp4Error("corrupt", "Fichier vidéo endommagé (boîte « " + type + " » invalide).");
      }
      const box = { type, start: p, size, hdr, buf };
      if (CONTAINERS.has(type)) box.children = parseBoxes(buf, p + hdr, p + size);
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
    return p[0] === 1
      ? { flags: flagsOf(p), trackId: u32(p, 20), duration: u64(p, 28) }
      : { flags: flagsOf(p), trackId: u32(p, 12), duration: u32(p, 20) };
  }
  function patchedTkhd(box, duration) {
    const out = raw(box).slice();
    const p = out.subarray(box.hdr);
    p[3] |= 0x03; // piste activée + utilisée dans le film
    if (duration != null) {
      if (p[0] === 1) w64(p, 28, duration); else w32(p, 20, Math.min(duration, 0xffffffff));
    }
    return out;
  }

  function handlerOf(trak) {
    const hdlr = path(trak, "mdia", "hdlr");
    return hdlr ? fourcc(payload(hdlr), 8) : "";
  }

  // Codec + canaux de la première entrée de stsd.
  function sampleEntryInfo(stsd) {
    const p = payload(stsd);
    if (u32(p, 4) < 1 || p.length < 16) return { codec: "????", channels: 0 };
    const e = 8; // début de la 1re entrée dans le payload
    const codec = fourcc(p, e + 4);
    const version = p.length >= e + 18 ? u16(p, e + 16) : 0;
    const channels = version < 2 && p.length >= e + 26 ? u16(p, e + 24) : 0;
    return { codec, channels };
  }

  // Refuse les fichiers dont les données sont dans un AUTRE fichier (rare).
  function checkSelfContained(trak) {
    const dref = path(trak, "mdia", "minf", "dinf", "dref");
    if (!dref) return;
    const p = payload(dref);
    const n = u32(p, 4);
    let o = 8;
    for (let i = 0; i < n && o + 12 <= p.length; i++) {
      const size = u32(p, o);
      if (!(p[o + 11] & 1)) throw new Mp4Error("external", "L'audio de cette vidéo est stocké dans un autre fichier.");
      o += Math.max(size, 12);
    }
  }

  // --- Tables d'échantillons (MP4 non fragmenté) -----------------------------

  function sampleSizes(stbl) {
    const stsz = child(stbl, "stsz");
    if (stsz) {
      const p = payload(stsz);
      const fixed = u32(p, 4), count = u32(p, 8);
      const sizes = new Uint32Array(count);
      if (fixed) sizes.fill(fixed);
      else for (let i = 0; i < count; i++) sizes[i] = u32(p, 12 + 4 * i);
      return sizes;
    }
    const stz2 = child(stbl, "stz2");
    if (stz2) {
      const p = payload(stz2);
      const bits = p[7], count = u32(p, 8);
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
    const n = u32(p, 4);
    const out = new Array(n);
    for (let i = 0; i < n; i++) out[i] = stco ? u32(p, 8 + 4 * i) : u64(p, 8 + 8 * i);
    return out;
  }

  // Position + taille de chaque chunk (un chunk = échantillons contigus).
  function chunkLayout(stbl, fileSize) {
    const sizes = sampleSizes(stbl);
    const offsets = chunkOffsets(stbl);
    const stsc = child(stbl, "stsc");
    const chunks = [];
    if (!stsc || !offsets.length || !sizes.length) return { chunks, sizes };
    const p = payload(stsc);
    const n = u32(p, 4);
    let sample = 0;
    for (let e = 0; e < n; e++) {
      const first = u32(p, 8 + 12 * e) - 1;
      const perChunk = u32(p, 12 + 12 * e);
      const last = e + 1 < n ? u32(p, 8 + 12 * (e + 1)) - 1 : offsets.length;
      for (let c = first; c < Math.min(last, offsets.length); c++) {
        let bytes = 0;
        for (let k = 0; k < perChunk && sample < sizes.length; k++) bytes += sizes[sample++];
        if (offsets[c] + bytes > fileSize) {
          throw new Mp4Error("truncated", "La vidéo semble incomplète (téléchargement interrompu ?).");
        }
        chunks.push({ offset: offsets[c], size: bytes, samples: perChunk });
      }
    }
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
      for (let k = 0; k < ch.samples && s < sizes.length; k++, s++) {
        out.offsets.push(off); out.sizes.push(sizes[s]); off += sizes[s];
      }
    }
    const stts = child(stbl, "stts");
    if (stts) {
      const p = payload(stts);
      const n = u32(p, 4);
      for (let e = 0; e < n; e++) {
        const count = u32(p, 8 + 8 * e), delta = u32(p, 12 + 8 * e);
        for (let k = 0; k < count; k++) out.durations.push(delta);
      }
    }
    out.durations.length = out.sizes.length;
    for (let i = 0; i < out.durations.length; i++) if (out.durations[i] == null) out.durations[i] = 0;
    return out;
  }

  // --- MP4 fragmenté (moof/traf/trun) ----------------------------------------

  function trexFor(moov, trackId) {
    for (const trex of childrenOf(child(moov, "mvex"), "trex")) {
      const p = payload(trex);
      if (u32(p, 4) === trackId) return { duration: u32(p, 12), size: u32(p, 16) };
    }
    return { duration: 0, size: 0 };
  }

  async function fragmentSamples(blob, tops, trackId, trex, onProgress) {
    const out = { offsets: [], sizes: [], durations: [] };
    const moofs = tops.filter((b) => b.type === "moof");
    for (let m = 0; m < moofs.length; m++) {
      const box = moofs[m];
      const buf = await readBytes(blob, box.start, box.size);
      const moof = parseBoxes(buf, 0, buf.length)[0];
      let prevEnd = box.start;
      for (const traf of childrenOf(moof, "traf")) {
        const tfhdBox = child(traf, "tfhd");
        if (!tfhdBox) continue;
        const t = payload(tfhdBox);
        const tf = flagsOf(t);
        const id = u32(t, 4);
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
          const rf = flagsOf(r);
          const count = u32(r, 4);
          let o = 8;
          if (rf & 0x1) { cursor = base + i32(r, o); o += 4; }
          if (rf & 0x4) o += 4;
          for (let i = 0; i < count; i++) {
            let dur = defDur, size = defSize;
            if (rf & 0x100) { dur = u32(r, o); o += 4; }
            if (rf & 0x200) { size = u32(r, o); o += 4; }
            if (rf & 0x400) o += 4;
            if (rf & 0x800) o += 4;
            if (id === trackId) {
              if (cursor + size > blob.size) {
                throw new Mp4Error("truncated", "La vidéo semble incomplète (téléchargement interrompu ?).");
              }
              out.offsets.push(cursor); out.sizes.push(size); out.durations.push(dur);
            }
            cursor += size;
          }
        }
        prevEnd = cursor;
      }
      if (onProgress && (m % 50 === 0 || m === moofs.length - 1)) onProgress((m + 1) / moofs.length);
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

  function u32Array(values) {
    const b = new Uint8Array(4 * values.length);
    values.forEach((v, i) => w32(b, 4 * i, v));
    return b;
  }

  function ftypBox() {
    return box("ftyp", typeBytes("M4A "), new Uint8Array(4), typeBytes("M4A mp42isom"));
  }

  // Titre iTunes (©nam) — affiché par la plupart des lecteurs.
  function titleBox(title) {
    if (!title) return null;
    const text = new TextEncoder().encode(String(title).slice(0, 200));
    const data = box("data", u32Array([1, 0]), text);
    const hdlr = fullBox("hdlr", 0, 0, Uint8Array.from([0, 0, 0, 0, ...typeBytes("mdir"), ...typeBytes("appl"), 0, 0, 0, 0, 0, 0, 0, 0, 0]));
    return box("udta", fullBox("meta", 0, 0, concat([hdlr, box("ilst", box("©nam", data))])));
  }

  function concat(parts) {
    const len = parts.reduce((s, p) => s + p.length, 0);
    const out = new Uint8Array(len);
    let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }

  function chunkOffsetBox(offsets) {
    const big = offsets.length && offsets[offsets.length - 1] > 0xffffffff;
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
      const e = stts[stts.length - 1];
      if (e && e[1] === d) e[0]++; else stts.push([1, d]);
    }
    const stsc = [];
    chunks.forEach((c, i) => {
      const e = stsc[stsc.length - 1];
      if (!e || e[1] !== c.samples) stsc.push([i + 1, c.samples, 1]);
    });
    const allSame = s.sizes.every((v) => v === s.sizes[0]);
    const boxes = {
      stts: fullBox("stts", 0, 0, u32Array([stts.length, ...stts.flat()])),
      stsc: fullBox("stsc", 0, 0, u32Array([stsc.length, ...stsc.flat()])),
      stsz: fullBox("stsz", 0, 0, u32Array(allSame ? [s.sizes[0] || 0, s.sizes.length] : [0, s.sizes.length, ...s.sizes])),
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
    // 1er passage pour mesurer le moov (sa taille dépend du type stco/co64).
    let moov = buildMoov(offsetsFrom(0));
    let dataStart = ftyp.length + moov.length + mdatHdr.length;
    moov = buildMoov(offsetsFrom(dataStart));
    dataStart = ftyp.length + moov.length + mdatHdr.length;
    moov = buildMoov(offsetsFrom(dataStart));

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

  // --- Point d'entrée --------------------------------------------------------

  async function extractAudio(blob, opts = {}) {
    const onProgress = opts.onProgress || null;
    const tops = await scanTopLevel(blob);
    const moovTop = tops.find((b) => b.type === "moov");
    if (!moovTop) throw new Mp4Error("no_moov", "Vidéo incomplète ou illisible (index « moov » absent).");
    if (moovTop.size > 256 * 1024 * 1024) throw new Mp4Error("corrupt", "Index vidéo anormalement gros.");
    const moovBuf = await readBytes(blob, moovTop.start, moovTop.size);
    const moov = parseBoxes(moovBuf, 0, moovBuf.length)[0];

    const traks = childrenOf(moov, "trak");
    const audio = traks.filter((t) => handlerOf(t) === "soun");
    if (!audio.length) throw new Mp4Error("no_audio", "Aucune piste audio dans cette vidéo.");
    const trak = audio.find((t) => readTkhd(child(t, "tkhd")).flags & 1) || audio[0];
    checkSelfContained(trak);

    const tkhd = child(trak, "tkhd");
    const mdia = child(trak, "mdia");
    const mdhd = child(mdia, "mdhd");
    const minf = child(mdia, "minf");
    const stbl = child(minf, "stbl");
    const mvhd = child(moov, "mvhd");
    if (!tkhd || !mdhd || !stbl || !mvhd) throw new Mp4Error("corrupt", "Piste audio illisible.");
    const stsd = child(stbl, "stsd");
    const info = sampleEntryInfo(stsd);
    const media = readTimes(mdhd);
    const movieScale = readTimes(mvhd).timescale || media.timescale;
    const udta = titleBox(opts.title);

    const fragmented = !!child(moov, "mvex") || tops.some((b) => b.type === "moof");
    let out, mediaDuration;

    if (!fragmented) {
      // Cas courant : on garde les tables d'origine, seul stco change.
      const { chunks } = chunkLayout(stbl, blob.size);
      if (!chunks.length) throw new Mp4Error("empty", "La piste audio est vide.");
      mediaDuration = media.duration;
      const trackDuration = readTkhd(tkhd).duration;
      out = assemble(blob, chunks, (offsets) => {
        const stblOut = box("stbl", ...stbl.children.map((c) =>
          c.type === "stco" || c.type === "co64" ? chunkOffsetBox(offsets) : raw(c)));
        const minfOut = box("minf", ...minf.children.map((c) => (c.type === "stbl" ? stblOut : raw(c))));
        const mdiaOut = box("mdia", ...mdia.children.map((c) => (c.type === "minf" ? minfOut : raw(c))));
        const keep = trak.children.filter((c) => c.type === "edts").map(raw);
        const trakOut = box("trak", patchedTkhd(tkhd, null), ...keep, mdiaOut);
        return box("moov", patchedTimes(mvhd, trackDuration), trakOut, ...(udta ? [udta] : []));
      });
    } else {
      // MP4 fragmenté : on reconstruit des tables classiques (fichier « à plat »).
      const trackId = readTkhd(tkhd).trackId;
      const samples = stblSamples(stbl, blob.size);
      const frag = await fragmentSamples(blob, tops, trackId, trexFor(moov, trackId), onProgress);
      for (const k of ["offsets", "sizes", "durations"]) samples[k] = samples[k].concat(frag[k]);
      if (!samples.sizes.length) throw new Mp4Error("empty", "La piste audio est vide.");
      mediaDuration = samples.durations.reduce((a, b) => a + b, 0);
      if (!mediaDuration) throw new Mp4Error("corrupt", "Durées d'échantillons manquantes.");
      const trackDuration = Math.round(mediaDuration * movieScale / media.timescale);
      const { chunks, boxes } = tablesFromSamples(samples);
      out = assemble(blob, chunks, (offsets) => {
        const stblOut = box("stbl", raw(stsd), boxes.stts, boxes.stsc, boxes.stsz, chunkOffsetBox(offsets));
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
      duration: media.timescale ? mediaDuration / media.timescale : 0,
      codec: info.codec,
      channels: info.channels,
      sampleRate: media.timescale,
      fragmented,
    };
  }

  // Détection rapide : le fichier commence-t-il comme un MP4/MOV ?
  async function looksLikeMp4(blob) {
    if (blob.size < 8) return false;
    const h = await readBytes(blob, 0, 8);
    return TOP_TYPES.has(fourcc(h, 4));
  }

  const api = { extractAudio, looksLikeMp4, Mp4Error };
  global.Mp4Audio = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
