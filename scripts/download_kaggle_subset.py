"""Plan and optionally download a curated Kaggle dataset subset.

The default command is plan-only. Pass ``--download`` after reviewing the
estimated bytes and selected groups. Individual public files are downloaded,
so the 33.5 GB archive is never required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from cloud_class_mapping import normalize_class_name
    from kaggle_dataset_utils import parse_augmented_filename
except ImportError:
    from scripts.cloud_class_mapping import normalize_class_name
    from scripts.kaggle_dataset_utils import parse_augmented_filename


DEFAULT_MANIFEST = Path("data/manifests/kaggle_software_architecture.json")
DEFAULT_OUTPUT = Path("dataset/raw_kaggle_selected")
DOWNLOAD_URL = "https://www.kaggle.com/api/v1/datasets/download/{owner}/{dataset}"


def build_selection_plan(
    manifest: dict,
    groups_per_primary_class: int,
    augmentations_per_group: int,
    max_image_bytes: int,
    seed: str,
    include_unmapped: bool,
) -> dict:
    groups: dict[str, dict] = defaultdict(lambda: {"variants": defaultdict(dict)})
    for item in manifest.get("files", []):
        role = item.get("role")
        if role not in {"image", "annotation"}:
            continue
        group_id = item.get("group_id")
        pair_key = item.get("pair_key")
        if not group_id or not pair_key:
            continue
        group = groups[group_id]
        group["group_id"] = group_id
        group["primary_class"] = item.get("primary_class") or group_id
        group["provider_hint"] = item.get("provider_hint") or "generic"
        group["canonical_primary_class"] = normalize_class_name(group["primary_class"])
        group["variants"][pair_key][role] = item

    by_primary_class: dict[str, list[dict]] = defaultdict(list)
    for group in groups.values():
        canonical = group["canonical_primary_class"]
        if canonical is None and not include_unmapped:
            continue
        by_primary_class[group["primary_class"]].append(group)

    selected_groups: list[dict] = []
    selected_pairs: list[dict] = []
    for primary_class, class_groups in sorted(by_primary_class.items()):
        ordered_groups = sorted(
            class_groups,
            key=lambda group: _stable_rank(seed, group["group_id"]),
        )
        if groups_per_primary_class > 0:
            ordered_groups = ordered_groups[:groups_per_primary_class]

        for group in ordered_groups:
            variants = []
            for pair_key, pair in group["variants"].items():
                if "image" not in pair or "annotation" not in pair:
                    continue
                image_size = int(pair["image"].get("size_bytes") or 0)
                if max_image_bytes > 0 and image_size > max_image_bytes:
                    continue
                parsed = parse_augmented_filename(pair["image"]["name"])
                variants.append(
                    {
                        "pair_key": pair_key,
                        "augmentation_index": parsed.augmentation_index,
                        "image": pair["image"],
                        "annotation": pair["annotation"],
                    }
                )

            chosen = _choose_variants(variants, augmentations_per_group)
            if not chosen:
                continue
            selected_groups.append(
                {
                    "group_id": group["group_id"],
                    "primary_class": primary_class,
                    "canonical_primary_class": group["canonical_primary_class"],
                    "provider_hint": group["provider_hint"],
                    "selected_variants": len(chosen),
                }
            )
            for variant in chosen:
                selected_pairs.append(
                    {
                        "group_id": group["group_id"],
                        "primary_class": primary_class,
                        "canonical_primary_class": group["canonical_primary_class"],
                        **variant,
                    }
                )

    estimated_image_bytes = sum(int(pair["image"].get("size_bytes") or 0) for pair in selected_pairs)
    estimated_annotation_bytes = sum(int(pair["annotation"].get("size_bytes") or 0) for pair in selected_pairs)
    estimated_bytes = estimated_image_bytes + estimated_annotation_bytes
    providers: dict[str, int] = defaultdict(int)
    canonical_classes: dict[str, int] = defaultdict(int)
    for group in selected_groups:
        providers[group["provider_hint"]] += 1
        canonical = group["canonical_primary_class"] or "unmapped"
        canonical_classes[canonical] += 1

    return {
        "dataset": manifest.get("dataset", "carlosrian/software-architecture-dataset"),
        "settings": {
            "groups_per_primary_class": groups_per_primary_class,
            "augmentations_per_group": augmentations_per_group,
            "max_image_bytes": max_image_bytes,
            "seed": seed,
            "include_unmapped": include_unmapped,
        },
        "summary": {
            "selected_groups": len(selected_groups),
            "selected_pairs": len(selected_pairs),
            "estimated_bytes": estimated_bytes,
            "estimated_megabytes": round(estimated_bytes / 1_000_000, 2),
            "estimated_image_bytes": estimated_image_bytes,
            "estimated_annotation_bytes": estimated_annotation_bytes,
            "provider_groups": dict(sorted(providers.items())),
            "canonical_primary_groups": dict(sorted(canonical_classes.items())),
        },
        "groups": selected_groups,
        "pairs": selected_pairs,
    }


def _choose_variants(variants: list[dict], maximum: int) -> list[dict]:
    if maximum <= 0 or len(variants) <= maximum:
        return sorted(variants, key=_variant_index)
    sizes = [int(item["image"].get("size_bytes") or 0) for item in variants]
    median_size = statistics.median(sizes)
    selected = sorted(
        variants,
        key=lambda item: (
            abs(int(item["image"].get("size_bytes") or 0) - median_size),
            _variant_index(item),
        ),
    )[:maximum]
    return sorted(selected, key=_variant_index)


def _variant_index(item: dict) -> int:
    value = item.get("augmentation_index")
    return int(value) if value is not None else -1


def _stable_rank(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def download_plan(
    plan: dict,
    output_root: Path,
    roles: tuple[str, ...] = ("image", "annotation"),
    retries: int = 4,
    workers: int = 4,
) -> dict[str, int]:
    owner, dataset = plan["dataset"].split("/", 1)
    output_root.mkdir(parents=True, exist_ok=True)
    counts = {"downloaded": 0, "skipped": 0, "failed": 0}
    total_files = len(plan["pairs"]) * len(roles)
    tasks: list[tuple[str, str, Path]] = []
    for pair in plan["pairs"]:
        for role in roles:
            item = pair[role]
            remote_name = item["name"]
            destination = output_root / Path(remote_name).name
            expected_size = int(item.get("size_bytes") or 0)
            if destination.exists() and (expected_size <= 0 or destination.stat().st_size == expected_size):
                counts["skipped"] += 1
                continue

            tasks.append((role, remote_name, destination))

    completed = counts["skipped"]
    if counts["skipped"]:
        print(f"[kaggle-download] skipped existing files: {counts['skipped']}", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(_download_file, owner, dataset, remote_name, destination, retries): (
                role,
                destination,
            )
            for role, remote_name, destination in tasks
        }
        for future in as_completed(futures):
            completed += 1
            role, destination = futures[future]
            try:
                future.result()
                counts["downloaded"] += 1
                print(
                    f"[kaggle-download] {completed}/{total_files} ok {role} {destination.name}",
                    flush=True,
                )
            except Exception as exc:
                counts["failed"] += 1
                print(
                    f"[kaggle-download] {completed}/{total_files} failed {destination.name}: {exc}",
                    flush=True,
                )

    return counts


def _download_file(owner: str, dataset: str, remote_name: str, destination: Path, retries: int) -> None:
    query = urllib.parse.urlencode(
        {
            "datasetVersionNumber": 1,
            "filename": remote_name,
        }
    )
    url = f"{DOWNLOAD_URL.format(owner=owner, dataset=dataset)}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "ThreatLens-AI-Dataset-Downloader/1.0"})
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as handle:
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
            temporary.replace(destination)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            temporary.unlink(missing_ok=True)
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed after {retries} attempts: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan or download a curated Kaggle subset")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--groups-per-primary-class", type=int, default=1)
    parser.add_argument("--augmentations-per-group", type=int, default=3)
    parser.add_argument("--max-image-mb", type=float, default=8.0)
    parser.add_argument("--seed", default="threatlens-kaggle-subset-v1")
    parser.add_argument("--include-unmapped", action="store_true")
    parser.add_argument(
        "--annotations-only",
        action="store_true",
        help="Download only XML annotations from the selected pairs",
    )
    parser.add_argument("--download", action="store_true", help="Download after writing the selection plan")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent download workers")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    plan = build_selection_plan(
        manifest=manifest,
        groups_per_primary_class=args.groups_per_primary_class,
        augmentations_per_group=args.augmentations_per_group,
        max_image_bytes=max(0, int(args.max_image_mb * 1_000_000)),
        seed=args.seed,
        include_unmapped=args.include_unmapped,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    plan_path = args.output / "selection-plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(plan["summary"], indent=2, ensure_ascii=False))
    print(f"[kaggle-download] plan: {plan_path}")

    if args.download:
        roles = ("annotation",) if args.annotations_only else ("image", "annotation")
        result = download_plan(plan, args.output, roles=roles, workers=args.workers)
        result_path = args.output / "download-result.json"
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        if result["failed"]:
            raise SystemExit("Some files failed to download. Re-run the command to retry only missing files.")
    else:
        print("[kaggle-download] plan-only; pass --download after reviewing estimated_megabytes")


if __name__ == "__main__":
    main()
