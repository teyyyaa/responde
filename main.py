"""Main entry point for the RESPONDE emergency-reporting system.

Run without arguments to open the complete GUI. Use --api to start the
local HTTP broker API instead.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="RESPONDE emergency-reporting system",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="start the HTTP API on 127.0.0.1:8000",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.api:
        from broker.api import app

        print("RESPONDE API listening at http://127.0.0.1:8000")
        app.run()
        return

    from examples.demo_full import main as launch_gui

    launch_gui()


if __name__ == "__main__":
    main()