"""Command-line entrypoint for the FactSet Client Watch demo."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .demo import run_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="factset-bot",
        description="FactSet Client Watch - detect LinkedIn job changes for Salesforce-tracked users.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    demo_p = sub.add_parser("demo", help="Run the offline sales demo end-to-end.")
    demo_p.add_argument("--csv", type=Path, default=Path("data/factset_users_demo.csv"),
                        help="Path to the demo Salesforce CSV export.")
    demo_p.add_argument("--out", type=Path, default=Path("demo_output"),
                        help="Directory where dashboard + previews are written.")
    demo_p.add_argument("--no-open", action="store_true",
                        help="Do not auto-open the dashboard in a browser.")
    demo_p.add_argument("--fast", action="store_true",
                        help="Skip pauses between pipeline steps.")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "demo":
        run_demo(
            csv_path=args.csv,
            out_dir=args.out,
            open_browser=not args.no_open,
            pause=0.0 if args.fast else 0.6,
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
