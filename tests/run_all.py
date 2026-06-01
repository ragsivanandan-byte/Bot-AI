#!/usr/bin/env python3
"""
run_all.py — Lance TOUTES les suites de tests et agrège le résultat.

    python tests/run_all.py

Sortie : le détail de chaque suite + un total global. Code de sortie 0 si tout
passe, 1 sinon.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITES = ["tests/test_core.py", "tests/test_extended.py"]


def main() -> int:
    total_pass = total_fail = 0
    failed_suites: list[str] = []

    for suite in SUITES:
        print(f"\n{'#' * 56}\n##  {suite}\n{'#' * 56}")
        r = subprocess.run([sys.executable, suite], cwd=ROOT,
                           capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.stderr.strip():
            sys.stderr.write(r.stderr)
        total_pass += r.stdout.count("  ✅ ")
        total_fail += r.stdout.count("  ❌ ")
        if r.returncode != 0:
            failed_suites.append(suite)

    print(f"\n{'=' * 56}")
    print(f"TOTAL GLOBAL : {total_pass} assertions OK, {total_fail} en échec "
          f"sur {len(SUITES)} suites.")
    if failed_suites:
        print(f"❌ Suites en échec : {', '.join(failed_suites)}")
        return 1
    print("✅ TOUT EST VERT — l'outil est opérationnel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
