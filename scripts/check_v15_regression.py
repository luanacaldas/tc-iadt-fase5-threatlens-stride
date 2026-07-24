"""Fail-closed regression gate for the v15 development baseline."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASELINE_RESULT = ROOT / "data/results/ocr-geometry-ablation/semantic-arbitration-v15/end-to-end-development_tuning.json"
BASELINE_RESULT_SHA256 = "2f4ba6719cb2ca53ce3245c6df49354ca00533ac6aab6cca19c021da33111fe7"
BENCHMARK = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"
ACTIVE_LEARNING_MANIFEST = ROOT / "dataset/active_learning_real_v1/active-learning-manifest.json"
PROSPECTIVE_AUDIT_SCRIPT = ROOT / "scripts/audit_prospective_v12.py"
DEVELOPMENT_SPLIT = "development_tuning"
BASELINE_PROTOCOL = "development_semantic_arbitration_v15_not_blind"

THRESHOLDS = {
    "f1": 0.5296,
    "precision": 0.4343,
    "recall": 0.6786,
    "correctThreats": 152,
    "falsePositives": 198,
    "testsRun": 85,
    "testFailures": 0,
}

Dependency = Callable[..., dict[str, Any]]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def round_for_gate(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Gate metric must be numeric, received {value!r}")
    return round(float(value), 4)


def relative_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ValueError(f"Gate artifacts must remain inside the project: {resolved}") from exc


def load_baseline() -> dict[str, Any]:
    if sha256(BASELINE_RESULT) != BASELINE_RESULT_SHA256:
        raise RuntimeError("The immutable v15 baseline hash does not match the registered contract.")
    payload = json.loads(BASELINE_RESULT.read_text(encoding="utf-8"))
    if payload.get("split") != DEVELOPMENT_SPLIT:
        raise RuntimeError("The v15 baseline does not use development_tuning.")
    if payload.get("evaluationProtocol") != BASELINE_PROTOCOL:
        raise RuntimeError("The v15 baseline protocol is not the registered development protocol.")
    baseline_metrics = metric_view(payload.get("aggregate"))
    expected = {
        "f1Rounded": THRESHOLDS["f1"],
        "precisionRounded": THRESHOLDS["precision"],
        "recallRounded": THRESHOLDS["recall"],
        "correctThreats": THRESHOLDS["correctThreats"],
        "falsePositives": THRESHOLDS["falsePositives"],
    }
    for field, value in expected.items():
        if baseline_metrics[field] != value:
            raise RuntimeError(f"The v15 baseline metric {field} differs from the registered contract.")
    return payload


def metric_view(aggregate: Any) -> dict[str, Any]:
    if not isinstance(aggregate, dict):
        raise ValueError("Evaluation result has no aggregate metrics object.")
    required = ("f1", "precision", "recall", "correct", "extra", "expected", "predicted")
    missing = [name for name in required if name not in aggregate]
    if missing:
        raise ValueError("Evaluation aggregate is missing: " + ", ".join(missing))
    return {
        "f1": float(aggregate["f1"]),
        "f1Rounded": round_for_gate(aggregate["f1"]),
        "precision": float(aggregate["precision"]),
        "precisionRounded": round_for_gate(aggregate["precision"]),
        "recall": float(aggregate["recall"]),
        "recallRounded": round_for_gate(aggregate["recall"]),
        "correctThreats": int(aggregate["correct"]),
        "falsePositives": int(aggregate["extra"]),
        "expectedThreats": int(aggregate["expected"]),
        "predictedThreats": int(aggregate["predicted"]),
    }


def _check(name: str, actual: Any, operator: str, expected: Any, passed: bool) -> dict[str, Any]:
    return {
        "name": name,
        "actual": actual,
        "operator": operator,
        "expected": expected,
        "passed": bool(passed),
    }


def build_checks(
    candidate_metrics: dict[str, Any] | None,
    test_summary: dict[str, Any] | None,
    prospective_audit: dict[str, Any] | None,
    real_audit: dict[str, Any] | None,
    baseline_ok: bool,
    split: str | None,
) -> list[dict[str, Any]]:
    metrics = candidate_metrics or {}
    tests = test_summary or {}
    prospective_status = "PASS" if (prospective_audit or {}).get("status") == "passed" else "FAIL"
    real_status = "PASS" if (real_audit or {}).get("status") == "passed" else "FAIL"
    return [
        _check("baselineIntegrity", "PASS" if baseline_ok else "FAIL", "==", "PASS", baseline_ok),
        _check("evaluationSplit", split, "==", DEVELOPMENT_SPLIT, split == DEVELOPMENT_SPLIT),
        _check("f1", metrics.get("f1Rounded"), ">=", THRESHOLDS["f1"], metrics.get("f1Rounded", -1) >= THRESHOLDS["f1"]),
        _check("precision", metrics.get("precisionRounded"), ">=", THRESHOLDS["precision"], metrics.get("precisionRounded", -1) >= THRESHOLDS["precision"]),
        _check("recall", metrics.get("recallRounded"), ">=", THRESHOLDS["recall"], metrics.get("recallRounded", -1) >= THRESHOLDS["recall"]),
        _check("correctThreats", metrics.get("correctThreats"), ">=", THRESHOLDS["correctThreats"], metrics.get("correctThreats", -1) >= THRESHOLDS["correctThreats"]),
        _check("falsePositives", metrics.get("falsePositives"), "<=", THRESHOLDS["falsePositives"], metrics.get("falsePositives", sys.maxsize) <= THRESHOLDS["falsePositives"]),
        _check("testsRun", tests.get("testsRun"), ">=", THRESHOLDS["testsRun"], tests.get("testsRun", -1) >= THRESHOLDS["testsRun"]),
        _check("testFailures", tests.get("testFailures"), "==", THRESHOLDS["testFailures"], tests.get("testFailures", -1) == THRESHOLDS["testFailures"]),
        _check("prospectiveV12Integrity", prospective_status, "==", "PASS", prospective_status == "PASS"),
        _check("realBenchmarkIntegrity", real_status, "==", "PASS", real_status == "PASS"),
    ]


def run_tests() -> dict[str, Any]:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    failures = len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses)
    return {
        "testsRun": result.testsRun,
        "testFailures": failures,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "unexpectedSuccesses": len(result.unexpectedSuccesses),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
    }


def audit_prospective_v12() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(PROSPECTIVE_AUDIT_SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Prospective v12 audit did not return valid JSON.") from exc
    payload["returnCode"] = completed.returncode
    if completed.returncode != 0 or payload.get("status") != "passed":
        payload["status"] = "failed"
    return payload


def audit_real_benchmark() -> dict[str, Any]:
    from scripts.audit_real_benchmark_integrity import audit

    result = audit(BENCHMARK, ACTIVE_LEARNING_MANIFEST)
    result["benchmark"] = relative_path(BENCHMARK)
    return result


def evaluate_development(output_dir: Path) -> dict[str, Any]:
    from scripts.evaluate_blind_end_to_end import evaluate

    result = evaluate(
        BENCHMARK,
        output_dir,
        split=DEVELOPMENT_SPLIT,
        protocol="v15_regression_gate_development_not_blind",
    )
    result["benchmark"] = relative_path(BENCHMARK)
    write_report(result, output_dir / f"end-to-end-{DEVELOPMENT_SPLIT}.json")
    return result


def collect_provenance(execution_timestamp: str) -> dict[str, Any]:
    from backend.arrowhead_classifier import MODEL_PATH as ARROWHEAD_MODEL_PATH
    from backend.config import (
        YOLO_CALIBRATION_PATH,
        YOLO_CONFIDENCE_THRESHOLD,
        YOLO_MIN_DETECTION_CONFIDENCE,
        YOLO_MODEL_PATH,
    )
    from backend.detector import PIPELINE_REVISION
    from backend.diagram_structure import MINIMUM_FLOW_SCORE
    from scripts.evaluate_blind_end_to_end import match_components

    model_path = ROOT / YOLO_MODEL_PATH
    calibration_path = ROOT / YOLO_CALIBRATION_PATH
    arrowhead_path = ROOT / ARROWHEAD_MODEL_PATH
    component_iou = inspect.signature(match_components).parameters["threshold"].default
    configuration = {
        "evaluationSplit": DEVELOPMENT_SPLIT,
        "componentMatchIou": component_iou,
        "yoloConfidenceThreshold": YOLO_CONFIDENCE_THRESHOLD,
        "yoloMinimumDetectionConfidence": YOLO_MIN_DETECTION_CONFIDENCE,
        "yoloCalibrationPath": relative_path(calibration_path),
        "yoloModelPath": relative_path(model_path),
        "arrowheadModelPath": relative_path(arrowhead_path),
        "minimumFlowScore": MINIMUM_FLOW_SCORE,
    }
    required_paths = (model_path, calibration_path, arrowhead_path, BENCHMARK)
    missing = [relative_path(path) for path in required_paths if not path.is_file()]
    if missing:
        raise RuntimeError("Required provenance artifacts are missing: " + ", ".join(missing))
    return {
        "pipelineRevision": PIPELINE_REVISION,
        "datasetHash": sha256(BENCHMARK),
        "configurationHash": canonical_hash(configuration),
        "modelHash": sha256(model_path),
        "executionTimestamp": execution_timestamp,
        "configuration": configuration,
        "supportingHashes": {
            "baselineResult": BASELINE_RESULT_SHA256,
            "detectorCode": sha256(ROOT / "backend/detector.py"),
            "evaluationCode": sha256(ROOT / "scripts/evaluate_blind_end_to_end.py"),
            "confidenceCalibration": sha256(calibration_path),
            "arrowheadModel": sha256(arrowhead_path),
        },
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
    }


def _safe_stage(name: str, operation: Callable[[], dict[str, Any]], errors: list[dict[str, str]]) -> dict[str, Any] | None:
    try:
        return operation()
    except Exception as exc:
        errors.append({"stage": name, "error": f"{type(exc).__name__}: {exc}"})
        return None


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(output_path)


def run_gate(
    output_dir: Path,
    *,
    test_runner: Dependency = run_tests,
    prospective_auditor: Dependency = audit_prospective_v12,
    real_auditor: Dependency = audit_real_benchmark,
    evaluator: Dependency = evaluate_development,
    provenance_collector: Dependency = collect_provenance,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    relative_path(output_dir)
    if "end-to-end-prospective-v12" in output_dir.as_posix().lower():
        raise ValueError("The regression gate cannot write into the prospective v12 result chain.")
    output_dir.mkdir(parents=True, exist_ok=True)
    execution_timestamp = datetime.now(timezone.utc).isoformat()
    errors: list[dict[str, str]] = []

    baseline = _safe_stage("baseline", load_baseline, errors)
    tests = _safe_stage("tests", test_runner, errors)
    prospective = _safe_stage("prospectiveV12Audit", prospective_auditor, errors)
    real = _safe_stage("realBenchmarkAudit", real_auditor, errors)
    provenance = _safe_stage(
        "provenance",
        lambda: provenance_collector(execution_timestamp),
        errors,
    )

    evaluation = None
    if baseline is not None and real is not None and real.get("status") == "passed":
        evaluation = _safe_stage("developmentEvaluation", lambda: evaluator(output_dir), errors)
    else:
        errors.append({
            "stage": "developmentEvaluation",
            "error": "Skipped because baseline or real benchmark integrity was not established.",
        })

    candidate_metrics = None
    split = None
    if evaluation is not None:
        split = evaluation.get("split")
        candidate_metrics = _safe_stage(
            "candidateMetrics",
            lambda: metric_view(evaluation.get("aggregate")),
            errors,
        )

    checks = build_checks(
        candidate_metrics,
        tests,
        prospective,
        real,
        baseline_ok=baseline is not None,
        split=split,
    )
    if provenance is None:
        checks.append(_check("provenanceIntegrity", "FAIL", "==", "PASS", False))
    else:
        checks.append(_check("provenanceIntegrity", "PASS", "==", "PASS", True))

    status = "passed" if not errors and all(check["passed"] for check in checks) else "failed"
    report = {
        "schemaVersion": "1.0",
        "gate": "v15-regression",
        "status": status,
        "baseline": {
            "source": relative_path(BASELINE_RESULT),
            "sha256": BASELINE_RESULT_SHA256,
            "metrics": metric_view(baseline.get("aggregate")) if baseline is not None else None,
        },
        "candidate": {
            "source": (
                f"{relative_path(output_dir)}/end-to-end-{DEVELOPMENT_SPLIT}.json"
                if evaluation is not None else None
            ),
            "split": split,
            "metrics": candidate_metrics,
        },
        "checks": checks,
        "tests": tests,
        "audits": {
            "prospectiveV12": prospective,
            "realBenchmark": real,
        },
        "provenance": provenance,
        "errors": errors,
    }
    write_report(report, output_dir / "gate-report.json")
    return report


def default_output_dir() -> Path:
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "data/results/v15-regression-gate" / suffix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output if args.output is not None else default_output_dir()
    if not output.is_absolute():
        output = ROOT / output
    try:
        report = run_gate(output)
    except Exception as exc:
        failure = {
            "schemaVersion": "1.0",
            "gate": "v15-regression",
            "status": "failed",
            "checks": [],
            "errors": [{"stage": "gate", "error": f"{type(exc).__name__}: {exc}"}],
        }
        print(json.dumps(failure, indent=2, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps({
        "status": report["status"],
        "report": f"{relative_path(output)}/gate-report.json",
        "checks": report["checks"],
    }, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
