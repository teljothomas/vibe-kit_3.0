"""Vibe Kit 3.0 command-line entry point."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, approvals, doctor, githooks, governance, state, verify


def build_parser():
    parser = argparse.ArgumentParser(prog="vibe", description="Vibe Kit 3.0 local-first engineering protocol")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="show a compact current-phase summary")
    p_doc = sub.add_parser("doctor", help="check runtime and repository integrity")
    p_doc.add_argument("--strict", action="store_true", help="run strict repository checks")
    sub.add_parser("verify", help="verify current state and active phase contract")

    p_governance = sub.add_parser("governance", help="inspect or maintain protected governance files")
    governance_sub = p_governance.add_subparsers(dest="governance_command", required=True)
    governance_sub.add_parser("check", help="check policy integrity and unresolved amendment proposals")
    governance_sub.add_parser("approve-staged", help="human-approve staged protected non-phase files")

    p_amend = sub.add_parser("amendment", help="apply a human-approved phase contract amendment")
    amend_sub = p_amend.add_subparsers(dest="amendment_command", required=True)
    p_apply = amend_sub.add_parser("apply", help="apply docs/proposals/phase-NN-amend.md after interactive review")
    p_apply.add_argument("--phase", help="active phase number; defaults to docs/state.json")

    p_hooks = sub.add_parser("hooks", help="install or remove the local Git pre-commit guard")
    hooks_sub = p_hooks.add_subparsers(dest="hooks_command", required=True)
    hooks_sub.add_parser("install", help="install the Vibe pre-commit hook, preserving any existing hook")
    hooks_sub.add_parser("uninstall", help="remove the Vibe pre-commit hook and restore any previous hook")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "status":
        try:
            current = state.load()
        except state.StateError as exc:
            print("STATUS-FAIL " + str(exc), file=sys.stderr)
            return 3
        print(json.dumps({"phase": current["phase"], "status": current["status"], "next": current["next"]}, separators=(",", ":")))
        return 0
    if args.command == "doctor":
        return doctor.run(strict=args.strict)
    if args.command == "verify":
        return verify.run()
    if args.command == "governance":
        if args.governance_command == "check":
            ok, message = governance.check_governance(Path.cwd())
            if ok:
                print("GOVERNANCE-OK policy-and-proposals-valid")
                return 0
            print("GOVERNANCE-FAIL " + (message or "governance check failed"), file=sys.stderr)
            return 1
        if args.governance_command == "approve-staged":
            try:
                written = approvals.approve_staged_paths(Path.cwd())
            except (approvals.ApprovalError, governance.GovernanceError) as exc:
                print("APPROVAL-FAIL " + str(exc), file=sys.stderr)
                return 2
            print("APPROVAL-OK " + ", ".join(written))
            return 0
    if args.command == "amendment" and args.amendment_command == "apply":
        try:
            current = state.load()
            phase = str(args.phase or current["phase"])
            result = approvals.apply_amendment(Path.cwd(), phase)
        except (state.StateError, approvals.ApprovalError, governance.GovernanceError, OSError) as exc:
            print("AMENDMENT-FAIL " + str(exc), file=sys.stderr)
            return 2
        print("AMENDMENT-OK " + result["target"] + " sha256=" + result["target_sha256"])
        return 0
    if args.command == "hooks":
        try:
            if args.hooks_command == "install":
                print("HOOKS-OK installed " + githooks.install(Path.cwd()))
                return 0
            if args.hooks_command == "uninstall":
                removed = githooks.uninstall(Path.cwd())
                print("HOOKS-OK " + ("removed" if removed else "not-installed"))
                return 0
        except governance.GovernanceError as exc:
            print("HOOKS-FAIL " + str(exc), file=sys.stderr)
            return 2
    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
