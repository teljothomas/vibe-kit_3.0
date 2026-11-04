"""Vibe Kit 3.0 command-line entry point."""
import argparse
import json
import sys
from pathlib import Path
from . import __version__, doctor, state, verify

def build_parser():
    parser = argparse.ArgumentParser(prog="vibe", description="Vibe Kit 3.0 local-first engineering protocol")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="show a compact current-phase summary")
    p_doc = sub.add_parser("doctor", help="check runtime and repository integrity")
    p_doc.add_argument("--strict", action="store_true", help="reserved for strict release checks; all current checks are strict")
    sub.add_parser("verify", help="verify current state and active phase contract")
    return parser

def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "status":
        try:
            st = state.load()
        except state.StateError as exc:
            print("STATUS-FAIL " + str(exc), file=sys.stderr)
            return 3
        print(json.dumps({"phase": st["phase"], "status": st["status"], "next": st["next"]}, separators=(",", ":")))
        return 0
    if args.command == "doctor":
        return doctor.run(strict=args.strict)
    if args.command == "verify":
        return verify.run()
    parser.error("unsupported command")
    return 2

if __name__ == "__main__":
    sys.exit(main())
