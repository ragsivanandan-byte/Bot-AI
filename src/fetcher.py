"""
fetcher.py — Récupération HTTP respectueuse des CGU.

Garanties de ce module (conformes au brief, NON contournables) :
  * Respect de robots.txt (urllib.robotparser) avant toute requête.
  * Rate limiting strict par domaine + jitter aléatoire.
  * User-agent honnête et identifiable (configuré dans config.yaml).
  * Retries avec backoff exponentiel (2s, 4s, 8s, 16s) sur erreurs réseau/5xx.
  * Cache disque (TTL configurable) pour ne pas re-télécharger inutilement.
  * Dégradation gracieuse : en cas d'échec, renvoie None + log clair, JAMAIS
    une exception qui stoppe tout l'outil.

Ce module ne contourne AUCUNE protection. Si un site répond 403 / bloque, on
le note et on rend la main. C'est volontaire.
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger("market_intel")


class FetchResult:
    """Petit conteneur de résultat pour transporter statut + contexte."""

    def __init__(self, url: str, text: str | None, status: int | None,
                 from_cache: bool = False, error: str | None = None,
                 blocked_by_robots: bool = False):
        self.url = url
        self.text = text
        self.status = status
        self.from_cache = from_cache
        self.error = error
        self.blocked_by_robots = blocked_by_robots

    @property
    def ok(self) -> bool:
        return self.text is not None


class RespectfulFetcher:
    """
    Client HTTP poli, réutilisable pour toute la durée d'un run.

    Tient un état par domaine : dernière requête (pour le rate limit) et cache
    du parseur robots.txt.
    """

    def __init__(self, network_cfg: dict):
        self.user_agent: str = network_cfg["user_agent"]
        self.timeout: int = int(network_cfg["request_timeout_seconds"])
        self.min_delay: float = float(network_cfg["min_delay_seconds"])
        self.jitter: float = float(network_cfg["max_delay_jitter_seconds"])
        self.max_retries: int = int(network_cfg["max_retries"])
        self.backoff_base: float = float(network_cfg["backoff_base_seconds"])
        self.respect_robots: bool = bool(network_cfg["respect_robots_txt"])
        self.cache_ttl_s: float = float(network_cfg["cache_ttl_hours"]) * 3600
        self.cache_dir = Path(network_cfg["cache_dir"])
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent,
                                      "Accept-Language": "en,fr;q=0.8"})
        self._last_request_at: dict[str, float] = {}      # domaine -> timestamp
        self._robots_cache: dict[str, RobotFileParser | None] = {}

    # --- robots.txt ----------------------------------------------------------
    def _robots_for(self, url: str) -> RobotFileParser | None:
        """Charge (et met en cache) le robots.txt du domaine de `url`."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain in self._robots_cache:
            return self._robots_cache[domain]

        rp = RobotFileParser()
        robots_url = f"{domain}/robots.txt"
        try:
            resp = self._session.get(robots_url, timeout=self.timeout)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                # Pas de robots.txt lisible -> on reste prudent : on autorise
                # mais on log. (Comportement standard des crawlers polis.)
                logger.debug("robots.txt %s -> HTTP %s (on continue prudemment)",
                             robots_url, resp.status_code)
                rp = None
        except requests.RequestException as e:
            logger.debug("robots.txt inaccessible (%s) : %s", robots_url, e)
            rp = None

        self._robots_cache[domain] = rp
        return rp

    def _allowed(self, url: str) -> bool:
        """True si robots.txt autorise notre UA à récupérer `url`."""
        if not self.respect_robots:
            return True
        rp = self._robots_for(url)
        if rp is None:
            return True  # pas de règle exploitable -> autorisé par défaut
        return rp.can_fetch(self.user_agent, url)

    # --- cache ---------------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{key}.html"

    def _read_cache(self, url: str) -> str | None:
        path = self._cache_path(url)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self.cache_ttl_s:
            logger.debug("Cache expiré (%.0fh) pour %s", age / 3600, url)
            return None
        logger.debug("Cache HIT pour %s", url)
        return path.read_text(encoding="utf-8", errors="replace")

    def _write_cache(self, url: str, text: str) -> None:
        try:
            self._cache_path(url).write_text(text, encoding="utf-8")
        except OSError as e:
            logger.debug("Impossible d'écrire le cache pour %s : %s", url, e)

    # --- rate limiting -------------------------------------------------------
    def _throttle(self, url: str) -> None:
        """Respecte un délai minimal entre deux requêtes vers le même domaine."""
        domain = urlparse(url).netloc
        last = self._last_request_at.get(domain)
        if last is not None:
            wait = self.min_delay - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
        # jitter aléatoire pour ne jamais marteler de façon régulière
        time.sleep(random.uniform(0, self.jitter))
        self._last_request_at[domain] = time.time()

    # --- API publique --------------------------------------------------------
    def get(self, url: str, use_cache: bool = True) -> FetchResult:
        """
        Récupère `url` de façon respectueuse. Ne lève jamais d'exception :
        renvoie toujours un FetchResult (succès, cache, blocage robots, ou erreur).
        """
        if use_cache:
            cached = self._read_cache(url)
            if cached is not None:
                return FetchResult(url, cached, 200, from_cache=True)

        if not self._allowed(url):
            logger.warning("robots.txt INTERDIT l'accès à %s -> on s'abstient.", url)
            return FetchResult(url, None, None, blocked_by_robots=True,
                               error="bloqué par robots.txt")

        last_error: str | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle(url)
            try:
                resp = self._session.get(url, timeout=self.timeout)
                status = resp.status_code
                if status == 200:
                    self._write_cache(url, resp.text)
                    return FetchResult(url, resp.text, status)
                if status in (403, 401, 404, 410):
                    # Blocage ou ressource absente : inutile de réessayer, on
                    # respecte la décision du serveur et on note.
                    logger.warning("HTTP %s sur %s (pas de retry, accès refusé"
                                   " ou ressource absente).", status, url)
                    return FetchResult(url, None, status,
                                       error=f"HTTP {status}")
                if status == 429 or 500 <= status < 600:
                    last_error = f"HTTP {status}"
                    logger.info("HTTP %s sur %s (tentative %d/%d)", status, url,
                                attempt, self.max_retries)
                else:
                    return FetchResult(url, None, status, error=f"HTTP {status}")
            except requests.RequestException as e:
                last_error = str(e)
                logger.info("Erreur réseau sur %s (tentative %d/%d) : %s",
                            url, attempt, self.max_retries, e)

            if attempt < self.max_retries:
                backoff = self.backoff_base * (2 ** (attempt - 1))  # 2,4,8,16
                logger.debug("Backoff %.0fs avant nouvelle tentative", backoff)
                time.sleep(backoff)

        logger.error("Échec définitif sur %s : %s", url, last_error)
        return FetchResult(url, None, None, error=last_error)
