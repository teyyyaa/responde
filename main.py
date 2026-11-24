"""Main entry point for the RESPONDE emergency-reporting system."""

from __future__ import annotations

import argparse


ROLES = ("operator", "barangay", "fire", "ambulance", "command")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="RESPONDE emergency-reporting system",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--server",
        action="store_true",
        help="run the broker server for clients on this LAN",
    )
    mode.add_argument("--connect", metavar="URL", help="connect dashboards to a broker server")
    parser.add_argument("--host", default="0.0.0.0", help="server bind address (default: all interfaces)")
    parser.add_argument("--port", type=int, default=8000, help="server port (default: 8000)")
    parser.add_argument(
        "--role",
        action="append",
        choices=ROLES,
        help="open only this dashboard role; may be supplied more than once",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.server:
        from broker.server import create_server

        server = create_server(host=args.host, port=args.port)
        print(f"RESPONDE broker listening on {args.host}:{args.port}")
        server.run()
        return

    from clients.http_broker import HttpBroker
    from examples.demo_full import main as launch_gui

    broker = HttpBroker(args.connect) if args.connect else None
    launch_gui(broker=broker, roles=args.role)


if __name__ == "__main__":
    main()