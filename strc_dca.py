#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STRC DCA Simulator — Closing-Price Edition
==========================================

Reproduit le « STRC Mode » du Bitcoin Intelligence Report
(https://btcintelligencereport.com/portfolio) :

    « Weekly DCA deploys into STRC at $100 par. »

MODIFICATION DEMANDÉE
---------------------
L'outil original suppose que chaque DCA hebdomadaire achète des actions STRC
au PAR de 100 $. Ce script remplace cette hypothèse par le CLOSING PRICE
HEBDOMADAIRE RÉEL de STRC depuis son lancement (IPO réglée le 29/07/2025,
première cotation Nasdaq ~30/07/2025).

Conséquence : si STRC a clôturé sous 100 $ une semaine donnée, le même montant
DCA achète DAVANTAGE d'actions ; et la valeur de marché courante reflète le
prix réel — donc une PERTE (ou un GAIN) en capital par rapport au par 100 $ est
désormais intégrée. Toutes les autres métriques sont recalculées en conséquence.

Le script :
  1. Récupère EN DIRECT les closing prices hebdo réels de STRC (Yahoo Finance,
     fallback Stooq). Aucune clé API, uniquement la bibliothèque standard Python.
  2. Simule le DCA hebdomadaire en deux modes :
       - MODE PAR     : achat à 100 $ (comme l'outil d'origine)
       - MODE CLOSING : achat au closing price réel (votre modification)
  3. Modélise le rendement (dividende variable mensuel de STRC) avec
     réinvestissement optionnel.
  4. Affiche une comparaison complète + un benchmark BTC optionnel.

Conçu pour tourner sur le terminal d'un Mac :
    python3 strc_dca.py
    python3 strc_dca.py --weekly-amount 1000 --reinvest-dividends
    python3 strc_dca.py --no-live            # utilise le snapshot embarqué
    python3 strc_dca.py --json               # sortie machine-readable

Aucune dépendance externe requise.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Constantes & métadonnées STRC
# --------------------------------------------------------------------------- #

STRC_PAR = 100.0                      # Valeur nominale (« stated amount ») par action
STRC_IPO_PRICE = 90.0                 # Prix d'introduction (24/07/2025)
STRC_FIRST_TRADE = dt.date(2025, 7, 30)   # Première cotation Nasdaq (approx.)
STRC_LAUNCH_LABEL = "2025-07-30"

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
SNAPSHOT_CSV = os.path.join(DATA_DIR, "strc_weekly_closes.csv")
DIVIDENDS_CSV = os.path.join(DATA_DIR, "strc_dividends.csv")

# Rendement annualisé de repli si aucune donnée de dividende n'est disponible.
# STRC est conçu pour rester proche du par via un dividende variable mensuel.
DEFAULT_DIVIDEND_APY = 0.09           # ~9 % annualisé au lancement

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# Récupération des prix (live)
# --------------------------------------------------------------------------- #

def _http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_weekly_closes_yahoo(symbol: str, start: dt.date, end: dt.date,
                              verbose: bool = False) -> Dict[dt.date, float]:
    """Closes hebdo via l'API chart publique de Yahoo Finance (sans clé)."""
    p1 = int(dt.datetime(start.year, start.month, start.day).timestamp())
    p2 = int(dt.datetime(end.year, end.month, end.day).timestamp()) + 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={p1}&period2={p2}&interval=1wk&events=div%2Csplits"
    )
    raw = _http_get(url)
    data = json.loads(raw)
    result = data["chart"]["result"][0]
    stamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    # Yahoo expose aussi adjclose ; on garde le close brut (prix de marché réel).
    out: Dict[dt.date, float] = {}
    for ts, c in zip(stamps, closes):
        if c is None:
            continue
        d = dt.datetime.utcfromtimestamp(ts).date()
        out[_to_friday(d)] = round(float(c), 4)
    if verbose:
        print(f"[live] Yahoo: {len(out)} closes hebdo pour {symbol}", file=sys.stderr)
    return out


def fetch_weekly_closes_stooq(symbol: str,
                              verbose: bool = False) -> Dict[dt.date, float]:
    """Fallback : Stooq CSV hebdomadaire (ex. 'strc.us')."""
    sym = symbol.lower()
    if "." not in sym and "-" not in sym:
        sym += ".us"
    url = f"https://stooq.com/q/d/l/?s={sym}&i=w"
    raw = _http_get(url).decode("utf-8", "replace")
    out: Dict[dt.date, float] = {}
    reader = csv.DictReader(raw.splitlines())
    for row in reader:
        try:
            d = dt.date.fromisoformat(row["Date"])
            out[_to_friday(d)] = round(float(row["Close"]), 4)
        except (KeyError, ValueError):
            continue
    if verbose:
        print(f"[live] Stooq: {len(out)} closes hebdo pour {symbol}", file=sys.stderr)
    return out


def fetch_weekly_closes(symbol: str, start: dt.date, end: dt.date,
                        verbose: bool = False) -> Dict[dt.date, float]:
    """Essaie Yahoo, puis Stooq. Lève si les deux échouent."""
    errors = []
    for name, fn in (("yahoo", lambda: fetch_weekly_closes_yahoo(symbol, start, end, verbose)),
                     ("stooq", lambda: fetch_weekly_closes_stooq(symbol, verbose))):
        try:
            series = fn()
            if series:
                return series
            errors.append(f"{name}: série vide")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    raise RuntimeError("Échec de récupération live (" + " | ".join(errors) + ")")


# --------------------------------------------------------------------------- #
# Snapshot embarqué (fallback hors-ligne)
# --------------------------------------------------------------------------- #

def _read_csv_rows(path: str) -> List[dict]:
    """Lit un CSV en ignorant les lignes de commentaire commençant par '#'."""
    with open(path, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


def load_snapshot(path: str = SNAPSHOT_CSV) -> Dict[dt.date, float]:
    out: Dict[dt.date, float] = {}
    if not os.path.exists(path):
        return out
    for row in _read_csv_rows(path):
        try:
            d = dt.date.fromisoformat(row["date"].strip())
            out[d] = float(row["close"])
        except (KeyError, ValueError, AttributeError):
            continue
    return out


def load_dividends(path: str = DIVIDENDS_CSV) -> List[Tuple[dt.date, float]]:
    """Retourne [(ex_date, montant_par_action), ...] trié par date."""
    out: List[Tuple[dt.date, float]] = []
    if not os.path.exists(path):
        return out
    for row in _read_csv_rows(path):
        try:
            d = dt.date.fromisoformat(row["ex_date"].strip())
            amt = float(row["amount_per_share"])
            out.append((d, amt))
        except (KeyError, ValueError, AttributeError):
            continue
    out.sort()
    return out


# --------------------------------------------------------------------------- #
# Construction de la série hebdomadaire continue
# --------------------------------------------------------------------------- #

def _to_friday(d: dt.date) -> dt.date:
    """Normalise une date sur le vendredi de sa semaine (clôture hebdo)."""
    return d + dt.timedelta(days=(4 - d.weekday()))


def fridays_between(start: dt.date, end: dt.date) -> List[dt.date]:
    out = []
    cur = _to_friday(start)
    while cur <= end:
        out.append(cur)
        cur += dt.timedelta(days=7)
    return out


def build_continuous_series(raw: Dict[dt.date, float],
                            start: dt.date, end: dt.date
                            ) -> Tuple[List[Tuple[dt.date, float, bool]], int]:
    """
    Aligne la série brute sur chaque vendredi entre start et end.
    Les semaines manquantes sont interpolées linéairement (drapeau estimated=True).
    Retourne (liste[(vendredi, close, estimated)], nb_interpolés).
    """
    fridays = fridays_between(start, end)
    known = {_to_friday(d): v for d, v in raw.items()}
    known_dates = sorted(known)
    if not known_dates:
        raise RuntimeError("Aucune donnée de prix disponible.")

    series: List[Tuple[dt.date, float, bool]] = []
    interpolated = 0
    for fri in fridays:
        if fri in known:
            series.append((fri, known[fri], False))
            continue
        # Interpolation linéaire entre les deux closes connus encadrants.
        prev = [d for d in known_dates if d <= fri]
        nxt = [d for d in known_dates if d >= fri]
        if prev and nxt:
            a, b = prev[-1], nxt[0]
            if a == b:
                val = known[a]
            else:
                t = (fri - a).days / (b - a).days
                val = known[a] + t * (known[b] - known[a])
        elif prev:
            val = known[prev[-1]]
        else:
            val = known[nxt[0]]
        series.append((fri, round(val, 4), True))
        interpolated += 1
    return series, interpolated


# --------------------------------------------------------------------------- #
# Modèle de dividende
# --------------------------------------------------------------------------- #

def weekly_dividend_per_share(week: dt.date,
                              schedule: List[Tuple[dt.date, float]],
                              fallback_apy: float) -> float:
    """
    Dividende par action attribué à une semaine donnée.

    Les dividendes des actions préférentielles sont calculés sur le PAR (100 $),
    indépendamment du prix d'achat. Si un calendrier de dividendes réel est
    fourni (data/strc_dividends.csv), on répartit le montant mensuel sur ~4,345
    semaines. Sinon on applique le rendement annualisé de repli sur le par.
    """
    if schedule:
        # Trouve le dernier dividende mensuel déclaré <= semaine.
        applicable = [amt for (d, amt) in schedule if d <= week]
        monthly = applicable[-1] if applicable else schedule[0][1]
        return monthly * 12.0 / 52.0
    return STRC_PAR * fallback_apy / 52.0


# --------------------------------------------------------------------------- #
# Simulation DCA
# --------------------------------------------------------------------------- #

@dataclass
class SimResult:
    mode: str                         # "par" | "closing"
    weekly_amount: float
    weeks: int
    invested: float = 0.0
    shares: float = 0.0
    dividends_cash: float = 0.0       # cumul des dividendes (non réinvestis)
    dividends_reinvested: float = 0.0
    latest_close: float = 0.0
    market_value: float = 0.0         # valeur des actions au dernier close réel
    avg_cost: float = 0.0
    capital_pl: float = 0.0           # plus/moins-value en capital
    capital_pl_pct: float = 0.0
    total_value: float = 0.0          # marché + dividendes cash
    total_pl: float = 0.0
    total_pl_pct: float = 0.0
    yield_on_cost: float = 0.0
    history: List[dict] = field(default_factory=list)


def simulate(series: List[Tuple[dt.date, float, bool]],
             weekly_amount: float,
             mode: str,
             dividend_schedule: List[Tuple[dt.date, float]],
             fallback_apy: float,
             reinvest: bool,
             par: float = STRC_PAR) -> SimResult:
    """
    mode == "par"     : chaque DCA achète weekly_amount/par actions (outil d'origine)
    mode == "closing" : chaque DCA achète weekly_amount/close actions (modification)
    """
    res = SimResult(mode=mode, weekly_amount=weekly_amount, weeks=len(series))
    shares = 0.0
    invested = 0.0
    div_cash = 0.0
    div_reinv = 0.0

    # MODE PAR  : achat ET valorisation au par 100 $ (STRC traité comme stable
    #             au par, sans variation de capital — vue de l'outil d'origine).
    # MODE CLOSING : achat ET valorisation au closing price réel de la semaine
    #             (votre modification : la perte/gain en capital est intégrée).
    for (week, close, est) in series:
        buy_price = par if mode == "par" else close
        mark_price = par if mode == "par" else close

        # 1) Dividende de la semaine sur les actions DÉJÀ détenues.
        dps = weekly_dividend_per_share(week, dividend_schedule, fallback_apy)
        div_week = shares * dps
        if reinvest:
            # Réinvesti au prix de la semaine (par en mode par, close en mode closing).
            reinv_shares = div_week / buy_price if buy_price > 0 else 0.0
            shares += reinv_shares
            div_reinv += div_week
        else:
            div_cash += div_week

        # 2) Achat DCA de la semaine.
        new_shares = weekly_amount / buy_price if buy_price > 0 else 0.0
        shares += new_shares
        invested += weekly_amount

        market_value = shares * mark_price
        res.history.append({
            "week": week.isoformat(),
            "close": round(close, 4),
            "estimated": est,
            "buy_price": round(buy_price, 4),
            "shares_bought": round(new_shares, 6),
            "shares_total": round(shares, 6),
            "invested": round(invested, 2),
            "dividend_week": round(div_week, 4),
            "market_value": round(market_value, 2),
        })

    latest_close = series[-1][1]
    final_mark = par if mode == "par" else latest_close
    res.invested = invested
    res.shares = shares
    res.dividends_cash = div_cash
    res.dividends_reinvested = div_reinv
    res.latest_close = final_mark
    res.market_value = shares * final_mark
    res.avg_cost = invested / shares if shares else 0.0
    res.capital_pl = res.market_value - invested
    res.capital_pl_pct = (res.capital_pl / invested * 100.0) if invested else 0.0
    res.total_value = res.market_value + div_cash
    res.total_pl = res.total_value - invested
    res.total_pl_pct = (res.total_pl / invested * 100.0) if invested else 0.0
    total_div = div_cash + div_reinv
    res.yield_on_cost = (total_div / invested * 100.0) if invested else 0.0
    return res


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #

def _eur(x: float) -> str:
    return f"${x:,.2f}"


def _pct(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f}%"


def print_report(par_res: SimResult, close_res: SimResult,
                 series: List[Tuple[dt.date, float, bool]],
                 interpolated: int, live: bool, source_note: str,
                 dividends_on: bool, reinvest: bool,
                 btc_res: Optional[SimResult] = None) -> None:
    first_week, last_week = series[0][0], series[-1][0]
    n_weeks = len(series)
    line = "=" * 74

    print(line)
    print("  STRC DCA SIMULATOR — Closing-Price Edition")
    print("  Bitcoin Intelligence Report · STRC Mode (recalculé au closing réel)")
    print(line)
    print(f"  Période        : {first_week} → {last_week}  ({n_weeks} semaines)")
    print(f"  DCA hebdo      : {_eur(close_res.weekly_amount)} / semaine")
    print(f"  Source prix    : {'LIVE — ' + source_note if live else 'SNAPSHOT embarqué (hors-ligne)'}")
    if interpolated:
        print(f"  ⚠ Semaines interpolées : {interpolated}/{n_weeks} "
              f"(closes manquants estimés linéairement)")
    print(f"  Dividendes     : {'ON' if dividends_on else 'OFF'}"
          f"{' · réinvestis' if (dividends_on and reinvest) else ''}")
    print(f"  Closing STRC   : IPO {_eur(STRC_IPO_PRICE)} → dernier {_eur(close_res.latest_close)} "
          f"(par {_eur(STRC_PAR)})")
    print(line)

    # Tableau comparatif
    rows = [
        ("Métrique", "MODE PAR ($100)", "MODE CLOSING (réel)"),
        ("Total investi", _eur(par_res.invested), _eur(close_res.invested)),
        ("Actions STRC", f"{par_res.shares:,.4f}", f"{close_res.shares:,.4f}"),
        ("Coût moyen / action", _eur(par_res.avg_cost), _eur(close_res.avg_cost)),
        ("Dernier closing", _eur(par_res.latest_close), _eur(close_res.latest_close)),
        ("Valeur de marché", _eur(par_res.market_value), _eur(close_res.market_value)),
        ("+/- value capital", _eur(par_res.capital_pl), _eur(close_res.capital_pl)),
        ("  (en %)", _pct(par_res.capital_pl_pct), _pct(close_res.capital_pl_pct)),
    ]
    if dividends_on:
        rows += [
            ("Dividendes perçus",
             _eur(par_res.dividends_cash + par_res.dividends_reinvested),
             _eur(close_res.dividends_cash + close_res.dividends_reinvested)),
            ("Yield on cost", _pct(par_res.yield_on_cost), _pct(close_res.yield_on_cost)),
        ]
    rows += [
        ("VALEUR TOTALE", _eur(par_res.total_value), _eur(close_res.total_value)),
        ("P/L TOTAL", _eur(par_res.total_pl), _eur(close_res.total_pl)),
        ("  (en %)", _pct(par_res.total_pl_pct), _pct(close_res.total_pl_pct)),
    ]

    w0, w1, w2 = 22, 20, 22
    for i, (a, b, c) in enumerate(rows):
        print(f"  {a:<{w0}} {b:>{w1}} {c:>{w2}}")
        if i == 0:
            print("  " + "-" * (w0 + w1 + w2 + 2))
    print(line)

    # L'impact de la modification : différence entre les deux modes.
    delta_shares = close_res.shares - par_res.shares
    delta_value = close_res.total_value - par_res.total_value
    print("  IMPACT DE LA MODIFICATION (closing réel vs par $100)")
    print("  " + "-" * 70)
    print(f"  Actions supplémentaires acquises : {delta_shares:+,.4f} "
          f"(achat sous le par => plus d'actions)")
    print(f"  Écart de valeur totale           : {_eur(delta_value)} "
          f"({_pct((delta_value / par_res.total_value * 100.0) if par_res.total_value else 0)})")
    if close_res.capital_pl < 0:
        print(f"  ⚠ Perte en capital intégrée      : {_eur(close_res.capital_pl)} "
              f"— STRC sous le par 100 $ au dernier closing.")
    else:
        print(f"  Plus-value en capital intégrée   : {_eur(close_res.capital_pl)}")
    print(line)

    if btc_res is not None:
        print("  BENCHMARK — même DCA hebdo déployé en BITCOIN (BTC-USD)")
        print("  " + "-" * 70)
        print(f"  Investi        : {_eur(btc_res.invested)}")
        print(f"  BTC accumulés  : {btc_res.shares:,.8f} BTC")
        print(f"  Valeur marché  : {_eur(btc_res.market_value)}")
        print(f"  P/L            : {_eur(btc_res.capital_pl)} ({_pct(btc_res.capital_pl_pct)})")
        print(line)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def get_series(symbol: str, start: dt.date, end: dt.date,
               use_live: bool, verbose: bool
               ) -> Tuple[Dict[dt.date, float], bool, str]:
    """Retourne (raw_closes, live?, note_source)."""
    if use_live:
        try:
            raw = fetch_weekly_closes(symbol, start, end, verbose)
            return raw, True, f"{symbol} (Yahoo/Stooq)"
        except RuntimeError as exc:
            print(f"[avertissement] Récupération live impossible : {exc}",
                  file=sys.stderr)
            print("[avertissement] Bascule sur le snapshot embarqué.",
                  file=sys.stderr)
    raw = load_snapshot()
    return raw, False, "snapshot local"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="STRC weekly-DCA simulator utilisant le closing price réel "
                    "(et non le par 100 $).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--weekly-amount", type=float, default=1000.0,
                    help="Montant DCA hebdomadaire en USD.")
    ap.add_argument("--start", type=str, default=STRC_LAUNCH_LABEL,
                    help="Date de début (YYYY-MM-DD). Défaut = lancement STRC.")
    ap.add_argument("--end", type=str, default=dt.date.today().isoformat(),
                    help="Date de fin (YYYY-MM-DD).")
    ap.add_argument("--no-live", action="store_true",
                    help="Ne pas récupérer en direct ; utiliser le snapshot embarqué.")
    ap.add_argument("--no-dividends", action="store_true",
                    help="Ignorer le rendement (dividende) de STRC.")
    ap.add_argument("--reinvest-dividends", action="store_true",
                    help="Réinvestir les dividendes (DRIP).")
    ap.add_argument("--apy", type=float, default=DEFAULT_DIVIDEND_APY,
                    help="Rendement annualisé de repli si pas de calendrier de dividendes.")
    ap.add_argument("--btc-benchmark", action="store_true",
                    help="Ajouter un benchmark : même DCA déployé en BTC.")
    ap.add_argument("--json", action="store_true",
                    help="Sortie JSON (machine-readable).")
    ap.add_argument("--csv-out", type=str, default=None,
                    help="Écrire l'historique semaine par semaine (mode closing) dans un CSV.")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    try:
        start = dt.date.fromisoformat(args.start)
        end = dt.date.fromisoformat(args.end)
    except ValueError as exc:
        print(f"Date invalide : {exc}", file=sys.stderr)
        return 2
    start = max(start, STRC_FIRST_TRADE)

    use_live = not args.no_live
    raw, live, source_note = get_series("STRC", start, end, use_live, args.verbose)
    if not raw:
        print("Erreur : aucune donnée de prix STRC (live indisponible et snapshot vide).",
              file=sys.stderr)
        return 1

    series, interpolated = build_continuous_series(raw, start, end)

    dividends_on = not args.no_dividends
    schedule = load_dividends() if dividends_on else []

    par_res = simulate(series, args.weekly_amount, "par", schedule,
                       args.apy if dividends_on else 0.0,
                       args.reinvest_dividends)
    close_res = simulate(series, args.weekly_amount, "closing", schedule,
                         args.apy if dividends_on else 0.0,
                         args.reinvest_dividends)

    btc_res = None
    if args.btc_benchmark:
        if not use_live:
            print("[avertissement] Benchmark BTC ignoré : nécessite les données live "
                  "(--btc-benchmark incompatible avec --no-live).", file=sys.stderr)
        else:
            try:
                # BTC : récupération live directe, pas de fallback snapshot STRC.
                btc_raw = fetch_weekly_closes("BTC-USD", start, end, args.verbose)
                btc_series, _ = build_continuous_series(btc_raw, start, end)
                # Pas de par ni dividende pour BTC : mode closing sans rendement.
                btc_res = simulate(btc_series, args.weekly_amount, "closing", [], 0.0, False)
            except Exception as exc:  # noqa: BLE001
                print(f"[avertissement] Benchmark BTC indisponible : {exc}", file=sys.stderr)

    if args.csv_out:
        with open(args.csv_out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(close_res.history[0].keys()))
            writer.writeheader()
            writer.writerows(close_res.history)
        print(f"Historique écrit dans {args.csv_out}", file=sys.stderr)

    if args.json:
        payload = {
            "params": {
                "weekly_amount": args.weekly_amount,
                "start": series[0][0].isoformat(),
                "end": series[-1][0].isoformat(),
                "weeks": len(series),
                "live": live,
                "source": source_note,
                "interpolated_weeks": interpolated,
                "dividends": dividends_on,
                "reinvest": args.reinvest_dividends,
                "par": STRC_PAR,
                "latest_close": close_res.latest_close,
            },
            "par_mode": {k: v for k, v in asdict(par_res).items() if k != "history"},
            "closing_mode": {k: v for k, v in asdict(close_res).items() if k != "history"},
            "impact": {
                "extra_shares": close_res.shares - par_res.shares,
                "value_delta": close_res.total_value - par_res.total_value,
                "capital_pl_closing": close_res.capital_pl,
            },
        }
        if btc_res is not None:
            payload["btc_benchmark"] = {
                k: v for k, v in asdict(btc_res).items() if k != "history"
            }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print_report(par_res, close_res, series, interpolated, live, source_note,
                     dividends_on, args.reinvest_dividends, btc_res)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
