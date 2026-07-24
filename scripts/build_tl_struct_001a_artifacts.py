"""Build TL-STRUCT-001A conservative structural-line gate evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.integrated_junction_strategy import apply_integrated_decisions, orchestrate_junction_aware
from backend.structural_line_gate import apply_structural_line_gate, evaluate_structural_line_gate
from scripts.build_tl004f_artifacts import (
    BENCHMARK,
    HUMAN_REVIEW,
    INVENTORY,
    STRATEGIES,
    TL004D_CONTROLS,
    _aggregate_metrics,
    _prepare_inputs,
    _read,
)
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


DEFAULT_OUTPUT = ROOT / "data/results/tl-struct-001a-final-gate"
FIXTURES = ROOT / "tests/fixtures/tl_struct_001a.json"
PRIORITY_SHORTCUTS = {"E03", "E10", "E14"}
AMBIGUOUS_REVIEW_CASES = {"E06", "E08", "E11", "E13", "E16"}
DEPENDENCY_HASHES = {
    "TL-004A": {"backend/geometric_events.py": "47e33d81208e744c46db37b58230277479ccb0630b74df1abd4d39ce9928c180"},
    "TL-004B": {"backend/endpoint_validation.py": "9b85458b3428ae2dd08c57e2cc17b58519c23779a98e56ffde7613d35860a66d"},
    "TL-004C": {"backend/intersection_validation.py": "545994754617bdf9478850c88edd247a3f3239c0a8c19bd4557deee13fafbf0e"},
    "TL-004D": {"backend/shared_trunk_reconstruction.py": "9430a46d70ad2438864cefba4477bf71f69840aa93b2208a58d1fb9b514493e3"},
    "TL-004E": {"backend/transitive_shortcut_validation.py": "4ceb879941a5c1e7c1d5ac69fd7c36eaf6d1a8b0bf7da7b98c5cd74f93aff0fd"},
    "TL-004F": {
        "backend/integrated_junction_strategy.py": "ab5295e6b5ae38b21f758c136b889fe36963f4a4f5a1e3d5c3ae2b59b08bb7c6",
        "scripts/build_tl004f_artifacts.py": "81e367f4186803579773345d2253a3d9dc8c8f7d0db45b0ff9f4a8eb277b9f7c",
        "tests/test_integrated_junction_strategy.py": "7426bb2297ecb6b672b68c9c97363fee06a0c6c8c86c2e9d720a76ff87288e16",
        "tests/fixtures/tl004f_integration.json": "ec8ed754a709454709fe55fa0990f495cfbfb75423e05a64b4c0d61eda0fd2e8",
        "data/results/tl004f-integrated-ablation/tl004f-decision.json": "06d1fca0ef52f6bd3927f70f5f9489eaf8a16d1b2ec155dcbdb119a106689e59",
        "data/results/tl004f-integrated-ablation/ablation-results.json": "a560e22c9383a4d17f87eb672c35ffc11357dd81c6fedb3a9ab77e0f248aef5e",
        "data/results/tl004f-integrated-ablation/legacy-shadow-comparison.json": "ce196b24ebdb175d973264cf0f4bdc6c26426a686453fcff60f6983e92d3e748",
    },
}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _integrity() -> dict[str, Any]:
    groups = {}
    for task, files in DEPENDENCY_HASHES.items():
        checks = {path: {"expected": expected, "actual": _sha(ROOT / path)} for path, expected in files.items()}
        groups[task] = {"status": "PASS" if all(item["expected"] == item["actual"] for item in checks.values()) else "FAIL", "files": checks}
    return groups


def _validation(args: argparse.Namespace | None) -> dict[str, Any]:
    dependencies = _integrity()
    if args is None or args.specific_tests_run is None:
        return {"status": "pending", "specificTests": None, "fullSuite": None, "v15Gate": None, "projectVerification": None, "prospectiveV12": None, "dependencyIntegrity": dependencies, "holdoutExecutions": 0}
    gate_path = (ROOT / args.gate_report).resolve()
    gate = _read(gate_path)
    result = {
        "specificTests": {"testsRun": args.specific_tests_run, "failures": args.specific_test_failures, "status": "PASS" if args.specific_test_failures == 0 else "FAIL"},
        "fullSuite": {"testsRun": args.full_tests_run, "failures": args.full_test_failures, "status": "PASS" if args.full_test_failures == 0 else "FAIL"},
        "v15Gate": {"status": "PASS" if gate.get("status") in {"pass", "passed", "PASS"} else "FAIL", "artifact": _relative(gate_path)},
        "projectVerification": {"status": args.verifier_status},
        "prospectiveV12": {"status": args.v12_status},
        "dependencyIntegrity": dependencies,
        "holdoutExecutions": 0,
    }
    statuses = [item["status"] for item in dependencies.values()]
    statuses.extend(item["status"] for item in result.values() if isinstance(item, dict) and "status" in item)
    result["status"] = "PASS" if all(value == "PASS" for value in statuses) else "FAIL"
    return result


def _structural_kind(review: dict[str, Any]) -> str:
    text = " ".join((review.get("observations") or "", review.get("expectedStructuralCorrection") or "")).lower()
    if "grade" in text:
        return "grid_line"
    if "subnet" in text:
        return "subnet_border"
    if "projeto" in text:
        return "project_border"
    if "icone" in text or "Ã­cone" in text or "traÃ§o interno" in text:
        return "icon_internal_stroke"
    if "container" in text or "agrup" in text:
        return "container_border"
    return "area_border"


def _candidate_evidence(base: dict[str, Any], record: dict[str, Any], case: dict[str, Any] | None) -> dict[str, Any]:
    ports = base.get("ports") or []
    verified = [item for item in ports if (item.get("geometricEvidence") or {}).get("endpointContactVerified")]
    source_contact = any(item.get("componentId") == base["legacyFrom"] for item in verified)
    destination_contact = any(item.get("componentId") == base["legacyTo"] for item in verified)
    review = case["review"] if case else {}
    human_structural = review.get("primaryCause") == "structural_line"
    direction = str((record.get("predictedFlow") or {}).get("directionEvidence") or "")
    direction_confidence = float((record.get("predictedFlow") or {}).get("directionConfidence") or 0)
    arrowhead = direction in {"visual_arrowhead", "supervised_arrowhead"} and direction_confidence >= 0.75
    direct = base.get("directEdgeEvidence") or {}
    own_continuity = bool(direct.get("confirmed"))
    return {
        "sourcePortConfirmed": source_contact,
        "destinationPortConfirmed": destination_contact,
        "structuralAlignment": {
            "aligned": human_structural,
            "kind": _structural_kind(review) if human_structural else "unknown",
            "confidence": review.get("confidence", "low") if human_structural else "low",
            "source": "human_review" if human_structural else "not_available",
        },
        "connectorContinuity": {"present": own_continuity, "confidence": "high" if own_continuity else "low", "source": "direct_edge_evidence"},
        "arrowheadPresent": arrowhead,
        "arrowheadEvidence": {"type": direction or "not_available", "confidence": direction_confidence},
        "unmarkedCrossingCount": len(base.get("intersectionIds") or []),
        "humanReview": {
            "caseId": case.get("caseId") if case else None,
            "decision": review.get("decision"),
            "primaryCause": review.get("primaryCause"),
            "confidence": review.get("confidence"),
        },
        "controlProtected": bool(base.get("protected")),
    }


def _promotion(metrics: dict[str, Any], *, controls_pass: bool, false_blocks: int, human_true_positives_blocked: int, direction_changes: int, new_edges: int, review_applied: int, validation: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "falsePositiveEdgeCount": metrics["falsePositiveEdgeCount"] <= 81,
        "correctAdjacencyCount": metrics["correctAdjacencyCount"] >= 52,
        "missedEdgeCount": metrics["missedEdgeCount"] <= 19,
        "edgeExistenceRecall": round(metrics["edgeExistenceRecall"], 4) >= 0.7324,
        "edgeExistenceF1": round(metrics["edgeExistenceF1"], 4) >= 0.5083,
        "directionAccuracy": round(metrics["directionAccuracy"], 4) >= 0.8654,
        "controlsC01ToC07": controls_pass,
        "humanTruePositivesBlocked": human_true_positives_blocked == 0,
        "possibleFalseBlockCount": false_blocks == 0,
        "correctDirectionsChanged": direction_changes == 0,
        "newEdgeCount": new_edges == 0,
        "reviewOnlyAppliedCount": review_applied == 0,
        "validation": validation["status"] == "PASS",
    }
    regression = any((metrics["correctAdjacencyCount"] < 52, metrics["missedEdgeCount"] > 19, human_true_positives_blocked > 0, false_blocks > 0, direction_changes > 0, new_edges > 0))
    decision = "blocked_by_regression" if regression else "eligible_for_controlled_promotion" if all(checks.values()) else "remain_shadow_only"
    return {"checks": checks, "passedCount": sum(checks.values()), "checkCount": len(checks), "allCriteriaPassed": all(checks.values()), "decision": decision}


def build_artifacts(output_dir: Path, validation_args: argparse.Namespace | None = None) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _relative(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"TL-STRUCT-001A output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    benchmark, inventory, review, prior_controls = _read(BENCHMARK), _read(INVENTORY), _read(HUMAN_REVIEW), _read(TL004D_CONTROLS)
    entries = {item["id"]: item for item in benchmark["entries"] if item.get("split") == "development_tuning"}
    records = [item for item in inventory["records"] if item["imageId"] in entries and item.get("predictedFlow")]
    by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_image[record["imageId"]].append(record)
    cases_by_record = {record_id: case for case in review["cases"] for record_id in case["recordIds"]}
    inputs = {image_id: _prepare_inputs(entry, sorted(by_image[image_id], key=lambda item: item["inventoryId"]), review["cases"]) for image_id, entry in entries.items()}
    legacy_sets = {image_id: [copy.deepcopy(item["predictedFlow"]) for item in by_image[image_id]] for image_id in entries}
    legacy_metrics = _aggregate_metrics(entries, legacy_sets)
    base_flow_sets, final_flow_sets = {}, {}
    all_gate_decisions, all_base_decisions = [], []
    application_by_image = {}
    flags = STRATEGIES["full_without_endpoint_redirect"]
    for image_id in sorted(entries):
        data = inputs[image_id]
        base = orchestrate_junction_aware(
            data["legacyFlows"], components_in_image_coordinates(entries[image_id], ROOT / entries[image_id]["image"]),
            segments=data["segments"], adjacent_relations=data["adjacentRelations"], confirmed_direct_edges=data["confirmedDirectEdges"],
            human_confirmed_shortcuts=data["humanConfirmedShortcuts"], protected_candidate_ids=data["protectedCandidateIds"],
            structural_candidate_ids=data["structuralCandidateIds"], recovery_candidates=data["recoveryCandidates"], module_flags=flags,
        )
        records_by_candidate = {str(item["predictedFlow"]["id"]): item for item in by_image[image_id]}
        augmented = []
        evidence = {}
        for decision in base["candidateDecisions"]:
            record = records_by_candidate[decision["candidateId"]]
            item = {**decision, "inventoryId": record["inventoryId"], "imageId": image_id, "provider": record.get("provider"), "benchmarkStatus": record["status"]}
            augmented.append(item)
            evidence[item["candidateId"]] = _candidate_evidence(item, record, cases_by_record.get(record["inventoryId"]))
        gate = evaluate_structural_line_gate(augmented, evidence)
        base_applied = apply_integrated_decisions(data["legacyFlows"], augmented, base["recoveryDecisions"])
        final_applied = apply_structural_line_gate(data["legacyFlows"], augmented, gate["decisions"])
        base_flow_sets[image_id], final_flow_sets[image_id] = base_applied["flows"], final_applied["flows"]
        all_base_decisions.extend(augmented)
        all_gate_decisions.extend({**item, "imageId": image_id, "provider": records_by_candidate[item["candidateId"]].get("provider"), "benchmarkStatus": records_by_candidate[item["candidateId"]]["status"]} for item in gate["decisions"])
        application_by_image[image_id] = {"base": base_applied, "final": {key: value for key, value in final_applied.items() if key != "updatedDecisions"}}

    base_metrics, final_metrics = _aggregate_metrics(entries, base_flow_sets), _aggregate_metrics(entries, final_flow_sets)
    expected_legacy = {"predictedEdgeCount": 142, "correctAdjacencyCount": 52, "falsePositiveEdgeCount": 90, "missedEdgeCount": 19, "reversedEdgeCount": 7}
    expected_base = {"predictedEdgeCount": 136, "correctAdjacencyCount": 52, "falsePositiveEdgeCount": 84, "missedEdgeCount": 19, "reversedEdgeCount": 7}
    if any(legacy_metrics[key] != value for key, value in expected_legacy.items()):
        raise RuntimeError(f"legacy structural baseline mismatch: {legacy_metrics}")
    if any(base_metrics[key] != value for key, value in expected_base.items()):
        raise RuntimeError(f"full_without_endpoint_redirect baseline mismatch: {base_metrics}")

    gate_by_record = {item["inventoryId"]: item for item in all_gate_decisions}
    base_by_record = {item["inventoryId"]: item for item in all_base_decisions}
    human_cases = []
    for case in review["cases"]:
        if case["group"] != "error":
            continue
        gates = [gate_by_record[item] for item in case["recordIds"] if item in gate_by_record]
        bases = [base_by_record[item] for item in case["recordIds"] if item in base_by_record]
        human_cases.append({
            "caseId": case["caseId"], "imageId": case["imageId"], "humanPrimaryCause": case["review"]["primaryCause"],
            "humanConfidence": case["review"]["confidence"], "baseActions": sorted({item["finalAction"] for item in bases}),
            "structuralGateActions": sorted({item["gateAction"] for item in gates}), "finalActions": sorted({item["finalAction"] for item in gates}),
            "recordIds": case["recordIds"], "expectedStructuralCorrection": case["review"]["expectedStructuralCorrection"],
        })

    prior_index = {item["caseId"]: item for item in prior_controls["controls"]}
    controls = []
    for case in (item for item in review["cases"] if item["group"] == "control"):
        gates = [gate_by_record[item] for item in case["recordIds"] if item in gate_by_record]
        blocked = [item["inventoryId"] for item in gates if item["gateAction"] == "block"]
        prior = prior_index[case["caseId"]]
        expected_prior_status = "supervised_shadow_recovered" if case["caseId"] == "C04" else "preserved"
        passed = bool(prior.get("preserved")) and prior.get("status") == expected_prior_status and not blocked
        controls.append({"caseId": case["caseId"], "requiredEdges": prior["requiredEdges"], "forbiddenEdges": prior["forbiddenEdges"], "legacyResult": prior.get("status"), "experimentalResult": "supervised_shadow_recovery" if case["caseId"] == "C04" else "preserved", "blockedRecordIds": blocked, "status": "PASS" if passed else "FAIL"})
    controls_pass = len(controls) == 7 and all(item["status"] == "PASS" for item in controls)

    blocked = [item for item in all_gate_decisions if item["gateAction"] == "block"]
    false_blocks = sum(item["benchmarkStatus"] in {"true_positive", "reversed"} for item in blocked)
    human_true_positives_blocked = sum(bool(item["blockedRecordIds"]) for item in controls)
    base_edges = {(image_id, flow["from"], flow["to"]) for image_id, flows in base_flow_sets.items() for flow in flows}
    final_edges = {(image_id, flow["from"], flow["to"]) for image_id, flows in final_flow_sets.items() for flow in flows}
    correct_before = {(item["imageId"], item["legacyFrom"], item["legacyTo"]) for item in all_base_decisions if item["benchmarkStatus"] == "true_positive"}
    direction_changes = len(correct_before - final_edges)
    new_edges = len(final_edges - base_edges)
    review_applied = sum(item["final"]["reviewOnlyAppliedCount"] for item in application_by_image.values())
    validation = _validation(validation_args)
    promotion = _promotion(final_metrics, controls_pass=controls_pass, false_blocks=false_blocks, human_true_positives_blocked=human_true_positives_blocked, direction_changes=direction_changes, new_edges=new_edges, review_applied=review_applied, validation=validation)
    priority_ok = all(next(item for item in human_cases if item["caseId"] == case_id)["finalActions"] == ["block"] for case_id in PRIORITY_SHORTCUTS)
    ambiguous_ok = all(next(item for item in human_cases if item["caseId"] == case_id)["finalActions"] == ["review_only"] for case_id in AMBIGUOUS_REVIEW_CASES)

    artifacts = {
        "decisions": output_dir / "structural-line-decisions.json", "human": output_dir / "human-cases-comparison.json",
        "controls": output_dir / "control-cases-results.json", "metrics": output_dir / "metrics-comparison.json",
        "criteria": output_dir / "promotion-criteria.json", "promotion": output_dir / "promotion-decision.json", "tests": output_dir / "test-report.json",
    }
    _write(artifacts["decisions"], {"schemaVersion": "1.0", "split": "development_tuning", "baseStrategy": "full_without_endpoint_redirect", "decisionCount": len(all_gate_decisions), "blockedCount": len(blocked), "reviewOnlyAppliedCount": review_applied, "newEdgeCount": new_edges, "decisions": all_gate_decisions})
    _write(artifacts["human"], {"schemaVersion": "1.0", "split": "development_tuning", "priorityShortcutsBlocked": priority_ok, "ambiguousCasesRemainReviewOnly": ambiguous_ok, "cases": human_cases})
    _write(artifacts["controls"], {"schemaVersion": "1.0", "split": "development_tuning", "allControlsPass": controls_pass, "c04AutonomousRecoveryApplied": False, "controls": controls})
    _write(artifacts["metrics"], {"schemaVersion": "1.0", "split": "development_tuning", "legacy": legacy_metrics, "fullWithoutEndpointRedirect": base_metrics, "fullWithoutEndpointRedirectPlusStructuralLineGate": final_metrics, "deltasVsBase": {"predictedEdgeCount": final_metrics["predictedEdgeCount"] - base_metrics["predictedEdgeCount"], "correctAdjacencyCount": final_metrics["correctAdjacencyCount"] - base_metrics["correctAdjacencyCount"], "falsePositiveEdgeCount": final_metrics["falsePositiveEdgeCount"] - base_metrics["falsePositiveEdgeCount"], "missedEdgeCount": final_metrics["missedEdgeCount"] - base_metrics["missedEdgeCount"], "edgeExistenceF1": final_metrics["edgeExistenceF1"] - base_metrics["edgeExistenceF1"]}})
    _write(artifacts["criteria"], {"schemaVersion": "1.0", "split": "development_tuning", "metrics": final_metrics, "possibleFalseBlockCount": false_blocks, "humanTruePositivesBlocked": human_true_positives_blocked, "correctDirectionsChanged": direction_changes, "newEdgeCount": new_edges, "reviewOnlyAppliedCount": review_applied, "checks": promotion["checks"]})
    _write(artifacts["promotion"], {"schemaVersion": "1.0", "decision": promotion["decision"], "allCriteriaPassed": promotion["allCriteriaPassed"], "defaultStrategy": "legacy", "defaultStrategyChanged": False, "shadowOnly": True, "holdoutExecutions": 0})
    _write(artifacts["tests"], {"schemaVersion": "1.0", "scope": "TL-STRUCT-001A", "split": "development_tuning", "validation": validation, "dependencyIntegrity": validation["dependencyIntegrity"], "holdoutExecutions": 0})
    return {"status": "passed" if validation["status"] == "PASS" else "pending_validation", "split": "development_tuning", "legacyMetrics": legacy_metrics, "baseMetrics": base_metrics, "finalMetrics": final_metrics, "blockedCount": len(blocked), "possibleFalseBlockCount": false_blocks, "controlsPass": controls_pass, "priorityShortcutsBlocked": priority_ok, "ambiguousCasesRemainReviewOnly": ambiguous_ok, "promotionDecision": promotion["decision"], "artifacts": {name: _relative(path) for name, path in artifacts.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--specific-tests-run", type=int)
    parser.add_argument("--specific-test-failures", type=int, default=0)
    parser.add_argument("--full-tests-run", type=int, default=0)
    parser.add_argument("--full-test-failures", type=int, default=0)
    parser.add_argument("--gate-report", type=str)
    parser.add_argument("--verifier-status", choices=("PASS", "FAIL"), default="FAIL")
    parser.add_argument("--v12-status", choices=("PASS", "FAIL"), default="FAIL")
    args = parser.parse_args()
    validation_args = args if args.specific_tests_run is not None else None
    if validation_args and not args.gate_report:
        parser.error("--gate-report is required with validation results")
    result = build_artifacts(args.output, validation_args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] in {"passed", "pending_validation"} else 1)


if __name__ == "__main__":
    main()
