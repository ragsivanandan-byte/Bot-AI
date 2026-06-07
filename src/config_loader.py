"""
config_loader.py — Chargement et validation de config.yaml.

Objectif : si le YAML est cassé ou incomplet, on le dit clairement plutôt que
de laisser le reste du code planter avec une stacktrace obscure. On applique
aussi des valeurs par défaut raisonnables pour les champs optionnels.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Levée quand config.yaml est absent, illisible ou incohérent."""


# Champs obligatoires de premier niveau. S'il en manque un, on refuse de démarrer.
REQUIRED_TOP_KEYS = ["shop", "niche", "network", "grok_prompts", "output"]


def load_config(path: str = "config.yaml") -> dict[str, Any]:
    """
    Charge config.yaml, valide la présence des sections clés, et complète les
    valeurs par défaut. Renvoie un dict prêt à l'emploi.
    """
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Fichier de config introuvable : {p.resolve()}")

    try:
        with p.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"config.yaml invalide (erreur YAML) : {e}") from e

    if not isinstance(cfg, dict):
        raise ConfigError("config.yaml doit contenir un mapping au niveau racine.")

    # Surcharge locale optionnelle : config.local.yaml (gitignored, propre à la
    # machine — ex. chemin Upscayl, préférences de sortie). Fusion profonde par-
    # dessus le YAML versionné -> plus besoin de modifier/stasher config.yaml.
    local = p.with_name("config.local.yaml")
    if local.exists():
        try:
            with local.open(encoding="utf-8") as f:
                override = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"config.local.yaml invalide (erreur YAML) : {e}") from e
        if not isinstance(override, dict):
            raise ConfigError("config.local.yaml doit contenir un mapping au niveau racine.")
        _deep_merge(cfg, override)

    missing = [k for k in REQUIRED_TOP_KEYS if k not in cfg]
    if missing:
        raise ConfigError(f"Sections manquantes dans config.yaml : {missing}")

    _apply_defaults(cfg)
    return cfg


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Fusionne `override` dans `base` en place. Les mappings sont fusionnés
    récursivement ; toute autre valeur (scalaire, liste) remplace celle de base."""
    for key, val in override.items():
        if (key in base and isinstance(base[key], dict) and isinstance(val, dict)):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def _apply_defaults(cfg: dict[str, Any]) -> None:
    """Complète en place les champs optionnels avec des défauts sûrs."""
    net = cfg.setdefault("network", {})
    net.setdefault("user_agent", "MarketIntel/1.0 (respectful-research)")
    net.setdefault("request_timeout_seconds", 20)
    net.setdefault("min_delay_seconds", 4.0)
    net.setdefault("max_delay_jitter_seconds", 3.0)
    net.setdefault("max_retries", 4)
    net.setdefault("backoff_base_seconds", 2.0)
    net.setdefault("respect_robots_txt", True)
    net.setdefault("cache_ttl_hours", 12)
    net.setdefault("cache_dir", "cache")

    out = cfg.setdefault("output", {})
    out.setdefault("reports_dir", "reports")
    out.setdefault("logs_dir", "logs")

    cfg.setdefault("competitors", [])
    cfg.setdefault("discovery", {"enabled": False, "search_queries": []})
    cfg.setdefault("revenue_estimation", {})
    cfg.setdefault("ai_inference", {"enabled": True, "threshold": 4, "weights": {}})
    cfg.setdefault("goals", {})

    gp = cfg.setdefault("grok_prompts", {})
    gp.setdefault("count_per_day", 5)
    gp.setdefault("palette", [])
    gp.setdefault("styles", ["gouache flat graphic"])
    gp.setdefault("shape_pool", [])
