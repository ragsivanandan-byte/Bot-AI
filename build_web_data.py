#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère le fichier de données du site web (docs/data/strc.json) à partir de la
même logique que strc_dca.py.

Le navigateur ne peut pas interroger Yahoo/Stooq directement (CORS). Ce script
est donc exécuté côté serveur (GitHub Action, ou en local sur votre Mac) pour
récupérer les closing prices hebdo réels de STRC et les figer dans un JSON que
le site statique consomme et recalcule en JavaScript.

Usage :
    python3 build_web_data.py             # données LIVE (Yahoo/Stooq)
    python3 build_web_data.py --no-live   # snapshot embarqué (hors-ligne)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import strc_dca as m

OUT_PATH = os.path.join(m.HERE, "docs", "data", "strc.json")


def build(use_live: bool, verbose: bool = False) -> dict:
    start = m.STRC_FIRST_TRADE
    end = dt.date.today()
    raw, live, source = m.get_series("STRC", start, end, use_live, verbose)
    if not raw:
        raise SystemExit("Aucune donnée STRC (live indisponible et snapshot vide).")

    series, interpolated = m.build_continuous_series(raw, start, end)
    dividends = m.load_dividends()

    return {
        "symbol": "STRC",
        "generated_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "live": live,
        "source": source,
        "par": m.STRC_PAR,
        "ipo_price": m.STRC_IPO_PRICE,
        "first_trade": m.STRC_FIRST_TRADE.isoformat(),
        "default_apy": m.DEFAULT_DIVIDEND_APY,
        "interpolated_weeks": interpolated,
        "weeks": len(series),
        "latest_close": series[-1][1] if series else None,
        "weekly_closes": [
            {"date": d.isoformat(), "close": c, "estimated": est}
            for (d, c, est) in series
        ],
        "dividends": [
            {"ex_date": d.isoformat(), "amount_per_share": a} for (d, a) in dividends
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Génère docs/data/strc.json pour le site web.")
    ap.add_argument("--no-live", action="store_true",
                    help="Utiliser le snapshot embarqué au lieu des données live.")
    ap.add_argument("--out", default=OUT_PATH, help="Chemin de sortie du JSON.")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    data = build(use_live=not args.no_live, verbose=args.verbose)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"Écrit {args.out} : {data['weeks']} semaines, "
          f"source={'LIVE ' + data['source'] if data['live'] else 'SNAPSHOT'}, "
          f"dernier close={data['latest_close']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
