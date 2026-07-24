"""Create a post-hoc benchmark revision with visually corrected FIAP AWS boxes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"
OUTPUT = ROOT / "data/benchmarks/real-architecture/benchmark-fiap-corrected-v3.json"
CORRECTED_AT = "2026-07-20T22:30:57.103410+00:00"

FIAP_AWS_BOXES = {
    "users": [0.065, 0.05, 0.14, 0.14],
    "shield": [0.305, 0.045, 0.385, 0.145],
    "cloudfront": [0.415, 0.045, 0.495, 0.145],
    "waf": [0.55, 0.045, 0.63, 0.145],
    "alb_a": [0.13, 0.34, 0.24, 0.48],
    "alb_b": [0.385, 0.34, 0.495, 0.48],
    "alb_c": [0.64, 0.34, 0.75, 0.48],
    "compute_a": [0.115, 0.55, 0.22, 0.69],
    "compute_b": [0.37, 0.55, 0.48, 0.69],
    "compute_c": [0.63, 0.55, 0.74, 0.69],
    "storage": [0.08, 0.76, 0.185, 0.91],
    "database": [0.18, 0.76, 0.28, 0.91],
    "cache": [0.44, 0.76, 0.55, 0.91],
    "cloudtrail": [0.82, 0.22, 0.94, 0.34],
    "kms": [0.82, 0.35, 0.94, 0.47],
    "backup": [0.82, 0.50, 0.94, 0.67],
    "cloudwatch": [0.82, 0.63, 0.94, 0.77],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    benchmark = json.loads(SOURCE.read_text(encoding="utf-8"))
    entry = next(item for item in benchmark["entries"] if item["id"] == "fiap-aws-multiaz")
    component_ids = {component["id"] for component in entry["components"]}
    if component_ids != set(FIAP_AWS_BOXES):
        raise RuntimeError("FIAP AWS component contract changed; review corrections manually")
    for component in entry["components"]:
        component["bboxNormalized"] = FIAP_AWS_BOXES[component["id"]]
    entry["annotationStatus"] = "human_verified_posthoc_correction"
    entry["annotationMethod"] = (
        "Manual visual realignment against the 886x778 source image after the sealed evaluation "
        "revealed systematic coordinate drift."
    )
    benchmark.update({
        "schemaVersion": "3.0",
        "builtAt": CORRECTED_AT,
        "evaluationStatus": "posthoc_corrected_annotations_not_blind",
        "parentBenchmark": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "parentBenchmarkSha256": sha256(SOURCE),
        "corrections": [{
            "entryId": "fiap-aws-multiaz",
            "field": "components[].bboxNormalized",
            "reason": "Original normalized boxes were systematically misaligned with visible nodes.",
        }],
    })
    return benchmark


def main() -> None:
    OUTPUT.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(f"Corrected benchmark written to {OUTPUT}")


if __name__ == "__main__":
    main()
