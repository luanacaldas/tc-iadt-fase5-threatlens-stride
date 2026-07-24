"""Build the first stratified human-review batch for TL-004 without changing the detector."""

from __future__ import annotations

import argparse
import copy
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_real_architecture_benchmark import components_in_image_coordinates


DEFAULT_INVENTORY = ROOT / "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-inventory.json"
DEFAULT_BENCHMARK = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"
DEFAULT_TEMPLATE = ROOT / "scripts/templates/tl004-review.html"
DEFAULT_OUTPUT = ROOT / "data/reviews/tl004-junction-aware/batch-01"

ERROR_CASES = (
    {
        "caseId": "E01",
        "title": "Caminho compartilhado entre banco e trigger",
        "recordIds": ("isolated_ground_truth:aws-video-pipeline:predicted:6",),
        "focus": ("incorrect_bifurcation", "parallel_connectors", "ambiguous_endpoint"),
    },
    {
        "caseId": "E02",
        "title": "Cruzamento entre funcoes de negocio",
        "recordIds": ("isolated_ground_truth:aws-video-pipeline:predicted:7",),
        "focus": ("crossing", "incorrect_bifurcation", "parallel_connectors"),
    },
    {
        "caseId": "E03",
        "title": "Atalho atravessando o terceiro estagio",
        "recordIds": ("isolated_ground_truth:aws-video-pipeline:predicted:31",),
        "focus": ("component_passthrough", "transitive_shortcut", "parallel_connectors"),
    },
    {
        "caseId": "E04",
        "title": "Tronco privado associado ao Bastion",
        "recordIds": ("isolated_ground_truth:azure-private-ai-platform:predicted:2",),
        "focus": ("crossing", "incorrect_bifurcation", "ambiguous_endpoint"),
    },
    {
        "caseId": "E05",
        "title": "Conector atravessando AI Search",
        "recordIds": ("isolated_ground_truth:azure-private-ai-platform:predicted:4",),
        "focus": ("component_passthrough", "parallel_connectors"),
    },
    {
        "caseId": "E06",
        "title": "Rota longa entre Firewall e Foundry Agent",
        "recordIds": ("isolated_ground_truth:azure-private-ai-platform:predicted:20",),
        "focus": ("crossing", "incorrect_bifurcation", "excessive_hops"),
    },
    {
        "caseId": "E07",
        "title": "Glue conectado ao RDS atraves do DynamoDB",
        "recordIds": ("isolated_ground_truth:aws-eks-platform:predicted:6",),
        "focus": ("component_passthrough", "transitive_shortcut", "parallel_connectors"),
    },
    {
        "caseId": "E08",
        "title": "Lambda conectado ao Glue atraves de Microservices",
        "recordIds": ("isolated_ground_truth:aws-eks-platform:predicted:18",),
        "focus": ("component_passthrough", "transitive_shortcut", "incorrect_bifurcation"),
    },
    {
        "caseId": "E09",
        "title": "Internet conectada diretamente ao Cloud Armor",
        "recordIds": ("isolated_ground_truth:gcp-secure-cloud-run:predicted:3",),
        "focus": ("component_passthrough", "transitive_shortcut", "fan_in_protection"),
    },
    {
        "caseId": "E10",
        "title": "Load Balancer conectado diretamente ao VPC Connector",
        "recordIds": ("isolated_ground_truth:gcp-secure-cloud-run:predicted:9",),
        "focus": ("component_passthrough", "transitive_shortcut"),
    },
    {
        "caseId": "E11",
        "title": "Linha do Compute associada ao Database",
        "recordIds": ("isolated_ground_truth:generic-cloud-api:predicted:6",),
        "focus": ("ambiguous_endpoint", "parallel_connectors"),
    },
    {
        "caseId": "E12",
        "title": "Linha vertical de grade interpretada como fluxo",
        "recordIds": ("isolated_ground_truth:generic-cloud-api:predicted:13",),
        "focus": ("crossing", "ambiguous_endpoint", "structural_line"),
    },
    {
        "caseId": "E13",
        "title": "Conta Foundry conectada diretamente ao modelo",
        "recordIds": ("isolated_ground_truth:azure-ai-foundry:predicted:4",),
        "focus": ("crossing", "transitive_shortcut", "parallel_connectors"),
    },
    {
        "caseId": "E14",
        "title": "API Handler conectado diretamente ao Worker",
        "recordIds": ("isolated_ground_truth:aws-serverless-async:predicted:6",),
        "focus": ("transitive_shortcut", "incorrect_bifurcation"),
    },
)

CONTROL_CASES = (
    {
        "caseId": "C01",
        "title": "Controle de fan-in no Load Balancer",
        "recordIds": (
            "isolated_ground_truth:gcp-secure-cloud-run:predicted:1",
            "isolated_ground_truth:gcp-secure-cloud-run:predicted:2",
        ),
        "focus": ("valid_fan_in", "junction_protection"),
    },
    {
        "caseId": "C02",
        "title": "Controle de fan-out no API Handler",
        "recordIds": (
            "isolated_ground_truth:aws-serverless-async:predicted:3",
            "isolated_ground_truth:aws-serverless-async:predicted:5",
        ),
        "focus": ("valid_fan_out", "shared_trunk_protection"),
    },
    {
        "caseId": "C03",
        "title": "Controle de fan-out no Foundry Agent",
        "recordIds": (
            "isolated_ground_truth:azure-ai-foundry:predicted:2",
            "isolated_ground_truth:azure-ai-foundry:predicted:3",
        ),
        "focus": ("valid_fan_out", "parallel_branch_protection"),
    },
    {
        "caseId": "C04",
        "title": "Controle de juncoes reais no barramento privado",
        "recordIds": (
            "isolated_ground_truth:azure-private-ai-platform:missed:3",
            "isolated_ground_truth:azure-private-ai-platform:missed:4",
        ),
        "focus": ("valid_junction", "missing_fan_out", "shared_trunk_protection"),
    },
)

CAUSE_OPTIONS = (
    {"value": "crossing_without_junction", "label": "Cruzamento sem juncao"},
    {"value": "transitive_shortcut", "label": "Atalho transitivo"},
    {"value": "component_passthrough", "label": "Passagem atraves de componente"},
    {"value": "incorrect_bifurcation", "label": "Bifurcacao incorreta"},
    {"value": "parallel_connector_merge", "label": "Mescla de conectores paralelos"},
    {"value": "ambiguous_endpoint", "label": "Associacao ambigua de endpoint"},
    {"value": "structural_line", "label": "Grade, borda ou linha estrutural"},
    {"value": "valid_junction_or_branch", "label": "Juncao, fan-in ou fan-out valido"},
    {"value": "annotation_or_ontology", "label": "Problema de anotacao ou ontologia"},
    {"value": "outside_tl004", "label": "Fora do escopo da TL-004"},
    {"value": "new_category", "label": "Nova categoria"},
    {"value": "inconclusive", "label": "Inconclusivo"},
)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources(inventory_path: Path, benchmark_path: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    inventory = _load_json(inventory_path)
    benchmark = _load_json(benchmark_path)
    records = {str(item["inventoryId"]): item for item in inventory["records"]}
    entries = {
        str(item["id"]): item
        for item in benchmark["entries"]
        if item.get("split") == "development_tuning"
    }
    return records, entries


def validate_selection(records: dict[str, dict], entries: dict[str, dict]) -> dict:
    selected = [*ERROR_CASES, *CONTROL_CASES]
    case_ids = [item["caseId"] for item in selected]
    record_ids = [record_id for item in selected for record_id in item["recordIds"]]
    if len(ERROR_CASES) not in range(12, 16):
        raise ValueError("The initial error sample must contain 12 to 15 cases.")
    if len(CONTROL_CASES) not in range(3, 6):
        raise ValueError("The control sample must contain 3 to 5 cases.")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Review case IDs must be unique.")
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("A diagnostic record cannot appear in more than one review case.")
    missing = sorted(set(record_ids) - set(records))
    if missing:
        raise ValueError(f"Selected diagnostic records are missing: {missing}")

    for spec in ERROR_CASES:
        item = records[spec["recordIds"][0]]
        if item["status"] != "false_positive" or item["predictedFlow"]["evidence"] != "segment_graph":
            raise ValueError(f"Error case {spec['caseId']} is not a segment_graph false positive.")
    for record_id in record_ids:
        image_id = str(records[record_id]["imageId"])
        if image_id not in entries:
            raise ValueError(f"Selected record is not in development_tuning: {record_id}")

    focus = {tag for item in selected for tag in item["focus"]}
    required_focus = {
        "crossing",
        "component_passthrough",
        "transitive_shortcut",
        "incorrect_bifurcation",
        "parallel_connectors",
        "ambiguous_endpoint",
        "valid_fan_in",
        "valid_fan_out",
        "valid_junction",
    }
    missing_focus = sorted(required_focus - focus)
    if missing_focus:
        raise ValueError(f"Review strata are incomplete: {missing_focus}")

    top_images = {"aws-video-pipeline", "azure-private-ai-platform", "aws-eks-platform"}
    top_image_cases = sum(
        records[spec["recordIds"][0]]["imageId"] in top_images for spec in ERROR_CASES
    )
    return {
        "errorCaseCount": len(ERROR_CASES),
        "controlCaseCount": len(CONTROL_CASES),
        "totalCaseCount": len(selected),
        "topImageErrorCaseCount": top_image_cases,
        "coveredFocus": sorted(focus),
    }


def _flow_text(flow: dict | None) -> str:
    return f"{flow['from']} -> {flow['to']}" if flow else "nenhum fluxo"


def _collect_involved_ids(records: list[dict]) -> set[str]:
    involved: set[str] = set()
    for record in records:
        for flow in (record.get("predictedFlow"), record.get("expectedFlow")):
            if flow:
                involved.update((str(flow["from"]), str(flow["to"])))
        involved.update(str(item) for item in record["diagnostic"].get("componentsTraversedByPath") or [])
    return involved


def _component_center(component: dict) -> tuple[float, float]:
    x1, y1, x2, y2 = component["bbox"]
    return (float(x1 + x2) / 2, float(y1 + y2) / 2)


def _expand_crop(
    bounds: tuple[float, float, float, float], image_size: tuple[int, int]
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bounds
    width, height = image_size
    span_x, span_y = max(1.0, x2 - x1), max(1.0, y2 - y1)
    padding_x, padding_y = max(70.0, span_x * 0.12), max(70.0, span_y * 0.18)
    x1, y1, x2, y2 = x1 - padding_x, y1 - padding_y, x2 + padding_x, y2 + padding_y
    minimum_width, minimum_height = min(620, width), min(420, height)
    if x2 - x1 < minimum_width:
        center = (x1 + x2) / 2
        x1, x2 = center - minimum_width / 2, center + minimum_width / 2
    if y2 - y1 < minimum_height:
        center = (y1 + y2) / 2
        y1, y2 = center - minimum_height / 2, center + minimum_height / 2
    return (
        max(0, int(x1)),
        max(0, int(y1)),
        min(width, int(x2 + 0.5)),
        min(height, int(y2 + 0.5)),
    )


def _dashed_line(
    drawing: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: str,
    width: int,
) -> None:
    import math

    distance = math.hypot(end[0] - start[0], end[1] - start[1])
    if distance <= 0:
        return
    dash, gap = max(10, width * 3), max(7, width * 2)
    offset = 0.0
    while offset < distance:
        finish = min(distance, offset + dash)
        first = offset / distance
        second = finish / distance
        drawing.line(
            (
                start[0] + (end[0] - start[0]) * first,
                start[1] + (end[1] - start[1]) * first,
                start[0] + (end[0] - start[0]) * second,
                start[1] + (end[1] - start[1]) * second,
            ),
            fill=fill,
            width=width,
        )
        offset += dash + gap


def _draw_label(
    drawing: ImageDraw.ImageDraw,
    point: tuple[int, int],
    text: str,
    fill: str,
    font: ImageFont.ImageFont,
) -> None:
    x, y = point
    box = drawing.textbbox((x, y), text, font=font)
    drawing.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill="#ffffff")
    drawing.text((x, y), text, fill=fill, font=font)


def render_visualization(
    case_id: str,
    source_path: Path,
    components: list[dict],
    records: list[dict],
    output_path: Path,
) -> dict:
    with Image.open(source_path) as original:
        image = original.convert("RGB")
    width, height = image.size
    component_index = {str(item["id"]): item for item in components}
    involved_ids = _collect_involved_ids(records)
    geometry: list[tuple[float, float]] = []
    for component_id in involved_ids:
        component = component_index.get(component_id)
        if component:
            x1, y1, x2, y2 = component["bbox"]
            geometry.extend(((x1, y1), (x2, y2)))
    for record in records:
        geometry.extend(
            (float(point[0]), float(point[1]))
            for point in (record.get("predictedFlow") or {}).get("pathPoints") or []
        )
    if not geometry:
        crop_box = (0, 0, width, height)
    else:
        xs, ys = [item[0] for item in geometry], [item[1] for item in geometry]
        crop_box = _expand_crop((min(xs), min(ys), max(xs), max(ys)), image.size)

    drawing = ImageDraw.Draw(image)
    stroke = max(4, round(min(width, height) * 0.004))
    font = ImageFont.load_default()
    traversed_ids = {
        str(item)
        for record in records
        for item in record["diagnostic"].get("componentsTraversedByPath") or []
    }
    expected_ids = {
        str(flow[key])
        for record in records
        for flow in (record.get("expectedFlow"),)
        if flow
        for key in ("from", "to")
    }
    predicted_source_ids = {
        str(record["predictedFlow"]["from"]) for record in records if record.get("predictedFlow")
    }
    predicted_target_ids = {
        str(record["predictedFlow"]["to"]) for record in records if record.get("predictedFlow")
    }

    for component_id in sorted(involved_ids):
        component = component_index.get(component_id)
        if not component:
            continue
        if component_id in traversed_ids:
            color = "#7c3aed"
        elif component_id in predicted_source_ids:
            color = "#c62828"
        elif component_id in predicted_target_ids:
            color = "#e65100"
        elif component_id in expected_ids:
            color = "#087f5b"
        else:
            color = "#155e75"
        bbox = tuple(int(value) for value in component["bbox"])
        drawing.rectangle(bbox, outline=color, width=stroke)
        _draw_label(drawing, (bbox[0] + 3, max(2, bbox[1] - 16)), component_id, color, font)

    for record in records:
        predicted = record.get("predictedFlow")
        path = (predicted or {}).get("pathPoints") or []
        if len(path) >= 2:
            points = [(int(point[0]), int(point[1])) for point in path]
            drawing.line(points, fill="#d32f2f", width=stroke + 2, joint="curve")
            radius = stroke * 2
            for point, color in ((points[0], "#c62828"), (points[-1], "#e65100")):
                drawing.ellipse(
                    (point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius),
                    fill=color,
                    outline="#ffffff",
                    width=max(1, stroke // 2),
                )
        expected = record.get("expectedFlow")
        if expected and not predicted:
            source = component_index.get(str(expected["from"]))
            target = component_index.get(str(expected["to"]))
            if source and target:
                _dashed_line(
                    drawing,
                    _component_center(source),
                    _component_center(target),
                    "#087f5b",
                    stroke,
                )

    crop = image.crop(crop_box)
    crop.thumbnail((1600, 1000), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(output_path, format="PNG", optimize=True)
    return {
        "cropBox": list(crop_box),
        "sourceImageSize": [width, height],
        "renderedImageSize": list(crop.size),
    }


def _record_payload(record: dict) -> dict:
    predicted = copy.deepcopy(record.get("predictedFlow"))
    expected = copy.deepcopy(record.get("expectedFlow"))
    return {
        "inventoryId": record["inventoryId"],
        "status": record["status"],
        "predictedFlow": predicted,
        "predictedFlowText": _flow_text(predicted),
        "expectedFlow": expected,
        "expectedFlowText": _flow_text(expected),
        "detectedPath": copy.deepcopy((predicted or {}).get("pathPoints") or []),
        "evidence": (predicted or {}).get("evidence"),
        "candidateLabels": copy.deepcopy(record.get("candidateLabels") or []),
        "componentsTraversedByPath": copy.deepcopy(
            record["diagnostic"].get("componentsTraversedByPath") or []
        ),
        "segmentHops": (predicted or {}).get("segmentHops"),
        "routeEfficiency": (predicted or {}).get("routeEfficiency"),
        "endpointAssociation": copy.deepcopy(
            record["diagnostic"].get("endpointAssociation") or {}
        ),
    }


def build_batch(
    output_dir: Path = DEFAULT_OUTPUT,
    inventory_path: Path = DEFAULT_INVENTORY,
    benchmark_path: Path = DEFAULT_BENCHMARK,
    template_path: Path = DEFAULT_TEMPLATE,
) -> dict:
    output_dir = output_dir.resolve()
    output_dir.relative_to(ROOT)
    records, entries = load_sources(inventory_path, benchmark_path)
    coverage = validate_selection(records, entries)
    cases = []
    all_specs = [
        *(("error", item) for item in ERROR_CASES),
        *(("control", item) for item in CONTROL_CASES),
    ]
    for order, (group, spec) in enumerate(all_specs, start=1):
        selected_records = [records[record_id] for record_id in spec["recordIds"]]
        image_ids = {str(item["imageId"]) for item in selected_records}
        if len(image_ids) != 1:
            raise ValueError(f"Review case {spec['caseId']} spans multiple images.")
        image_id = image_ids.pop()
        entry = entries[image_id]
        image_path = ROOT / entry["image"]
        components = components_in_image_coordinates(entry, image_path)
        involved_ids = _collect_involved_ids(selected_records)
        component_payload = [
            {
                "id": str(item["id"]),
                "name": str(item.get("name") or item["id"]),
                "type": str(item.get("type") or "unknown"),
                "bbox": copy.deepcopy(item.get("bbox")),
                "role": (
                    "traversed"
                    if str(item["id"])
                    in {
                        str(value)
                        for record in selected_records
                        for value in record["diagnostic"].get("componentsTraversedByPath") or []
                    }
                    else "endpoint"
                ),
            }
            for item in components
            if str(item["id"]) in involved_ids
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
                "records": [_record_payload(item) for item in selected_records],
                "components": component_payload,
                "automaticHypotheses": sorted(
                    {
                        label
                        for item in selected_records
                        for label in item.get("candidateLabels") or []
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

    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schemaVersion": "1.0",
        "batchId": "tl004-junction-review-batch-01",
        "submissionToken": secrets.token_urlsafe(32),
        "generatedAt": generated_at,
        "split": "development_tuning",
        "sourceInventory": _relative(inventory_path),
        "sourceBenchmark": _relative(benchmark_path),
        "selectionPolicy": {
            "type": "stratified_initial_batch",
            "allErrorCasesUseSegmentGraph": True,
            "humanCausePreselected": False,
            "secondBatchSize": "8-10",
            "secondBatchConditions": [
                "underrepresented_categories",
                "ambiguous_causes",
                "new_patterns",
                "valid_and_invalid_connections_not_distinguishable",
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
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")
    embedded = json.dumps(manifest, ensure_ascii=True).replace("</", "<\\/")
    (output_dir / "index.html").write_text(
        template.replace("__BATCH_DATA__", embedded), encoding="utf-8"
    )
    (output_dir / "README.md").write_text(
        "\n".join(
            (
                "# TL-004 Human Review - Batch 01",
                "",
                "Open `index.html` in a browser, review every case, and export the JSON result.",
                "The page stores progress locally in the browser and does not call the backend.",
                "",
                f"- Errors: {coverage['errorCaseCount']}",
                f"- Controls: {coverage['controlCaseCount']}",
                f"- Total: {coverage['totalCaseCount']}",
                "- Split: `development_tuning`",
                "- Human causes preselected: no",
                "",
                "Do not generate batch 02 until the exported result has been evaluated against the batch policy.",
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
    args = parser.parse_args()
    result = build_batch(args.output, args.inventory, args.benchmark, args.template)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
