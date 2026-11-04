from __future__ import annotations

import base64
import io
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / ".bootstrap"
PARTS = [PAYLOAD / f"phase29-final.part-{number:02d}" for number in range(1, 5)]
PREFIX = "vibe-kit_3.0"
EXPECTED_FILES = 36


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    missing = [part.name for part in PARTS if not part.is_file()]
    if missing:
        raise SystemExit("Missing Phase 29 payload parts: " + ", ".join(missing))

    encoded = "".join(part.read_text(encoding="ascii").strip() for part in PARTS)
    compressed = base64.b64decode(encoded, validate=True)

    with tarfile.open(fileobj=io.BytesIO(compressed), mode="r:xz") as archive:
        members = archive.getmembers()
        files = [member for member in members if member.isfile()]
        if len(files) != EXPECTED_FILES:
            raise SystemExit(f"Expected {EXPECTED_FILES} regular source files, found {len(files)}")

        seen: set[str] = set()
        for member in members:
            source_path = PurePosixPath(member.name)
            if (
                source_path.is_absolute()
                or ".." in source_path.parts
                or not source_path.parts
                or source_path.parts[0] != PREFIX
            ):
                raise SystemExit(f"Rejected unsafe archive path: {member.name}")
            if not member.isfile():
                if member.isdir():
                    continue
                raise SystemExit(f"Rejected non-regular archive entry: {member.name}")

            relative_parts = source_path.parts[1:]
            if not relative_parts:
                raise SystemExit("Archive contains a file at its root prefix")
            relative = Path(*relative_parts)
            normalized = relative.as_posix()
            if normalized in seen:
                raise SystemExit(f"Duplicate archive path: {normalized}")
            seen.add(normalized)

            if normalized.startswith(".github/workflows/"):
                raise SystemExit("Phase 29 archive must not replace protected CI workflows")

            destination = (ROOT / relative).resolve()
            if ROOT.resolve() not in destination.parents:
                raise SystemExit(f"Rejected destination outside repository: {normalized}")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise SystemExit(f"Could not read archive entry: {normalized}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(extracted.read())
            destination.chmod(member.mode & 0o777)

    shutil.rmtree(PAYLOAD)
    (ROOT / "scripts" / "bootstrap_phase29.py").unlink(missing_ok=True)

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "-A")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        raise SystemExit("Phase 29 import produced no changes")

    run("git", "commit", "-m", "feat(phase-29): add governance and phase-contract integrity")
    run("git", "push", "origin", "HEAD:refs/heads/phase/29-governance-integrity")


if __name__ == "__main__":
    main()
