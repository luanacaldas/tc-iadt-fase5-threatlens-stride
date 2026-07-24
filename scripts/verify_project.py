"""One-command project verification for local and offline demonstrations."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    print(f"[verify] {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def verify_hashes(
    manifest_path: Path | None = None,
    root: Path = ROOT,
) -> None:
    manifest_path = manifest_path or root / "data/manifests/reproducibility.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = []
    for relative, expected in manifest["files"].items():
        if expected is None:
            continue
        path = root / relative
        actual = sha256(path) if path.is_file() else None
        actual_bytes = path.stat().st_size if path.is_file() else None
        if actual != expected["sha256"] or actual_bytes != expected.get("bytes"):
            mismatches.append(relative)
    if mismatches:
        raise RuntimeError(f"Reproducibility hash mismatch: {', '.join(mismatches)}")
    print(f"[verify] {len(manifest['files'])} tracked artifacts verified")


def verify_locked_dependencies() -> None:
    lock_path = ROOT / "backend/requirements-lock.txt"
    mismatches = []
    checked = 0
    for raw_line in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        package, expected = line.split("==", 1)
        distribution = package.split("[", 1)[0]
        try:
            actual = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        checked += 1
        if actual != expected:
            mismatches.append(f"{distribution}: expected {expected}, found {actual}")
    if mismatches:
        raise RuntimeError("Locked dependency mismatch: " + "; ".join(mismatches))
    print(f"[verify] {checked} locked runtime dependencies verified")


def verify_offline_image_contract() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    required = (
        "backend/requirements-lock.txt",
        "HF_HUB_OFFLINE=1",
        "TRANSFORMERS_OFFLINE=1",
        "/api/health",
        "rag.initialize_rag()",
        'org.opencontainers.image.version="1.0.0-mvp"',
    )
    missing = [item for item in required if item not in dockerfile]
    if missing:
        raise RuntimeError("Offline image contract is incomplete: " + ", ".join(missing))
    print("[verify] offline image contract verified")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Also execute real and sealed end-to-end benchmarks")
    args = parser.parse_args()
    verify_hashes()
    verify_locked_dependencies()
    verify_offline_image_contract()
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([sys.executable, "scripts/evaluate_stride_golden_set.py"])
    run([sys.executable, "scripts/audit_real_benchmark_integrity.py"])
    run([sys.executable, "scripts/audit_prospective_v12.py"])
    run(["node", "--check", "app/main.js"])
    run(["node", "--check", "app/ui-contract.mjs"])
    run(["node", "--test", "tests/test_web_mvp.mjs"])
    if args.full:
        run([sys.executable, "scripts/evaluate_real_architecture_benchmark.py"])
        run([
            sys.executable,
            "scripts/evaluate_blind_end_to_end.py",
            "--output",
            "data/results/verification",
            "--protocol",
            "reproducibility_replay_after_unsealing",
        ])
    print("[verify] PASS")


if __name__ == "__main__":
    main()
