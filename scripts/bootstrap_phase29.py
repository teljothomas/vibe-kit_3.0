from __future__ import annotations

import base64
import io
import lzma
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PARTS = [
    ROOT / ".bootstrap" / "phase29-final.part-01",
    ROOT / ".bootstrap" / "phase29-final.part-02",
]
PREFIX = "vibe-kit_3.0"
ALLOWED = {
    "vibe/governance.py",
    "vibe/approvals.py",
    "tests/phase29/test_amendments.py",
}


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    missing = [p.name for p in PARTS if not p.is_file()]
    if missing:
        raise SystemExit("Missing Phase 29 correction payload: " + ", ".join(missing))

    encoded = "".join(p.read_text(encoding="ascii").strip() for p in PARTS)
    archive_bytes = lzma.decompress(base64.b64decode(encoded, validate=True))
    seen: set[str] = set()

    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != PREFIX:
                raise SystemExit(f"Unsafe correction archive path: {member.name}")
            if member.isdir():
                continue
            if not member.isfile():
                raise SystemExit(f"Unsupported correction archive entry: {member.name}")
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            if relative not in ALLOWED or relative in seen:
                raise SystemExit(f"Unexpected or duplicate correction target: {relative}")
            seen.add(relative)
            destination = (ROOT / relative).resolve()
            if ROOT.resolve() not in destination.parents:
                raise SystemExit(f"Correction target escapes repository: {relative}")
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(f"Cannot read correction target: {relative}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read())

    if seen != ALLOWED:
        raise SystemExit(f"Correction payload incomplete: missing {sorted(ALLOWED - seen)}")

    shutil.rmtree(ROOT / ".bootstrap")
    (ROOT / "scripts" / "bootstrap_phase29.py").unlink(missing_ok=True)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "-A")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    )
    if not status.stdout.strip():
        raise SystemExit("Correction import produced no changes")
    run("git", "commit", "-m", "fix(phase-29): handle Windows paths and Git-normalized approvals")
    run("git", "push", "origin", "HEAD:refs/heads/phase/29-governance-integrity")


if __name__ == "__main__":
    main()
