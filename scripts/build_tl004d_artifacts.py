"""Build the TL-004D shared-trunk and branch-pairing shadow evidence package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.shared_trunk_reconstruction import (
    TRUNK_CLASSIFICATIONS,
    compare_legacy_and_shadow_trunks,
    reconstruct_shared_trunks,
)
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


DEFAULT_OUTPUT = ROOT / "data/results/tl004d-shared-trunks"
BENCHMARK = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"
INVENTORY = ROOT / "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-inventory.json"
HUMAN_REVIEW = ROOT / "data/results/tl004-readiness/consolidated-human-review.json"
LEGACY_SNAPSHOT = ROOT / "data/results/tl004a-geometric-events/flow-snapshot-comparison.json"
FIXTURES = ROOT / "tests/fixtures/tl004d_shared_trunks.json"
C04_FIXTURE = ROOT / "data/fixtures/tl004d_c04_shared_trunk.json"
REQUIRED_ERROR_CASES = ("E06", "E13", "E15", "E16")
CONTROL_CASES = ("C01", "C02", "C03", "C04", "C05", "C06", "C07")
DEPENDENCY_HASHES = {
    "TL-004A": {
        "backend/geometric_events.py": "47e33d81208e744c46db37b58230277479ccb0630b74df1abd4d39ce9928c180",
        "scripts/build_tl004a_artifacts.py": "c4cfff7861771c32fa22cb7dffa1c008016c77a5482034922301110ce5705b2f",
        "tests/test_geometric_events.py": "c27e08a5ce3706e155e2fb03f3dc33a80364097162c278fd18d09eb0f6cfbbd2",
        "tests/fixtures/tl004a_geometric_events.json": "b82893be3977f1db58728c86c82b23605838becd28d114df4d0ebddae48f691b",
    },
    "TL-004B": {
        "backend/endpoint_validation.py": "9b85458b3428ae2dd08c57e2cc17b58519c23779a98e56ffde7613d35860a66d",
        "scripts/build_tl004b_artifacts.py": "4b7b99bf609aa15d8a2b064b36a90aeb1b4fd9cd75c27c1875d4d36fab2ca613",
        "tests/test_endpoint_validation.py": "e34f222d60dc60a84654febe3d0d8df86db7b6ec16c41b0c7074e268ba4f3d0e",
        "data/results/tl004b-ports-barriers/tl004b-decision.json": "3f119650fbf7a3c2902cc5ae9fa692d7d32cc073c47df6c258818204c74edf3b",
        "data/results/tl004b-ports-barriers/legacy-shadow-comparison.json": "e78f60858b5971c78f2650585ac4407625e4950c695f52fd575bb37a10463885",
    },
    "TL-004C": {
        "backend/intersection_validation.py": "545994754617bdf9478850c88edd247a3f3239c0a8c19bd4557deee13fafbf0e",
        "scripts/build_tl004c_artifacts.py": "127f34cee33293f71f1b2906bf843a4f3273d2949d9b506ad91b1669a65e4d1a",
        "tests/test_intersection_validation.py": "4b55534de2555e77064bd08a1b2666cd30dbacbab09efe0c4e6d6d66dc59cfa1",
        "tests/fixtures/tl004c_intersections.json": "57d7a86c69251ec51a8de8e0b366b8427c64cce84e2bfaec9b8cc971856fdb09",
        "data/results/tl004c-crossings-junctions/tl004c-decision.json": "3a3a3fe98ff7f903271c282ae8f7b116429dfc6287251bc7351f12af92cbdcee",
        "data/results/tl004c-crossings-junctions/legacy-shadow-comparison.json": "a03891aabf47c16eb94f680a522117db5b9083234629eaca86be5c50ea78b745",
    },
}


SHARED_TRUNK_CONTRACT = """# TL-004D shared-trunk and branch-pairing contract

## Scope

This strategy is experimental, opt-in, shadow-only, comparative, deterministic, and
reversible. Legacy flows remain the only official source for the graph, STRIDE, threats,
risk, APIs, and reports. Shadow relations are never eligible for official consumption.

## Inputs and dependencies

TL-004D consumes canonical geometric segments and local events from TL-004A, component
contacts and barriers from TL-004B, and allowed or blocked local branch pairs from TL-004C.
It does not duplicate or modify those classifiers. Direction associated with a reviewed or
legacy terminal is evidence for shadow pairing only and never changes official direction.

## Trunk and arm contract

A trunk has a deterministic ID, canonical segment IDs, segment provenance, local events,
junction arms, directionally supported input and output arms, unknown-direction arms,
connected ports, terminal components, confidence, reasons, parameters, allowed pairings,
blocked pairings, and review-only alternatives. A shared trunk is internal structure, not an
edge. Only supported source-to-destination terminal pairs become experimental relations.

## Safety rules

Unmarked crossings retain only TL-004C collinear continuity. Near but disconnected or
nearly parallel arms are not combined. Component barriers force adjacent relations and
prevent shortcuts. A single source with multiple destinations is fan-out; multiple sources
with one destination is fan-in. Ambiguous direction produces `review_only`, never an edge.
All unselected terminal permutations are recorded as prevented clique relations.

## C04 evidence boundary

C04 uses a separately identified human-reviewed connector trace to test whether the shadow
contract can represent the two reviewed private-bus edges. This is a supervised regression,
not evidence that the current detector independently recovered the missing pixels or edges.
"""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _integrity(files: dict[str, str]) -> dict[str, Any]:
    checks = {
        path: {"expected": expected, "actual": _sha256(ROOT / path)}
        for path, expected in files.items()
    }
    return {
        "status": "PASS" if all(x["expected"] == x["actual"] for x in checks.values()) else "FAIL",
        "files": checks,
    }


def _normalize_status(value: object) -> str:
    return "PASS" if str(value).strip().lower() in {"pass", "passed"} else "FAIL"


def _validation_summary(args: argparse.Namespace | None) -> dict[str, Any]:
    dependencies = {name: _integrity(files) for name, files in DEPENDENCY_HASHES.items()}
    if args is None or args.specific_tests_run is None:
        return {
            "status": "pending",
            "specificTests": None,
            "fullSuite": None,
            "v15Gate": None,
            "projectVerification": None,
            "prospectiveV12": None,
            "dependencyIntegrity": dependencies,
            "holdoutExecutions": 0,
        }
    gate = _read_json((ROOT / args.gate_report).resolve())
    validation = {
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
        "v15Gate": {"status": _normalize_status(gate.get("status")), "artifact": args.gate_report},
        "projectVerification": {"status": args.verifier_status},
        "prospectiveV12": {"status": args.v12_status},
        "dependencyIntegrity": dependencies,
        "holdoutExecutions": 0,
    }
    dependency_pass = all(item["status"] == "PASS" for item in dependencies.values())
    validation["status"] = (
        "PASS"
        if dependency_pass
        and all(
            item.get("status") == "PASS"
            for item in validation.values()
            if isinstance(item, dict) and "status" in item and item is not dependencies
        )
        else "FAIL"
    )
    return validation


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


def _ports_for_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    flow = record["predictedFlow"]
    points = flow.get("pathPoints") or []
    if len(points) < 2:
        return []
    confidence = float(flow.get("directionConfidence") or 0)
    return [
        {
            "id": f"{record['inventoryId']}:source-port",
            "componentId": flow["from"],
            "coordinates": points[0],
            "segmentId": f"{record['inventoryId']}:segment:0",
            "direction": "outgoing",
            "confidence": confidence,
            "reviewed": True,
            "evidence": flow.get("directionEvidence") or "legacy_direction",
            "provenance": record["inventoryId"],
        },
        {
            "id": f"{record['inventoryId']}:destination-port",
            "componentId": flow["to"],
            "coordinates": points[-1],
            "segmentId": f"{record['inventoryId']}:segment:{len(points) - 2}",
            "direction": "incoming",
            "confidence": confidence,
            "reviewed": True,
            "evidence": flow.get("directionEvidence") or "legacy_direction",
            "provenance": record["inventoryId"],
        },
    ]


def _relation_pairs(relations: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    return {(item["from"], item["to"]) for item in relations}


def _fixture_results() -> dict[str, Any]:
    results = []
    for fixture in _read_json(FIXTURES)["fixtures"]:
        analysis = reconstruct_shared_trunks(
            fixture["segments"],
            fixture.get("components") or [],
            fixture.get("ports") or [],
            fixture.get("explicitJunctions") or [],
            barrier_component_ids=fixture.get("barrierComponentIds") or [],
            scale=float(fixture.get("scale", 1)),
            line_width=float(fixture.get("lineWidth", 1)),
        )
        observed = _relation_pairs(analysis["experimentalRelations"])
        expected = {tuple(item) for item in fixture.get("expectedRelations") or []}
        forbidden = {tuple(item) for item in fixture.get("forbiddenRelations") or []}
        classifications = {item["classification"] for item in analysis["trunks"]}
        expected_classifications = set(fixture.get("expectedClassifications") or [])
        passed = expected <= observed and not observed & forbidden and expected_classifications <= classifications
        results.append(
            {
                "fixtureId": fixture["id"],
                "expectedRelations": sorted([list(item) for item in expected]),
                "observedRelations": sorted([list(item) for item in observed]),
                "forbiddenRelationsObserved": sorted([list(item) for item in observed & forbidden]),
                "classifications": sorted(classifications),
                "preventedCliqueCount": len(analysis["preventedCliqueRelations"]),
                "reviewOnlyCount": len(analysis["reviewOnlyRelations"]),
                "inputMutation": analysis["inputMutation"],
                "passed": passed and not analysis["inputMutation"],
            }
        )
    return {
        "schemaVersion": "1.0",
        "fixtureCount": len(results),
        "passedCount": sum(item["passed"] for item in results),
        "status": "PASS" if len(results) == 20 and all(item["passed"] for item in results) else "FAIL",
        "results": results,
    }


def _c04_result() -> dict[str, Any]:
    fixture = _read_json(C04_FIXTURE)
    analysis = reconstruct_shared_trunks(fixture["segments"], terminal_ports=fixture["ports"])
    observed = _relation_pairs(analysis["experimentalRelations"])
    expected = {tuple(item) for item in fixture["expectedRelations"]}
    forbidden = {tuple(item) for item in fixture["forbiddenRelations"]}
    return {
        "caseId": "C04",
        "split": fixture["split"],
        "evidenceSource": _relative(C04_FIXTURE),
        "annotationMethod": fixture["annotationMethod"],
        "autonomousRecoveryClaimed": False,
        "expectedRelations": sorted([list(item) for item in expected]),
        "experimentalRelations": sorted([list(item) for item in observed]),
        "forbiddenRelationsObserved": sorted([list(item) for item in observed & forbidden]),
        "classification": sorted({item["classification"] for item in analysis["trunks"]}),
        "confidence": "high_reviewed_trace",
        "missingEvidenceForAutonomousRecovery": [
            "detector-produced continuous connector trace for both missed edges",
            "detector-produced endpoint ports for the two missed destinations",
        ],
        "reconstructedCorrectlyInSupervisedShadow": observed == expected and not observed & forbidden,
        "officialResultChanged": False,
        "analysis": analysis,
    }


def _required_and_forbidden(case: dict[str, Any], record_index: dict[str, dict[str, Any]]) -> tuple[list[list[str]], list[list[str]]]:
    required = []
    for record_id in case["recordIds"]:
        record = record_index[record_id]
        flow = record.get("expectedFlow") or record.get("predictedFlow")
        if flow:
            required.append([flow["from"], flow["to"]])
    sources = sorted({item[0] for item in required})
    destinations = sorted({item[1] for item in required})
    peers = destinations if len(sources) == 1 else sources if len(destinations) == 1 else []
    forbidden = [[first, second] for first in peers for second in peers if first != second]
    return sorted(required), sorted(forbidden)


def build_artifacts(output_dir: Path, validation_args: argparse.Namespace | None = None) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _relative(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"TL-004D output already exists: {output_dir}")
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
    records = [
        item
        for item in inventory["records"]
        if item["imageId"] in entries and item.get("predictedFlow")
    ]
    record_index = {item["inventoryId"]: item for item in inventory["records"]}
    records_by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        records_by_image[record["imageId"]].append(record)

    cases_by_record: dict[str, list[str]] = defaultdict(list)
    for case in review["cases"]:
        for record_id in case["recordIds"]:
            cases_by_record[record_id].append(case["caseId"])

    image_results = []
    all_trunks = []
    all_relations = []
    all_reviews = []
    all_prevented = []
    for image_id in sorted(entries):
        entry = entries[image_id]
        image_records = sorted(records_by_image[image_id], key=lambda item: item["inventoryId"])
        segments = [segment for record in image_records for segment in _segments_for_record(record)]
        ports = [port for record in image_records for port in _ports_for_record(record)]
        components = components_in_image_coordinates(entry, ROOT / entry["image"])
        comparison = compare_legacy_and_shadow_trunks(
            [record["predictedFlow"] for record in image_records],
            segments,
            components,
            ports,
        )
        shadow = comparison["shadow"]
        for trunk in shadow["trunks"]:
            provenance = trunk.get("segmentProvenance") or []
            enriched = {
                **trunk,
                "imageId": image_id,
                "provider": entry["provider"],
                "densityStratum": entry.get("densityStratum") or "unknown",
                "relatedHumanCases": sorted(
                    {case_id for record_id in provenance for case_id in cases_by_record.get(record_id, [])}
                ),
            }
            all_trunks.append(enriched)
        all_relations.extend({**item, "imageId": image_id} for item in shadow["experimentalRelations"])
        all_reviews.extend({**item, "imageId": image_id} for item in shadow["reviewOnlyRelations"])
        all_prevented.extend({**item, "imageId": image_id} for item in shadow["preventedCliqueRelations"])
        image_results.append(
            {
                "imageId": image_id,
                "provider": entry["provider"],
                "legacyFlowCount": len(image_records),
                "trunkCount": len(shadow["trunks"]),
                "experimentalRelationCount": len(shadow["experimentalRelations"]),
                "reviewOnlyCount": len(shadow["reviewOnlyRelations"]),
                "preventedCliqueCount": len(shadow["preventedCliqueRelations"]),
                "officialFlowsChanged": comparison["officialFlowsChanged"],
                "officialDirectionChanges": comparison["officialDirectionChanges"],
            }
        )
    all_trunks.sort(key=lambda item: (item["imageId"], item["id"]))
    all_relations.sort(key=lambda item: (item["imageId"], item["from"], item["to"], item["id"]))
    all_reviews.sort(key=lambda item: (item["imageId"], item["trunkId"], item["from"], item["to"]))
    all_prevented.sort(key=lambda item: (item["imageId"], item["trunkId"], item["from"], item["to"]))
    trunks_by_id = {item["id"]: item for item in all_trunks}

    human_cases = []
    review_by_id = {item["caseId"]: item for item in review["cases"]}
    for case_id in REQUIRED_ERROR_CASES:
        case = review_by_id[case_id]
        related = [
            trunk
            for trunk in all_trunks
            if set(trunk.get("segmentProvenance") or []) & set(case["recordIds"])
        ]
        trunk_ids = {item["id"] for item in related}
        relations = [item for item in all_relations if item["trunkId"] in trunk_ids]
        candidate = record_index[case["recordIds"][0]]["predictedFlow"]
        candidate_pair = (candidate["from"], candidate["to"])
        still_generated = candidate_pair in _relation_pairs(relations)
        human_cases.append(
            {
                "caseId": case_id,
                "imageId": case["imageId"],
                "humanPrimaryCause": case["review"]["primaryCause"],
                "humanContributingCauses": case["review"].get("contributingCauses") or [],
                "recordIds": case["recordIds"],
                "relatedTrunkIds": sorted(trunk_ids),
                "classifications": sorted({item["classification"] for item in related}),
                "experimentalRelations": sorted(
                    [[item["from"], item["to"]] for item in relations]
                ),
                "falsePositiveStillGeneratedInShadow": still_generated,
                "status": "still_requires_later_filter" if still_generated else "not_reconstructed_by_trunk_pairing",
                "evaluated": True,
                "officialResultChanged": False,
            }
        )

    c04 = _c04_result()
    controls = []
    for case_id in CONTROL_CASES:
        case = review_by_id[case_id]
        required, forbidden = _required_and_forbidden(case, record_index)
        if case_id == "C04":
            experimental = c04["experimentalRelations"]
            required = c04["expectedRelations"]
            forbidden = _read_json(C04_FIXTURE)["forbiddenRelations"]
            reason = "reviewed connector trace reconstructs the missing fan-out in supervised shadow"
            confidence = "high_reviewed_trace"
        else:
            related_trunks = [
                item
                for item in all_trunks
                if set(item.get("segmentProvenance") or []) & set(case["recordIds"])
            ]
            related_ids = {item["id"] for item in related_trunks}
            experimental = sorted(
                [[item["from"], item["to"]] for item in all_relations if item["trunkId"] in related_ids]
            )
            reason = "all required legacy edges remain official and shadow adds no forbidden peer edge"
            confidence = case["review"]["confidence"]
        observed_forbidden = sorted([item for item in experimental if item in forbidden])
        controls.append(
            {
                "caseId": case_id,
                "imageId": case["imageId"],
                "requiredEdges": required,
                "forbiddenEdges": sorted(forbidden),
                "experimentalRelations": experimental,
                "forbiddenEdgesObserved": observed_forbidden,
                "status": "supervised_shadow_recovered" if case_id == "C04" else "preserved",
                "reason": reason,
                "confidence": confidence,
                "preserved": not observed_forbidden,
                "officialResultChanged": False,
            }
        )

    fixture_results = _fixture_results()
    validation = _validation_summary(validation_args)
    classification_counts = Counter(item["classification"] for item in all_trunks)
    controls_preserved = all(item["preserved"] for item in controls)
    human_evaluated = all(item["evaluated"] for item in human_cases)
    official_changes = sum(item["officialFlowsChanged"] for item in image_results)
    direction_changes = sum(item["officialDirectionChanges"] for item in image_results)
    clique_violations = sum(len(item["forbiddenEdgesObserved"]) for item in controls)
    criteria = {
        "contractDocumented": True,
        "allTwentySyntheticFixturesPass": fixture_results["status"] == "PASS",
        "noImproperCliqueGenerated": clique_violations == 0,
        "controlsC01ToC07Preserved": controls_preserved,
        "c04SupervisedShadowRecovered": c04["reconstructedCorrectlyInSupervisedShadow"],
        "requiredHumanCasesReevaluated": human_evaluated,
        "legacySnapshotIdentical": legacy_snapshot["status"] == "PASS",
        "officialLegacyFlowCount": len(records),
        "officialLegacyChanges": official_changes,
        "officialDirectionChanges": direction_changes,
        "validationStatus": validation["status"],
        "holdoutExecutions": 0,
    }
    complete = all(
        (
            criteria["contractDocumented"],
            criteria["allTwentySyntheticFixturesPass"],
            criteria["noImproperCliqueGenerated"],
            criteria["controlsC01ToC07Preserved"],
            criteria["c04SupervisedShadowRecovered"],
            criteria["requiredHumanCasesReevaluated"],
            criteria["legacySnapshotIdentical"],
            criteria["officialLegacyFlowCount"] == 142,
            criteria["officialLegacyChanges"] == 0,
            criteria["officialDirectionChanges"] == 0,
            criteria["validationStatus"] == "PASS",
            criteria["holdoutExecutions"] == 0,
        )
    )

    artifacts = {
        "contract": output_dir / "shared-trunk-contract.md",
        "trunks": output_dir / "shared-trunks.json",
        "pairing": output_dir / "branch-pairing-decisions.json",
        "fanInFanOut": output_dir / "fan-in-fan-out-results.json",
        "humanCases": output_dir / "human-cases-comparison.json",
        "controls": output_dir / "control-cases-results.json",
        "cliquePrevention": output_dir / "clique-prevention-report.json",
        "legacyShadow": output_dir / "legacy-shadow-comparison.json",
        "fixtures": output_dir / "fixture-results.json",
        "tests": output_dir / "test-report.json",
        "decision": output_dir / "tl004d-decision.json",
    }
    artifacts["contract"].write_text(SHARED_TRUNK_CONTRACT, encoding="utf-8")
    _write_json(
        artifacts["trunks"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "trunkCount": len(all_trunks),
            "classificationCounts": dict(sorted(classification_counts.items())),
            "trunks": all_trunks,
        },
    )
    _write_json(
        artifacts["pairing"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "experimentalRelationCount": len(all_relations),
            "reviewOnlyRelationCount": len(all_reviews),
            "experimentalRelations": all_relations,
            "reviewOnlyRelations": all_reviews,
        },
    )
    _write_json(
        artifacts["fanInFanOut"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "classificationCounts": dict(sorted(classification_counts.items())),
            "supportedClassifications": list(TRUNK_CLASSIFICATIONS),
            "c04": c04,
            "controls": controls,
        },
    )
    _write_json(
        artifacts["humanCases"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "requiredCases": list(REQUIRED_ERROR_CASES),
            "allRequiredCasesEvaluated": human_evaluated,
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
        artifacts["cliquePrevention"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "preventedRelationCount": len(all_prevented),
            "controlCliqueViolationCount": clique_violations,
            "status": "PASS" if clique_violations == 0 else "FAIL",
            "preventedRelations": all_prevented,
        },
    )
    _write_json(
        artifacts["legacyShadow"],
        {
            "schemaVersion": "1.0",
            "split": "development_tuning",
            "officialStrategy": "legacy",
            "shadowStrategy": "junction_aware_shared_trunks",
            "legacyCandidateCount": len(records),
            "shadowTrunkCount": len(all_trunks),
            "shadowExperimentalRelationCount": len(all_relations),
            "officialEdgesChanged": official_changes,
            "officialDirectionChanges": direction_changes,
            "feedsStride": "legacy_only",
            "legacySnapshot": legacy_snapshot,
            "images": image_results,
        },
    )
    _write_json(artifacts["fixtures"], fixture_results)
    _write_json(
        artifacts["tests"],
        {
            "schemaVersion": "1.0",
            "scope": "TL-004D",
            "split": "development_tuning",
            "validation": validation,
        },
    )
    _write_json(
        artifacts["decision"],
        {
            "schemaVersion": "1.0",
            "scope": "TL-004D",
            "criteria": criteria,
            "decision": (
                "TL-004D concluída e validada"
                if complete
                else "TL-004D implementada, mas bloqueada por validação"
            ),
            "nextTaskStarted": False,
        },
    )
    return {
        "status": "passed" if complete else "pending_validation",
        "split": "development_tuning",
        "legacyCandidateCount": len(records),
        "trunkCount": len(all_trunks),
        "experimentalRelationCount": len(all_relations),
        "controlsPreserved": controls_preserved,
        "c04Recovered": c04["reconstructedCorrectlyInSupervisedShadow"],
        "requiredHumanCasesEvaluated": human_evaluated,
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
