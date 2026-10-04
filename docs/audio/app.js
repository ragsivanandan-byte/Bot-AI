"use strict";
// Leçons Audio — interface : ajout/conversion, bibliothèque hors ligne
// (IndexedDB, sur l'appareil) et lecteur (reprise, vitesse, écran verrouillé).
(function () {
  const $ = (id) => document.getElementById(id);
  const audio = $("audio");

  // --- Préférences locales (facultatives) ------------------------------------
  const pref = {
    get(k, d) { try { const v = localStorage.getItem("la:" + k); return v === null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("la:" + k, v); } catch (e) { /* stockage indisponible */ } },
  };

  // --- Formatage -----------------------------------------------------------------
  function fmtTime(s) {
    if (!isFinite(s) || s < 0) s = 0;
    s = Math.floor(s);
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
  }
  function fmtDur(s) {
    if (!s || !isFinite(s)) return "";
    const m = Math.round(s / 60);
    if (m < 1) return `${Math.round(s)} s`;
    if (m < 60) return `${m} min`;
    return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
  }
  function fmtSize(b) {
    if (!b) return "0 Mo";
    if (b < 1e6) return `${Math.max(1, Math.round(b / 1e3))} Ko`;
    if (b < 1e9) return `${(b / 1e6).toFixed(b < 1e7 ? 1 : 0).replace(".", ",")} Mo`;
    return `${(b / 1e9).toFixed(1).replace(".", ",")} Go`;
  }
  const frDate = (iso) => (iso ? iso.split("-").reverse().join("/") : "");

  // « 2026-09-20-bitcoin-talk-life-discord » -> titre + date.
  function prettyName(base) {
    let date = null, rest = base;
    const m = base.match(/^(\d{4})-(\d{2})-(\d{2})[-_ .]*(.*)$/);
    if (m) { date = `${m[1]}-${m[2]}-${m[3]}`; rest = m[4]; }
    let title = rest.replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
    if (title) title = title[0].toUpperCase() + title.slice(1);
    return { title: title || (date ? `Leçon du ${frDate(date)}` : "Leçon"), date };
  }
  const safeFileName = (t) => (t.replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 100) || "lecon");

  function toast(msg, ms = 2600) {
    const el = $("toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => { el.hidden = true; }, ms);
  }

  // --- Stockage IndexedDB : métadonnées (tracks) + fichiers audio (blobs) ---------
  let dbp = null;
  function db() {
    if (!dbp) {
      dbp = new Promise((resolve, reject) => {
        const req = indexedDB.open("lecons-audio", 1);
        req.onupgradeneeded = () => {
          const d = req.result;
          if (!d.objectStoreNames.contains("tracks")) d.createObjectStore("tracks", { keyPath: "id" });
          if (!d.objectStoreNames.contains("blobs")) d.createObjectStore("blobs");
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
    }
    return dbp;
  }
  async function tx(stores, mode, fn) {
    const d = await db();
    return new Promise((resolve, reject) => {
      const t = d.transaction(stores, mode);
      let out;
      const req = fn(t);
      if (req) req.onsuccess = () => { out = req.result; };
      t.oncomplete = () => resolve(out);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error || new Error("Enregistrement annulé (espace insuffisant ?)"));
    });
  }
  const dbAll = () => tx("tracks", "readonly", (t) => t.objectStore("tracks").getAll());
  const dbPut = (track) => tx("tracks", "readwrite", (t) => t.objectStore("tracks").put(track));
  const dbBlob = (id) => tx("blobs", "readonly", (t) => t.objectStore("blobs").get(id));
  async function dbAdd(track, blob) {
    try {
      await tx(["tracks", "blobs"], "readwrite", (t) => { t.objectStore("blobs").put(blob, track.id); t.objectStore("tracks").put(track); });
    } catch (e) {
      // Repli pour les moteurs qui refusent les Blob dans IndexedDB.
      const buf = await blob.arrayBuffer();
      await tx(["tracks", "blobs"], "readwrite", (t) => { t.objectStore("blobs").put(buf, track.id); t.objectStore("tracks").put(track); });
    }
  }
  const dbDelete = (id) => tx(["tracks", "blobs"], "readwrite", (t) => { t.objectStore("blobs").delete(id); t.objectStore("tracks").delete(id); });

  // --- État ---------------------------------------------------------------------
  const state = { tracks: new Map(), currentId: null, loading: false, pendingSeek: 0 };
  const media = new Map(); // id -> { blob, url } (prêt à lire tout de suite)

  async function mediaFor(id) {
    let m = media.get(id);
    if (m) return m;
    const t = state.tracks.get(id);
    let v = await dbBlob(id);
    if (!v) throw new Error("Fichier audio introuvable.");
    if (!(v instanceof Blob)) v = new Blob([v], { type: (t && t.mime) || "audio/mp4" });
    m = { blob: v, url: URL.createObjectURL(v) };
    media.set(id, m);
    return m;
  }

  // --- Onglets ------------------------------------------------------------------
  const TABS = ["library", "add", "help"];
  function showTab(name) {
    for (const t of TABS) {
      $("tab-" + t).setAttribute("aria-selected", String(t === name));
      $(t).hidden = t !== name;
    }
    pref.set("tab", name);
    if (name === "help") loadScript();
  }
  for (const t of TABS) $("tab-" + t).addEventListener("click", () => showTab(t));
  $("empty-add").addEventListener("click", () => showTab("add"));

  // --- Bibliothèque ---------------------------------------------------------------
  function trackRow(t) {
    const li = document.createElement("li");
    li.className = "track";
    li.dataset.id = t.id;
    const main = document.createElement("button");
    main.type = "button";
    main.className = "track-main";
    const title = document.createElement("span");
    title.className = "t-title";
    const meta = document.createElement("span");
    meta.className = "t-meta";
    const bar = document.createElement("span");
    bar.className = "t-bar";
    bar.appendChild(document.createElement("span"));
    main.append(title, meta, bar);
    main.addEventListener("click", () => playTrack(t.id));
    const more = document.createElement("button");
    more.type = "button";
    more.className = "t-more";
    more.textContent = "⋯";
    more.setAttribute("aria-label", "Options");
    more.addEventListener("click", () => openMenu(t.id));
    li.append(main, more);
    fillRow(li, t);
    return li;
  }

  function fillRow(li, t) {
    li.querySelector(".t-title").textContent = t.title;
    const bits = [];
    if (t.date) bits.push(frDate(t.date));
    if (t.duration) bits.push(fmtDur(t.duration));
    bits.push(fmtSize(t.size));
    if (t.done) bits.push("écoutée ✓");
    else if (t.position > 5) bits.push("reprise à " + fmtTime(t.position));
    li.querySelector(".t-meta").textContent = bits.join(" · ");
    const pct = t.done ? 100 : t.duration ? Math.min(100, (100 * t.position) / t.duration) : 0;
    li.querySelector(".t-bar span").style.width = pct + "%";
    li.classList.toggle("done", !!t.done);
    li.classList.toggle("current", t.id === state.currentId);
  }

  function refreshRow(id) {
    const t = state.tracks.get(id);
    const li = document.querySelector(`.track[data-id="${CSS.escape(id)}"]`);
    if (t && li) fillRow(li, t);
  }

  async function renderLibrary() {
    const tracks = (await dbAll()).sort((a, b) => b.addedAt - a.addedAt);
    state.tracks = new Map(tracks.map((t) => [t.id, t]));
    const ul = $("tracks");
    ul.replaceChildren(...tracks.map(trackRow));
    $("empty").hidden = tracks.length > 0;
    updateStorage();
    // Prépare les fichiers : un toucher lance la lecture immédiatement (exigence iOS).
    for (const t of tracks) await mediaFor(t.id).catch(() => {});
  }

  async function updateStorage() {
    let total = 0;
    for (const t of state.tracks.values()) total += t.size || 0;
    const n = state.tracks.size;
    $("storage").textContent = n ? `${n} leçon${n > 1 ? "s" : ""} · ${fmtSize(total)}` : "";
  }

  // --- Ajout / conversion -----------------------------------------------------------
  const AUDIO_EXT = /\.(mp3|m4a|m4b|aac|wav|caf|flac|aiff?)$/i;
  const MIME = { mp3: "audio/mpeg", m4a: "audio/mp4", m4b: "audio/mp4", aac: "audio/aac", wav: "audio/wav", caf: "audio/x-caf", flac: "audio/flac", aif: "audio/aiff", aiff: "audio/aiff" };

  function probeDuration(blob) {
    return new Promise((resolve) => {
      const a = document.createElement("audio");
      const url = URL.createObjectURL(blob);
      const done = (d) => { URL.revokeObjectURL(url); resolve(isFinite(d) ? d : 0); };
      a.preload = "metadata";
      a.onloadedmetadata = () => done(a.duration);
      a.onerror = () => done(0);
      setTimeout(() => done(0), 8000);
      a.src = url;
    });
  }

  async function convert(file, onProgress) {
    const base = file.name.replace(/\.[^.]+$/, "");
    const { title, date } = prettyName(base);
    if (await Mp4Audio.looksLikeMp4(file)) {
      const r = await Mp4Audio.extractAudio(file, { title, onProgress });
      return { blob: r.blob, duration: r.duration, title, date, mime: "audio/mp4" };
    }
    if (/^audio\//.test(file.type) || AUDIO_EXT.test(file.name)) {
      const ext = (file.name.match(/\.([^.]+)$/) || [])[1] || "";
      return { blob: file, duration: await probeDuration(file), title, date, mime: file.type || MIME[ext.toLowerCase()] || "audio/mpeg" };
    }
    if (/^video\//.test(file.type) || /\.(webm|mkv|avi|wmv|flv|ts)$/i.test(file.name)) {
      throw new Error("Format vidéo non pris en charge : seuls MP4, MOV et M4V sont acceptés.");
    }
    throw new Error("Ce fichier n'est ni une vidéo MP4/MOV ni un fichier audio.");
  }

  function newId() {
    return (crypto.randomUUID && crypto.randomUUID()) || Date.now().toString(36) + Math.random().toString(36).slice(2);
  }

  async function importFiles(files) {
    const jobs = $("jobs");
    let added = 0;
    for (const file of files) {
      const li = document.createElement("li");
      li.className = "job";
      const name = document.createElement("strong");
      name.textContent = file.name;
      const st = document.createElement("span");
      st.className = "j-state";
      st.textContent = `Extraction de l'audio… (${fmtSize(file.size)})`;
      li.append(name, st);
      jobs.prepend(li);
      try {
        const r = await convert(file, (p) => { st.textContent = `Analyse de la vidéo… ${Math.round(p * 100)} %`; });
        st.textContent = `Enregistrement sur l'iPhone… (${fmtSize(r.blob.size)})`;
        const track = {
          id: newId(), title: r.title, date: r.date, fileName: file.name, mime: r.mime,
          size: r.blob.size, duration: r.duration, addedAt: Date.now(), position: 0, done: false,
        };
        await dbAdd(track, r.blob);
        li.classList.add("ok");
        st.textContent = `✓ Ajoutée : ${r.title} — ${[fmtDur(r.duration), fmtSize(r.blob.size)].filter(Boolean).join(" · ")}`;
        added++;
      } catch (e) {
        li.classList.add("err");
        const quota = e && (e.name === "QuotaExceededError" || /quota/i.test(e.message || ""));
        st.textContent = "✗ " + (quota ? "Espace de stockage insuffisant sur l'iPhone." : (e && e.message) || "Échec de la conversion.");
        console.error(e);
      }
    }
    if (added) {
      try { if (navigator.storage && navigator.storage.persist) await navigator.storage.persist(); } catch (e) { /* facultatif */ }
      await renderLibrary();
      toast(added > 1 ? `${added} leçons ajoutées` : "Leçon ajoutée à la bibliothèque");
      showTab("library");
    }
  }

  $("file").addEventListener("change", (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (files.length) importFiles(files);
  });

  // --- Lecteur ---------------------------------------------------------------------
  const SPEEDS = [1, 1.25, 1.5, 1.75, 2, 0.75];
  let speed = Number(pref.get("speed", "1")) || 1;
  const speedLabel = (s) => String(s).replace(".", ",") + "×";
  $("p-speed").textContent = speedLabel(speed);

  function playTrack(id) {
    if (state.currentId === id && audio.src) { togglePlay(); return; }
    const m = media.get(id);
    if (m) { startTrack(id, m); return; }
    // Fichier pas encore prêt : on « déverrouille » l'audio pendant le geste (iOS).
    audio.removeAttribute("src");
    audio.play().catch(() => {});
    mediaFor(id).then((mm) => startTrack(id, mm)).catch((e) => toast(e.message));
  }

  function startTrack(id, m) {
    savePosition();
    const t = state.tracks.get(id);
    if (!t) return;
    const prev = state.currentId;
    state.currentId = id;
    state.loading = true;
    state.pendingSeek = !t.done && t.position > 3 && (!t.duration || t.position < t.duration - 5) ? t.position : 0;
    audio.src = m.url;
    audio.defaultPlaybackRate = speed;
    audio.playbackRate = speed;
    audio.play().catch(() => { /* lecture refusée : le bouton ▶ reste disponible */ });
    $("p-title").textContent = t.title;
    $("player").hidden = false;
    document.body.classList.add("has-player");
    if (prev) refreshRow(prev);
    refreshRow(id);
    setMediaSession(t);
  }

  function togglePlay() {
    if (!audio.src) return;
    if (audio.paused) audio.play().catch(() => {}); else audio.pause();
  }

  function skip(delta) {
    if (!audio.src || !isFinite(audio.duration)) return;
    audio.currentTime = Math.max(0, Math.min(audio.duration - 0.5, audio.currentTime + delta));
  }

  function savePosition() {
    const t = state.currentId && state.tracks.get(state.currentId);
    if (!t || state.loading || !audio.src) return;
    t.position = audio.currentTime || 0;
    if (!t.duration && isFinite(audio.duration)) t.duration = audio.duration;
    dbPut(t).catch(() => {});
    refreshRow(t.id);
  }

  audio.addEventListener("loadedmetadata", () => {
    if (state.pendingSeek) audio.currentTime = state.pendingSeek;
    state.pendingSeek = 0;
    state.loading = false;
    audio.playbackRate = speed;
    updateTimes();
    updatePositionState();
  });
  let lastSave = 0, dragging = false;
  audio.addEventListener("timeupdate", () => {
    updateTimes();
    if (Date.now() - lastSave > 5000) { lastSave = Date.now(); savePosition(); }
  });
  audio.addEventListener("play", () => { $("p-play").textContent = "❚❚"; $("p-play").setAttribute("aria-label", "Pause"); updatePositionState(); });
  audio.addEventListener("pause", () => { $("p-play").textContent = "▶"; $("p-play").setAttribute("aria-label", "Lecture"); savePosition(); });
  audio.addEventListener("ratechange", updatePositionState);
  audio.addEventListener("seeked", updatePositionState);
  audio.addEventListener("ended", () => {
    const t = state.tracks.get(state.currentId);
    if (!t) return;
    t.done = true;
    t.position = 0;
    dbPut(t).catch(() => {});
    refreshRow(t.id);
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) savePosition(); });
  window.addEventListener("pagehide", savePosition);

  function updateTimes() {
    const d = audio.duration, c = audio.currentTime;
    if (!isFinite(d) || !d) return;
    $("p-cur").textContent = fmtTime(c);
    $("p-left").textContent = "-" + fmtTime(d - c);
    if (!dragging) $("p-range").value = String(Math.round((1000 * c) / d));
  }

  const range = $("p-range");
  range.addEventListener("input", () => {
    dragging = true;
    if (isFinite(audio.duration)) $("p-cur").textContent = fmtTime((range.value / 1000) * audio.duration);
  });
  range.addEventListener("change", () => {
    dragging = false;
    if (isFinite(audio.duration)) audio.currentTime = (range.value / 1000) * audio.duration;
  });
  $("p-play").addEventListener("click", togglePlay);
  $("p-back").addEventListener("click", () => skip(-15));
  $("p-fwd").addEventListener("click", () => skip(30));
  $("p-speed").addEventListener("click", () => {
    speed = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length] || 1;
    audio.defaultPlaybackRate = speed;
    audio.playbackRate = speed;
    $("p-speed").textContent = speedLabel(speed);
    pref.set("speed", String(speed));
  });
  $("p-close").addEventListener("click", () => {
    audio.pause();
    savePosition();
    const prev = state.currentId;
    state.currentId = null;
    audio.removeAttribute("src");
    audio.load();
    $("player").hidden = true;
    document.body.classList.remove("has-player");
    if (prev) refreshRow(prev);
  });

  // Écran verrouillé / Centre de contrôle.
  function setMediaSession(t) {
    if (!("mediaSession" in navigator)) return;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: t.title,
        artist: "Leçons Audio",
        album: t.date ? frDate(t.date) : "",
        artwork: [{ src: new URL("icon-512.png", location.href).href, sizes: "512x512", type: "image/png" }],
      });
    } catch (e) { /* non pris en charge */ }
  }
  function updatePositionState() {
    if (!("mediaSession" in navigator) || !navigator.mediaSession.setPositionState) return;
    const d = audio.duration;
    if (!isFinite(d) || !d) return;
    try {
      navigator.mediaSession.setPositionState({ duration: d, playbackRate: audio.playbackRate || 1, position: Math.min(audio.currentTime, d) });
    } catch (e) { /* ignoré */ }
  }
  if ("mediaSession" in navigator) {
    const handlers = {
      play: () => audio.play(),
      pause: () => audio.pause(),
      seekbackward: (d) => skip(-((d && d.seekOffset) || 15)),
      seekforward: (d) => skip((d && d.seekOffset) || 30),
      seekto: (d) => { if (d && isFinite(d.seekTime)) audio.currentTime = d.seekTime; },
    };
    for (const k in handlers) { try { navigator.mediaSession.setActionHandler(k, handlers[k]); } catch (e) { /* action inconnue */ } }
  }

  // --- Menu d'une leçon -------------------------------------------------------------
  const menu = $("menu");
  let menuId = null;
  function openMenu(id) {
    const t = state.tracks.get(id);
    if (!t) return;
    menuId = id;
    $("menu-title").textContent = t.title;
    menu.querySelector('[data-act="done"]').textContent = t.done ? "Marquer comme non écoutée" : "Marquer comme écoutée";
    if (menu.showModal) menu.showModal(); else menu.setAttribute("open", "");
  }
  function closeMenu() { if (menu.close) menu.close(); else menu.removeAttribute("open"); }
  menu.addEventListener("click", (e) => {
    const r = menu.getBoundingClientRect();
    if (e.target === menu && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) {
      closeMenu(); // toucher hors de la feuille
      return;
    }
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = menuId, t = state.tracks.get(id);
    closeMenu();
    if (!t) return;
    const act = btn.dataset.act;
    if (act === "share") shareTrack(t);
    else if (act === "rename") {
      const v = prompt("Nouveau titre", t.title);
      if (v && v.trim()) {
        t.title = v.trim();
        dbPut(t).then(() => refreshRow(id));
        if (state.currentId === id) { $("p-title").textContent = t.title; setMediaSession(t); }
      }
    } else if (act === "done") {
      t.done = !t.done;
      t.position = 0;
      dbPut(t).then(() => refreshRow(id));
    } else if (act === "delete") {
      if (!confirm(`Supprimer « ${t.title} » de l'iPhone ?`)) return;
      if (state.currentId === id) $("p-close").click();
      const m = media.get(id);
      if (m) { URL.revokeObjectURL(m.url); media.delete(id); }
      dbDelete(id).then(renderLibrary).then(() => toast("Leçon supprimée"));
    }
  });

  function shareTrack(t) {
    const m = media.get(t.id);
    if (!m) { mediaFor(t.id).then(() => toast("Fichier prêt : touchez à nouveau « Enregistrer »")); return; }
    const ext = /mpeg/.test(t.mime) ? "mp3" : /aac/.test(t.mime) ? "aac" : /wav/.test(t.mime) ? "wav" : "m4a";
    const name = `${t.date ? t.date + " " : ""}${safeFileName(t.title)}.${ext}`;
    const file = new File([m.blob], name, { type: t.mime || "audio/mp4" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      navigator.share({ files: [file], title: t.title }).catch(() => {});
      return;
    }
    const a = document.createElement("a");
    a.href = m.url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  // --- Mode d'emploi : script du raccourci + boutons « Copier » -------------------------
  let scriptLoaded = false;
  function loadScript() {
    if (scriptLoaded) return;
    scriptLoaded = true;
    fetch("detect.js")
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(r.status))))
      .then((code) => {
        $("script-code").textContent = code;
        $("script-size").textContent = `${code.split("\n").length} lignes`;
      })
      .catch(() => { scriptLoaded = false; $("script-code").textContent = "Script indisponible hors ligne : rouvrez cette page avec une connexion."; });
  }
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* repli ci-dessous */ }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    const text = $(btn.dataset.copy).textContent;
    if (!text || text === "Chargement…") { toast("Patientez, chargement du script…"); return; }
    toast((await copyText(text)) ? "Copié ✓ — collez-le dans le raccourci" : "Copie impossible : sélectionnez le texte manuellement");
  });

  // --- Installation sur l'écran d'accueil -------------------------------------------------
  const standalone = navigator.standalone === true || (window.matchMedia && matchMedia("(display-mode: standalone)").matches);
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  if (ios && !standalone && pref.get("tipClosed", "") !== "1") $("install-tip").hidden = false;
  $("install-tip-close").addEventListener("click", () => { $("install-tip").hidden = true; pref.set("tipClosed", "1"); });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
  }

  // --- Démarrage ---------------------------------------------------------------------
  const startTab = pref.get("tab", "library");
  showTab(TABS.includes(startTab) ? startTab : "library");
  renderLibrary().catch((e) => {
    console.error(e);
    toast("Bibliothèque indisponible (navigation privée ?)", 5000);
  });

  // Exposé pour les tests automatisés.
  window.__leconsAudioApp = { importFiles, state, prettyName };
})();
