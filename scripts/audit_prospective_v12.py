"""Verify the immutable chain for the prospective v12 first-pass evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SEAL = ROOT / "data/benchmarks/real-architecture/prospective-v12-seal.json"
RESULT_SEAL = ROOT / "data/results/end-to-end-prospective-v12/result-seal.json"
PROVENANCE_ERRATUM = ROOT / "data/benchmarks/real-architecture/prospective-v12-provenance-erratum.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    benchmark_seal = json.loads(BENCHMARK_SEAL.read_text(encoding="utf-8"))
    result_seal = json.loads(RESULT_SEAL.read_text(encoding="utf-8"))
    benchmark_path = ROOT / benchmark_seal["benchmark"]
    result_path = ROOT / result_seal["result"]
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    provenance = json.loads(PROVENANCE_ERRATUM.read_text(encoding="utf-8"))
    checks = {
        "benchmarkHash": sha256(benchmark_path) == benchmark_seal["benchmarkSha256"],
        "detectorHash": sha256(ROOT / benchmark_seal["detector"]) == benchmark_seal["detectorSha256"],
        "resultHash": sha256(result_path) == result_seal["resultSha256"],
        "sealAgreement": (
            result_seal["benchmarkSha256"] == benchmark_seal["benchmarkSha256"]
            and result_seal["detectorSha256"] == benchmark_seal["detectorSha256"]
        ),
        "imageHashes": all(
            sha256(ROOT / entry["image"]) == entry["imageSha256"]
            for entry in benchmark["entries"]
        ),
        "firstPass": result_seal.get("firstPass") is True,
        "provenanceDeclared": provenance["benchmarkSha256"] == benchmark_seal["benchmarkSha256"],
    }
    payload = {"status": "passed" if all(checks.values()) else "failed", "checks": checks}
    print(json.dumps(payload, indent=2))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
