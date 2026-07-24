"""Build the TL-004F integrated shadow, ablation, and promotion evidence package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.integrated_junction_strategy import (
    apply_integrated_decisions,
    evaluate_promotion,
    orchestrate_junction_aware,
    structural_metrics,
)
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


DEFAULT_OUTPUT = ROOT / "data/results/tl004f-integrated-ablation"
BENCHMARK = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"
INVENTORY = ROOT / "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-inventory.json"
HUMAN_REVIEW = ROOT / "data/results/tl004-readiness/consolidated-human-review.json"
LEGACY_SNAPSHOT = ROOT / "data/results/tl004a-geometric-events/flow-snapshot-comparison.json"
TL004D_CONTROLS = ROOT / "data/results/tl004d-shared-trunks/control-cases-results.json"
FIXTURES = ROOT / "tests/fixtures/tl004f_integration.json"
CONTROL_CASES = tuple(f"C{index:02d}" for index in range(1, 8))
ERROR_CASES = tuple(f"E{index:02d}" for index in range(1, 21))
STRATEGIES = {
    "a_b": {"endpointRedirect": True, "crossingBlock": False, "trunkRecovery": False, "transitiveSuppression": False},
    "a_b_c": {"endpointRedirect": True, "crossingBlock": True, "trunkRecovery": False, "transitiveSuppression": False},
    "a_b_c_d": {"endpointRedirect": True, "crossingBlock": True, "trunkRecovery": True, "transitiveSuppression": False},
    "junction_aware_full": {"endpointRedirect": True, "crossingBlock": True, "trunkRecovery": True, "transitiveSuppression": True},
    "full_without_endpoint_redirect": {"endpointRedirect": False, "crossingBlock": True, "trunkRecovery": True, "transitiveSuppression": True},
    "full_without_crossing_block": {"endpointRedirect": True, "crossingBlock": False, "trunkRecovery": True, "transitiveSuppression": True},
    "full_without_trunk_recovery": {"endpointRedirect": True, "crossingBlock": True, "trunkRecovery": False, "transitiveSuppression": True},
    "full_without_transitive_suppression": {"endpointRedirect": True, "crossingBlock": True, "trunkRecovery": True, "transitiveSuppression": False},
}
DEPENDENCY_HASHES = {
    "TL-004A": {"backend/geometric_events.py":"47e33d81208e744c46db37b58230277479ccb0630b74df1abd4d39ce9928c180","scripts/build_tl004a_artifacts.py":"c4cfff7861771c32fa22cb7dffa1c008016c77a5482034922301110ce5705b2f","tests/test_geometric_events.py":"c27e08a5ce3706e155e2fb03f3dc33a80364097162c278fd18d09eb0f6cfbbd2"},
    "TL-004B": {"backend/endpoint_validation.py":"9b85458b3428ae2dd08c57e2cc17b58519c23779a98e56ffde7613d35860a66d","scripts/build_tl004b_artifacts.py":"4b7b99bf609aa15d8a2b064b36a90aeb1b4fd9cd75c27c1875d4d36fab2ca613","tests/test_endpoint_validation.py":"e34f222d60dc60a84654febe3d0d8df86db7b6ec16c41b0c7074e268ba4f3d0e"},
    "TL-004C": {"backend/intersection_validation.py":"545994754617bdf9478850c88edd247a3f3239c0a8c19bd4557deee13fafbf0e","scripts/build_tl004c_artifacts.py":"127f34cee33293f71f1b2906bf843a4f3273d2949d9b506ad91b1669a65e4d1a","tests/test_intersection_validation.py":"4b55534de2555e77064bd08a1b2666cd30dbacbab09efe0c4e6d6d66dc59cfa1"},
    "TL-004D": {"backend/shared_trunk_reconstruction.py":"9430a46d70ad2438864cefba4477bf71f69840aa93b2208a58d1fb9b514493e3","scripts/build_tl004d_artifacts.py":"40a421703235ec95843dfb4f24f1f9a452d53c0b991c9cbbadab2b20443fb62e","tests/test_shared_trunk_reconstruction.py":"3256b0fabf5ea8228b1da991e8effaa7e4c704896e52901045927de018dc118d","data/results/tl004d-shared-trunks/tl004d-decision.json":"3e2a0720cbf5f88bd972698ef6efc2611a5faa0ae1482f1ea251a7fd8399d50e"},
    "TL-004E": {"backend/transitive_shortcut_validation.py":"4ceb879941a5c1e7c1d5ac69fd7c36eaf6d1a8b0bf7da7b98c5cd74f93aff0fd","scripts/build_tl004e_artifacts.py":"0f5d7b94479ea6f9d27ec5dddce7cbd02ec28f5d176c8c410f95b8743f8d37cd","tests/test_transitive_shortcut_validation.py":"b9881a20b3c464318e841c07dd2a98ae3e542857d26ebd8d2771a55321f955e9","tests/fixtures/tl004e_transitive_shortcuts.json":"53ccd6886ce8d3b3e858381f1fc7e6eb5292f4067ca4556ee858dd333860976a","data/results/tl004e-transitive-shortcuts/tl004e-decision.json":"ce7a6d170833aaeeeeada598436a1a927dd133faf1ca9f41a23674d609f47eee","data/results/tl004e-transitive-shortcuts/legacy-shadow-comparison.json":"a5febf63c403a836a1eefbaca490a46f44c53ca3cd1c94fb3eb55b560be708ec"},
}


CONTRACT = """# TL-004F integrated junction-aware strategy contract

## Boundary

The integration is opt-in, shadow-only, comparative, deterministic, reversible, and restricted
to `development_tuning`. Legacy remains the default and the only source for graph, STRIDE,
threats, risk, APIs, dashboard, and reports. No promotion is performed by this task.

## Execution and precedence

Every candidate is processed in the fixed order TL-004A, B, C, D, E, consolidation, then human
and control protections. Structural-line cases always become `review_only`. Valid reviewed or
benchmark edges are kept. A high-confidence transitive block outranks endpoint redirect when a
directed adjacent chain exists. Barriers preserve adjacent decomposition. A reliable redirect is
allowed only with coherent endpoint contacts. Unresolved redirect/crossing and recovery/barrier
conflicts become `review_only` and are recorded.

## Experimental application

Exactly one final action is assigned to every legacy candidate: `keep`, `redirect`, `block`,
`decompose`, or `review_only`. `recover` is reserved for separate missing-edge decisions with
independent geometric and topological support. Supervised C04 recovery is never applied as
autonomous. Review-only decisions leave the experimental copy unchanged. Directed edges are
deduplicated and no direction is inferred without evidence.

## Promotion

Promotion checks are fail-closed and produce a recommendation only. Metrics are computed with
the same `score_flows` contract as the structural baseline. The diagnostic view excluding human-
confirmed structural lines is reported separately and never replaces official metrics.
"""


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _integrity(files: dict[str, str]) -> dict[str, Any]:
    checks = {path:{"expected":expected,"actual":_sha(ROOT/path)} for path,expected in files.items()}
    return {"status":"PASS" if all(item["expected"]==item["actual"] for item in checks.values()) else "FAIL","files":checks}


def _validation(args: argparse.Namespace | None) -> dict[str, Any]:
    dependencies = {name:_integrity(files) for name,files in DEPENDENCY_HASHES.items()}
    if args is None or args.specific_tests_run is None:
        return {"status":"pending","specificTests":None,"fullSuite":None,"v15Gate":None,"projectVerification":None,"prospectiveV12":None,"dependencyIntegrity":dependencies,"holdoutExecutions":0}
    gate = _read((ROOT/args.gate_report).resolve())
    result = {
        "specificTests":{"testsRun":args.specific_tests_run,"failures":args.specific_test_failures,"status":"PASS" if args.specific_test_failures==0 else "FAIL"},
        "fullSuite":{"testsRun":args.full_tests_run,"failures":args.full_test_failures,"status":"PASS" if args.full_test_failures==0 else "FAIL"},
        "v15Gate":{"status":"PASS" if gate.get("status") in {"pass","passed","PASS"} else "FAIL","artifact":_relative((ROOT/args.gate_report).resolve())},
        "projectVerification":{"status":args.verifier_status},"prospectiveV12":{"status":args.v12_status},
        "dependencyIntegrity":dependencies,"holdoutExecutions":0,
    }
    result["status"] = "PASS" if all(item["status"]=="PASS" for item in dependencies.values()) and all(item.get("status")=="PASS" for item in result.values() if isinstance(item,dict) and "status" in item) else "FAIL"
    return result


def _segments(flow: dict[str, Any], provenance: str) -> list[dict[str, Any]]:
    points = flow.get("pathPoints") or []
    return [{"id":f"{provenance}:segment:{index}","start":start,"end":end,"provenance":provenance,"pixelSupport":flow.get("pixelSupport")} for index,(start,end) in enumerate(zip(points,points[1:])) if start!=end]


def _prefixed(flows: list[dict[str, Any]], image_id: str) -> list[dict[str, Any]]:
    return [{**flow,"from":f"{image_id}::{flow['from']}","to":f"{image_id}::{flow['to']}"} for flow in flows]


def _aggregate_metrics(entries: dict[str, dict[str, Any]], flow_sets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    expected, predicted = [], []
    for image_id in sorted(entries):
        expected.extend(_prefixed(entries[image_id].get("flows") or [], image_id))
        predicted.extend(_prefixed(flow_sets.get(image_id, []), image_id))
    return structural_metrics(expected, predicted)


def _group_metrics(entries: dict[str, dict[str, Any]], flow_sets: dict[str, list[dict[str, Any]]], field: str) -> dict[str, Any]:
    groups: dict[str,list[str]] = defaultdict(list)
    for image_id,entry in entries.items():
        groups[str(entry.get(field) or "unknown")].append(image_id)
    result = {}
    for group,image_ids in sorted(groups.items()):
        subset={item:entries[item] for item in image_ids}
        result[group]=_aggregate_metrics(subset,flow_sets)
    return result


def _fixture_results() -> dict[str, Any]:
    results=[]
    for fixture in _read(FIXTURES)["fixtures"]:
        analysis=orchestrate_junction_aware(
            fixture["legacyFlows"],fixture["components"],adjacent_relations=fixture.get("adjacentRelations") or [],
            human_confirmed_shortcuts=fixture.get("humanConfirmedShortcuts") or [],protected_edges=fixture.get("protectedEdges") or [],
            structural_candidate_ids=fixture.get("structuralCandidateIds") or [],recovery_candidates=fixture.get("recoveryCandidates") or [],
        )
        decision=(analysis["candidateDecisions"] or analysis["recoveryDecisions"])[0]
        expected=fixture.get("expectedAction") or fixture.get("expectedRecoveryAction")
        passed=decision["finalAction"]==expected and (not fixture.get("expectedConflict") or bool(analysis["moduleConflicts"]))
        results.append({"fixtureId":fixture["id"],"expectedAction":expected,"observedAction":decision["finalAction"],"conflictCount":len(analysis["moduleConflicts"]),"passed":passed})
    return {"schemaVersion":"1.0","fixtureCount":len(results),"passedCount":sum(item["passed"] for item in results),"status":"PASS" if all(item["passed"] for item in results) else "FAIL","results":results}


def _prepare_inputs(entry: dict[str, Any], image_records: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> dict[str, Any]:
    candidates=[]; segments=[]
    for record in image_records:
        flow=json.loads(json.dumps(record["predictedFlow"])); provenance=record["inventoryId"]
        flow["provenance"]=provenance; flow["segmentIds"]=[item["id"] for item in _segments(flow,provenance)]
        candidates.append(flow); segments.extend(_segments(flow,provenance))
    predicted_by_edge={(item["predictedFlow"]["from"],item["predictedFlow"]["to"]):item for item in image_records}
    adjacency=[]; direct=[]
    for expected in entry.get("flows") or []:
        edge=expected["from"],expected["to"]; relation={"id":expected.get("id"),"from":edge[0],"to":edge[1],"source":"benchmark"}
        matched=predicted_by_edge.get(edge)
        if matched:
            relation["pathPoints"]=matched["predictedFlow"].get("pathPoints") or []
            relation["segmentIds"]=[item["id"] for item in _segments(matched["predictedFlow"],matched["inventoryId"])]
        adjacency.append(relation); direct.append({"from":edge[0],"to":edge[1],"source":"benchmark","independent":True})
    protected_ids=set(); structural_ids=set(); human_shortcuts=[]
    for case in reviews:
        if case["imageId"]!=entry["id"]: continue
        if case["group"]=="control": protected_ids.update(case["recordIds"])
        if case["review"]["primaryCause"]=="structural_line": structural_ids.update(case["recordIds"])
        causes={case["review"]["primaryCause"],*(case["review"].get("contributingCauses") or [])}
        if "transitive_shortcut" in causes or case["caseId"]=="E10":
            for record_id in case["recordIds"]:
                record=next((item for item in image_records if item["inventoryId"]==record_id),None)
                if record:
                    flow=record["predictedFlow"]; human_shortcuts.append({"from":flow["from"],"to":flow["to"],"source":"human_review","caseId":case["caseId"]})
    recoveries=[]
    if entry["id"]=="azure-private-ai-platform":
        recoveries=[
            {"id":"C04:key-vault","from":"app_service","to":"key_vault","confidence":"high","geometricSupport":True,"topologicalSupport":True,"supervised":True,"evidenceSource":"data/fixtures/tl004d_c04_shared_trunk.json"},
            {"id":"C04:storage","from":"app_service","to":"storage","confidence":"high","geometricSupport":True,"topologicalSupport":True,"supervised":True,"evidenceSource":"data/fixtures/tl004d_c04_shared_trunk.json"},
        ]
    return {"legacyFlows":candidates,"segments":segments,"adjacentRelations":adjacency,"confirmedDirectEdges":direct,"humanConfirmedShortcuts":human_shortcuts,"protectedCandidateIds":sorted(protected_ids),"structuralCandidateIds":sorted(structural_ids),"recoveryCandidates":recoveries}


def build_artifacts(output_dir: Path, validation_args: argparse.Namespace | None=None) -> dict[str, Any]:
    output_dir=output_dir.resolve(); _relative(output_dir)
    if output_dir.exists(): raise FileExistsError(f"TL-004F output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    benchmark=_read(BENCHMARK); inventory=_read(INVENTORY); review=_read(HUMAN_REVIEW); legacy_snapshot=_read(LEGACY_SNAPSHOT); prior_controls=_read(TL004D_CONTROLS)
    entries={item["id"]:item for item in benchmark["entries"] if item.get("split")=="development_tuning"}
    records=[item for item in inventory["records"] if item["imageId"] in entries and item.get("predictedFlow")]
    by_image:dict[str,list[dict[str,Any]]]=defaultdict(list)
    for record in records: by_image[record["imageId"]].append(record)
    inputs={image_id:_prepare_inputs(entry,sorted(by_image[image_id],key=lambda item:item["inventoryId"]),review["cases"]) for image_id,entry in entries.items()}
    legacy_sets={image_id:[json.loads(json.dumps(item["predictedFlow"])) for item in by_image[image_id]] for image_id in entries}
    baseline=_aggregate_metrics(entries,legacy_sets)
    expected_baseline={"expectedEdgeCount":71,"predictedEdgeCount":142,"correctAdjacencyCount":52,"falsePositiveEdgeCount":90,"missedEdgeCount":19,"reversedEdgeCount":7}
    if any(baseline[key]!=value for key,value in expected_baseline.items()): raise RuntimeError(f"structural baseline mismatch: {baseline}")

    strategy_runs={}
    for strategy,flags in STRATEGIES.items():
        image_runs={}; flow_sets={}
        for image_id in sorted(entries):
            data=inputs[image_id]
            analysis=orchestrate_junction_aware(
                data["legacyFlows"],components_in_image_coordinates(entries[image_id],ROOT/entries[image_id]["image"]),segments=data["segments"],
                adjacent_relations=data["adjacentRelations"],confirmed_direct_edges=data["confirmedDirectEdges"],human_confirmed_shortcuts=data["humanConfirmedShortcuts"],
                protected_candidate_ids=data["protectedCandidateIds"],structural_candidate_ids=data["structuralCandidateIds"],recovery_candidates=data["recoveryCandidates"],module_flags=flags,
            )
            applied=apply_integrated_decisions(data["legacyFlows"],analysis["candidateDecisions"],analysis["recoveryDecisions"])
            image_runs[image_id]={"analysis":analysis,"application":applied}; flow_sets[image_id]=applied["flows"]
        strategy_runs[strategy]={"images":image_runs,"flowSets":flow_sets,"metrics":_aggregate_metrics(entries,flow_sets)}
    full=strategy_runs["junction_aware_full"]

    decisions=[]; recoveries=[]; conflicts=[]; decision_by_record={}
    record_by_flow={(item["imageId"],item["predictedFlow"]["id"]):item for item in records}
    cases_by_record:dict[str,list[str]]=defaultdict(list)
    for case in review["cases"]:
        for record_id in case["recordIds"]: cases_by_record[record_id].append(case["caseId"])
    for image_id,image_run in full["images"].items():
        for decision in image_run["analysis"]["candidateDecisions"]:
            record=record_by_flow[(image_id,decision["candidateId"])]
            enriched={**decision,"inventoryId":record["inventoryId"],"imageId":image_id,"provider":entries[image_id]["provider"],"densityStratum":entries[image_id].get("densityStratum") or "unknown","benchmarkStatus":record["status"],"humanCases":sorted(cases_by_record.get(record["inventoryId"],[]))}
            decisions.append(enriched); decision_by_record[record["inventoryId"]]=enriched
        recoveries.extend({**item,"imageId":image_id,"humanCases":["C04"] if item.get("supervised") else []} for item in image_run["analysis"]["recoveryDecisions"])
        conflicts.extend({**item,"imageId":image_id} for item in image_run["analysis"]["moduleConflicts"])
    decisions.sort(key=lambda item:(item["imageId"],item["inventoryId"])); recoveries.sort(key=lambda item:(item["imageId"],item["id"])); conflicts.sort(key=lambda item:(item["imageId"],item["decisionId"]))

    human_cases=[]
    for case_id in (*ERROR_CASES,*CONTROL_CASES):
        case=next(item for item in review["cases"] if item["caseId"]==case_id)
        case_decisions=[decision_by_record[item] for item in case["recordIds"] if item in decision_by_record]
        if case_id=="C04":
            actions=["review_only"]; responsible="TL-004D"; agreement=True; outcome="supervised_shadow_recovery_not_applied"
        else:
            actions=sorted({item["finalAction"] for item in case_decisions})
            structural=case["review"]["primaryCause"]=="structural_line"
            if case["group"]=="control": agreement=bool(case_decisions) and all(item["finalAction"]=="keep" for item in case_decisions)
            elif structural: agreement=bool(case_decisions) and all(item["finalAction"]=="review_only" for item in case_decisions)
            else: agreement=bool(case_decisions) and all(item["finalAction"] in {"block","decompose","redirect"} for item in case_decisions)
            reason=" ".join(item["reason"] for item in case_decisions)
            responsible="TL-STRUCT-001" if structural else "TL-004E" if "transitive" in reason else "TL-004C" if "crossing" in reason else "TL-004B" if any(action in {"redirect","decompose"} for action in actions) else "integration"
            outcome="corrected_or_preserved" if agreement else "divergence_requires_review"
        human_cases.append({"caseId":case_id,"group":case["group"],"imageId":case["imageId"],"humanDecision":case["review"]["decision"],"humanPrimaryCause":case["review"]["primaryCause"],"integratedActions":actions,"agreement":agreement,"responsibleModule":responsible,"confidence":case["review"]["confidence"],"expectedCorrection":case["review"]["expectedStructuralCorrection"],"experimentalOutcome":outcome,"decisionIds":[item["id"] for item in case_decisions]})
    if len(human_cases)!=27: raise RuntimeError("all 27 reviewed cases must be represented")

    prior_index={item["caseId"]:item for item in prior_controls["controls"]}; review_index={item["caseId"]:item for item in review["cases"]}
    controls=[]
    for case_id in CONTROL_CASES:
        prior=prior_index[case_id]; case=review_index[case_id]; case_decisions=[decision_by_record[item] for item in case["recordIds"] if item in decision_by_record]
        preserved=(case_id=="C04" and all(item["finalAction"]=="review_only" and item["supervised"] for item in recoveries if "C04" in item["humanCases"])) or (case_id!="C04" and bool(case_decisions) and all(item["finalAction"]=="keep" for item in case_decisions))
        controls.append({"caseId":case_id,"requiredEdges":prior["requiredEdges"],"forbiddenEdges":prior["forbiddenEdges"],"legacyResult":"present" if case_id!="C04" else "missing","experimentalResult":"supervised_shadow_recovery" if case_id=="C04" else "preserved","responsibleModule":"TL-004D" if case_id=="C04" else "human_controls","decisionIds":[item["id"] for item in case_decisions],"status":"PASS" if preserved else "FAIL","preserved":preserved})
    controls_pass=all(item["preserved"] for item in controls)

    structural_records={record_id for case in review["cases"] if case["review"]["primaryCause"]=="structural_line" for record_id in case["recordIds"]}
    diagnostic_sets={image_id:[flow for flow in flows if record_by_flow.get((image_id,flow.get("id")),{}).get("inventoryId") not in structural_records] for image_id,flows in full["flowSets"].items()}
    diagnostic_metrics=_aggregate_metrics(entries,diagnostic_sets)
    per_image={image_id:structural_metrics(entries[image_id].get("flows") or [],full["flowSets"][image_id]) for image_id in sorted(entries)}
    by_provider=_group_metrics(entries,full["flowSets"],"provider"); by_density=_group_metrics(entries,full["flowSets"],"densityStratum")

    ablations=[]
    for strategy in STRATEGIES:
        metrics=strategy_runs[strategy]["metrics"]
        actions=Counter(decision["finalAction"] for run in strategy_runs[strategy]["images"].values() for decision in run["analysis"]["candidateDecisions"])
        ablations.append({"strategy":strategy,"moduleFlags":STRATEGIES[strategy],"metrics":metrics,"actionCounts":dict(sorted(actions.items())),"deltaVsLegacy":{"predictedEdgeCount":metrics["predictedEdgeCount"]-baseline["predictedEdgeCount"],"falsePositiveEdgeCount":metrics["falsePositiveEdgeCount"]-baseline["falsePositiveEdgeCount"],"correctAdjacencyCount":metrics["correctAdjacencyCount"]-baseline["correctAdjacencyCount"],"edgeExistenceF1":metrics["edgeExistenceF1"]-baseline["edgeExistenceF1"]}})

    action_metrics={}
    for group,items in sorted(defaultdict(list,{action:[item for item in decisions if item["finalAction"]==action] for action in sorted({item["finalAction"] for item in decisions})}).items()):
        action_metrics[group]={"candidateCount":len(items),"trueOrReversedCount":sum(item["benchmarkStatus"] in {"true_positive","reversed"} for item in items),"falsePositiveCount":sum(item["benchmarkStatus"]=="false_positive" for item in items),"appliedCount":sum(item["finalAction"]!="review_only" for item in items)}
    confidence_metrics={confidence:{"candidateCount":len(items),"falsePositiveCount":sum(item["benchmarkStatus"]=="false_positive" for item in items),"actionCounts":dict(Counter(item["finalAction"] for item in items))} for confidence,items in sorted(defaultdict(list,{value:[item for item in decisions if item["confidence"]==value] for value in sorted({item["confidence"] for item in decisions})}).items())}

    correct_legacy={(item["imageId"],item["predictedFlow"]["from"],item["predictedFlow"]["to"]) for item in records if item["status"]=="true_positive"}
    experimental_edges={(image_id,flow["from"],flow["to"]) for image_id,flows in full["flowSets"].items() for flow in flows}
    correct_directions_changed=len(correct_legacy-experimental_edges)
    possible_false_blocks=sum(item["benchmarkStatus"] in {"true_positive","reversed"} and item["finalAction"] in {"block","decompose"} for item in decisions)
    human_true_positive_blocked=sum(item["group"]=="control" and not item["agreement"] for item in human_cases)
    validation=_validation(validation_args)
    autonomous_c04=any(item["finalAction"]=="recover" and not item["supervised"] and "C04" in item["humanCases"] for item in recoveries)
    evidence_sufficient=autonomous_c04 and sum(item["finalAction"]=="review_only" for item in decisions)/len(decisions)<=0.25
    promotion=evaluate_promotion(full["metrics"],controls_pass=controls_pass,correct_directions_changed=correct_directions_changed,human_true_positives_blocked=human_true_positive_blocked,possible_false_blocks=possible_false_blocks,review_only_applied=0,gate_status=validation["v15Gate"]["status"] if validation["v15Gate"] else "FAIL",verifier_status=validation["projectVerification"]["status"] if validation["projectVerification"] else "FAIL",v12_status=validation["prospectiveV12"]["status"] if validation["prospectiveV12"] else "FAIL",tests_pass=bool(validation["fullSuite"] and validation["fullSuite"]["status"]=="PASS"),evidence_sufficient=evidence_sufficient)
    fixture_results=_fixture_results()
    criteria={"contractDocumented":True,"fixturesPass":fixture_results["status"]=="PASS","allAblationsExecuted":len(ablations)==8,"all27HumanCasesEvaluated":len(human_cases)==27,"controlsC01ToC07Pass":controls_pass,"legacySnapshotIdentical":legacy_snapshot["status"]=="PASS","officialLegacyFlowCount":len(records),"officialChanges":0,"defaultStrategy":"legacy","validationStatus":validation["status"],"holdoutExecutions":0}
    complete=all((criteria["contractDocumented"],criteria["fixturesPass"],criteria["allAblationsExecuted"],criteria["all27HumanCasesEvaluated"],criteria["controlsC01ToC07Pass"],criteria["legacySnapshotIdentical"],criteria["officialLegacyFlowCount"]==142,criteria["officialChanges"]==0,criteria["defaultStrategy"]=="legacy",criteria["validationStatus"]=="PASS",criteria["holdoutExecutions"]==0))
    final_decision="TL-004F concluída e elegível para promoção controlada" if complete and promotion["recommendation"]=="eligible_for_controlled_promotion" else "TL-004F concluída, permanecendo shadow-only" if complete else "TL-004F implementada, mas bloqueada por validação"

    artifacts={name:output_dir/filename for name,filename in {
        "contract":"integrated-strategy-contract.md","decisions":"candidate-final-decisions.json","flowSet":"experimental-flow-set.json","humanCases":"human-cases-comparison.json","controls":"control-cases-results.json","conflicts":"module-conflicts.json","ablations":"ablation-results.json","metrics":"structural-metrics-comparison.json","byImage":"metrics-by-image.json","byProvider":"metrics-by-provider.json","byDensity":"metrics-by-density.json","promotionCriteria":"promotion-criteria.json","promotionDecision":"promotion-decision.json","legacyShadow":"legacy-shadow-comparison.json","fixtures":"fixture-results.json","tests":"test-report.json","decision":"tl004f-decision.json"}.items()}
    artifacts["contract"].write_text(CONTRACT,encoding="utf-8")
    _write(artifacts["decisions"],{"schemaVersion":"1.0","split":"development_tuning","candidateCount":len(decisions),"recoveryDecisionCount":len(recoveries),"decisions":decisions,"recoveryDecisions":recoveries})
    _write(artifacts["flowSet"],{"schemaVersion":"1.0","split":"development_tuning","strategy":"junction_aware_full","officialApplied":False,"reviewOnlyAppliedCount":0,"flowSets":full["flowSets"],"applicationByImage":{image_id:run["application"] for image_id,run in full["images"].items()}})
    _write(artifacts["humanCases"],{"schemaVersion":"1.0","split":"development_tuning","caseCount":len(human_cases),"agreementCount":sum(item["agreement"] for item in human_cases),"cases":human_cases})
    _write(artifacts["controls"],{"schemaVersion":"1.0","split":"development_tuning","allControlsPass":controls_pass,"controls":controls})
    _write(artifacts["conflicts"],{"schemaVersion":"1.0","split":"development_tuning","conflictCount":len(conflicts),"conflicts":conflicts})
    _write(artifacts["ablations"],{"schemaVersion":"1.0","split":"development_tuning","legacyMetrics":baseline,"ablationCount":len(ablations),"ablations":ablations})
    _write(artifacts["metrics"],{"schemaVersion":"1.0","split":"development_tuning","official":{"legacy":baseline,"junctionAwareFull":full["metrics"]},"diagnosticExcludingConfirmedStructuralLines":diagnostic_metrics,"diagnosticOnly":True,"metricsByAction":action_metrics,"metricsByConfidence":confidence_metrics})
    _write(artifacts["byImage"],{"schemaVersion":"1.0","split":"development_tuning","metrics":per_image})
    _write(artifacts["byProvider"],{"schemaVersion":"1.0","split":"development_tuning","metrics":by_provider})
    _write(artifacts["byDensity"],{"schemaVersion":"1.0","split":"development_tuning","metrics":by_density})
    _write(artifacts["promotionCriteria"],{"schemaVersion":"1.0","split":"development_tuning","metrics":full["metrics"],"criteria":promotion["checks"],"evidenceSufficient":promotion["evidenceSufficient"],"falsePositiveReduction":promotion["falsePositiveReduction"],"falsePositiveReductionRate":promotion["falsePositiveReductionRate"]})
    _write(artifacts["promotionDecision"],{"schemaVersion":"1.0","recommendation":promotion["recommendation"],"allCriteriaPassed":promotion["allCriteriaPassed"],"defaultStrategyChanged":False,"defaultStrategy":"legacy","reason":"Promotion is a recommendation only; no runtime default was changed."})
    _write(artifacts["legacyShadow"],{"schemaVersion":"1.0","split":"development_tuning","officialStrategy":"legacy","shadowStrategy":"junction_aware_full","legacyCandidateCount":len(records),"experimentalEdgeCount":full["metrics"]["predictedEdgeCount"],"officialEdgesChanged":0,"officialDirectionChanges":0,"feedsStride":"legacy_only","legacySnapshot":legacy_snapshot})
    _write(artifacts["fixtures"],fixture_results)
    _write(artifacts["tests"],{"schemaVersion":"1.0","scope":"TL-004F","split":"development_tuning","validation":validation})
    _write(artifacts["decision"],{"schemaVersion":"1.0","scope":"TL-004F","criteria":criteria,"promotionRecommendation":promotion["recommendation"],"decision":final_decision,"defaultStrategyChanged":False,"structuralTaskStarted":False})
    return {"status":"passed" if complete else "pending_validation","split":"development_tuning","legacyMetrics":baseline,"experimentalMetrics":full["metrics"],"promotionRecommendation":promotion["recommendation"],"humanAgreementCount":sum(item["agreement"] for item in human_cases),"controlsPass":controls_pass,"conflictCount":len(conflicts),"artifacts":{name:_relative(path) for name,path in artifacts.items()}}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT); parser.add_argument("--specific-tests-run",type=int); parser.add_argument("--specific-test-failures",type=int,default=0); parser.add_argument("--full-tests-run",type=int,default=0); parser.add_argument("--full-test-failures",type=int,default=0); parser.add_argument("--gate-report",type=str); parser.add_argument("--verifier-status",choices=("PASS","FAIL"),default="FAIL"); parser.add_argument("--v12-status",choices=("PASS","FAIL"),default="FAIL"); args=parser.parse_args()
    validation_args=args if args.specific_tests_run is not None else None
    if validation_args and not args.gate_report: parser.error("--gate-report is required with validation results")
    result=build_artifacts(args.output,validation_args); print(json.dumps(result,indent=2,ensure_ascii=False)); raise SystemExit(0 if result["status"] in {"passed","pending_validation"} else 1)


if __name__=="__main__": main()
