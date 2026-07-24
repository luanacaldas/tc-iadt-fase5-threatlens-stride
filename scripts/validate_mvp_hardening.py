"""Validate MVP-HARDENING-001 against one explicitly supplied local image."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import detector  # noqa: E402
from backend.analysis_quality import assess_analysis_quality  # noqa: E402


DEFAULT_OUTPUT = ROOT / "data/results/mvp-hardening-001/external-image-quality.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(image_path: Path) -> dict:
    architecture = detector.detect(image_path)
    if not architecture:
        raise RuntimeError("The supervised detector did not return an architecture.")
    sanitized, quality = assess_analysis_quality(architecture)
    return {
        "schemaVersion": 1,
        "task": "MVP-HARDENING-001",
        "scope": {
            "retrainedModel": False,
            "datasetAdjusted": False,
            "holdoutsExecuted": [],
            "flowStrategyChanged": False,
        },
        "input": {
            "fileName": image_path.name,
            "sha256": _sha256(image_path),
        },
        "observed": {
            "inputComponentCount": len(architecture.get("components") or []),
            "inputFlowCount": len(architecture.get("flows") or []),
            "outputFlowCount": len(sanitized.get("flows") or []),
            "blockedFlowIds": quality["blockedFlowIds"],
        },
        "analysisQuality": quality,
        "safetyDecision": {
            "threatGenerationAllowed": quality["status"] != "rejected",
            "riskCalculationAllowed": quality["status"] != "rejected",
            "reportGenerationAllowed": quality["status"] != "rejected",
        },
        "checks": {
            "multipleDiagramSignal": any(
                reason["code"] == "multiple_diagrams_suspected" for reason in quality["reasons"]
            ),
            "unconfirmedSelfLoopBlocked": any(
                reason["code"] == "semantic_self_loop_blocked" for reason in quality["reasons"]
            ),
            "providerInconsistencyDetected": any(
                reason["code"] == "provider_inconsistency" for reason in quality["reasons"]
            ),
            "invalidReportSuppressed": quality["status"] == "rejected",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.image.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["analysisQuality"]["status"], "output": str(args.output)}))
    return 0 if result["analysisQuality"]["status"] == "rejected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
