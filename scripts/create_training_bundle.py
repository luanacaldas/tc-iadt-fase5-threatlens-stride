"""Create a portable, self-contained GPU training bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = ROOT / "dataset" / "hybrid_v2"
DEFAULT_OUTPUT = ROOT / "artifacts" / "threatlens-training-bundle.zip"
SUPPORT_FILES = (
    ROOT / "scripts" / "train_yolo.py",
    ROOT / "scripts" / "evaluate_model.py",
    ROOT / "scripts" / "evaluate_source_slices.py",
    ROOT / "scripts" / "create_replay_manifest.py",
    ROOT / "scripts" / "register_model.py",
)
LOCAL_REPLAY_ARTIFACTS = {
    "architecture-replay.yaml",
    "train-replay-balanced.txt",
    "val-replay-balanced.txt",
    "replay-balanced-summary.json",
}


def _dataset_files(dataset_root: Path) -> list[Path]:
    files = [path for path in dataset_root.rglob("*") if path.is_file()]
    return sorted(
        path
        for path in files
        if path.suffix.lower() not in {".cache", ".npy"}
        and path.name not in LOCAL_REPLAY_ARTIFACTS
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_bundle(dataset_root: Path, output_path: Path) -> dict:
    dataset_root = dataset_root.resolve()
    output_path = output_path.resolve()
    if not (dataset_root / "architecture.yaml").exists():
        raise RuntimeError(f"Dataset YAML not found in {dataset_root}")

    missing = [path for path in SUPPORT_FILES if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing support files: {missing}")

    dataset_files = _dataset_files(dataset_root)
    image_files = [path for path in dataset_files if "images" in path.parts]
    label_files = [path for path in dataset_files if "labels" in path.parts]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bundle_root = Path("threatlens_training")
    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in dataset_files:
            relative = path.relative_to(dataset_root)
            archive.write(path, bundle_root / "dataset" / "hybrid_v2" / relative)
        for path in SUPPORT_FILES:
            archive.write(path, bundle_root / path.relative_to(ROOT))

        archive.writestr(
            str(bundle_root / "requirements-training.txt"),
            "ultralytics==8.4.60\nPyYAML>=6.0\n",
        )
        archive.writestr(
            str(bundle_root / "BUNDLE_INFO.md"),
            "# ThreatLens Training Bundle\n\n"
            "Portable hybrid_v2 dataset and YOLO training utilities. "
            "Use notebooks/train_threatlens_colab.ipynb from the main project.\n",
        )

    summary = {
        "bundle": str(output_path),
        "dataset": str(dataset_root),
        "images": len(image_files),
        "labels": len(label_files),
        "files_in_zip": len(dataset_files) + len(SUPPORT_FILES) + 2,
        "size_bytes": output_path.stat().st_size,
        "sha256": _sha256(output_path),
    }
    sidecar = output_path.with_suffix(".json")
    sidecar.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the ThreatLens GPU training bundle")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(create_bundle(args.dataset, args.output), indent=2))


if __name__ == "__main__":
    main()
