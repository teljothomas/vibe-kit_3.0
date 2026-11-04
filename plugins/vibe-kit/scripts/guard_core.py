#!/usr/bin/env python3
"""Standalone, stdlib-only PreToolUse decision core shipped with the plugin.

This file intentionally has no dependency on the machine-level `vibe` package.
Its policy defaults are parity-tested against vibe.governance.DEFAULT_POLICY and
plugins/vibe-kit/templates/governance.json.
"""
from __future__ import annotations

import fnmatch
import json
import re
import shlex
from pathlib import Path
from typing import Any, Dict

DEFAULT_POLICY: Dict[str, Any] = {
    "schema": 1,
    "protected_paths": [
        "docs/state.json", "docs/invariants.md", "docs/decisions.md",
        "docs/governance.json", "docs/contracts/**", "docs/approvals/**",
        ".vibe/approvals/**",
        "AGENTS.md",
        ".github/workflows/**",
        "plugins/vibe-kit/**",
        "scripts/gate",
        "tests/phase29/**",
        "tests/test_ci_contract.py",
        "vibe/approvals.py",
        "vibe/cli.py",
        "vibe/doctor.py",
        "vibe/githooks.py",
        "vibe/governance.py",
        "vibe/verify.py",
    ],
    "phase_source_pattern": "docs/phases/phase-[0-9][0-9].md",
    "generated_phase_suffixes": [".context.md", ".repair.md"],
    "proposal_directory": "docs/proposals",
    "amendment_archive_directory": "docs/amendments",
    "approval_directory": "docs/approvals",
}
_PHASE_SOURCE = re.compile(r"^docs/phases/phase-[0-9]{2}\.md$", re.IGNORECASE)
_GENERATED_PHASE = re.compile(r"^docs/phases/phase-[0-9]{2}\.(?:context|repair)\.md$", re.IGNORECASE)


class GuardPathError(ValueError):
    pass


def normalize_relative_path(root: str | Path, target: str) -> str:
    root_path = Path(root).resolve(strict=True)
    raw = str(target).strip().replace("\\", "/")
    if not raw or "\x00" in raw:
        raise GuardPathError("target path is empty or invalid")
    if any(part == ".." for part in raw.split("/")):
        raise GuardPathError("path traversal is not allowed")
    drive_match = re.match(r"^([A-Za-z]):/(.*)$", raw)
    if drive_match:
        root_text = str(root_path).replace("\\", "/")
        root_drive = re.match(r"^([A-Za-z]):/(.*)$", root_text)
        if not root_drive or root_drive.group(1).casefold() != drive_match.group(1).casefold():
            raise GuardPathError("target path is outside the repository")
        prefix = root_text.rstrip("/")
        target_text = raw.rstrip("/")
        if target_text.casefold() == prefix.casefold():
            relative = ""
        elif target_text.casefold().startswith(prefix.casefold() + "/"):
            relative = target_text[len(prefix) + 1:]
        else:
            raise GuardPathError("target path is outside the repository")
        return relative.casefold()
    candidate = Path(raw) if raw.startswith("/") else root_path.joinpath(*[p for p in raw.split("/") if p not in ("", ".")])
    resolved = candidate.resolve(strict=False)
    try:
        relative = resolved.relative_to(root_path).as_posix()
    except ValueError as exc:
        raise GuardPathError("target path resolves outside the repository") from exc
    if relative in ("", "."):
        raise GuardPathError("repository root is not a file target")
    return relative.casefold()


def load_policy(root: str | Path) -> Dict[str, Any]:
    root = Path(root)
    project_policy = root / "docs" / "governance.json"
    template = Path(__file__).resolve().parents[1] / "templates" / "governance.json"
    candidate = project_policy if project_policy.exists() else template
    try:
        policy = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GuardPathError("governance policy is unreadable or invalid JSON") from exc
    if not isinstance(policy, dict) or policy.get("schema") != 1:
        raise GuardPathError("governance policy has an unsupported schema")
    patterns = policy.get("protected_paths")
    if not isinstance(patterns, list) or not all(isinstance(p, str) and p.strip() for p in patterns):
        raise GuardPathError("protected_paths must be a list of non-empty strings")
    # An on-disk policy can extend, never remove, the shipped baseline protections.
    merged = list(DEFAULT_POLICY["protected_paths"])
    for item in patterns:
        if item not in merged:
            merged.append(item)
    policy["protected_paths"] = merged
    return policy


def is_protected(relative_path: str, policy: Dict[str, Any]) -> bool:
    path = relative_path.replace("\\", "/").strip("/").casefold()
    if _GENERATED_PHASE.fullmatch(path):
        return False
    if _PHASE_SOURCE.fullmatch(path):
        return True
    return any(fnmatch.fnmatchcase(path, p.replace("\\", "/").casefold()) for p in policy["protected_paths"])


def active_state(root: str | Path) -> tuple[bool, bool]:
    """Return (active, readable); file existence identifies Vibe even if corrupt."""
    path = Path(root) / "docs" / "state.json"
    if not path.exists():
        return False, True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return True, False
    valid_statuses = {"not_started", "in_progress", "gated", "approved", "rejected"}
    phase = data.get("phase") if isinstance(data, dict) else None
    last_gate = data.get("last_gate") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or data.get("schema") != 1
        or not isinstance(phase, str)
        or not re.fullmatch(r"[0-9]{2}", phase)
        or data.get("status") not in valid_statuses
        or not isinstance(last_gate, dict)
        or last_gate.get("phase") != phase
    ):
        return True, False
    return True, True



def is_human_only_command(command: str, tool_name: str) -> bool:
    """Detect explicit CLI paths reserved for a human reviewer.

    This is a narrow guard against ordinary direct invocations, not a shell parser
    or a sandbox; arbitrary Python/shell code remains outside hook coverage.
    """
    if not isinstance(command, str) or not command.strip():
        return False
    for segment in re.split(r"&&|\|\||[|;]", command):
        try:
            tokens = shlex.split(segment.strip(), posix=(tool_name != "PowerShell"))
        except ValueError:
            tokens = segment.replace('"', ' ').replace("'", " ").split()
        lowered = [str(token).casefold() for token in tokens]
        for index, token in enumerate(lowered):
            base = token.replace("\\", "/").rsplit("/", 1)[-1]
            rest = lowered[index + 1:]
            if base in {"vibe", "vibe.exe", "vibe.py"}:
                if rest[:2] in (
                    ["amendment", "apply"], ["governance", "approve-staged"],
                    ["hooks", "uninstall"], ["mode", "set"], ["decision", "approve"],
                    ["phase", "start"],
                ):
                    return True
            if base in {"python", "python3", "py", "python.exe", "python3.exe"}:
                for j, item in enumerate(rest[:-1]):
                    if item == "-m" and rest[j + 1] == "vibe":
                        if rest[j + 2:j + 4] in (
                            ["amendment", "apply"], ["governance", "approve-staged"],
                            ["hooks", "uninstall"], ["mode", "set"], ["decision", "approve"],
                            ["phase", "start"],
                        ):
                            return True
    return False

def decide(payload: Any, root: str | Path) -> Dict[str, str]:
    active, readable = active_state(root)
    if not active:
        return {"decision": "allow", "reason": "not a Vibe-governed project"}
    if not readable:
        return {"decision": "deny", "reason": "Vibe state is unreadable; governance write checks fail closed"}
    if not isinstance(payload, dict):
        return {"decision": "deny", "reason": "malformed hook payload in a Vibe-governed project"}
    if payload.get("hook_event_name", payload.get("event_name", "PreToolUse")) != "PreToolUse":
        return {"decision": "allow", "reason": "not a PreToolUse event"}
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool, str) or not tool:
        return {"decision": "deny", "reason": "PreToolUse payload has no valid tool_name"}
    if tool in {"Bash", "PowerShell"}:
        if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
            return {"decision": "deny", "reason": "shell tool payload has no inspectable command; governance checks fail closed"}
        command = tool_input.get("command", "")
        if is_human_only_command(command, str(tool)):
            return {"decision": "deny", "reason": "human approval and hook maintenance commands must be run directly by a human outside the agent session"}
        return {"decision": "allow", "reason": "shell command is outside the protected-write decision surface"}
    if tool not in {"Write", "Edit", "NotebookEdit"}:
        return {"decision": "allow", "reason": "tool is outside the file-write policy"}
    if not isinstance(tool_input, dict):
        return {"decision": "deny", "reason": "write request has malformed tool_input"}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str) or not target.strip():
        return {"decision": "deny", "reason": "write request has no inspectable target path"}
    try:
        relative = normalize_relative_path(root, target)
        policy = load_policy(root)
        protected = is_protected(relative, policy)
    except GuardPathError as exc:
        return {"decision": "deny", "reason": str(exc)}
    if protected:
        return {
            "decision": "deny",
            "reason": relative + " is protected; submit a non-authoritative phase amendment proposal for human review",
        }
    # Agent role is deliberately ignored for governance writes: subagents have no bypass.
    return {"decision": "allow", "reason": "target is not a protected governance file"}
