from __future__ import annotations

import base64
import io
import lzma
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_DIR = ROOT / ".bootstrap"
PARTS = sorted(PAYLOAD_DIR.glob("payload.part-*"))
PREFIX = "vibe-kit_3.0"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    if len(PARTS) != 5:
        raise SystemExit(f"Expected 5 payload parts, found {len(PARTS)}")

    encoded = "".join(part.read_text(encoding="ascii").strip() for part in PARTS)
    compressed = base64.b64decode(encoded, validate=True)
    archive = lzma.decompress(compressed)

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tf:
        members = tf.getmembers()
        if not members:
            raise SystemExit("The source archive is empty")

        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not name.parts or name.parts[0] != PREFIX:
                raise SystemExit(f"Unsafe archive path: {member.name}")
            if member.isdir():
                continue
            if not member.isfile():
                raise SystemExit(f"Unsupported archive entry: {member.name}")

            relative = Path(*name.parts[1:])
            if not relative.parts:
                continue
            # Workflow files require a separate GitHub App workflow permission.
            if relative.as_posix().startswith(".github/workflows/"):
                continue
            destination = ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = tf.extractfile(member)
            if source is None:
                raise SystemExit(f"Could not read archive entry: {member.name}")
            destination.write_bytes(source.read())

    shutil.rmtree(PAYLOAD_DIR)
    (ROOT / "scripts" / "bootstrap_import.py").unlink(missing_ok=True)

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "-A")
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True)
    if not status.stdout.strip():
        raise SystemExit("Import produced no repository changes")
    run("git", "commit", "-m", "chore: import independent Vibe Kit 3.0 V3 foundation")
    run("git", "push", "origin", "HEAD:refs/heads/phase/28-v3-foundation")


if __name__ == "__main__":
    main()
