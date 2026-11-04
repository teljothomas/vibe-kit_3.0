"""Dispatch the stable Vibe CLI plus Phase 30 event and execution-governance commands."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _events(args):
    from . import events
    parser = argparse.ArgumentParser(prog="vibe events")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("verify", help="verify event ledger, chain and compact snapshot")
    migrate = sub.add_parser("migrate-v2", help="preview or import a V2 schema-2 state history")
    migrate.add_argument("--input", required=True, help="path to a V2 docs/state.json")
    group = migrate.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="preview without writing (default)")
    group.add_argument("--apply", action="store_true", help="append imported events and update snapshot")
    sub.add_parser("replay", help="recover the compact snapshot from the last durable snapshot event")
    rollback = sub.add_parser("rollback", help="human-approve restore of the previous snapshot without deleting history")
    rollback.add_argument("--reason", required=True, help="why the previous durable snapshot is being restored")
    parsed = parser.parse_args(args)
    root = Path.cwd()
    if parsed.action == "verify":
        result = events.verify_project(root)
        print("EVENTS-OK count={events} state_bytes={state_bytes}/{state_limit_bytes} human_signatures={human_decision_signatures_verified} verified/{human_decision_signatures_unverified} unverified head={last_hash}".format(**result))
        return 0
    if parsed.action == "migrate-v2":
        result = events.migrate_legacy_state(root, parsed.input, dry_run=not parsed.apply)
        label = "MIGRATION-OK" if parsed.apply else "MIGRATION-DRY-RUN"
        print(label + " entries={legacy_entries} already={already_imported} missing={would_import} null_timestamps={null_original_timestamps}".format(
            legacy_entries=result.get("legacy_entries", 0),
            already_imported=result.get("already_imported", 0),
            would_import=result.get("would_import", 0),
            null_original_timestamps=result.get("null_original_timestamps", 0),
        ))
        if parsed.apply:
            print("MIGRATION-SNAPSHOT sequence={final_sequence} bytes={state_bytes}".format(**result))
        return 0
    if parsed.action == "replay":
        result = events.replay_snapshot(root)
        print("REPLAY-OK phase=" + str(result.get("phase")) + " status=" + str(result.get("status")))
        return 0
    if parsed.action == "rollback":
        result = events.rollback_snapshot(root, parsed.reason)
        print("ROLLBACK-OK phase=" + result["phase"] + " status=" + result["status"]
              + " event_sequence=" + str(result["event_sequence"])
              + " approval_event=" + result["approval_event_id"])
        return 0
    return 2


def _mode(args):
    from . import execution
    parser = argparse.ArgumentParser(prog="vibe mode")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("show", help="show owner-selected execution governance mode")
    change = sub.add_parser("set", help="change mode through signed interactive owner approval")
    change.add_argument("--mode", required=True, choices=("supervised", "autonomous"))
    parsed = parser.parse_args(args)
    if parsed.action == "show":
        mode = execution.load_mode(Path.cwd())
        print("MODE=" + mode.upper() + " HUMAN_APPROVAL=" + ("ON" if mode == "supervised" else "OFF"))
        return 0
    result = execution.set_mode(Path.cwd(), parsed.mode)
    print("MODE-OK " + result["mode"] + (" unchanged" if not result["changed"] else " approval=" + result["approval"]))
    return 0


def _decision(args):
    from . import execution
    parser = argparse.ArgumentParser(prog="vibe decision")
    sub = parser.add_subparsers(dest="action", required=True)
    evaluate = sub.add_parser("evaluate", help="evaluate and record an agent decision")
    evaluate.add_argument("--class", dest="decision_class", required=True)
    evaluate.add_argument("--summary", required=True)
    evaluate.add_argument("--gate-passed", action="store_true")
    evaluate.add_argument("--out-of-scope", action="store_true")
    approve = sub.add_parser("approve", help="human-approve one exact decision")
    approve.add_argument("--class", dest="decision_class", required=True)
    approve.add_argument("--summary", required=True)
    parsed = parser.parse_args(args)
    if parsed.action == "evaluate":
        result = execution.record_decision(
            Path.cwd(), parsed.decision_class, parsed.summary,
            gate_passed=parsed.gate_passed, within_phase_scope=not parsed.out_of_scope,
        )
        label = "DECISION-REQUIRES-HUMAN" if result["decision"] == "human_required" else "DECISION-OK"
        print(label + " class=" + parsed.decision_class + " mode=" + result["mode"]
              + " actor=" + result["actor"] + " reason=" + result["reason"])
        return 2 if result["decision"] == "human_required" else 0
    result = execution.approve_decision(Path.cwd(), parsed.decision_class, parsed.summary)
    print("DECISION-HUMAN-APPROVED class=" + parsed.decision_class + " reviewer=" + result["reviewer"])
    return 0


def _phase(args):
    from . import phase
    parser = argparse.ArgumentParser(prog="vibe phase")
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("start", help="owner-sign and activate the immediately following phase contract")
    start.add_argument("phase")
    parsed = parser.parse_args(args)
    result = phase.start_phase(Path.cwd(), parsed.phase)
    print("PHASE-STARTED phase=" + result["phase"] + " status=" + result["status"]
          + " event_sequence=" + str(result["event_sequence"])
          + " approvals=" + str(len(result["approval_records"])))
    print("Execution mode: " + result["execution_mode"])
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "events":
        from .events import EventError
        try:
            return _events(args[1:])
        except (EventError, OSError, ValueError) as exc:
            print("EVENTS-FAIL " + str(exc), file=sys.stderr)
            return 2
    if args and args[0] == "mode":
        from .execution import ExecutionPolicyError
        try:
            return _mode(args[1:])
        except (ExecutionPolicyError, ValueError, OSError) as exc:
            print("MODE-FAIL " + str(exc), file=sys.stderr)
            return 2
    if args and args[0] == "decision":
        from .execution import ExecutionPolicyError
        from .approvals import ApprovalError
        try:
            return _decision(args[1:])
        except (ExecutionPolicyError, ApprovalError, ValueError, OSError) as exc:
            print("DECISION-FAIL " + str(exc), file=sys.stderr)
            return 2
    if args and args[0] == "phase":
        from .phase import PhaseStartError
        from .approvals import ApprovalError
        from .events import EventError
        try:
            return _phase(args[1:])
        except (PhaseStartError, ApprovalError, EventError, ValueError, OSError) as exc:
            print("PHASE-FAIL " + str(exc), file=sys.stderr)
            return 2
    from .cli import main as legacy_main
    return legacy_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
