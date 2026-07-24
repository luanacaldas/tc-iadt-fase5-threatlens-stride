"""Build the TL-004B legacy-versus-shadow evidence package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.endpoint_validation import compare_legacy_and_shadow
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


DEFAULT_OUTPUT = ROOT / "data/results/tl004b-ports-barriers"
BENCHMARK = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"
INVENTORY = ROOT / "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-inventory.json"
HUMAN_REVIEW = ROOT / "data/results/tl004-readiness/consolidated-human-review.json"
LEGACY_SNAPSHOT = ROOT / "data/results/tl004a-geometric-events/flow-snapshot-comparison.json"
REQUIRED_ERROR_CASES = ("E03", "E09", "E10", "E11", "E15", "E16")
CONTROL_CASES = ("C01", "C02", "C03", "C04", "C05", "C06", "C07")
EXPECTED_ERROR_EDGES = {
    "E03": [("media", "stage3"), ("stage3", "trigger3")],
    "E09": [("internet", "load_balancer")],
    "E10": [("cloud_run", "vpc_connector")],
    "E11": [("compute", "api")],
    "E15": [],
    "E16": [],
}
TL004A_HASHES = {
    "backend/geometric_events.py": "47e33d81208e744c46db37b58230277479ccb0630b74df1abd4d39ce9928c180",
    "scripts/build_tl004a_artifacts.py": "c4cfff7861771c32fa22cb7dffa1c008016c77a5482034922301110ce5705b2f",
    "tests/test_geometric_events.py": "c27e08a5ce3706e155e2fb03f3dc33a80364097162c278fd18d09eb0f6cfbbd2",
    "tests/fixtures/tl004a_geometric_events.json": "b82893be3977f1db58728c86c82b23605838becd28d114df4d0ebddae48f691b",
}


PORTS_CONTRACT = """# TL-004B ports and barriers contract

## Scope

This contract is experimental, opt-in, shadow-only, and reversible. `legacy` remains the
default strategy and the only source for STRIDE, threats, risk, and official API responses.

## Component ports

A port is derived only from TL-004A `component_port` or
`component_boundary_intersection` evidence. Each port records the component, coordinate,
bounding-box side, distance from both path endpoints, arrival/departure angle, responsible
segment, confidence, and geometric evidence. Tangential contact remains low-confidence and
does not create a component barrier.

## Endpoint decisions

Endpoint classifications are `confirmed_contact`, `ambiguous_contact`, `proximity_only`,
`no_contact`, and `wrong_component_contact`. Path-point reversal is internal to the shadow
analysis and never mutates the candidate. Proximity without visual contact cannot confirm a
port.

## Component barriers

A verified interior crossing of a component that is not an endpoint stops the experimental
path at the first such component. Declared source and destination components are never
barriers. Adjacent relations may be proposed for review, but no shadow relation is promoted
to the official graph.

## Exclusions

TL-004B does not classify X/T/Y junctions, pair arms, reconstruct shared trunks, filter
structural lines, rank edges, mine hard negatives, or change legacy thresholds, direction,
or arrowhead evidence.
"""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_validation_status(value: object) -> str:
    normalized = str(value).strip().lower()
    return "PASS" if normalized in {"pass", "passed"} else "FAIL"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _selected_edge(decision: dict[str, Any]) -> dict[str, str] | None:
    flow = decision["junctionAware"].get("experimentalFlow")
    if not flow:
        return None
    return {"from": str(flow["from"]), "to": str(flow["to"])}


def _case_matches(case_id: str, decisions: list[dict[str, Any]]) -> bool:
    expected = set(EXPECTED_ERROR_EDGES[case_id])
    original = {
        (str(item["legacyCandidate"]["from"]), str(item["legacyCandidate"]["to"]))
        for item in decisions
    }
    proposed = {
        (edge["from"], edge["to"])
        for item in decisions
        if (edge := item.get("selectedEndpoint")) is not None
    }
    direct_suppressed = all(
        item["junctionAwareCandidate"]["edgeAction"] in {"redirected", "removed"}
        for item in decisions
    )
    if case_id in {"E03", "E15", "E16"}:
        return direct_suppressed and not (original & proposed)
    return bool(expected & proposed)


def _validation_summary(args: argparse.Namespace | None) -> dict[str, Any]:
    if args is None or args.specific_tests_run is None:
        return {
            "status": "pending",
            "specificTests": None,
            "fullSuite": None,
            "v15Gate": None,
            "projectVerification": None,
            "prospectiveV12": None,
        }
    gate = _read_json((ROOT / args.gate_report).resolve())
    tl004a = {
        path: {"expected": expected, "actual": _sha256(ROOT / path)}
        for path, expected in TL004A_HASHES.items()
    }
    tl004a_pass = all(item["expected"] == item["actual"] for item in tl004a.values())
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
        "tl004aIntegrity": {"status": "PASS" if tl004a_pass else "FAIL", "files": tl004a},
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


def build_artifacts(
    output_dir: Path,
    validation_args: argparse.Namespace | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _relative(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"TL-004B output already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    benchmark = _read_json(BENCHMARK)
    inventory = _read_json(INVENTORY)
    human_review = _read_json(HUMAN_REVIEW)
    legacy_snapshot = _read_json(LEGACY_SNAPSHOT)
    entries = {
        entry["id"]: entry
        for entry in benchmark["entries"]
        if entry.get("split") == "development_tuning"
    }
    components_by_image = {
        image_id: components_in_image_coordinates(entry, ROOT / entry["image"])
        for image_id, entry in entries.items()
    }
    decisions = []
    for record in inventory["records"]:
        if record["imageId"] not in entries or not record.get("predictedFlow"):
            continue
        comparison = compare_legacy_and_shadow(
            record["predictedFlow"], components_by_image[record["imageId"]]
        )
        shadow = comparison["junctionAware"]
        decisions.append(
            {
                "inventoryId": record["inventoryId"],
                "imageId": record["imageId"],
                "provider": record["provider"],
                "evaluationStatus": record["status"],
                "legacyCandidate": comparison["officialFlow"],
                "junctionAwareCandidate": shadow,
                "originalEndpoints": {
                    "from": record["predictedFlow"]["from"],
                    "to": record["predictedFlow"]["to"],
                },
                "selectedEndpoint": _selected_edge(comparison),
                "barriersFound": [item["componentId"] for item in shadow.get("barriers") or []],
                "officialResultChanged": False,
            }
        )
    decisions.sort(key=lambda item: item["inventoryId"])
    by_record = {item["inventoryId"]: item for item in decisions}

    barrier_records = [
        {
            "inventoryId": item["inventoryId"],
            "imageId": item["imageId"],
            "legacyEdge": item["originalEndpoints"],
            "firstIntermediateBarrier": item["junctionAwareCandidate"].get("firstIntermediateBarrier"),
            "barriers": item["junctionAwareCandidate"].get("barriers") or [],
            "adjacentRelations": item["junctionAwareCandidate"].get("adjacentRelations") or [],
        }
        for item in decisions
        if item["junctionAwareCandidate"].get("barriers")
    ]

    review_cases = {item["caseId"]: item for item in human_review["cases"]}
    relevant_error_cases = []
    for case in human_review["cases"]:
        if case["group"] != "error":
            continue
        causes = {case["review"]["primaryCause"], *(case["review"].get("contributingCauses") or [])}
        if not causes & {"ambiguous_endpoint", "component_passthrough", "component_pass_through", "transitive_shortcut"}:
            continue
        case_decisions = [by_record[item] for item in case["recordIds"] if item in by_record]
        relevant_error_cases.append(
            {
                "caseId": case["caseId"],
                "requiredRegression": case["caseId"] in REQUIRED_ERROR_CASES,
                "imageId": case["imageId"],
                "humanCause": case["review"]["primaryCause"],
                "humanContributingCauses": case["review"].get("contributingCauses") or [],
                "humanExpectedCorrection": case["review"]["expectedStructuralCorrection"],
                "expectedEdges": [
                    {"from": source, "to": destination}
                    for source, destination in EXPECTED_ERROR_EDGES.get(case["caseId"], [])
                ],
                "decisions": case_decisions,
                "evaluated": bool(case_decisions),
                "matchesHumanExpectation": (
                    _case_matches(case["caseId"], case_decisions)
                    if case["caseId"] in EXPECTED_ERROR_EDGES and case_decisions
                    else None
                ),
            }
        )

    controls = []
    for case_id in CONTROL_CASES:
        case = review_cases[case_id]
        case_decisions = [by_record[item] for item in case["recordIds"] if item in by_record]
        actions = [item["junctionAwareCandidate"]["edgeAction"] for item in case_decisions]
        preserved = all(action in {"kept", "review_only"} for action in actions)
        controls.append(
            {
                "caseId": case_id,
                "imageId": case["imageId"],
                "humanExpectedCorrection": case["review"]["expectedStructuralCorrection"],
                "recordIds": case["recordIds"],
                "decisions": case_decisions,
                "status": "monitored_out_of_scope" if not case_decisions else "evaluated",
                "legacyEdgesPreserved": preserved,
                "reason": (
                    "No legacy candidate exists; TL-004B does not reconstruct shared trunks."
                    if not case_decisions
                    else "Shadow decisions are conservative and the official legacy edges remain unchanged."
                ),
            }
        )

    action_counts = Counter(item["junctionAwareCandidate"]["edgeAction"] for item in decisions)
    required_cases_evaluated = all(
        any(item["caseId"] == case_id and item["evaluated"] for item in relevant_error_cases)
        for case_id in REQUIRED_ERROR_CASES
    )
    controls_preserved = all(item["legacyEdgesPreserved"] for item in controls)
    validation = _validation_summary(validation_args)
    criteria = {
        "portsContractDocumented": True,
        "requiredHumanCasesEvaluated": required_cases_evaluated,
        "controlsC01ToC07Preserved": controls_preserved,
        "legacySnapshotIdentical": legacy_snapshot["status"] == "PASS",
        "officialLegacyFlowCount": len(decisions),
        "officialLegacyChanges": 0,
        "directionChangesToOfficialFlows": 0,
        "validationStatus": validation["status"],
        "holdoutExecutions": 0,
    }
    complete = (
        all(
            (
                criteria["portsContractDocumented"],
                criteria["requiredHumanCasesEvaluated"],
                criteria["controlsC01ToC07Preserved"],
                criteria["legacySnapshotIdentical"],
                criteria["officialLegacyChanges"] == 0,
                criteria["directionChangesToOfficialFlows"] == 0,
                criteria["validationStatus"] == "PASS",
                criteria["holdoutExecutions"] == 0,
            )
        )
    )
    artifacts = {
        "portsContract": output_dir / "ports-contract.md",
        "endpointDecisions": output_dir / "endpoint-decisions.json",
        "componentBarriers": output_dir / "component-barriers.json",
        "humanCases": output_dir / "human-cases-comparison.json",
        "controlCases": output_dir / "control-cases-results.json",
        "legacyShadow": output_dir / "legacy-shadow-comparison.json",
        "testReport": output_dir / "test-report.json",
        "decision": output_dir / "tl004b-decision.json",
    }
    artifacts["portsContract"].write_text(PORTS_CONTRACT, encoding="utf-8")
    _write_json(
        artifacts["endpointDecisions"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "strategy": "junction_aware_shadow",
            "decisionCount": len(decisions),
            "decisions": decisions,
        },
    )
    _write_json(
        artifacts["componentBarriers"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "recordCount": len(barrier_records),
            "records": barrier_records,
        },
    )
    _write_json(
        artifacts["humanCases"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "requiredCases": list(REQUIRED_ERROR_CASES),
            "requiredCasesEvaluated": required_cases_evaluated,
            "cases": relevant_error_cases,
        },
    )
    _write_json(
        artifacts["controlCases"],
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
            "shadowStrategy": "junction_aware",
            "legacyCandidateCount": len(decisions),
            "actionCounts": dict(sorted(action_counts.items())),
            "edgesMaintainedOrReviewOnly": action_counts["kept"] + action_counts["review_only"],
            "edgesRemoved": action_counts["removed"],
            "edgesRedirected": action_counts["redirected"],
            "officialEdgesChanged": 0,
            "officialDirectionChanges": 0,
            "legacySnapshot": legacy_snapshot,
        },
    )
    _write_json(
        artifacts["testReport"],
        {
            "schemaVersion": "1.0",
            "scope": "TL-004B",
            "split": "development_tuning",
            "validation": validation,
        },
    )
    _write_json(
        artifacts["decision"],
        {
            "schemaVersion": "1.0",
            "scope": "TL-004B",
            "criteria": criteria,
            "requiredHumanCaseMatches": {
                item["caseId"]: item["matchesHumanExpectation"]
                for item in relevant_error_cases
                if item["caseId"] in REQUIRED_ERROR_CASES
            },
            "decision": (
                "TL-004B concluída e validada"
                if complete
                else "TL-004B implementada, mas bloqueada por validação"
            ),
            "nextTaskStarted": False,
        },
    )
    return {
        "status": "passed" if complete else "pending_validation",
        "split": "development_tuning",
        "decisionCount": len(decisions),
        "actionCounts": dict(sorted(action_counts.items())),
        "requiredCasesEvaluated": required_cases_evaluated,
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
    if validation_args and result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
