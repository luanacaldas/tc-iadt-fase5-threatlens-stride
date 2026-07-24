"""Inventory the public Kaggle software architecture dataset without downloading it.

The script uses Kaggle's public file-list endpoint, pairs PNG/XML files, and
groups all ``aug_N`` variants under their original architecture id. This makes
data leakage visible before any train/validation/test split is created.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

try:
    from cloud_class_mapping import normalize_class_name
    from kaggle_dataset_utils import IMAGE_EXTENSIONS, parse_augmented_filename
except ImportError:
    from scripts.cloud_class_mapping import normalize_class_name
    from scripts.kaggle_dataset_utils import IMAGE_EXTENSIONS, parse_augmented_filename


DEFAULT_OWNER = "carlosrian"
DEFAULT_DATASET = "software-architecture-dataset"
DEFAULT_OUTPUT = Path("data/manifests/kaggle_software_architecture")
API_URL = "https://www.kaggle.com/api/v1/datasets/list/{owner}/{dataset}"


def fetch_file_manifest(
    owner: str,
    dataset: str,
    page_size: int = 200,
    max_pages: int | None = None,
    request_delay: float = 0.05,
) -> tuple[list[dict], bool, int]:
    files: list[dict] = []
    page_token: str | None = None
    page_count = 0
    complete = False

    while True:
        query: dict[str, str | int] = {"pageSize": min(max(page_size, 1), 200)}
        if page_token:
            query["pageToken"] = page_token
        url = f"{API_URL.format(owner=owner, dataset=dataset)}?{urllib.parse.urlencode(query)}"
        payload = _request_json(url)
        page_files = payload.get("datasetFiles", [])
        if not isinstance(page_files, list):
            raise RuntimeError("Kaggle response did not contain a datasetFiles list.")

        for item in page_files:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            files.append(
                {
                    "name": str(item["name"]),
                    "size_bytes": int(item.get("totalBytes") or 0),
                    "created_at": item.get("creationDate"),
                }
            )

        page_count += 1
        print(f"[kaggle-audit] page={page_count} files={len(files)}")
        page_token = payload.get("nextPageToken") or None
        if not page_token:
            complete = True
            break
        if max_pages is not None and page_count >= max_pages:
            break
        if request_delay > 0:
            time.sleep(request_delay)

    return files, complete, page_count


def _request_json(url: str, retries: int = 4) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ThreatLens-AI-Dataset-Auditor/1.0"},
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                if not isinstance(data, dict):
                    raise RuntimeError("Unexpected Kaggle API response.")
                return data
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Kaggle API request failed after {retries} attempts: {last_error}")


def build_audit(files: list[dict], complete: bool, page_count: int) -> dict:
    pairs: dict[str, dict[str, dict]] = defaultdict(dict)
    groups: dict[str, set[str]] = defaultdict(set)
    primary_classes: Counter[str] = Counter()
    providers: Counter[str] = Counter()
    extensions: Counter[str] = Counter()
    image_sizes: list[int] = []

    enriched_files: list[dict] = []
    for item in files:
        info = parse_augmented_filename(item["name"])
        extensions[info.extension] += 1
        if info.extension in IMAGE_EXTENSIONS:
            role = "image"
            image_sizes.append(item["size_bytes"])
        elif info.extension == ".xml":
            role = "annotation"
        else:
            role = "other"

        pair_key = str(Path(info.path).with_suffix("")).replace("\\", "/")
        if role in {"image", "annotation"}:
            pairs[pair_key][role] = item
        groups[info.group_id].add(info.stem)
        primary_classes[info.primary_class] += 1
        providers[info.provider_hint] += 1
        enriched_files.append(
            {
                **item,
                "extension": info.extension,
                "role": role,
                "pair_key": pair_key,
                "group_id": info.group_id,
                "primary_class": info.primary_class,
                "source_index": info.source_index,
                "augmentation_index": info.augmentation_index,
                "provider_hint": info.provider_hint,
            }
        )

    paired = sum(1 for pair in pairs.values() if "image" in pair and "annotation" in pair)
    paired_by_group: Counter[str] = Counter()
    for pair_key, pair in pairs.items():
        if "image" in pair and "annotation" in pair:
            paired_by_group[parse_augmented_filename(pair_key).group_id] += 1
    missing_image = sorted(key for key, pair in pairs.items() if "image" not in pair)
    missing_annotation = sorted(key for key, pair in pairs.items() if "annotation" not in pair)
    augmentation_histogram = Counter(len(stems) for stems in groups.values())
    canonical_primary_classes: Counter[str] = Counter()
    unmapped_primary_classes: dict[str, int] = {}
    for raw_class, count in primary_classes.items():
        canonical = normalize_class_name(raw_class)
        if canonical:
            canonical_primary_classes[canonical] += count
        else:
            unmapped_primary_classes[raw_class] = count

    summary = {
        "manifest_complete": complete,
        "pages_fetched": page_count,
        "total_files": len(files),
        "total_bytes": sum(item["size_bytes"] for item in files),
        "image_files": sum(extensions[ext] for ext in IMAGE_EXTENSIONS),
        "annotation_files": extensions[".xml"],
        "paired_samples": paired,
        "missing_images": len(missing_image),
        "missing_annotations": len(missing_annotation),
        "augmentation_groups": len(groups),
        "primary_class_count": len(primary_classes),
        "mapped_primary_class_count": len(primary_classes) - len(unmapped_primary_classes),
        "unmapped_primary_class_count": len(unmapped_primary_classes),
        "provider_file_counts": dict(sorted(providers.items())),
        "augmentation_count_histogram": {
            str(key): value for key, value in sorted(augmentation_histogram.items())
        },
        "image_size_bytes": _size_statistics(image_sizes),
    }

    group_rows = []
    for group_id, stems in sorted(groups.items()):
        parsed = parse_augmented_filename(next(iter(stems)))
        group_rows.append(
            {
                "group_id": group_id,
                "primary_class": parsed.primary_class,
                "provider_hint": parsed.provider_hint,
                "variant_count": len(stems),
                "paired_variant_count": paired_by_group[group_id],
            }
        )

    return {
        "dataset": f"{DEFAULT_OWNER}/{DEFAULT_DATASET}",
        "summary": summary,
        "primary_classes": dict(sorted(primary_classes.items())),
        "canonical_primary_classes": dict(sorted(canonical_primary_classes.items())),
        "unmapped_primary_classes": dict(sorted(unmapped_primary_classes.items())),
        "missing_image_examples": missing_image[:50],
        "missing_annotation_examples": missing_annotation[:50],
        "groups": group_rows,
        "files": enriched_files,
    }


def _size_statistics(values: list[int]) -> dict[str, int | float]:
    if not values:
        return {"min": 0, "median": 0, "p95": 0, "max": 0, "mean": 0}
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": _percentile(ordered, 0.5),
        "p95": _percentile(ordered, 0.95),
        "max": ordered[-1],
        "mean": round(sum(ordered) / len(ordered), 2),
    }


def _percentile(ordered: list[int], quantile: float) -> int:
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def write_outputs(audit: dict, output_base: Path) -> None:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_base.with_suffix(".json")
    report_path = output_base.with_suffix(".md")
    groups_path = output_base.with_name(f"{output_base.name}_groups.csv")

    json_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    with groups_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "group_id",
                "primary_class",
                "provider_hint",
                "variant_count",
                "paired_variant_count",
            ],
        )
        writer.writeheader()
        writer.writerows(audit["groups"])

    summary = audit["summary"]
    image_sizes = summary["image_size_bytes"]
    lines = [
        "# Kaggle Software Architecture Dataset Audit",
        "",
        f"- Complete manifest: {summary['manifest_complete']}",
        f"- API pages fetched: {summary['pages_fetched']}",
        f"- Files: {summary['total_files']}",
        f"- Images: {summary['image_files']}",
        f"- XML annotations: {summary['annotation_files']}",
        f"- Paired samples: {summary['paired_samples']}",
        f"- Original augmentation groups: {summary['augmentation_groups']}",
        f"- Primary filename classes: {summary['primary_class_count']}",
        f"- Primary classes mapped to ThreatLens: {summary['mapped_primary_class_count']}",
        f"- Primary classes left unmapped: {summary['unmapped_primary_class_count']}",
        f"- Missing images: {summary['missing_images']}",
        f"- Missing annotations: {summary['missing_annotations']}",
        "",
        "## Image size",
        "",
        f"- Minimum: {image_sizes['min']} bytes",
        f"- Median: {image_sizes['median']} bytes",
        f"- P95: {image_sizes['p95']} bytes",
        f"- Maximum: {image_sizes['max']} bytes",
        "",
        "## Leakage control",
        "",
        "All files sharing the same `group_id` must remain in the same split.",
        "The group id is the filename stem without the `_aug_N` suffix.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[kaggle-audit] JSON: {json_path}")
    print(f"[kaggle-audit] report: {report_path}")
    print(f"[kaggle-audit] groups: {groups_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the public Kaggle architecture dataset")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=0, help="0 fetches the complete manifest")
    parser.add_argument("--request-delay", type=float, default=0.05)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--input-manifest",
        type=Path,
        help="Rebuild the audit from a previously generated JSON without calling Kaggle",
    )
    args = parser.parse_args()

    if args.input_manifest:
        previous = json.loads(args.input_manifest.read_text(encoding="utf-8"))
        files = [
            {
                "name": item["name"],
                "size_bytes": int(item.get("size_bytes") or 0),
                "created_at": item.get("created_at"),
            }
            for item in previous.get("files", [])
        ]
        complete = bool(previous.get("summary", {}).get("manifest_complete"))
        page_count = int(previous.get("summary", {}).get("pages_fetched") or 0)
    else:
        max_pages = args.max_pages or None
        files, complete, page_count = fetch_file_manifest(
            owner=args.owner,
            dataset=args.dataset,
            page_size=args.page_size,
            max_pages=max_pages,
            request_delay=args.request_delay,
        )
    audit = build_audit(files, complete=complete, page_count=page_count)
    audit["dataset"] = f"{args.owner}/{args.dataset}"
    write_outputs(audit, args.output)


if __name__ == "__main__":
    main()
