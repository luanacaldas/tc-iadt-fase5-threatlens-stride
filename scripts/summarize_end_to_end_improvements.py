"""Summarize end-to-end revisions without conflating sealed and post-hoc evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/end-to-end-improvement-comparison.json"

SOURCES = {
    "sealedHistorical": "data/results/end-to-end/end-to-end-blind_holdout-initial.json",
    "legacyPosthoc": "data/results/end-to-end-posthoc/end-to-end-blind_holdout.json",
    "currentDevelopment": "data/results/ocr-geometry-ablation/stacked-labels-v7/end-to-end-development_tuning.json",
    "developmentV12": "data/results/ocr-geometry-ablation/resolution-aware-v12/end-to-end-development_tuning.json",
    "developmentV13": "data/results/ocr-geometry-ablation/semantic-abstention-v13/end-to-end-development_tuning.json",
    "developmentV15": "data/results/ocr-geometry-ablation/semantic-arbitration-v15/end-to-end-development_tuning.json",
    "prospectiveV12": "data/results/end-to-end-prospective-v12/end-to-end-prospective_holdout.json",
    "posthocV12": "data/results/end-to-end-posthoc-v5-resolution-aware/end-to-end-blind_holdout.json",
    "prospectiveV13Posthoc": "data/results/end-to-end-prospective-v13-posthoc/end-to-end-prospective_holdout.json",
    "posthocV13": "data/results/end-to-end-posthoc-v6-semantic-abstention/end-to-end-blind_holdout.json",
    "currentOriginalAnnotations": "data/results/end-to-end-posthoc-v3/end-to-end-blind_holdout.json",
    "currentCorrectedAnnotations": (
        "data/results/end-to-end-posthoc-v4-corrected-annotations/end-to-end-blind_holdout.json"
    ),
}


def read_result(relative: str) -> dict:
    payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    aggregate = payload["aggregate"]
    return {
        "source": relative,
        "schemaVersion": payload["schemaVersion"],
        "split": payload["split"],
        "protocol": payload["evaluationProtocol"],
        "evaluatedAt": payload["evaluatedAt"],
        "imageCount": payload["imageCount"],
        "precision": aggregate["precision"],
        "recall": aggregate["recall"],
        "f1": aggregate["f1"],
        "meanComponentTypedRecall": aggregate["meanComponentTypedRecall"],
        "correctThreats": aggregate["correct"],
        "expectedThreats": aggregate["expected"],
    }


def main() -> None:
    results = {name: read_result(path) for name, path in SOURCES.items()}
    current_original = results["currentOriginalAnnotations"]
    current_corrected = results["currentCorrectedAnnotations"]
    payload = {
        "schemaVersion": "1.0",
        "generatedAt": max(result["evaluatedAt"] for result in results.values()),
        "results": results,
        "sameDetectorAnnotationCorrection": {
            "f1Before": current_original["f1"],
            "f1After": current_corrected["f1"],
            "absoluteGain": current_corrected["f1"] - current_original["f1"],
        },
        "interpretation": [
            "sealedHistorical is immutable and remains the only truly blind result.",
            "legacyPosthoc used the original provider-unaware scoring contract.",
            "currentDevelopment guided implementation and is not holdout evidence.",
            "developmentV12 guided the final localization and replica-grouping composition and is not holdout evidence.",
            "developmentV13 adds auditable semantic abstention and is not holdout evidence.",
            "developmentV15 arbitrates shared semantic anchors and nearby conflicting hypotheses; it is not holdout evidence.",
            "prospectiveV12 was sealed with benchmark, image, and detector hashes before its first inference.",
            "posthocV12 is a diagnostic replay on the previously opened corrected benchmark and is not blind evidence.",
            "prospectiveV13Posthoc and posthocV13 are diagnostic replays performed after their benchmarks were opened.",
            "currentOriginalAnnotations and currentCorrectedAnnotations use the same detector and provider-aware scoring contract.",
            "The corrected FIAP benchmark is explicitly post-hoc and must not be described as blind.",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Improvement comparison written to {OUTPUT}")


if __name__ == "__main__":
    main()
