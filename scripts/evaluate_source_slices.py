"""Compare model performance across dataset sources without changing the test set."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from .evaluate_model import evaluate_model
except ImportError:  # Direct script execution.
    from evaluate_model import evaluate_model


DEFAULT_MODEL = Path("models/threatlens-hybrid-v2/weights/best.pt")
DEFAULT_DATASET = Path("dataset/hybrid_v2/architecture.yaml")
DEFAULT_PROVENANCE = Path("dataset/hybrid_v2/reports/provenance.csv")
DEFAULT_OUTPUT = Path("data/results/threatlens-source-slices")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def group_images_by_source(
    provenance_path: Path,
    dataset_root: Path,
    split: str,
) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    with provenance_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("split") != split:
                continue
            stem = row["output_stem"]
            image = next(
                (
                    dataset_root / "images" / split / f"{stem}{suffix}"
                    for suffix in IMAGE_SUFFIXES
                    if (dataset_root / "images" / split / f"{stem}{suffix}").exists()
                ),
                None,
            )
            if image is None:
                raise RuntimeError(f"Image listed in provenance was not found: {stem}")
            grouped[row["source"]].append(image.resolve())
    return {source: sorted(images) for source, images in sorted(grouped.items())}


def write_slice_yaml(
    source: str,
    images: list[Path],
    dataset_config: dict[str, Any],
    output_dir: Path,
    split: str,
) -> Path:
    source_dir = output_dir / "manifests" / source
    source_dir.mkdir(parents=True, exist_ok=True)
    image_list = source_dir / f"{split}.txt"
    image_list.write_text(
        "\n".join(path.as_posix() for path in images) + "\n",
        encoding="utf-8",
    )
    config = {
        "path": str(dataset_config["path"]),
        "train": str(dataset_config.get("train", "images/train")),
        "val": str(dataset_config.get("val", "images/val")),
        "test": str(dataset_config.get("test", "images/test")),
        "nc": int(dataset_config["nc"]),
        "names": dataset_config["names"],
    }
    config[split] = image_list.resolve().as_posix()
    yaml_path = source_dir / "architecture.yaml"
    yaml_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return yaml_path


def evaluate_sources(
    model_path: Path,
    dataset_yaml: Path,
    provenance_path: Path,
    output_dir: Path,
    split: str,
    device: str,
    imgsz: int,
    batch: int,
) -> dict[str, Any]:
    dataset_yaml = dataset_yaml.resolve()
    provenance_path = provenance_path.resolve()
    output_dir = output_dir.resolve()
    dataset_config = yaml.safe_load(dataset_yaml.read_text(encoding="utf-8"))
    configured_root = Path(str(dataset_config["path"]))
    dataset_root = (
        configured_root
        if configured_root.is_absolute()
        else (dataset_yaml.parent / configured_root).resolve()
    )
    grouped = group_images_by_source(provenance_path, dataset_root, split)
    if not grouped:
        raise RuntimeError(f"No provenance entries found for split '{split}'")

    source_results = []
    for source, images in grouped.items():
        slice_yaml = write_slice_yaml(source, images, dataset_config, output_dir, split)
        summary = evaluate_model(
            model_path=model_path,
            dataset_yaml=slice_yaml,
            output_dir=output_dir / source,
            split=split,
            device=device,
            imgsz=imgsz,
            batch=batch,
            minimum_map50=0.0,
            minimum_recall=0.0,
            minimum_critical_ap50=0.0,
        )
        source_results.append(
            {
                "source": source,
                "imageCount": len(images),
                "aggregate": summary["aggregate"],
                "perClass": summary["perClass"],
                "evaluationSummary": str(
                    (output_dir / source / "evaluation-summary.json").resolve()
                ),
            }
        )

    comparison = {
        "schemaVersion": "1.0",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "model": {
            "path": str(model_path.resolve()),
            "sha256": _sha256(model_path.resolve()),
        },
        "dataset": str(dataset_yaml),
        "provenance": str(provenance_path),
        "split": split,
        "sources": source_results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "source-comparison.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "source-comparison.md").write_text(
        markdown_comparison(comparison),
        encoding="utf-8",
    )
    return comparison


def markdown_comparison(comparison: dict[str, Any]) -> str:
    lines = [
        "# ThreatLens Evaluation by Dataset Source",
        "",
        f"- Split: `{comparison['split']}`",
        "- This diagnostic comparison does not replace the full-test quality gate.",
        "",
        "| Source | Images | Precision | Recall | mAP50 | mAP50-95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in comparison["sources"]:
        aggregate = item["aggregate"]
        lines.append(
            f"| {item['source']} | {item['imageCount']} | "
            f"{aggregate['precision']:.4f} | {aggregate['recall']:.4f} | "
            f"{aggregate['map50']:.4f} | {aggregate['map50_95']:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ThreatLens by dataset source")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    args = parser.parse_args()

    comparison = evaluate_sources(
        args.model,
        args.data,
        args.provenance,
        args.output_dir,
        args.split,
        args.device,
        args.imgsz,
        args.batch,
    )
    for item in comparison["sources"]:
        aggregate = item["aggregate"]
        print(
            f"{item['source']}: images={item['imageCount']} "
            f"mAP50={aggregate['map50']:.4f} recall={aggregate['recall']:.4f}"
        )
    print(f"Comparison: {args.output_dir / 'source-comparison.json'}")


if __name__ == "__main__":
    main()
