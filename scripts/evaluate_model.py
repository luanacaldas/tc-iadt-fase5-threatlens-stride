"""Evaluate a trained YOLO detector and write auditable model evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ultralytics import YOLO


DEFAULT_MODEL = Path("models/threatlens-hybrid-v2/weights/best.pt")
DEFAULT_DATASET = Path("dataset/hybrid_v2/architecture.yaml")
DEFAULT_OUTPUT = Path("data/results/threatlens-model-evaluation")
CRITICAL_CLASSES = ("api_gateway", "compute", "database", "internet", "user")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_list(value: Any) -> list[float]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        value = [value]
    return [float(item) for item in value]


def _metric(results: Any, key: str) -> float:
    value = results.results_dict.get(key, 0.0)
    return float(value.item() if hasattr(value, "item") else value)


def build_quality_gate(
    aggregate: dict[str, float],
    per_class: list[dict[str, Any]],
    minimum_map50: float,
    minimum_recall: float,
    minimum_critical_ap50: float,
) -> dict[str, Any]:
    class_metrics = {item["name"]: item for item in per_class}
    checks = [
        {
            "name": "aggregate_mAP50",
            "value": aggregate["map50"],
            "minimum": minimum_map50,
            "passed": aggregate["map50"] >= minimum_map50,
        },
        {
            "name": "aggregate_recall",
            "value": aggregate["recall"],
            "minimum": minimum_recall,
            "passed": aggregate["recall"] >= minimum_recall,
        },
    ]
    for class_name in CRITICAL_CLASSES:
        metric = class_metrics.get(class_name)
        value = float(metric["map50"]) if metric else 0.0
        checks.append(
            {
                "name": f"critical_class_ap50:{class_name}",
                "value": value,
                "minimum": minimum_critical_ap50,
                "passed": value >= minimum_critical_ap50,
            }
        )
    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def evaluate_model(
    model_path: Path,
    dataset_yaml: Path,
    output_dir: Path,
    split: str,
    device: str,
    imgsz: int,
    batch: int,
    minimum_map50: float,
    minimum_recall: float,
    minimum_critical_ap50: float,
) -> dict[str, Any]:
    model_path = model_path.resolve()
    dataset_yaml = dataset_yaml.resolve()
    output_dir = output_dir.resolve()
    if not model_path.exists():
        raise RuntimeError(f"Model not found: {model_path}")
    if not dataset_yaml.exists():
        raise RuntimeError(f"Dataset YAML not found: {dataset_yaml}")

    output_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(model_path))
    results = model.val(
        data=str(dataset_yaml),
        split=split,
        device=device,
        imgsz=imgsz,
        batch=batch,
        plots=True,
        save_json=False,
        project=str(output_dir),
        name="plots",
        exist_ok=True,
    )

    aggregate = {
        "precision": _metric(results, "metrics/precision(B)"),
        "recall": _metric(results, "metrics/recall(B)"),
        "map50": _metric(results, "metrics/mAP50(B)"),
        "map50_95": _metric(results, "metrics/mAP50-95(B)"),
        "fitness": float(results.fitness),
    }

    box = results.box
    class_indices = [int(value) for value in _as_list(getattr(results, "ap_class_index", []))]
    precisions = _as_list(getattr(box, "p", []))
    recalls = _as_list(getattr(box, "r", []))
    ap50 = _as_list(getattr(box, "ap50", []))
    ap = _as_list(getattr(box, "ap", []))
    support = [int(value) for value in _as_list(getattr(box, "nt_per_class", []))]
    names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))

    per_class: list[dict[str, Any]] = []
    for position, class_index in enumerate(class_indices):
        per_class.append(
            {
                "index": class_index,
                "name": names.get(class_index, str(class_index)),
                "support": support[class_index] if class_index < len(support) else None,
                "precision": precisions[position] if position < len(precisions) else 0.0,
                "recall": recalls[position] if position < len(recalls) else 0.0,
                "map50": ap50[position] if position < len(ap50) else 0.0,
                "map50_95": ap[position] if position < len(ap) else 0.0,
            }
        )

    gate = build_quality_gate(
        aggregate,
        per_class,
        minimum_map50,
        minimum_recall,
        minimum_critical_ap50,
    )
    speed = {
        key: float(value)
        for key, value in getattr(results, "speed", {}).items()
        if isinstance(value, (int, float))
    }
    summary = {
        "schemaVersion": "1.0",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "model": {
            "path": str(model_path),
            "sha256": _sha256(model_path),
            "framework": "ultralytics",
            "classCount": len(names),
        },
        "dataset": {
            "yaml": str(dataset_yaml),
            "yamlSha256": _sha256(dataset_yaml),
            "split": split,
        },
        "settings": {
            "device": device,
            "imgsz": imgsz,
            "batch": batch,
        },
        "aggregate": aggregate,
        "perClass": per_class,
        "qualityGate": gate,
        "speedMillisecondsPerImage": speed,
        "plotsDirectory": str(Path(results.save_dir).resolve()),
    }
    (output_dir / "evaluation-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "evaluation-summary.md").write_text(
        _markdown_summary(summary),
        encoding="utf-8",
    )
    return summary


def _markdown_summary(summary: dict[str, Any]) -> str:
    aggregate = summary["aggregate"]
    lines = [
        "# ThreatLens Model Evaluation",
        "",
        f"- Model SHA-256: `{summary['model']['sha256']}`",
        f"- Dataset split: `{summary['dataset']['split']}`",
        f"- Quality gate: **{'PASS' if summary['qualityGate']['passed'] else 'FAIL'}**",
        f"- Precision: {aggregate['precision']:.4f}",
        f"- Recall: {aggregate['recall']:.4f}",
        f"- mAP50: {aggregate['map50']:.4f}",
        f"- mAP50-95: {aggregate['map50_95']:.4f}",
        "",
        "## Per-Class Metrics",
        "",
        "| Class | Support | Precision | Recall | AP50 | AP50-95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summary["perClass"]:
        lines.append(
            f"| {item['name']} | {item['support'] or 0} | {item['precision']:.4f} | "
            f"{item['recall']:.4f} | {item['map50']:.4f} | {item['map50_95']:.4f} |"
        )
    lines.extend(["", "## Quality Gate", ""])
    for check in summary["qualityGate"]["checks"]:
        lines.append(
            f"- {'PASS' if check['passed'] else 'FAIL'} `{check['name']}`: "
            f"{check['value']:.4f} (minimum {check['minimum']:.4f})"
        )
    lines.append("")
    return "\n".join(lines)


def run_inference(model_path: Path, image_path: Path, output_dir: Path, confidence: float) -> Path:
    model = YOLO(str(model_path))
    results = model.predict(
        source=str(image_path),
        conf=confidence,
        save=True,
        project=str(output_dir.resolve()),
        name="inference",
        exist_ok=True,
        verbose=False,
    )
    detections = len(results[0].boxes) if results and results[0].boxes is not None else 0
    print(f"Detections: {detections}")
    return Path(results[0].save_dir).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate and document a ThreatLens YOLO model")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--minimum-map50", type=float, default=0.25)
    parser.add_argument("--minimum-recall", type=float, default=0.25)
    parser.add_argument("--minimum-critical-ap50", type=float, default=0.10)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--confidence", type=float, default=0.35)
    args = parser.parse_args()

    try:
        if args.image:
            result_dir = run_inference(args.model, args.image, args.output_dir, args.confidence)
            print(f"Inference artifacts: {result_dir}")
            return
        summary = evaluate_model(
            args.model,
            args.data,
            args.output_dir,
            args.split,
            args.device,
            args.imgsz,
            args.batch,
            args.minimum_map50,
            args.minimum_recall,
            args.minimum_critical_ap50,
        )
    except Exception as exc:
        raise SystemExit(f"Evaluation failed: {exc}") from exc

    print(json.dumps(summary["aggregate"], indent=2))
    print(f"Quality gate: {'PASS' if summary['qualityGate']['passed'] else 'FAIL'}")
    print(f"Summary: {args.output_dir / 'evaluation-summary.json'}")


if __name__ == "__main__":
    main()
