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


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read())


def _from_cryptocompare() -> list:
    """[[ms, prix_eur], ...] quotidiens — CryptoCompare CCCAGG (indice EUR), sans clé."""
    j = _get_json("https://min-api.cryptocompare.com/data/v2/histoday"
                  "?fsym=BTC&tsym=EUR&allData=true")
    data = (j.get("Data") or {}).get("Data") or []
    pts = [[d["time"] * 1000, float(d["close"])] for d in data if d.get("close")]
    if not pts:
        raise RuntimeError("CryptoCompare : aucune donnée")
    return pts


def _from_kraken() -> list:
    """[[ms, prix_eur], ...] hebdomadaires — Kraken XBT/EUR (bourse), sans clé."""
    j = _get_json("https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval=10080")
    if j.get("error"):
        raise RuntimeError("Kraken : " + ",".join(j["error"]))
    result = j.get("result") or {}
    key = next((k for k in result if k != "last"), None)
    rows = result.get(key) or []
    pts = [[row[0] * 1000, float(row[4])] for row in rows]
    if not pts:
        raise RuntimeError("Kraken : aucune donnée")
    return pts


def fetch_points() -> tuple:
    """Essaie chaque source sans clé. Retourne (points[[ms,prix]], nom_source)."""
    errors = []
    for name, fn in (("CryptoCompare CCCAGG (indice EUR)", _from_cryptocompare),
                     ("Kraken XBT/EUR (bourse)", _from_kraken)):
        try:
            return fn(), name
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    raise RuntimeError("Sources BTC/EUR indisponibles — " + " | ".join(errors))


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

    prices, src_name = fetch_points()
    weekly = compute_series(resample_weekly(prices), 200)
    payload = {
        "source": src_name,
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
