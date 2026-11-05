#!/usr/bin/env python3
"""Deterministic merge controller for delegated phase delivery.

Canonical procedure: docs/reference/delegated-delivery.md. This script decides; it
never reviews. It refuses unless every precondition holds for the exact head SHA
that the independent reviewer approved, then squash-merges with --match-head-commit.
Run it from a clean checkout of current origin/main, never from the PR branch.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANCH_RE = re.compile(r"^phase/(3[0-4])-[a-z0-9][a-z0-9-]*$")
VERDICT_RE = re.compile(r"```vibe-review-verdict[ \t]*\r?\n(.*?)\r?\n```", re.DOTALL)
GATE_RE = re.compile(r"^G-PASS phase-(3[0-4])$")
REQUIRED_CHECKS = frozenset(
    {"gate"} | {"%s / py%s" % (os_name, py)
                for os_name in ("ubuntu-24.04", "macos-latest", "windows-latest")
                for py in ("3.9", "3.11", "3.13")}
)
OK_CONCLUSIONS = {"SUCCESS"}
NEUTRAL_CONCLUSIONS = {"SKIPPED", "NEUTRAL"}


class ControllerError(RuntimeError):
    """A precondition could not be evaluated."""


def _timestamp(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def parse_verdicts(comments):
    """Yield (created_at, verdict dict) for every well-formed verdict block, oldest first."""
    found = []
    for comment in comments:
        for block in VERDICT_RE.findall(comment.get("body") or ""):
            try:
                verdict = json.loads(block)
            except ValueError:
                continue
            if isinstance(verdict, dict) and verdict.get("schema") == 1:
                found.append((comment.get("createdAt") or "", verdict))
    return sorted(found, key=lambda item: item[0])


def evaluate(pr, comments, threads, head_committed_at, is_protected, expected_phase=None):
    """Return a list of human-readable failures; empty means every precondition holds."""
    failures = []
    head = pr.get("headRefOid") or ""
    branch = pr.get("headRefName") or ""
    if pr.get("state") != "OPEN" or pr.get("isDraft"):
        failures.append("PR is not open and ready")
    if pr.get("baseRefName") != "main":
        failures.append("PR does not target main")
    match = BRANCH_RE.match(branch)
    if not match:
        failures.append("branch " + branch + " is not a delegated phase/3N-* branch")
    elif expected_phase and match.group(1) != str(expected_phase):
        failures.append("branch phase " + match.group(1) + " does not match expected phase " + str(expected_phase))

    seen = {}
    for check in pr.get("statusCheckRollup") or []:
        name = check.get("name") or check.get("context") or ""
        conclusion = (check.get("conclusion") or check.get("state") or "").upper()
        if check.get("status") not in (None, "COMPLETED") and check.get("__typename") == "CheckRun":
            conclusion = "PENDING"
        seen[name] = conclusion
        if conclusion not in OK_CONCLUSIONS | NEUTRAL_CONCLUSIONS:
            failures.append("check " + name + " is " + (conclusion or "unknown"))
    for name in sorted(REQUIRED_CHECKS - set(seen)):
        failures.append("required check " + name + " is missing")
    for name in sorted(REQUIRED_CHECKS & set(seen)):
        if seen[name] not in OK_CONCLUSIONS:
            failures.append("required check " + name + " did not succeed")

    if pr.get("mergeable") != "MERGEABLE":
        failures.append("GitHub reports mergeable=" + str(pr.get("mergeable")))
    unresolved = sum(1 for thread in threads if not thread.get("isResolved"))
    if unresolved:
        failures.append(str(unresolved) + " unresolved review thread(s)")

    touched = sorted(item["path"] for item in pr.get("files") or [] if is_protected(item["path"]))
    if touched:
        failures.append("protected paths changed; the human owner must merge: " + ", ".join(touched[:5]))

    verdicts = [(at, v) for at, v in parse_verdicts(comments) if v.get("head_sha") == head]
    if not verdicts:
        failures.append("no independent review verdict is bound to head " + head[:12])
    else:
        created, verdict = verdicts[-1]
        if verdict.get("verdict") != "approve":
            failures.append("latest verdict for head is " + str(verdict.get("verdict")))
        if verdict.get("critical") != 0 or verdict.get("high") != 0:
            failures.append("verdict reports unresolved Critical or High findings")
        reviewer, implementer = verdict.get("reviewer_session"), verdict.get("implementer_session")
        if not (isinstance(reviewer, str) and reviewer.strip() and isinstance(implementer, str)
                and implementer.strip() and reviewer != implementer):
            failures.append("verdict does not name distinct reviewer and implementer sessions")
        gate = verdict.get("gate_result")
        gate_match = GATE_RE.match(gate) if isinstance(gate, str) else None
        if not gate_match or (match and gate_match.group(1) != match.group(1)):
            failures.append("verdict lacks a passing gate result for this phase")
        try:
            if _timestamp(created) < _timestamp(head_committed_at):
                failures.append("verdict predates the head commit")
        except ValueError:
            failures.append("verdict or head commit timestamp is unreadable")
    return failures


def _run(command, cwd=None):
    proc = subprocess.run(command, cwd=str(cwd or ROOT), capture_output=True, text=True)
    if proc.returncode:
        raise ControllerError(" ".join(command[:3]) + " failed: " + (proc.stderr.strip() or proc.stdout.strip())[:240])
    return proc.stdout


def _gh_json(*args):
    return json.loads(_run(["gh", *args]))


def _repo():
    return _run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()


def _threads(repo, number):
    owner, name = repo.split("/")
    query = ("query($o:String!,$n:String!,$p:Int!){repository(owner:$o,name:$n){pullRequest(number:$p)"
             "{reviewThreads(first:100){pageInfo{hasNextPage} nodes{isResolved}}}}}")
    data = _gh_json("api", "graphql", "-f", "query=" + query, "-F", "o=" + owner, "-F", "n=" + name, "-F", "p=" + str(number))
    block = data["data"]["repository"]["pullRequest"]["reviewThreads"]
    if block["pageInfo"]["hasNextPage"]:
        raise ControllerError("more than 100 review threads; resolve some before delegating the merge")
    return block["nodes"]


def _require_current_main():
    _run(["git", "fetch", "origin", "main", "--quiet"])
    if _run(["git", "rev-parse", "HEAD"]).strip() != _run(["git", "rev-parse", "origin/main"]).strip():
        raise ControllerError("run from a clean checkout of current origin/main, not the PR branch")
    if _run(["git", "status", "--porcelain", "--untracked-files=no"]).strip():
        raise ControllerError("controller checkout has local modifications")


def _load_protection():
    sys.path.insert(0, str(ROOT))
    from vibe import governance
    policy = governance.load_policy(ROOT)
    return lambda path: governance.is_protected_path(governance.normalize_relative_path(ROOT, path), policy)


def _inspect(number, expected_phase):
    repo = _repo()
    pr = _gh_json("pr", "view", str(number), "--json",
                  "state,isDraft,baseRefName,headRefName,headRefOid,mergeable,statusCheckRollup,files,comments,commits")
    commits = pr.get("commits") or []
    head_date = commits[-1]["committedDate"] if commits else ""
    failures = evaluate(pr, pr.get("comments") or [], _threads(repo, number), head_date,
                        _load_protection(), expected_phase)
    return pr, failures


def cmd_check(args):
    _require_current_main()
    pr, failures = _inspect(args.pr, args.phase)
    for failure in failures:
        print("MERGE-BLOCKED " + failure)
    if failures:
        return 1
    print("MERGE-READY pr=%d head=%s" % (args.pr, pr["headRefOid"]))
    return 0


def cmd_merge(args):
    _require_current_main()
    pr, failures = _inspect(args.pr, args.phase)
    if failures:
        for failure in failures:
            print("MERGE-BLOCKED " + failure)
        return 1
    head = pr["headRefOid"]
    _run(["gh", "pr", "merge", str(args.pr), "--squash", "--match-head-commit", head,
          "--subject", "%s (#%d)" % (args.subject, args.pr)])
    after = _gh_json("pr", "view", str(args.pr), "--json", "state,mergeCommit")
    merge_sha = (after.get("mergeCommit") or {}).get("oid")
    if after.get("state") != "MERGED" or not merge_sha:
        raise ControllerError("PR did not report MERGED after merge")
    _run(["git", "fetch", "origin", "main", "--quiet"])
    _run(["git", "merge-base", "--is-ancestor", merge_sha, "origin/main"])
    print(json.dumps({"merged": True, "pr": args.pr, "reviewed_head": head, "merge_commit": merge_sha}, sort_keys=True))
    return 0


def cmd_post_merge(args):
    deadline = time.time() + args.timeout
    while True:
        runs = _gh_json("run", "list", "--commit", args.sha, "--json", "workflowName,status,conclusion")
        if runs and all(item["status"] == "completed" for item in runs):
            bad = [item["workflowName"] for item in runs if item["conclusion"] != "success"]
            if bad:
                print("POST-MERGE-FAIL " + ", ".join(sorted(set(bad))))
                return 1
            print("POST-MERGE-OK runs=%d commit=%s" % (len(runs), args.sha))
            return 0
        if time.time() > deadline:
            print("POST-MERGE-PENDING timed out waiting for CI on " + args.sha)
            return 2
        time.sleep(20)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Delegated-delivery merge controller")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="evaluate every merge precondition; never merges")
    check.add_argument("--pr", type=int, required=True)
    check.add_argument("--phase", help="expected phase number, e.g. 31")
    check.set_defaults(func=cmd_check)
    merge = sub.add_parser("merge", help="merge only if every precondition holds")
    merge.add_argument("--pr", type=int, required=True)
    merge.add_argument("--phase", required=True)
    merge.add_argument("--subject", required=True, help="squash commit subject, without the PR number")
    merge.set_defaults(func=cmd_merge)
    post = sub.add_parser("post-merge", help="wait for CI on the merge commit")
    post.add_argument("--sha", required=True)
    post.add_argument("--timeout", type=int, default=900)
    post.set_defaults(func=cmd_post_merge)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ControllerError, OSError, ValueError) as exc:
        print("MERGE-CONTROLLER-FAIL " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
