#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère docs/data/btc_eur.json : clôtures HEBDOMADAIRES BTC/EUR depuis 2013,
moyenne mobile 200 semaines (200 WMA) et périodes sous la 200 WMA.

Source de prix RÉELLE en euros : CoinGecko (vs_currency=eur). Aucun prix n'est
codé en dur — 0 hallucination : tout vient de l'API et est calculé ici.

Sert de repli au site (le navigateur charge d'abord CoinGecko en direct, puis
ce fichier). Exécuté aussi par la GitHub Action de rafraîchissement.

Usage :
    python3 build_btc_data.py            # récupère et écrit docs/data/btc_eur.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "docs", "data", "btc_eur.json")
START_DISPLAY = "2015-01-01"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
COINGECKO = ("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
             "?vs_currency=eur&days=max")


def fetch_prices() -> list:
    """Retourne [[ms, prix_eur], ...] quotidiens depuis CoinGecko."""
    req = urllib.request.Request(COINGECKO, headers={"User-Agent": USER_AGENT,
                                                     "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read())
    prices = data.get("prices") or []
    if not prices:
        raise RuntimeError("CoinGecko : aucune donnée de prix")
    return prices


def monday_of(ms: float) -> dt.date:
    d = dt.datetime.utcfromtimestamp(ms / 1000.0).date()
    return d - dt.timedelta(days=d.weekday())


def resample_weekly(prices: list) -> list:
    """[[ms, prix]] quotidiens -> [{date, close}] (dernier prix de chaque semaine)."""
    best: dict = {}
    for row in prices:
        ms, price = row[0], row[1]
        if price is None:
            continue
        key = monday_of(ms).isoformat()
        if key not in best or ms >= best[key][0]:
            best[key] = (ms, float(price))
    return [{"date": k, "close": v[1]} for k, v in sorted(best.items())]


def compute_series(weekly: list, win: int = 200) -> list:
    closes = [w["close"] for w in weekly]
    out = []
    for i, w in enumerate(weekly):
        wma = None
        if i >= win - 1:
            wma = sum(closes[i - win + 1:i + 1]) / win
        out.append({"date": w["date"], "close": round(w["close"], 2),
                    "wma200": round(wma, 2) if wma is not None else None})
    return out


def below_periods(series: list) -> list:
    out, cur = [], None
    for p in series:
        below = p["wma200"] is not None and p["close"] < p["wma200"]
        if below:
            dev = (p["close"] / p["wma200"] - 1) * 100
            if cur is None:
                cur = {"start": p["date"], "end": p["date"], "weeks": 0,
                       "maxDev": 0.0, "maxDevDate": p["date"], "_sum": 0.0}
            cur["end"] = p["date"]
            cur["weeks"] += 1
            cur["_sum"] += dev
            if dev < cur["maxDev"]:
                cur["maxDev"] = dev
                cur["maxDevDate"] = p["date"]
        elif cur is not None:
            cur["avgDev"] = cur.pop("_sum") / cur["weeks"]
            cur["maxDev"] = round(cur["maxDev"], 2)
            cur["avgDev"] = round(cur["avgDev"], 2)
            out.append(cur)
            cur = None
    if cur is not None:
        cur["avgDev"] = round(cur.pop("_sum") / cur["weeks"], 2)
        cur["maxDev"] = round(cur["maxDev"], 2)
        out.append(cur)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Génère docs/data/btc_eur.json (BTC/EUR + 200 WMA).")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args(argv)

    prices = fetch_prices()
    weekly = compute_series(resample_weekly(prices), 200)
    payload = {
        "source": "CoinGecko (BTC/EUR, prix natif en euros)",
        "currency": "EUR",
        "generated_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "start_display": START_DISPLAY,
        "weeks": len(weekly),
        "weekly": weekly,
        "below_200wma_periods": below_periods([w for w in weekly if w["date"] >= START_DISPLAY]),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.write("\n")

    last = weekly[-1] if weekly else {}
    print(f"Écrit {args.out} : {len(weekly)} semaines, dernier {last.get('date')} "
          f"= €{last.get('close')}, 200WMA=€{last.get('wma200')}, "
          f"{len(payload['below_200wma_periods'])} périodes sous la 200WMA",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
