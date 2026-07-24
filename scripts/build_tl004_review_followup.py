"""Build the reduced TL-004 confirmation batch without changing the detector."""

from __future__ import annotations

import argparse
import copy
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_tl004_review_batch import (
    CAUSE_OPTIONS,
    DEFAULT_BENCHMARK,
    DEFAULT_INVENTORY,
    DEFAULT_TEMPLATE,
    ROOT,
    _collect_involved_ids,
    _record_payload,
    _relative,
    load_sources,
    render_visualization,
)
from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


DEFAULT_OUTPUT = ROOT / "data/reviews/tl004-junction-aware/batch-02"
DEFAULT_PREVIOUS_MANIFEST = (
    ROOT / "data/reviews/tl004-junction-aware/batch-01/review-manifest.json"
)
DEFAULT_PREVIOUS_RESULT = (
    ROOT / "data/reviews/tl004-junction-aware/batch-01/review-result.json"
)
DEFAULT_PREVIOUS_ANALYSIS = (
    ROOT / "data/reviews/tl004-junction-aware/batch-01/review-analysis.json"
)

ERROR_CASES = (
    {
        "caseId": "E15",
        "title": "Ramo da Lambda associado ao DynamoDB no EKS",
        "recordIds": ("isolated_ground_truth:aws-eks-platform:predicted:13",),
        "focus": (
            "incorrect_bifurcation",
            "parallel_connectors",
            "high_density_context",
            "excessive_hops",
        ),
    },
    {
        "caseId": "E16",
        "title": "Comprehend associado ao ramo do Glue no EKS",
        "recordIds": ("isolated_ground_truth:aws-eks-platform:predicted:12",),
        "focus": (
            "incorrect_bifurcation",
            "parallel_connectors",
            "high_density_context",
        ),
    },
    {
        "caseId": "E17",
        "title": "Linha densa entre usuario e banco generico",
        "recordIds": ("isolated_ground_truth:generic-cloud-api:predicted:14",),
        "focus": (
            "crossing",
            "incorrect_bifurcation",
            "high_density_context",
            "ambiguous_endpoint",
        ),
    },
    {
        "caseId": "E18",
        "title": "Tronco do App Gateway associado aos Build Agents",
        "recordIds": (
            "isolated_ground_truth:azure-private-ai-platform:predicted:10",
        ),
        "focus": (
            "crossing",
            "incorrect_bifurcation",
            "parallel_connectors",
            "shared_trunk",
            "excessive_hops",
        ),
    },
    {
        "caseId": "E19",
        "title": "Cruzamento entre Cloud Armor e Artifact Registry",
        "recordIds": ("isolated_ground_truth:gcp-secure-cloud-run:predicted:7",),
        "focus": ("crossing", "incorrect_bifurcation", "parallel_connectors"),
    },
    {
        "caseId": "E20",
        "title": "Ramo do transcoder associado ao terceiro estagio",
        "recordIds": ("isolated_ground_truth:aws-video-pipeline:predicted:8",),
        "focus": ("crossing", "incorrect_bifurcation", "parallel_connectors"),
    },
)

CONTROL_CASES = (
    {
        "caseId": "C05",
        "title": "Controle denso de fan-in no Storage",
        "recordIds": (
            "isolated_ground_truth:generic-cloud-api:predicted:4",
            "isolated_ground_truth:generic-cloud-api:predicted:8",
        ),
        "focus": (
            "valid_fan_in",
            "valid_junction",
            "high_density_context",
            "shared_trunk_protection",
        ),
    },
    {
        "caseId": "C06",
        "title": "Controle denso de fan-in no Foundry Agent",
        "recordIds": (
            "isolated_ground_truth:azure-ai-foundry:predicted:1",
            "isolated_ground_truth:azure-ai-foundry:predicted:5",
        ),
        "focus": (
            "valid_fan_in",
            "valid_junction",
            "high_density_context",
            "shared_trunk_protection",
        ),
    },
    {
        "caseId": "C07",
        "title": "Controle de fan-out do aplicativo movel",
        "recordIds": (
            "isolated_ground_truth:aws-video-pipeline:predicted:1",
            "isolated_ground_truth:aws-video-pipeline:predicted:41",
        ),
        "focus": ("valid_fan_out", "valid_junction", "shared_trunk_protection"),
    },
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_selection(
    records: dict[str, dict],
    entries: dict[str, dict],
    previous_manifest: dict[str, Any],
    previous_result: dict[str, Any],
    previous_analysis: dict[str, Any],
) -> dict[str, Any]:
    selected = [*ERROR_CASES, *CONTROL_CASES]
    if len(selected) not in range(8, 11):
        raise ValueError("The confirmation batch must contain 8 to 10 cases.")
    if previous_result.get("batchId") != previous_manifest.get("batchId"):
        raise ValueError("Previous review result does not match its manifest.")
    decision = (previous_analysis.get("nextStepDecision") or {}).get("action")
    if decision != "generate_batch_02":
        raise ValueError("The completed review does not authorize batch 02.")

    case_ids = [str(spec["caseId"]) for spec in selected]
    record_ids = [str(item) for spec in selected for item in spec["recordIds"]]
    if len(case_ids) != len(set(case_ids)) or len(record_ids) != len(set(record_ids)):
        raise ValueError("Follow-up case and record IDs must be unique.")
    previous_record_ids = {
        str(record["inventoryId"])
        for case in previous_manifest.get("cases") or []
        for record in case.get("records") or []
    }
    overlap = sorted(previous_record_ids.intersection(record_ids))
    if overlap:
        raise ValueError(f"Follow-up records already appeared in batch 01: {overlap}")
    missing = sorted(set(record_ids) - set(records))
    if missing:
        raise ValueError(f"Selected diagnostic records are missing: {missing}")

    for spec in ERROR_CASES:
        record = records[spec["recordIds"][0]]
        if record["status"] != "false_positive":
            raise ValueError(f"Error case {spec['caseId']} is not a false positive.")
        if record["predictedFlow"]["evidence"] != "segment_graph":
            raise ValueError(f"Error case {spec['caseId']} is not produced by segment_graph.")
    for spec in CONTROL_CASES:
        for record_id in spec["recordIds"]:
            if records[record_id]["status"] != "true_positive":
                raise ValueError(f"Control record {record_id} is not a true positive.")
    for record_id in record_ids:
        if records[record_id]["imageId"] not in entries:
            raise ValueError(f"Selected record is outside development_tuning: {record_id}")

    focus = {tag for spec in selected for tag in spec["focus"]}
    required_focus = {
        "crossing",
        "incorrect_bifurcation",
        "parallel_connectors",
        "high_density_context",
        "valid_fan_in",
        "valid_fan_out",
        "valid_junction",
        "shared_trunk_protection",
    }
    if not required_focus.issubset(focus):
        raise ValueError(f"Follow-up focus is incomplete: {sorted(required_focus - focus)}")
    high_density_cases = sum(
        records[spec["recordIds"][0]]["diagnostic"]["diagramDensity"]["stratum"]
        == "high"
        for spec in selected
    )
    if high_density_cases < 5:
        raise ValueError("At least five follow-up cases must be high-density examples.")
    return {
        "errorCaseCount": len(ERROR_CASES),
        "controlCaseCount": len(CONTROL_CASES),
        "totalCaseCount": len(selected),
        "highDensityCaseCount": high_density_cases,
        "imageCount": len(
            {records[spec["recordIds"][0]]["imageId"] for spec in selected}
        ),
        "coveredFocus": sorted(focus),
        "previousRecordOverlapCount": 0,
    }


def build_batch(
    output_dir: Path = DEFAULT_OUTPUT,
    inventory_path: Path = DEFAULT_INVENTORY,
    benchmark_path: Path = DEFAULT_BENCHMARK,
    template_path: Path = DEFAULT_TEMPLATE,
    previous_manifest_path: Path = DEFAULT_PREVIOUS_MANIFEST,
    previous_result_path: Path = DEFAULT_PREVIOUS_RESULT,
    previous_analysis_path: Path = DEFAULT_PREVIOUS_ANALYSIS,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.relative_to(ROOT)
    records, entries = load_sources(inventory_path, benchmark_path)
    previous_manifest = _load_json(previous_manifest_path)
    previous_result = _load_json(previous_result_path)
    previous_analysis = _load_json(previous_analysis_path)
    coverage = validate_selection(
        records, entries, previous_manifest, previous_result, previous_analysis
    )
    cases: list[dict[str, Any]] = []
    all_specs = [
        *(("error", spec) for spec in ERROR_CASES),
        *(("control", spec) for spec in CONTROL_CASES),
    ]
    for order, (group, spec) in enumerate(all_specs, start=1):
        selected_records = [records[record_id] for record_id in spec["recordIds"]]
        image_ids = {str(record["imageId"]) for record in selected_records}
        if len(image_ids) != 1:
            raise ValueError(f"Review case {spec['caseId']} spans multiple images.")
        image_id = image_ids.pop()
        entry = entries[image_id]
        image_path = ROOT / entry["image"]
        components = components_in_image_coordinates(entry, image_path)
        involved_ids = _collect_involved_ids(selected_records)
        traversed_ids = {
            str(component_id)
            for record in selected_records
            for component_id in record["diagnostic"].get("componentsTraversedByPath") or []
        }
        component_payload = [
            {
                "id": str(component["id"]),
                "name": str(component.get("name") or component["id"]),
                "type": str(component.get("type") or "unknown"),
                "bbox": copy.deepcopy(component.get("bbox")),
                "role": "traversed" if str(component["id"]) in traversed_ids else "endpoint",
            }
            for component in components
            if str(component["id"]) in involved_ids
        ]
        visualization_path = output_dir / "crops" / f"{spec['caseId']}.png"
        visualization = render_visualization(
            spec["caseId"], image_path, components, selected_records, visualization_path
        )
        cases.append(
            {
                "caseId": spec["caseId"],
                "order": order,
                "group": group,
                "title": spec["title"],
                "imageId": image_id,
                "provider": selected_records[0]["provider"],
                "densityStratum": selected_records[0]["diagnostic"]["diagramDensity"]["stratum"],
                "sourceImage": entry["image"],
                "visualization": f"crops/{spec['caseId']}.png",
                "visualizationMetadata": visualization,
                "focus": list(spec["focus"]),
                "records": [_record_payload(record) for record in selected_records],
                "components": component_payload,
                "automaticHypotheses": sorted(
                    {
                        label
                        for record in selected_records
                        for label in record.get("candidateLabels") or []
                    }
                ),
                "humanReview": {
                    "decision": None,
                    "primaryCause": None,
                    "contributingCauses": [],
                    "tl004Scope": None,
                    "confidence": None,
                    "observations": "",
                    "expectedStructuralCorrection": "",
                    "newCategory": "",
                    "reviewer": "",
                    "reviewedAt": None,
                },
            }
        )

    manifest = {
        "schemaVersion": "1.0",
        "batchId": "tl004-junction-review-batch-02",
        "submissionToken": secrets.token_urlsafe(32),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "split": "development_tuning",
        "sourceInventory": _relative(inventory_path),
        "sourceBenchmark": _relative(benchmark_path),
        "sourcePreviousManifest": _relative(previous_manifest_path),
        "sourcePreviousReviewResult": _relative(previous_result_path),
        "sourcePreviousReviewAnalysis": _relative(previous_analysis_path),
        "selectionPolicy": {
            "type": "stratified_confirmation_batch",
            "humanCausePreselected": False,
            "triggerChecks": previous_analysis["nextStepDecision"]["triggerChecks"],
            "targetGaps": [
                "crossing_without_junction",
                "parallel_connector_merge",
                "incorrect_bifurcation",
                "valid_dense_junctions",
                "shared_trunk_fan_in_fan_out",
            ],
            "stopRule": "Stop after two consecutive completed batches reveal no relevant new cause.",
        },
        "coverage": coverage,
        "causeOptions": list(CAUSE_OPTIONS),
        "cases": cases,
        "batchAssessment": {
            "reviewer": "",
            "completedAt": None,
            "newRelevantCategoriesFound": None,
            "newCategories": "",
            "categoriesNeedingMoreExamples": "",
            "validInvalidDistinctionResolved": None,
            "observations": "",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "review-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    template = template_path.read_text(encoding="utf-8")
    embedded = json.dumps(manifest, ensure_ascii=True).replace("</", "<\\/")
    (output_dir / "index.html").write_text(
        template.replace("__BATCH_DATA__", embedded), encoding="utf-8"
    )
    (output_dir / "README.md").write_text(
        "\n".join(
            (
                "# TL-004 Human Review - Batch 02",
                "",
                "Review the nine confirmation cases and export the JSON result.",
                "This batch contains only development_tuning records not used in batch 01.",
                "",
                f"- Errors: {coverage['errorCaseCount']}",
                f"- Controls: {coverage['controlCaseCount']}",
                f"- Total: {coverage['totalCaseCount']}",
                f"- High-density cases: {coverage['highDensityCaseCount']}",
                "- Human causes preselected: no",
                "",
                "Stop the review if this completed batch adds no relevant cause. Together with batch 01,",
                "that satisfies the two-consecutive-batches stopping rule.",
            )
        ),
        encoding="utf-8",
    )
    return {
        "status": "passed",
        "batchId": manifest["batchId"],
        "coverage": coverage,
        "artifacts": {
            "review": _relative(output_dir / "index.html"),
            "manifest": _relative(manifest_path),
            "readme": _relative(output_dir / "README.md"),
            "crops": _relative(output_dir / "crops"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--previous-manifest", type=Path, default=DEFAULT_PREVIOUS_MANIFEST)
    parser.add_argument("--previous-result", type=Path, default=DEFAULT_PREVIOUS_RESULT)
    parser.add_argument("--previous-analysis", type=Path, default=DEFAULT_PREVIOUS_ANALYSIS)
    args = parser.parse_args()
    result = build_batch(
        args.output,
        args.inventory,
        args.benchmark,
        args.template,
        args.previous_manifest,
        args.previous_result,
        args.previous_analysis,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
