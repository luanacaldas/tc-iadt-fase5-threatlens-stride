"""Promote a quality-gated ThreatLens model into the backend model registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EVALUATION = Path("data/results/threatlens-model-evaluation/evaluation-summary.json")
DEFAULT_SOURCE_COMPARISON = Path(
    "data/results/threatlens-hybrid-v2-source-slices/source-comparison.json"
)
DEFAULT_TARGET = Path("models/threatlens-hybrid-v2/weights/best.pt")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_gate(
    comparison: dict[str, Any],
    required_source: str = "kaggle_unique",
    minimum_map50: float = 0.25,
    minimum_recall: float = 0.20,
) -> dict[str, Any]:
    source = next(
        (item for item in comparison.get("sources", []) if item.get("source") == required_source),
        None,
    )
    aggregate = source.get("aggregate", {}) if source else {}
    checks = [
        {
            "name": f"source_present:{required_source}",
            "value": 1.0 if source else 0.0,
            "minimum": 1.0,
            "passed": source is not None,
        },
        {
            "name": f"source_mAP50:{required_source}",
            "value": float(aggregate.get("map50", 0.0)),
            "minimum": minimum_map50,
            "passed": float(aggregate.get("map50", 0.0)) >= minimum_map50,
        },
        {
            "name": f"source_recall:{required_source}",
            "value": float(aggregate.get("recall", 0.0)),
            "minimum": minimum_recall,
            "passed": float(aggregate.get("recall", 0.0)) >= minimum_recall,
        },
    ]
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def register_model(
    evaluation_path: Path,
    target_path: Path,
    allow_unqualified: bool = False,
    source_comparison_path: Path | None = None,
    required_source: str = "kaggle_unique",
    minimum_source_map50: float = 0.25,
    minimum_source_recall: float = 0.20,
) -> dict[str, Any]:
    evaluation_path = evaluation_path.resolve()
    target_path = target_path.resolve()
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    if not evaluation.get("qualityGate", {}).get("passed") and not allow_unqualified:
        raise RuntimeError("Quality gate failed; model was not promoted.")

    source_path = Path(evaluation["model"]["path"])
    if not source_path.exists():
        raise RuntimeError(f"Evaluated model not found: {source_path}")
    source_hash = _sha256(source_path)
    if source_hash != evaluation["model"]["sha256"]:
        raise RuntimeError("Model hash differs from the evaluated artifact.")

    source_gate = None
    if source_comparison_path is not None:
        source_comparison_path = source_comparison_path.resolve()
        comparison = json.loads(source_comparison_path.read_text(encoding="utf-8"))
        if comparison.get("model", {}).get("sha256") != source_hash:
            raise RuntimeError("Source comparison was produced by a different model artifact.")
        source_gate = build_source_gate(
            comparison,
            required_source,
            minimum_source_map50,
            minimum_source_recall,
        )
        if not source_gate["passed"] and not allow_unqualified:
            raise RuntimeError("Source quality gate failed; model was not promoted.")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    target_hash = _sha256(target_path)
    if target_hash != source_hash:
        raise RuntimeError("Promoted model failed hash verification.")

    fully_qualified = evaluation["qualityGate"]["passed"] and (
        source_gate is None or source_gate["passed"]
    )
    card = {
        "schemaVersion": "1.0",
        "registeredAt": datetime.now(timezone.utc).isoformat(),
        "status": "qualified" if fully_qualified else "experimental",
        "modelPath": str(target_path),
        "sha256": target_hash,
        "sourceEvaluation": str(evaluation_path),
        "dataset": evaluation["dataset"],
        "settings": evaluation["settings"],
        "aggregate": evaluation["aggregate"],
        "qualityGate": evaluation["qualityGate"],
        "sourceComparison": str(source_comparison_path) if source_comparison_path else None,
        "sourceQualityGate": source_gate,
    }
    card_path = target_path.parent.parent / "model-card.json"
    card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return card


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a quality-gated ThreatLens model")
    parser.add_argument("--evaluation", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--source-comparison", type=Path, default=DEFAULT_SOURCE_COMPARISON)
    parser.add_argument("--skip-source-gate", action="store_true")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--required-source", default="kaggle_unique")
    parser.add_argument("--minimum-source-map50", type=float, default=0.25)
    parser.add_argument("--minimum-source-recall", type=float, default=0.20)
    parser.add_argument("--allow-unqualified", action="store_true")
    args = parser.parse_args()
    try:
        card = register_model(
            args.evaluation,
            args.target,
            args.allow_unqualified,
            None if args.skip_source_gate else args.source_comparison,
            args.required_source,
            args.minimum_source_map50,
            args.minimum_source_recall,
        )
    except Exception as exc:
        raise SystemExit(f"Registration failed: {exc}") from exc
    print(json.dumps(card, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
