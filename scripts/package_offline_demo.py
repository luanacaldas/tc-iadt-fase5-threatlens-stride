"""Build and export a self-contained Docker image for an offline demonstration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    print(f"[offline] {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def find_docker() -> str:
    discovered = shutil.which("docker")
    if discovered:
        return discovered

    candidates = []
    if local_app_data := os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(local_app_data) / "Programs/Docker/Docker/resources/bin/docker.exe")
        candidates.append(Path(local_app_data) / "Programs/DockerDesktop/resources/bin/docker.exe")
    if program_files := os.environ.get("ProgramFiles"):
        candidates.append(Path(program_files) / "Docker/Docker/resources/bin/docker.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("Docker Desktop was not found. Install it and restart Windows before packaging.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="Export an image already built locally")
    parser.add_argument("--image", default="threatlens-ai:offline")
    parser.add_argument("--output", type=Path, default=Path("artifacts/offline/threatlens-ai-offline.tar"))
    args = parser.parse_args()

    docker = find_docker()
    if not args.skip_build:
        run([docker, "compose", "build"])

    run([docker, "image", "inspect", args.image])

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    run([docker, "save", "--output", str(output), args.image])
    metadata = {
        "schemaVersion": "1.0",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "image": args.image,
        "archive": str(args.output).replace("\\", "/"),
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
        "loadCommand": f"docker load --input {output.name}",
        "runCommand": "docker run --rm -p 4173:4173 threatlens-ai:offline",
        "remoteCallsRequired": False,
        "offlineVerification": {
            "healthEndpoint": "http://127.0.0.1:4173/api/ready",
            "expectedStatus": 200,
            "networkRequiredAfterImageLoad": False,
        },
    }
    manifest = output.with_suffix(".json")
    manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"[offline] archive: {output}")
    print(f"[offline] manifest: {manifest}")


if __name__ == "__main__":
    main()
