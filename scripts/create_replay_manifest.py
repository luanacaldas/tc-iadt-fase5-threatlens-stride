"""Create a source-balanced training manifest for domain-adaptation replay."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


DEFAULT_DATA = Path("dataset/hybrid_v2/architecture.yaml")
DEFAULT_PROVENANCE = Path("dataset/hybrid_v2/reports/provenance.csv")
DEFAULT_OUTPUT = Path("dataset/hybrid_v2/architecture-replay.yaml")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def _find_image(dataset_root: Path, split: str, stem: str) -> Path:
    for suffix in IMAGE_SUFFIXES:
        candidate = dataset_root / "images" / split / f"{stem}{suffix}"
        if candidate.exists():
            return candidate.resolve()
    raise RuntimeError(f"Image not found for provenance entry: {stem}")


def _class_counts(dataset_root: Path, split: str, stem: str) -> Counter[int]:
    label_path = dataset_root / "labels" / split / f"{stem}.txt"
    counts: Counter[int] = Counter()
    for line in label_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields:
            counts[int(fields[0])] += 1
    return counts


def select_replay_examples(
    candidates: list[dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    if target_count >= len(candidates):
        return list(candidates)
    global_frequency: Counter[int] = Counter()
    for item in candidates:
        global_frequency.update(item["classCounts"])

    selected: list[dict[str, Any]] = []
    selected_objects: Counter[int] = Counter()
    remaining = list(candidates)
    while remaining and len(selected) < target_count:
        best = max(
            remaining,
            key=lambda item: (
                sum(
                    object_count
                    / (global_frequency[class_id] * (1 + selected_objects[class_id]))
                    for class_id, object_count in item["classCounts"].items()
                ),
                len(item["classCounts"]),
                item["stem"],
            ),
        )
        selected.append(best)
        selected_objects.update(best["classCounts"])
        remaining.remove(best)
    return selected


def create_replay_manifest(
    dataset_yaml: Path,
    provenance_path: Path,
    output_yaml: Path,
    replay_source: str,
    focus_source: str,
    replay_count: int | None,
) -> dict[str, Any]:
    dataset_yaml = dataset_yaml.resolve()
    provenance_path = provenance_path.resolve()
    output_yaml = output_yaml.resolve()
    config = yaml.safe_load(dataset_yaml.read_text(encoding="utf-8"))
    configured_root = Path(str(config["path"]))
    dataset_root = (
        configured_root
        if configured_root.is_absolute()
        else (dataset_yaml.parent / configured_root).resolve()
    )

    by_split_source: dict[str, dict[str, list[dict[str, Any]]]] = {
        split: {replay_source: [], focus_source: []} for split in ("train", "val")
    }
    with provenance_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            split = row.get("split")
            source = row.get("source")
            if split not in by_split_source or source not in by_split_source[split]:
                continue
            stem = row["output_stem"]
            by_split_source[split][source].append(
                {
                    "stem": stem,
                    "image": _find_image(dataset_root, split, stem),
                    "classCounts": _class_counts(dataset_root, split, stem),
                }
            )

    train_sources = by_split_source["train"]
    focus = sorted(train_sources[focus_source], key=lambda item: item["stem"])
    replay_candidates = sorted(train_sources[replay_source], key=lambda item: item["stem"])
    if not focus or not replay_candidates:
        raise RuntimeError(
            f"Replay sources were not found in training provenance: {replay_source}, {focus_source}"
        )
    target = replay_count if replay_count is not None else len(focus)
    replay = select_replay_examples(replay_candidates, target)
    training_examples = focus + sorted(replay, key=lambda item: item["stem"])

    val_sources = by_split_source["val"]
    validation_focus = sorted(val_sources[focus_source], key=lambda item: item["stem"])
    validation_candidates = sorted(val_sources[replay_source], key=lambda item: item["stem"])
    if not validation_focus or not validation_candidates:
        raise RuntimeError(
            f"Replay sources were not found in validation provenance: {replay_source}, {focus_source}"
        )
    validation_replay = select_replay_examples(validation_candidates, len(validation_focus))
    validation_examples = validation_focus + sorted(
        validation_replay,
        key=lambda item: item["stem"],
    )

    output_yaml.parent.mkdir(parents=True, exist_ok=True)
    train_list = output_yaml.with_name("train-replay-balanced.txt")
    train_list.write_text(
        "\n".join(str(item["image"].as_posix()) for item in training_examples) + "\n",
        encoding="utf-8",
    )
    val_list = output_yaml.with_name("val-replay-balanced.txt")
    val_list.write_text(
        "\n".join(str(item["image"].as_posix()) for item in validation_examples) + "\n",
        encoding="utf-8",
    )
    replay_config = dict(config)
    replay_config["path"] = str(dataset_root.as_posix())
    replay_config["train"] = str(train_list.as_posix())
    replay_config["val"] = str(val_list.as_posix())
    output_yaml.write_text(
        "# ThreatLens source-balanced replay dataset\n"
        + yaml.safe_dump(replay_config, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    class_counts: Counter[int] = Counter()
    for item in training_examples:
        class_counts.update(item["classCounts"])
    names = config["names"]
    summary = {
        "datasetYaml": str(output_yaml),
        "trainList": str(train_list),
        "validationList": str(val_list),
        "focusSource": focus_source,
        "focusImages": len(focus),
        "replaySource": replay_source,
        "replayImages": len(replay),
        "totalTrainingImages": len(training_examples),
        "focusValidationImages": len(validation_focus),
        "replayValidationImages": len(validation_replay),
        "totalValidationImages": len(validation_examples),
        "classObjects": {
            str(names.get(class_id, names.get(str(class_id), class_id))): class_counts[class_id]
            for class_id in range(int(config["nc"]))
        },
    }
    summary_path = output_yaml.with_name("replay-balanced-summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a domain-adaptation replay manifest")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--replay-source", default="current")
    parser.add_argument("--focus-source", default="kaggle_unique")
    parser.add_argument("--replay-count", type=int)
    args = parser.parse_args()
    summary = create_replay_manifest(
        args.data,
        args.provenance,
        args.output,
        args.replay_source,
        args.focus_source,
        args.replay_count,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
