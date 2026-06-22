"use strict";
// Génère un QR code pointant vers le site, pour ouverture rapide sur mobile.
// Utilise la lib globale `qrcode` (qrcode-generator, CDN). Repli propre si absente.
(function () {
  var el = document.getElementById("qr");
  if (!el) return;
  // URL canonique du site (indépendante de l'onglet courant).
  var url = (document.getElementById("qrlink") && document.getElementById("qrlink").href) ||
            "https://ragsivanandan-byte.github.io/Bot-AI/";
  try {
    if (typeof qrcode === "function") {
      var qr = qrcode(0, "M");        // type auto, correction d'erreur niveau M
      qr.addData(url);
      qr.make();
      el.innerHTML = qr.createImgTag(5, 8); // taille module, marge
      var img = el.querySelector("img");
      if (img) { img.alt = "QR code vers l'outil STRC"; img.style.borderRadius = "8px"; }
      return;
    }
  } catch (e) { /* repli ci-dessous */ }
  el.innerHTML = '<p class="muted small">QR indisponible — ouvrez le lien ci-contre.</p>';
})();
