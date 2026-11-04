"""V3 governance defaults, path canonicalization, and phase-contract checks.

The plugin guard is intentionally standalone, so its policy projection is checked
against DEFAULT_POLICY by tests/test_phase29.py. The JSON template is the project
onboarding projection of these same defaults.
"""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = 1
PHASE_SOURCE_RE = re.compile(r"^docs/phases/phase-[0-9]{2}\.md$", re.IGNORECASE)
GENERATED_PHASE_SUFFIXES = (".context.md", ".repair.md")
GENERATED_PHASE_RE = re.compile(r"^docs/phases/phase-[0-9]{2}\.(?:context|repair)\.md$", re.IGNORECASE)

DEFAULT_POLICY: dict[str, Any] = {
    "schema": SCHEMA,
    "protected_paths": [
        "docs/state.json",
        "docs/invariants.md",
        "docs/decisions.md",
        "docs/governance.json",
        "docs/contracts/**",
        "docs/approvals/**",
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
    "generated_phase_suffixes": list(GENERATED_PHASE_SUFFIXES),
    "proposal_directory": "docs/proposals",
    "amendment_archive_directory": "docs/amendments",
    "approval_directory": "docs/approvals",
}


class GovernanceError(ValueError):
    """Raised for invalid governance configuration or unsafe paths."""


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def normalize_relative_path(root: str | Path, target: str | Path) -> str:
    """Return a case-folded, POSIX, repository-relative path.

    Traversal is rejected before normalization. Native absolute paths are resolved
    through symlinks and must remain within the repository. Windows separators and
    case are normalized on every platform; drive-qualified paths are accepted only
    when they share the repository's native drive/root.
    """
    root_path = Path(root).resolve(strict=True)
    raw = str(target).strip().replace("\\", "/")
    if not raw or "\x00" in raw:
        raise GovernanceError("target path is empty or invalid")

    # Reject traversal explicitly, including forms such as a/../b that would
    # otherwise normalize back inside the repository.
    if any(part == ".." for part in raw.split("/")):
        raise GovernanceError("path traversal is not allowed")

    drive_match = re.match(r"^([A-Za-z]):/(.*)$", raw)
    if drive_match:
        root_text = str(root_path).replace("\\", "/")
        root_drive = re.match(r"^([A-Za-z]):/(.*)$", root_text)
        if not root_drive or root_drive.group(1).casefold() != drive_match.group(1).casefold():
            raise GovernanceError("target path is outside the repository")
        root_prefix = root_text.rstrip("/")
        target_text = raw.rstrip("/")
        if target_text.casefold() == root_prefix.casefold():
            relative = ""
        elif target_text.casefold().startswith(root_prefix.casefold() + "/"):
            relative = target_text[len(root_prefix) + 1 :]
        else:
            raise GovernanceError("target path is outside the repository")
        return relative.replace("\\", "/").casefold()

    candidate_text = raw
    if raw.startswith("/"):
        candidate = Path(candidate_text)
    else:
        candidate = root_path.joinpath(*[part for part in raw.split("/") if part not in ("", ".")])

    resolved = candidate.resolve(strict=False)
    if not _inside(resolved, root_path):
        raise GovernanceError("target path resolves outside the repository")
    relative = resolved.relative_to(root_path).as_posix()
    if relative in ("", "."):
        raise GovernanceError("repository root is not a file target")
    return relative.casefold()


def is_phase_source(relative_path: str) -> bool:
    """True only for phase source contracts, never generated context/repair files."""
    normalized = str(relative_path).replace("\\", "/").strip("/").casefold()
    if normalized.endswith(GENERATED_PHASE_SUFFIXES):
        return False
    return bool(PHASE_SOURCE_RE.fullmatch(normalized))


def is_protected_path(relative_path: str, policy: dict[str, Any] | None = None) -> bool:
    """Check canonical protected globs plus phase source contracts."""
    policy = DEFAULT_POLICY if policy is None else policy
    normalized = str(relative_path).replace("\\", "/").strip("/").casefold()
    if GENERATED_PHASE_RE.fullmatch(normalized):
        return False
    if is_phase_source(normalized):
        return True
    patterns = policy.get("protected_paths", [])
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        raise GovernanceError("protected_paths must be a list of strings")
    return any(fnmatch.fnmatchcase(normalized, str(pattern).replace("\\", "/").casefold()) for pattern in patterns)


def load_policy(root: str | Path = ".") -> dict[str, Any]:
    """Load project policy or canonical defaults; malformed active policy fails closed."""
    root = Path(root).resolve()
    policy_path = root / "docs" / "governance.json"
    if not policy_path.exists():
        return dict(DEFAULT_POLICY)
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GovernanceError("docs/governance.json is unreadable or invalid JSON") from exc
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        raise GovernanceError("docs/governance.json has an unsupported schema")
    result = dict(DEFAULT_POLICY)
    result.update(raw)
    configured = result.get("protected_paths")
    if not isinstance(configured, list) or not all(
        isinstance(x, str) and x.strip() for x in configured
    ):
        raise GovernanceError("docs/governance.json protected_paths must be non-empty strings")
    # Project policy may add protections, but may not remove V3's baseline guardrails.
    merged = list(DEFAULT_POLICY["protected_paths"])
    for item in configured:
        if item not in merged:
            merged.append(item)
    result["protected_paths"] = merged
    return result


def is_vibe_project(root: str | Path) -> bool:
    """A repository is governed when its state file exists, even if it is corrupt."""
    return (Path(root) / "docs" / "state.json").exists()


def check_unresolved_proposals(root: str | Path = ".") -> list[Path]:
    """Return all unresolved phase amendment proposals in stable order."""
    root = Path(root)
    directory = root / DEFAULT_POLICY["proposal_directory"]
    if not directory.is_dir():
        return []
    # Every artifact in the proposal directory is non-authoritative and unresolved
    # until a human explicitly applies/archives it. README.md is explanatory only.
    return sorted(
        p for p in directory.rglob("*")
        if p.is_file() and p.name.casefold() != "readme.md"
    )


def check_governance(root: str | Path = ".") -> tuple[bool, str | None]:
    """Validate policy and block while an amendment proposal remains unresolved."""
    root = Path(root).resolve()
    if not is_vibe_project(root):
        return True, None
    try:
        load_policy(root)
    except GovernanceError as exc:
        return False, str(exc)
    proposals = check_unresolved_proposals(root)
    if proposals:
        rel = proposals[0].relative_to(root).as_posix()
        return False, f"unresolved amendment proposal {rel}; human approval is required"
    return True, None


def evaluate_write(root: str | Path, target: str | None, tool_name: str,
                   *, payload_valid: bool = True, agent_role: str = "main") -> dict[str, str]:
    """Neutral policy decision for a file-writing tool request.

    `agent_role` is informational only: subagents receive no governance write
    exemption. Non-Vibe projects are intentionally untouched.
    """
    root = Path(root).resolve()
    if not is_vibe_project(root):
        return {"decision": "allow", "reason": "not a Vibe-governed project"}
    if not payload_valid:
        return {"decision": "deny", "reason": "malformed hook payload in a Vibe-governed project"}
    if tool_name not in {"Write", "Edit", "NotebookEdit"}:
        return {"decision": "allow", "reason": "tool is outside the file-write policy"}
    if not isinstance(target, str) or not target.strip():
        return {"decision": "deny", "reason": "write request has no inspectable target path"}
    try:
        relative = normalize_relative_path(root, target)
        policy = load_policy(root)
    except GovernanceError as exc:
        return {"decision": "deny", "reason": str(exc)}
    if is_protected_path(relative, policy):
        return {
            "decision": "deny",
            "reason": f"{relative} is a protected governance or phase-contract file; submit a non-authoritative amendment proposal for human review",
        }
    return {"decision": "allow", "reason": "target is not a protected governance file"}
