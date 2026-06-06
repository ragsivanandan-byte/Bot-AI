"""
storage.py — Historisation des snapshots concurrents (SQLite) + calcul de diffs.

But : transformer l'outil d'un instantané en une vraie VEILLE. À chaque run, on
enregistre l'état public de chaque concurrent (ventes, fiches, avis, prix). Au
run suivant, on compare au dernier snapshot disponible pour afficher l'évolution
(« +120 ventes depuis le 28/05 », « +3 nouvelles fiches »…).

Choix : SQLite (stdlib, zéro dépendance, fichier unique versionnable ou non).
Robuste : si la base est absente/corrompue, on (re)crée et on dégrade en « pas
d'historique » plutôt que de planter.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .etsy_parser import ShopData

logger = logging.getLogger("market_intel")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    run_date        TEXT NOT NULL,   -- AAAA-MM-JJ
    slug            TEXT NOT NULL,
    market          TEXT,
    total_sales     INTEGER,
    active_listings INTEGER,
    reviews         INTEGER,
    avg_rating      REAL,
    avg_price_eur   REAL,
    fetched         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_date, slug)
);
"""


@dataclass
class CompetitorDelta:
    """Évolution d'un concurrent entre deux snapshots datés."""
    slug: str
    prev_date: str
    sales_delta: int | None = None
    listings_delta: int | None = None
    reviews_delta: int | None = None
    price_delta: float | None = None

    @property
    def has_change(self) -> bool:
        return any(v not in (None, 0) for v in
                   (self.sales_delta, self.listings_delta,
                    self.reviews_delta, self.price_delta))


class HistoryStore:
    """Accès à la base d'historique. Toutes les méthodes dégradent en silence."""

    def __init__(self, db_path: str = "cache/history.sqlite3"):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute(_SCHEMA)
            self._conn.commit()
        except sqlite3.Error as e:
            logger.warning("Historique indisponible (SQLite : %s) — l'outil "
                           "continue sans diff.", e)
            self._conn = None

    @property
    def available(self) -> bool:
        return self._conn is not None

    def save_snapshot(self, run_date: str, shops: list[ShopData]) -> None:
        """Enregistre (ou remplace) le snapshot du jour pour chaque boutique."""
        if not self._conn:
            return
        try:
            rows = [(run_date, s.slug, s.market, s.total_sales,
                     s.active_listings, s.reviews, s.avg_rating,
                     s.avg_price_eur, int(s.fetched)) for s in shops]
            self._conn.executemany(
                "INSERT OR REPLACE INTO snapshots (run_date, slug, market, "
                "total_sales, active_listings, reviews, avg_rating, "
                "avg_price_eur, fetched) VALUES (?,?,?,?,?,?,?,?,?)", rows)
            self._conn.commit()
            logger.info("Snapshot historisé : %d boutiques au %s",
                        len(rows), run_date)
        except sqlite3.Error as e:
            logger.warning("Échec d'historisation (ignoré) : %s", e)

    def compute_deltas(self, current: list[ShopData], current_date: str,
                       cutoff: str | None = None) -> dict[str, CompetitorDelta]:
        """
        Pour chaque boutique courante, calcule l'écart avec un snapshot antérieur.
        - cutoff=None : snapshot PRÉCÉDENT le plus récent (run_date < current_date)
          -> évolution jour-à-jour.
        - cutoff="AAAA-MM-JJ" : snapshot le plus récent avec run_date <= cutoff
          -> sert à l'évolution hebdo (cutoff = aujourd'hui - 7 j).
        Renvoie un dict slug->CompetitorDelta.
        """
        if not self._conn:
            return {}
        deltas: dict[str, CompetitorDelta] = {}
        if cutoff:
            where, bound = "run_date <= ?", cutoff
        else:
            where, bound = "run_date < ?", current_date
        try:
            for shop in current:
                row = self._conn.execute(
                    "SELECT run_date, total_sales, active_listings, reviews, "
                    f"avg_price_eur FROM snapshots WHERE slug = ? AND {where} "
                    "ORDER BY run_date DESC LIMIT 1",
                    (shop.slug, bound)).fetchone()
                if not row:
                    continue
                prev_date, p_sales, p_list, p_rev, p_price = row
                deltas[shop.slug] = CompetitorDelta(
                    slug=shop.slug,
                    prev_date=prev_date,
                    sales_delta=_diff_int(shop.total_sales, p_sales),
                    listings_delta=_diff_int(shop.active_listings, p_list),
                    reviews_delta=_diff_int(shop.reviews, p_rev),
                    price_delta=_diff_float(shop.avg_price_eur, p_price),
                )
        except sqlite3.Error as e:
            logger.warning("Calcul des diffs impossible (ignoré) : %s", e)
        return deltas

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def _diff_int(curr, prev) -> int | None:
    if curr is None or prev is None:
        return None
    return int(curr) - int(prev)


def _diff_float(curr, prev) -> float | None:
    if curr is None or prev is None:
        return None
    return round(float(curr) - float(prev), 2)
