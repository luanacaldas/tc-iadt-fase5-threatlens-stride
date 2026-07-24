"""Audit real benchmark hashes, annotation contracts, and holdout leakage."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TYPES = {
    "user", "internet", "identity_provider", "waf", "cdn", "api_gateway",
    "load_balancer", "compute", "database", "storage", "queue", "monitoring",
    "backup", "secrets_kms",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _project_relative(path: Path) -> str:
    try:
        return _project_path(path).relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"Audit input must be inside the project root: {path}") from exc


def _valid_box(component: dict, annotation_size: list[int] | None) -> bool:
    if component.get("bboxNormalized") is not None:
        box = component["bboxNormalized"]
        return len(box) == 4 and all(0 <= value <= 1 for value in box) and box[0] < box[2] and box[1] < box[3]
    box = component.get("bbox")
    if not box or len(box) != 4 or not annotation_size:
        return False
    width, height = annotation_size
    return 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height


def audit(benchmark_path: Path, active_manifest_path: Path | None = None) -> dict:
    benchmark_path = _project_path(benchmark_path)
    active_manifest_path = _project_path(active_manifest_path) if active_manifest_path else None
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    seen_images: dict[str, str] = {}
    seen_groups: dict[str, str] = {}
    split_counts = Counter()
    provider_counts = Counter()

    for entry in benchmark.get("entries") or []:
        prefix = entry.get("id") or "<missing-id>"
        split = entry.get("split")
        split_counts[split] += 1
        provider_counts[entry.get("provider")] += 1
        if split not in {"development_tuning", "blind_holdout"}:
            errors.append(f"{prefix}: invalid split {split}")
        if entry.get("annotationStatus") != "human_verified":
            errors.append(f"{prefix}: annotation is not human_verified")

        image = ROOT / str(entry.get("image") or "")
        if not image.is_file():
            errors.append(f"{prefix}: image is missing")
        else:
            actual_hash = sha256(image)
            if actual_hash != entry.get("imageSha256"):
                errors.append(f"{prefix}: image SHA-256 mismatch")
            previous = seen_images.get(actual_hash)
            if previous and previous != split:
                errors.append(f"{prefix}: duplicate image hash crosses {previous} and {split}")
            seen_images[actual_hash] = split

        source_group = entry.get("sourceGroup")
        if source_group:
            previous = seen_groups.get(source_group)
            if previous and previous != split:
                errors.append(f"{prefix}: source group leaks across {previous} and {split}")
            seen_groups[source_group] = split

        component_ids = [component.get("id") for component in entry.get("components") or []]
        if len(component_ids) != len(set(component_ids)):
            errors.append(f"{prefix}: duplicate component ids")
        for component in entry.get("components") or []:
            if component.get("type") not in CANONICAL_TYPES:
                errors.append(f"{prefix}: non-canonical component type {component.get('type')}")
            if not _valid_box(component, entry.get("annotationSize")):
                errors.append(f"{prefix}: invalid box for {component.get('id')}")

        known = set(component_ids)
        flow_ids = []
        for flow in entry.get("flows") or []:
            flow_ids.append(flow.get("id"))
            if flow.get("from") not in known or flow.get("to") not in known:
                errors.append(f"{prefix}: flow {flow.get('id')} references an unknown component")
            if flow.get("from") == flow.get("to"):
                errors.append(f"{prefix}: flow {flow.get('id')} is a self-loop")
            if not str(flow.get("protocol") or "").strip():
                errors.append(f"{prefix}: flow {flow.get('id')} has no protocol field")
        if len(flow_ids) != len(set(flow_ids)):
            errors.append(f"{prefix}: duplicate flow ids")

        boundary_ids = []
        for boundary in entry.get("boundaries") or []:
            boundary_ids.append(boundary.get("id"))
            unknown = set(boundary.get("componentIds") or []) - known
            if unknown:
                errors.append(f"{prefix}: boundary {boundary.get('id')} has unknown members {sorted(unknown)}")
        if len(boundary_ids) != len(set(boundary_ids)):
            errors.append(f"{prefix}: duplicate boundary ids")

    if split_counts != Counter({"development_tuning": 9, "blind_holdout": 6}):
        errors.append(f"unexpected split counts: {dict(split_counts)}")
    if set(provider_counts) != {"aws", "azure", "gcp", "generic"}:
        errors.append(f"provider coverage is incomplete: {dict(provider_counts)}")
    if sum("fiap" in str(entry.get("id", "")).lower() for entry in benchmark.get("entries") or []) < 2:
        errors.append("both FIAP reference styles are required")
    if not benchmark.get("sealedAt"):
        errors.append("benchmark has no sealedAt timestamp")

    leakage = {"checked": False, "blindIdsInActiveLearning": []}
    if active_manifest_path and active_manifest_path.is_file():
        active = json.loads(active_manifest_path.read_text(encoding="utf-8"))
        blind_ids = {entry["id"] for entry in benchmark["entries"] if entry.get("split") == "blind_holdout"}
        active_ids = {record["id"] for record in active.get("records") or []}
        leaked = sorted(blind_ids & active_ids)
        leakage = {"checked": True, "blindIdsInActiveLearning": leaked}
        if active.get("blindHoldoutIncluded") is not False or leaked:
            errors.append(f"active-learning leakage detected: {leaked}")
    else:
        warnings.append("active-learning manifest was not available for leakage verification")

    warnings.append("Annotations are human verified but do not yet record an independent second annotator.")
    return {
        "schemaVersion": "1.1",
        "benchmark": _project_relative(benchmark_path),
        "status": "passed" if not errors else "failed",
        "imageCount": len(benchmark.get("entries") or []),
        "splitCounts": dict(split_counts),
        "providerCounts": dict(provider_counts),
        "uniqueImageHashes": len(seen_images),
        "activeLearningLeakage": leakage,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=Path("data/benchmarks/real-architecture/benchmark-expanded.json"))
    parser.add_argument("--active-manifest", type=Path, default=Path("dataset/active_learning_real_v1/active-learning-manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("data/results/benchmark-audit/real-benchmark-integrity.json"))
    args = parser.parse_args()
    result = audit(args.benchmark, args.active_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "imageCount", "splitCounts", "uniqueImageHashes", "errors")}, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
