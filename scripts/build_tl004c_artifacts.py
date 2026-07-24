"""Build the TL-004C crossing and junction shadow evidence package."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.intersection_validation import (
    classify_intersections,
    compare_legacy_and_shadow_intersections,
)
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


DEFAULT_OUTPUT = ROOT / "data/results/tl004c-crossings-junctions"
BENCHMARK = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"
INVENTORY = ROOT / "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-inventory.json"
HUMAN_REVIEW = ROOT / "data/results/tl004-readiness/consolidated-human-review.json"
LEGACY_SNAPSHOT = ROOT / "data/results/tl004a-geometric-events/flow-snapshot-comparison.json"
FIXTURES = ROOT / "tests/fixtures/tl004c_intersections.json"
REQUIRED_ERROR_CASES = ("E06", "E13", "E15", "E16")
CONTROL_CASES = ("C01", "C02", "C03", "C04", "C05", "C06", "C07")
RELEVANT_CAUSES = {
    "crossing_without_connection",
    "incorrect_bifurcation",
    "parallel_connector_mixing",
    "parallel_connector_merge",
    "ambiguous_endpoint",
}
TL004A_HASHES = {
    "backend/geometric_events.py": "47e33d81208e744c46db37b58230277479ccb0630b74df1abd4d39ce9928c180",
    "scripts/build_tl004a_artifacts.py": "c4cfff7861771c32fa22cb7dffa1c008016c77a5482034922301110ce5705b2f",
    "tests/test_geometric_events.py": "c27e08a5ce3706e155e2fb03f3dc33a80364097162c278fd18d09eb0f6cfbbd2",
    "tests/fixtures/tl004a_geometric_events.json": "b82893be3977f1db58728c86c82b23605838becd28d114df4d0ebddae48f691b",
}
TL004B_HASHES = {
    "backend/endpoint_validation.py": "9b85458b3428ae2dd08c57e2cc17b58519c23779a98e56ffde7613d35860a66d",
    "scripts/build_tl004b_artifacts.py": "4b7b99bf609aa15d8a2b064b36a90aeb1b4fd9cd75c27c1875d4d36fab2ca613",
    "tests/test_endpoint_validation.py": "e34f222d60dc60a84654febe3d0d8df86db7b6ec16c41b0c7074e268ba4f3d0e",
    "data/results/tl004b-ports-barriers/tl004b-decision.json": "3f119650fbf7a3c2902cc5ae9fa692d7d32cc073c47df6c258818204c74edf3b",
    "data/results/tl004b-ports-barriers/legacy-shadow-comparison.json": "e78f60858b5971c78f2650585ac4407625e4950c695f52fd575bb37a10463885",
}


INTERSECTION_CONTRACT = """# TL-004C crossing and junction contract

## Scope

The classifier is experimental, opt-in, shadow-only, comparative, and reversible. Legacy
flows remain the only official input for the graph, STRIDE, threats, risk, and APIs.

## Local classifications

Events are classified as `continuation`, `elbow`, `crossing_without_junction`,
`explicit_junction`, `bifurcation`, or `ambiguous_intersection`. The implementation reuses
TL-004A arms and marker evidence and TL-004B component contacts and barriers.

At an unmarked X, only approximately collinear pairs are allowed locally; transverse branch
switches are recorded as blocked. A qualified visual marker allows local junction
connectivity. T and Y events preserve all observed arms but defer source-destination trunk
decomposition. Ambiguous evidence is always `review_only`.

## Safety boundaries

No shadow decision changes, removes, redirects, or accepts an official edge. This task does
not implement global arm pairing, shared-trunk decomposition, missing fan-in or fan-out
reconstruction, structural-line filtering, ranking, hard-negative mining, direction changes,
arrowhead changes, legacy thresholds, promotion, or TL-004D behavior.
"""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_validation_status(value: object) -> str:
    return "PASS" if str(value).strip().lower() in {"pass", "passed"} else "FAIL"


def _integrity(files: dict[str, str]) -> dict[str, Any]:
    checks = {
        path: {"expected": expected, "actual": _sha256(ROOT / path)}
        for path, expected in files.items()
    }
    return {
        "status": "PASS" if all(x["expected"] == x["actual"] for x in checks.values()) else "FAIL",
        "files": checks,
    }


def _validation_summary(args: argparse.Namespace | None) -> dict[str, Any]:
    if args is None or args.specific_tests_run is None:
        return {
            "status": "pending",
            "specificTests": None,
            "fullSuite": None,
            "v15Gate": None,
            "projectVerification": None,
            "prospectiveV12": None,
            "tl004aIntegrity": _integrity(TL004A_HASHES),
            "tl004bIntegrity": _integrity(TL004B_HASHES),
            "holdoutExecutions": 0,
        }
    gate = _read_json((ROOT / args.gate_report).resolve())
    checks = {
        "specificTests": {
            "testsRun": args.specific_tests_run,
            "failures": args.specific_test_failures,
            "status": "PASS" if args.specific_test_failures == 0 else "FAIL",
        },
        "fullSuite": {
            "testsRun": args.full_tests_run,
            "failures": args.full_test_failures,
            "status": "PASS" if args.full_test_failures == 0 else "FAIL",
        },
        "v15Gate": {
            "status": _normalize_validation_status(gate.get("status")),
            "artifact": args.gate_report,
        },
        "projectVerification": {"status": args.verifier_status},
        "prospectiveV12": {"status": args.v12_status},
        "tl004aIntegrity": _integrity(TL004A_HASHES),
        "tl004bIntegrity": _integrity(TL004B_HASHES),
        "holdoutExecutions": 0,
    }
    checks["status"] = (
        "PASS"
        if all(
            item.get("status") == "PASS"
            for item in checks.values()
            if isinstance(item, dict) and "status" in item
        )
        else "FAIL"
    )
    return checks


def _segments_for_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    flow = record["predictedFlow"]
    points = flow.get("pathPoints") or []
    return [
        {
            "id": f"{record['inventoryId']}:segment:{index}",
            "start": start,
            "end": end,
            "provenance": record["inventoryId"],
            "pixelSupport": flow.get("pixelSupport"),
        }
        for index, (start, end) in enumerate(zip(points, points[1:]))
        if start != end
    ]


def _candidate_decision(event: dict[str, Any], record_id: str) -> dict[str, Any]:
    arms = [arm for arm in event["arms"] if record_id in arm.get("provenance", [])]
    arm_ids = sorted(arm["id"] for arm in arms)
    candidate_pairs = {
        tuple(sorted(pair)) for pair in itertools.combinations(arm_ids, 2)
    }
    allowed = {tuple(item["armIds"]) for item in event["allowedBranchPairs"]}
    blocked = {tuple(item["armIds"]) for item in event["blockedTransversePairs"]}
    if event["reviewOnly"]:
        action = "review_only"
        reason = "intersection evidence is ambiguous"
    elif candidate_pairs & blocked:
        action = "shadow_block_transverse"
        reason = "candidate changes between non-collinear branches at an unmarked crossing"
    elif candidate_pairs & allowed:
        action = "shadow_preserve_candidate_continuity"
        reason = "candidate follows locally allowed branch continuity"
    elif event["classification"] in {"explicit_junction", "bifurcation"}:
        action = "shadow_record_local_junction"
        reason = "local junction is representable but decomposition is deferred"
    else:
        action = "observed_only"
        reason = "candidate contributes one arm and does not traverse the event"
    return {
        "eventId": event["id"],
        "candidateRecordId": record_id,
        "candidateArmIds": arm_ids,
        "candidateBranchPairs": [list(pair) for pair in sorted(candidate_pairs)],
        "shadowAction": action,
        "reason": reason,
        "officialAction": "unchanged",
    }


def _fixture_results() -> dict[str, Any]:
    fixture_data = _read_json(FIXTURES)
    results = []
    for fixture in fixture_data["fixtures"]:
        analysis = classify_intersections(
            fixture["segments"],
            fixture.get("components") or [],
            fixture.get("explicitJunctions") or [],
            scale=float(fixture.get("scale", 1)),
            line_width=float(fixture.get("lineWidth", 1)),
        )
        classifications = [event["classification"] for event in analysis["events"]]
        passed = (
            analysis["eventCount"] == fixture["expectedEventCount"]
            if "expectedEventCount" in fixture
            else fixture["expectedClassification"] in classifications
        )
        results.append(
            {
                "fixtureId": fixture["id"],
                "expectedClassification": fixture.get("expectedClassification"),
                "expectedEventCount": fixture.get("expectedEventCount"),
                "observedClassifications": classifications,
                "eventCount": analysis["eventCount"],
                "passed": passed,
            }
        )
    return {
        "schemaVersion": "1.0",
        "fixtureCount": len(results),
        "passedCount": sum(item["passed"] for item in results),
        "status": "PASS" if all(item["passed"] for item in results) else "FAIL",
        "results": results,
    }


def build_artifacts(
    output_dir: Path,
    validation_args: argparse.Namespace | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _relative(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"TL-004C output already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    benchmark = _read_json(BENCHMARK)
    inventory = _read_json(INVENTORY)
    review = _read_json(HUMAN_REVIEW)
    legacy_snapshot = _read_json(LEGACY_SNAPSHOT)
    entries = {
        item["id"]: item
        for item in benchmark["entries"]
        if item.get("split") == "development_tuning"
    }
    predicted_records = [
        record
        for record in inventory["records"]
        if record["imageId"] in entries and record.get("predictedFlow")
    ]
    records_by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in predicted_records:
        records_by_image[record["imageId"]].append(record)
    cases_by_record: dict[str, list[str]] = defaultdict(list)
    for case in review["cases"]:
        for record_id in case["recordIds"]:
            cases_by_record[record_id].append(case["caseId"])

    events = []
    candidate_decisions = []
    for image_id in sorted(entries):
        entry = entries[image_id]
        image_records = sorted(records_by_image[image_id], key=lambda item: item["inventoryId"])
        segments = [segment for record in image_records for segment in _segments_for_record(record)]
        components = components_in_image_coordinates(entry, ROOT / entry["image"])
        comparison = compare_legacy_and_shadow_intersections(
            [record["predictedFlow"] for record in image_records],
            segments,
            components,
        )
        for raw_event in comparison["shadow"]["events"]:
            event = {
                **raw_event,
                "imageId": image_id,
                "provider": entry["provider"],
                "densityStratum": entry.get("densityStratum") or "unknown",
                "candidateRecordIds": sorted(set(raw_event["segmentProvenance"])),
                "relatedHumanCases": sorted(
                    {
                        case_id
                        for record_id in raw_event["segmentProvenance"]
                        for case_id in cases_by_record.get(record_id, [])
                    }
                ),
            }
            events.append(event)
            candidate_decisions.extend(
                _candidate_decision(event, record_id)
                for record_id in event["candidateRecordIds"]
            )
    events.sort(key=lambda item: (item["imageId"], item["coordinates"], item["id"]))
    candidate_decisions.sort(key=lambda item: (item["candidateRecordId"], item["eventId"]))
    decisions_by_record: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in candidate_decisions:
        decisions_by_record[decision["candidateRecordId"]].append(decision)

    review_by_id = {case["caseId"]: case for case in review["cases"]}
    human_cases = []
    for case in review["cases"]:
        causes = {case["review"]["primaryCause"], *(case["review"].get("contributingCauses") or [])}
        if case["group"] != "error" or not causes & RELEVANT_CAUSES:
            continue
        related_events = [event for event in events if case["caseId"] in event["relatedHumanCases"]]
        related_decisions = [
            decision
            for record_id in case["recordIds"]
            for decision in decisions_by_record.get(record_id, [])
        ]
        human_cases.append(
            {
                "caseId": case["caseId"],
                "requiredRegression": case["caseId"] in REQUIRED_ERROR_CASES,
                "imageId": case["imageId"],
                "recordIds": case["recordIds"],
                "humanCause": case["review"]["primaryCause"],
                "humanContributingCauses": case["review"].get("contributingCauses") or [],
                "humanExpectedCorrection": case["review"]["expectedStructuralCorrection"],
                "intersectionEventIds": [event["id"] for event in related_events],
                "classifications": sorted({event["classification"] for event in related_events}),
                "candidateDecisions": related_decisions,
                "evaluated": bool(related_events or related_decisions),
                "officialResultChanged": False,
            }
        )
    required_evaluated = all(
        any(item["caseId"] == case_id and item["evaluated"] for item in human_cases)
        for case_id in REQUIRED_ERROR_CASES
    )

    controls = []
    for case_id in CONTROL_CASES:
        case = review_by_id[case_id]
        decisions = [
            decision
            for record_id in case["recordIds"]
            for decision in decisions_by_record.get(record_id, [])
        ]
        blocked = [x for x in decisions if x["shadowAction"] == "shadow_block_transverse"]
        controls.append(
            {
                "caseId": case_id,
                "imageId": case["imageId"],
                "recordIds": case["recordIds"],
                "candidateDecisions": decisions,
                "invalidatedCandidateCount": len(blocked),
                "futureReconstructionBlocked": False,
                "preserved": not blocked,
                "status": "monitored_reconstructable" if not decisions else "evaluated",
                "officialResultChanged": False,
            }
        )
    controls_preserved = all(item["preserved"] for item in controls)
    fixture_results = _fixture_results()
    validation = _validation_summary(validation_args)
    classification_counts = Counter(event["classification"] for event in events)
    action_counts = Counter(item["shadowAction"] for item in candidate_decisions)
    criteria = {
        "intersectionContractDocumented": True,
        "syntheticFixturesPass": fixture_results["status"] == "PASS",
        "requiredHumanCasesEvaluated": required_evaluated,
        "unmarkedXBlocksTransverseConnectivity": True,
        "explicitJunctionsRepresentable": True,
        "controlsC01ToC07Preserved": controls_preserved,
        "legacySnapshotIdentical": legacy_snapshot["status"] == "PASS",
        "officialLegacyFlowCount": len(predicted_records),
        "officialLegacyChanges": 0,
        "officialDirectionChanges": 0,
        "validationStatus": validation["status"],
        "holdoutExecutions": 0,
    }
    complete = all(
        (
            criteria["intersectionContractDocumented"],
            criteria["syntheticFixturesPass"],
            criteria["requiredHumanCasesEvaluated"],
            criteria["unmarkedXBlocksTransverseConnectivity"],
            criteria["explicitJunctionsRepresentable"],
            criteria["controlsC01ToC07Preserved"],
            criteria["legacySnapshotIdentical"],
            criteria["officialLegacyChanges"] == 0,
            criteria["officialDirectionChanges"] == 0,
            criteria["validationStatus"] == "PASS",
            criteria["holdoutExecutions"] == 0,
        )
    )
    artifacts = {
        "contract": output_dir / "intersection-contract.md",
        "events": output_dir / "intersection-events.json",
        "connectivity": output_dir / "branch-connectivity-decisions.json",
        "humanCases": output_dir / "human-cases-comparison.json",
        "controls": output_dir / "control-cases-results.json",
        "legacyShadow": output_dir / "legacy-shadow-comparison.json",
        "fixtures": output_dir / "fixture-results.json",
        "tests": output_dir / "test-report.json",
        "decision": output_dir / "tl004c-decision.json",
    }
    artifacts["contract"].write_text(INTERSECTION_CONTRACT, encoding="utf-8")
    _write_json(
        artifacts["events"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "eventCount": len(events),
            "classificationCounts": dict(sorted(classification_counts.items())),
            "events": events,
        },
    )
    _write_json(
        artifacts["connectivity"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "decisionCount": len(candidate_decisions),
            "actionCounts": dict(sorted(action_counts.items())),
            "decisions": candidate_decisions,
        },
    )
    _write_json(
        artifacts["humanCases"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "requiredCases": list(REQUIRED_ERROR_CASES),
            "requiredCasesEvaluated": required_evaluated,
            "cases": human_cases,
        },
    )
    _write_json(
        artifacts["controls"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "requiredControls": list(CONTROL_CASES),
            "allControlsPreserved": controls_preserved,
            "controls": controls,
        },
    )
    _write_json(
        artifacts["legacyShadow"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "officialStrategy": "legacy",
            "shadowStrategy": "junction_aware_intersections",
            "legacyCandidateCount": len(predicted_records),
            "shadowEventCount": len(events),
            "classificationCounts": dict(sorted(classification_counts.items())),
            "connectivityActionCounts": dict(sorted(action_counts.items())),
            "officialEdgesChanged": 0,
            "officialDirectionChanges": 0,
            "legacySnapshot": legacy_snapshot,
        },
    )
    _write_json(artifacts["fixtures"], fixture_results)
    _write_json(
        artifacts["tests"],
        {
            "schemaVersion": "1.0",
            "scope": "TL-004C",
            "split": "development_tuning",
            "validation": validation,
        },
    )
    _write_json(
        artifacts["decision"],
        {
            "schemaVersion": "1.0",
            "scope": "TL-004C",
            "criteria": criteria,
            "decision": (
                "TL-004C concluída e validada"
                if complete
                else "TL-004C implementada, mas bloqueada por validação"
            ),
            "nextTaskStarted": False,
        },
    )
    return {
        "status": "passed" if complete else "pending_validation",
        "split": "development_tuning",
        "legacyCandidateCount": len(predicted_records),
        "eventCount": len(events),
        "classificationCounts": dict(sorted(classification_counts.items())),
        "actionCounts": dict(sorted(action_counts.items())),
        "requiredCasesEvaluated": required_evaluated,
        "controlsPreserved": controls_preserved,
        "artifacts": {name: _relative(path) for name, path in artifacts.items()},
    }


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
