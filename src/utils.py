"""
utils.py — Fonctions transverses : logging, dates, chemins, marqueurs de fiabilité.

Toutes les briques partagées par les autres modules vivent ici pour éviter la
duplication. Aucune logique métier lourde ici.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

# --- Marqueurs de fiabilité standardisés -------------------------------------
# On s'en sert PARTOUT pour ne jamais présenter une estimation comme un fait.
# Voir règles anti-hallucination du brief.
UNAVAILABLE = "donnée indisponible"
ESTIMATION = "ESTIMATION"
INFERENCE = "INFÉRENCE, non confirmée"


def today_str() -> str:
    """
    Date du jour au format ISO AAAA-MM-JJ.
    ⚠️ Format INTERNE (clés d'historique SQLite, noms de logs, calculs de dates) :
    l'ordre lexicographique ISO est indispensable aux comparaisons de la veille.
    Ne PAS changer ce format. Pour l'AFFICHAGE, voir today_display().
    """
    return date.today().isoformat()


def today_display() -> str:
    """Date du jour au format AFFICHAGE jj-mm-aaaa (nom de dossier, titres)."""
    return date.today().strftime("%d-%m-%Y")


def now_iso() -> str:
    """Horodatage ISO complet pour les en-têtes de rapport et les logs."""
    return datetime.now().isoformat(timespec="seconds")


def ensure_dir(path: str | Path) -> Path:
    """Crée le dossier (et ses parents) si besoin, renvoie un Path.
    Développe `~` (ex. '~/Downloads/reports' -> /Users/<toi>/Downloads/reports)."""
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def report_dir(base_reports_dir: str) -> Path:
    """Dossier de rapport du jour : <base>/jj-mm-aaaa/ (format d'affichage)."""
    return ensure_dir(Path(base_reports_dir) / today_display())


def setup_logging(logs_dir: str, verbose: bool = False) -> logging.Logger:
    """
    Configure un logger qui écrit à la fois sur la console et dans un fichier
    horodaté. Les logs sont volontairement bavards sur les échecs réseau pour
    que tu saches toujours pourquoi une donnée est manquante.
    """
    ensure_dir(logs_dir)
    log_path = Path(logs_dir) / f"run_{today_str()}.log"

    logger = logging.getLogger("market_intel")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()  # évite les doublons si appelé plusieurs fois

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    logger.debug("Logging initialisé -> %s", log_path)
    return logger


def fmt_eur(value: float | None) -> str:
    """Formate un GROS montant en EUR (CA), arrondi à l'euro, ou le marqueur."""
    if value is None:
        return UNAVAILABLE
    return f"{value:,.0f} €".replace(",", " ")


def fmt_price(value: float | None) -> str:
    """Formate un PRIX en EUR avec 2 décimales (les printables sont bon marché)."""
    if value is None:
        return UNAVAILABLE
    return f"{value:,.2f} €".replace(",", " ")


def safe_div(num: float, den: float) -> float | None:
    """Division qui ne plante jamais (renvoie None si dénominateur nul)."""
    try:
        return num / den if den else None
    except (TypeError, ZeroDivisionError):
        return None
