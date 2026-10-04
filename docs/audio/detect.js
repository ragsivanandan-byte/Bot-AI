// Leçons Audio — script de l'action « Exécuter du JavaScript sur une page web »
// du raccourci iOS « Leçon en audio ».
//
// Il s'exécute DANS la page de la leçon ouverte dans Safari (donc avec votre
// session connectée), repère la vidéo (Vimeo, YouTube, Wistia, Bunny, lecteur
// HTML5, HLS…) et renvoie au raccourci la commande yt-dlp à lancer dans a-Shell
// pour télécharger UNIQUEMENT la piste audio.
(function () {
  "use strict";

  var HOSTS = [
    [/(^|\.)vimeo\.com$/, "vimeo"],
    [/(^|\.)(youtube|youtube-nocookie)\.com$/, "youtube"],
    [/(^|\.)youtu\.be$/, "youtube"],
    [/(^|\.)(wistia\.com|wistia\.net|wi\.st)$/, "wistia"],
    [/(^|\.)mediadelivery\.net$/, "bunny"],
    [/(^|\.)loom\.com$/, "loom"],
    [/(^|\.)(dailymotion\.com|dai\.ly)$/, "dailymotion"],
    [/(^|\.)vidyard\.com$/, "vidyard"],
    [/(^|\.)brightcove\.(net|com)$/, "brightcove"],
    [/(^|\.)(jwplayer\.com|jwplatform\.com|jwpcdn\.com)$/, "jwplayer"],
    [/(^|\.)(cloudflarestream\.com|videodelivery\.net)$/, "cloudflare"],
    [/(^|\.)spotlightr\.com$/, "spotlightr"],
    [/(^|\.)streamable\.com$/, "streamable"],
    [/(^|\.)kaltura\.com$/, "kaltura"],
  ];
  var MEDIA_EXT = /\.(mp4|m4v|mov|m4a|mp3|aac|m3u8|mpd|webm)(\?|#|$)/i;
  var STREAM_EXT = /\.(m3u8|mpd)(\?|#|$)/i;
  // Attributs portant l'adresse d'une vidéo : sur iframe/vidéo (src paresseux)…
  var SRC_ATTRS = ["src", "data-src", "data-lazy-src", "data-litespeed-src", "data-rocket-src", "data-url", "data-video-url", "data-video-src"];
  // … et sur n'importe quel élément (lecteurs chargés en JavaScript).
  var ANY_ATTRS = ["data-video-url", "data-video-src", "data-embed-url", "data-vimeo-url"];
  // Accents à retirer des noms de fichiers (marques combinantes U+0300 à U+036F).
  var ACCENTS = new RegExp("[" + String.fromCharCode(0x300) + "-" + String.fromCharCode(0x36f) + "]", "g");

  function abs(u) {
    if (!u || typeof u !== "string") return null;
    u = u.trim();
    if (/^(blob|data|about|javascript|mediastream):/i.test(u)) return null;
    try {
      var x = new URL(u, document.baseURI);
      return /^https?:$/.test(x.protocol) ? x : null;
    } catch (e) { return null; }
  }

  function providerOf(url) {
    for (var i = 0; i < HOSTS.length; i++) if (HOSTS[i][0].test(url.hostname)) return HOSTS[i][1];
    return MEDIA_EXT.test(url.pathname) ? "media" : null;
  }

  // URL canonique comprise par yt-dlp pour chaque hébergeur, ou null si ce
  // n'est pas une vidéo (script player.js, logo, page d'accueil…).
  function canonical(url, provider) {
    var m;
    if (provider === "vimeo") {
      if (url.hostname.indexOf("player.") === 0) {
        m = url.pathname.match(/^\/video\/(\d+)/);
        if (!m) return null;
        var h = url.searchParams.get("h");
        return "https://player.vimeo.com/video/" + m[1] + (h ? "?h=" + encodeURIComponent(h) : "");
      }
      // vimeo.com/ID ou vimeo.com/ID/HASH -> lecteur intégré (accepte le referer).
      m = url.pathname.match(/^\/(\d+)(?:\/([0-9a-f]+))?\/?$/);
      if (m) return "https://player.vimeo.com/video/" + m[1] + (m[2] ? "?h=" + m[2] : "");
      return /\/\d{5,}(\/|$)/.test(url.pathname) ? url.href : null;
    }
    if (provider === "youtube") {
      m = url.pathname.match(/\/(?:embed|shorts|live|v)\/([\w-]{6,})/) ||
        (url.hostname.indexOf("youtu.be") >= 0 && url.pathname.match(/^\/([\w-]{6,})/));
      var id = (m && m[1]) || url.searchParams.get("v");
      return id && id !== "videoseries" ? "https://www.youtube.com/watch?v=" + id : null;
    }
    if (provider === "wistia") {
      m = url.pathname.match(/\/(?:embed\/iframe|embed\/medias|medias)\/([a-z0-9]+)/i);
      return m ? "https://fast.wistia.net/embed/iframe/" + m[1] : null;
    }
    return url.href;
  }

  // Une même vidéo peut apparaître sous plusieurs formes (iframe + attribut) :
  // on les fusionne par identifiant en gardant l'URL la plus complète (hash Vimeo).
  function keyOf(href, provider) {
    var m;
    if (provider === "vimeo" && (m = href.match(/vimeo\.com\/(?:video\/)?(\d+)/))) return "vimeo:" + m[1];
    if (provider === "youtube" && (m = href.match(/[?&]v=([\w-]+)/))) return "youtube:" + m[1];
    return href;
  }

  var found = [];
  var ignored = {}; // vidéos décoratives (aussi visibles dans les ressources chargées)
  var order = 0;
  var mseArea = -1; // plus grande vidéo alimentée en flux (src « blob: », HLS/DASH)

  function areaOf(el) {
    if (!el || !el.getBoundingClientRect) return 0;
    var r = el.getBoundingClientRect();
    return Math.max(0, r.width) * Math.max(0, r.height);
  }

  function add(rawUrl, el, priority, forcedArea) {
    var url = abs(rawUrl);
    if (!url || ignored[url.href]) return;
    var provider = providerOf(url);
    if (!provider) return;
    var href = canonical(url, provider);
    if (!href) return;
    var key = keyOf(href, provider);
    var area = forcedArea != null ? forcedArea : areaOf(el);
    for (var i = 0; i < found.length; i++) {
      if (found[i].key === key) {
        found[i].area = Math.max(found[i].area, area);
        found[i].priority = Math.max(found[i].priority, priority);
        if (href.length > found[i].url.length) found[i].url = href;
        return;
      }
    }
    found.push({ url: href, key: key, provider: provider, priority: priority, area: area, order: order++ });
  }

  function addById(provider, id, el) {
    provider = String(provider).toLowerCase();
    id = String(id).trim();
    if (/^https?:/i.test(id)) return add(id, el, 3);
    if (provider.indexOf("vimeo") >= 0) add("https://player.vimeo.com/video/" + id, el, 3);
    else if (provider.indexOf("youtube") >= 0) add("https://www.youtube.com/watch?v=" + id, el, 3);
    else if (provider.indexOf("wistia") >= 0) add("https://fast.wistia.net/embed/iframe/" + id, el, 3);
  }

  function visit(el) {
    var tag = el.tagName;
    var i;
    if (tag === "SCRIPT" || tag === "LINK" || tag === "IMG" || tag === "STYLE") return;
    if (tag === "IFRAME" || tag === "EMBED" || tag === "OBJECT") {
      for (i = 0; i < SRC_ATTRS.length; i++) add(el.getAttribute(SRC_ATTRS[i]), el, 3);
      add(el.getAttribute("data"), el, 3);
    } else if (tag === "VIDEO" || tag === "AUDIO") {
      var srcs = [el.currentSrc, el.getAttribute("src")];
      var subs = el.querySelectorAll("source");
      for (i = 0; i < subs.length; i++) srcs.push(subs[i].getAttribute("src"));
      // Vidéo décorative (fond animé muet en boucle) : ignorée.
      if (el.autoplay && el.muted && el.loop && !el.controls) {
        for (i = 0; i < srcs.length; i++) { var u = abs(srcs[i]); if (u) ignored[u.href] = true; }
        return;
      }
      if (/^blob:/i.test(el.currentSrc || el.getAttribute("src") || "")) mseArea = Math.max(mseArea, areaOf(el));
      for (i = 0; i < srcs.length; i++) add(srcs[i], el, 3);
      for (i = 0; i < SRC_ATTRS.length; i++) add(el.getAttribute(SRC_ATTRS[i]), el, 3);
    } else if (tag === "A") {
      var href = el.getAttribute("href");
      if (href && MEDIA_EXT.test(href)) add(href, el, 1); // lien de téléchargement direct
    }
    for (i = 0; i < ANY_ATTRS.length; i++) add(el.getAttribute(ANY_ATTRS[i]), el, 3);
    // Lecteurs chargés en JavaScript (Plyr, Presto Player, lite-youtube, etc.).
    var vimeoId = el.getAttribute("data-vimeo-id");
    if (vimeoId) addById("vimeo", vimeoId, el);
    var plyrProvider = el.getAttribute("data-plyr-provider");
    var plyrId = el.getAttribute("data-plyr-embed-id");
    if (plyrProvider && plyrId) addById(plyrProvider, plyrId, el);
    var provider = el.getAttribute("provider") || el.getAttribute("data-provider") || el.getAttribute("data-video-provider");
    var videoId = el.getAttribute("video-id") || el.getAttribute("data-video-id") || el.getAttribute("videoid");
    if (provider && videoId) addById(provider, videoId, el);
    if (tag === "LITE-YOUTUBE" && videoId) addById("youtube", videoId, el);
    if (tag === "LITE-VIMEO" && videoId) addById("vimeo", videoId, el);
    if (/-PLAYER$/.test(tag)) add(el.getAttribute("src"), el, 3); // presto-player, media-player…
    var cls = typeof el.className === "string" ? el.className : "";
    var w = cls.match(/wistia_async_([a-z0-9]+)/i);
    if (w) add("https://fast.wistia.net/embed/iframe/" + w[1], el, 3);
  }

  // Parcourt le document, les shadow DOM ouverts et les iframes du même site.
  var docs = [];
  function walk(root, depth) {
    if (!root || depth > 4) return;
    if (root.nodeType === 9) docs.push(root);
    var els = root.querySelectorAll("*");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      visit(el);
      if (el.shadowRoot) walk(el.shadowRoot, depth + 1);
      if (el.tagName === "IFRAME") {
        try { if (el.contentDocument) walk(el.contentDocument, depth + 1); } catch (e) { /* autre domaine */ }
      }
    }
  }

  // Lecteurs globaux : JW Player et Video.js.
  function globalPlayers() {
    try {
      if (typeof window.jwplayer === "function") {
        var item = window.jwplayer().getPlaylistItem();
        if (item) add(item.file || (item.sources && item.sources[0] && item.sources[0].file), null, 2);
      }
    } catch (e) { /* pas de JW Player actif */ }
    try {
      if (window.videojs && window.videojs.getPlayers) {
        var players = window.videojs.getPlayers();
        for (var k in players) if (players[k] && players[k].currentSrc) add(players[k].currentSrc(), null, 2);
      }
    } catch (e) { /* pas de Video.js */ }
  }

  // Flux réellement chargés par la page. Un .m3u8/.mpd alimente presque
  // toujours la vidéo « blob: » affichée : il hérite alors de sa priorité.
  function loadedStreams() {
    for (var d = 0; d < docs.length; d++) {
      try {
        var res = docs[d].defaultView.performance.getEntriesByType("resource");
        for (var r = 0; r < res.length; r++) {
          var name = res[r].name;
          if (STREAM_EXT.test(name)) add(name, null, mseArea >= 0 ? 3 : 1, mseArea >= 0 ? mseArea : 0);
          else if (/\.(mp4|m4a)(\?|$)/i.test(name)) add(name, null, 1);
        }
      } catch (e) { /* API indisponible */ }
    }
  }

  // Nom de fichier : le « slug » de l'adresse de la leçon (ex. 2026-09-20-bitcoin-talk-life-discord).
  function fileName() {
    var seg = location.pathname.split("/").filter(Boolean).pop() || "";
    try { seg = decodeURIComponent(seg); } catch (e) { /* garde tel quel */ }
    seg = seg.replace(/\.(html?|php|aspx?)$/i, "");
    var h1 = document.querySelector("h1");
    var name = seg || (h1 && h1.textContent) || document.title || "lecon";
    name = name.normalize ? name.normalize("NFD").replace(ACCENTS, "") : name;
    name = name.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/-+/g, "-").replace(/^[-.]+|[-.]+$/g, "");
    return name.slice(0, 80) || "lecon";
  }

  // Chaîne sûre entre apostrophes pour le shell d'a-Shell.
  function quote(s) { return "'" + String(s).replace(/'/g, "%27") + "'"; }
  function say(msg) { return "echo " + quote(msg); }

  var command;
  try {
    walk(document, 0);
    globalPlayers();
    loadedStreams();
    found.sort(function (a, b) {
      return b.priority - a.priority || b.area - a.area || a.order - b.order;
    });
    if (found.length) {
      command = [
        "yt-dlp",
        "--no-playlist",
        "-N", "4",
        "-f", quote("ba[ext=m4a]/ba/b[ext=mp4]/b"),
        "--referer", quote(location.href.split("#")[0]),
        "-P", "~/Documents/Lecons-Audio",
        "-o", quote(fileName() + ".%(ext)s"),
        quote(found[0].url),
      ].join(" ");
    } else {
      command = say("Aucune video trouvee sur cette page. Lancez la lecture de la video, attendez quelques secondes puis relancez le raccourci.");
    }
  } catch (e) {
    // Le raccourci attend toujours une réponse : on renvoie l'erreur lisiblement.
    command = say("Erreur du script Lecons Audio : " + String((e && e.message) || e).replace(/[^\x20-\x7e]/g, "?").slice(0, 200));
  }

  // Exposé pour les tests et le débogage.
  try { window.__leconsAudio = { candidates: found, command: command }; } catch (e) { /* page figée */ }
  if (typeof completion === "function") completion(command);
})();
