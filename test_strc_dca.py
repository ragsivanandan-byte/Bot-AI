#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Suite de tests pour strc_dca.py — validation de la logique financière
et des cas limites. Aucune dépendance externe (unittest stdlib).

    python3 -m unittest test_strc_dca -v
    python3 test_strc_dca.py
"""

import datetime as dt
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

import strc_dca as m


D = dt.date


class TestDateHelpers(unittest.TestCase):
    def test_to_friday(self):
        self.assertEqual(m._to_friday(D(2025, 8, 4)), D(2025, 8, 8))   # lundi
        self.assertEqual(m._to_friday(D(2025, 8, 8)), D(2025, 8, 8))   # vendredi
        self.assertEqual(m._to_friday(D(2025, 8, 9)), D(2025, 8, 8))   # samedi
        self.assertEqual(m._to_friday(D(2025, 8, 10)), D(2025, 8, 8))  # dimanche
        self.assertEqual(m._to_friday(D(2025, 9, 15)), D(2025, 9, 19))  # lundi

    def test_fridays_between(self):
        out = m.fridays_between(D(2025, 8, 1), D(2025, 8, 20))
        self.assertEqual(out, [D(2025, 8, 1), D(2025, 8, 8), D(2025, 8, 15)])

    def test_fridays_between_empty(self):
        # start > end => aucune semaine
        self.assertEqual(m.fridays_between(D(2026, 1, 1), D(2025, 1, 1)), [])


class TestSeriesBuild(unittest.TestCase):
    def test_linear_interpolation(self):
        raw = {D(2025, 8, 1): 50.0, D(2025, 8, 15): 100.0}
        series, interp = m.build_continuous_series(raw, D(2025, 8, 1), D(2025, 8, 15))
        self.assertEqual(interp, 1)
        self.assertEqual([s[0] for s in series],
                         [D(2025, 8, 1), D(2025, 8, 8), D(2025, 8, 15)])
        self.assertEqual(series[0][1], 50.0)
        self.assertAlmostEqual(series[1][1], 75.0)   # milieu interpolé
        self.assertTrue(series[1][2])                # marqué estimated
        self.assertEqual(series[2][1], 100.0)
        self.assertFalse(series[2][2])

    def test_flat_carry_after_last_known(self):
        raw = {D(2025, 8, 1): 90.0}
        series, interp = m.build_continuous_series(raw, D(2025, 8, 1), D(2025, 8, 22))
        # Toutes les semaines après l'unique point connu reprennent sa valeur.
        self.assertTrue(all(s[1] == 90.0 for s in series))
        self.assertEqual(interp, len(series) - 1)

    def test_raises_when_no_data(self):
        with self.assertRaises(RuntimeError):
            m.build_continuous_series({}, D(2025, 8, 1), D(2025, 8, 15))


class TestSimulateCore(unittest.TestCase):
    def _two_week(self):
        # Semaine 1 close 50, semaine 2 close 100.
        return [(D(2025, 8, 1), 50.0, False), (D(2025, 8, 8), 100.0, False)]

    def test_par_mode_no_capital_pl(self):
        r = m.simulate(self._two_week(), 100.0, "par", [], 0.0, False)
        self.assertEqual(r.invested, 200.0)
        self.assertAlmostEqual(r.shares, 2.0)            # 1 + 1 au par 100
        self.assertAlmostEqual(r.avg_cost, 100.0)
        self.assertAlmostEqual(r.market_value, 200.0)    # valorisé au par
        self.assertAlmostEqual(r.capital_pl, 0.0)        # AUCUNE perte en mode par
        self.assertAlmostEqual(r.capital_pl_pct, 0.0)

    def test_closing_mode_captures_capital(self):
        r = m.simulate(self._two_week(), 100.0, "closing", [], 0.0, False)
        self.assertEqual(r.invested, 200.0)
        self.assertAlmostEqual(r.shares, 3.0)            # 2 (à 50) + 1 (à 100)
        self.assertAlmostEqual(r.avg_cost, 200.0 / 3.0)
        self.assertAlmostEqual(r.latest_close, 100.0)
        self.assertAlmostEqual(r.market_value, 300.0)    # 3 * 100
        self.assertAlmostEqual(r.capital_pl, 100.0)      # +100 de plus-value
        self.assertAlmostEqual(r.capital_pl_pct, 50.0)

    def test_closing_mode_capital_loss(self):
        # Achat à 100 puis le titre tombe à 80 => perte en capital.
        series = [(D(2025, 8, 1), 100.0, False), (D(2025, 8, 8), 80.0, False)]
        r = m.simulate(series, 100.0, "closing", [], 0.0, False)
        # sem1: 1 action @100 ; sem2: 1.25 action @80 => 2.25 actions
        self.assertAlmostEqual(r.shares, 2.25)
        self.assertAlmostEqual(r.market_value, 2.25 * 80.0)   # 180
        self.assertAlmostEqual(r.capital_pl, 180.0 - 200.0)   # -20
        self.assertLess(r.capital_pl, 0)

    def test_zero_buy_price_safe(self):
        # Un close à 0 ne doit pas planter (division protégée).
        series = [(D(2025, 8, 1), 0.0, True), (D(2025, 8, 8), 100.0, False)]
        r = m.simulate(series, 100.0, "closing", [], 0.0, False)
        self.assertAlmostEqual(r.shares, 1.0)   # rien acheté semaine 1, 1 action semaine 2


class TestDividends(unittest.TestCase):
    def test_weekly_dividend_fallback_apy(self):
        # apy 52% sur par 100 => 100*0.52/52 = 1.0 / action / semaine
        self.assertAlmostEqual(m.weekly_dividend_per_share(D(2025, 8, 1), [], 0.52), 1.0)

    def test_weekly_dividend_schedule_lookup(self):
        sched = [(D(2025, 8, 15), 0.85), (D(2026, 1, 15), 0.96)]
        # avant la 1re ex-date => prend le 1er montant
        self.assertAlmostEqual(m.weekly_dividend_per_share(D(2025, 8, 1), sched, 0.0),
                               0.85 * 12 / 52)
        # entre les deux => 0.85
        self.assertAlmostEqual(m.weekly_dividend_per_share(D(2025, 11, 1), sched, 0.0),
                               0.85 * 12 / 52)
        # après la 2e => 0.96
        self.assertAlmostEqual(m.weekly_dividend_per_share(D(2026, 3, 1), sched, 0.0),
                               0.96 * 12 / 52)

    def test_dividends_cash_accrual(self):
        # 2 semaines à close 100, apy 52% => dps 1.0. Semaine 1 : 0 action détenue
        # avant achat => div 0. Semaine 2 : 1 action détenue => div 1.0.
        series = [(D(2025, 8, 1), 100.0, False), (D(2025, 8, 8), 100.0, False)]
        r = m.simulate(series, 100.0, "par", [], 0.52, False)
        self.assertAlmostEqual(r.dividends_cash, 1.0)
        self.assertAlmostEqual(r.total_value, 201.0)
        self.assertAlmostEqual(r.yield_on_cost, 0.5)

    def test_reinvest_matches_cash_value_at_par(self):
        # Réinvesti au par (=prix de valorisation) => même valeur totale que cash.
        series = [(D(2025, 8, 1), 100.0, False), (D(2025, 8, 8), 100.0, False)]
        cash = m.simulate(series, 100.0, "par", [], 0.52, False)
        drip = m.simulate(series, 100.0, "par", [], 0.52, True)
        self.assertAlmostEqual(cash.total_value, drip.total_value)
        self.assertAlmostEqual(drip.dividends_cash, 0.0)
        self.assertAlmostEqual(drip.dividends_reinvested, 1.0)
        self.assertGreater(drip.shares, cash.shares)   # actions DRIP en plus


class TestDataFiles(unittest.TestCase):
    def test_snapshot_loads_anchor(self):
        snap = m.load_snapshot()
        self.assertTrue(snap, "snapshot vide")
        self.assertIn(D(2026, 6, 18), snap)
        self.assertAlmostEqual(snap[D(2026, 6, 18)], 88.59)

    def test_dividends_load_sorted(self):
        div = m.load_dividends()
        self.assertTrue(div)
        dates = [d for d, _ in div]
        self.assertEqual(dates, sorted(dates))

    def test_read_csv_skips_comments(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("# commentaire\ndate,close\n2025-08-15,96.95\n")
            path = fh.name
        try:
            rows = m._read_csv_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["close"], "96.95")
        finally:
            os.unlink(path)


class TestMainCLI(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = m.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_reject_negative_amount(self):
        code, _, err = self._run(["--no-live", "--weekly-amount", "-5"])
        self.assertEqual(code, 2)
        self.assertIn("positif", err)

    def test_reject_end_before_start(self):
        code, _, err = self._run(["--no-live", "--start", "2026-01-01",
                                  "--end", "2025-12-01"])
        self.assertEqual(code, 2)
        self.assertIn("précède", err)

    def test_reject_bad_date(self):
        code, _, _ = self._run(["--no-live", "--start", "not-a-date"])
        self.assertEqual(code, 2)

    def test_text_report_runs(self):
        code, out, _ = self._run(["--no-live", "--weekly-amount", "1000"])
        self.assertEqual(code, 0)
        self.assertIn("MODE CLOSING", out)
        self.assertIn("IMPACT DE LA MODIFICATION", out)

    def test_json_output_valid(self):
        import json
        code, out, _ = self._run(["--no-live", "--weekly-amount", "500", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["par_mode"]["capital_pl"], 0.0)   # par => 0 capital P/L
        self.assertLess(payload["closing_mode"]["capital_pl"], 0)  # closing => perte réelle
        self.assertIn("impact", payload)

    def test_btc_benchmark_skipped_offline(self):
        code, _, err = self._run(["--no-live", "--btc-benchmark"])
        self.assertEqual(code, 0)
        self.assertIn("Benchmark BTC ignoré", err)

    def test_csv_export(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "hist.csv")
            code, _, _ = self._run(["--no-live", "--csv-out", path])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(path))
            with open(path) as fh:
                head = fh.readline()
            self.assertIn("week", head)
            self.assertIn("market_value", head)


if __name__ == "__main__":
    unittest.main(verbosity=2)
