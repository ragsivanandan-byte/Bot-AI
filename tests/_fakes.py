"""
_fakes.py — Doublures réseau pour tester les chemins HTTP SANS vrai réseau.

Permet d'exercer les cas de succès ET d'échec (200, 403, 500->retry, timeouts,
robots.txt) de façon déterministe et instantanée.
"""
from __future__ import annotations

import requests


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "",
                 json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("pas de JSON dans la réponse simulée")
        return self._json


class FakeSession:
    """
    Session HTTP simulée. `handler(method, url, params, data, n)` renvoie une
    FakeResponse (ou lève requests.RequestException pour simuler une panne).
    """
    def __init__(self, handler):
        self.headers: dict = {}
        self.handler = handler
        self.n_get = 0
        self.n_post = 0

    def get(self, url, params=None, timeout=None):
        self.n_get += 1
        return self.handler("GET", url, params, None, self.n_get)

    def post(self, url, data=None, timeout=None):
        self.n_post += 1
        return self.handler("POST", url, None, data, self.n_post)


# Réexport pratique pour lever des pannes réseau dans les handlers.
RequestException = requests.RequestException
