"""Script de treino YOLOv8 para detecção de componentes arquiteturais.

Uso:
    # Treino padrão (GPU)
    python scripts/train_yolo.py

    # Treino em CPU (lento, para teste)
    python scripts/train_yolo.py --device cpu

    # Retomar treino interrompido
    python scripts/train_yolo.py --resume

Pré-requisitos:
    1. Dataset em dataset/ com imagens e labels YOLOv8
    2. Rode primeiro: python scripts/generate_synthetic_dataset.py --count 300
       (ou baixe dataset real: python scripts/download_roboflow_dataset.py --api-key SUA_KEY)
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from ultralytics import YOLO

DATASET_YAML = Path("dataset/architecture.yaml")
EPOCHS = 100
IMAGE_SIZE = 640
PROJECT = "models"
RUN_NAME = "threatlens-v1"


def _augmentation_config(profile: str) -> dict[str, float]:
    if profile == "none":
        return {
            "hsv_h": 0.0,
            "hsv_s": 0.0,
            "hsv_v": 0.0,
            "flipud": 0.0,
            "fliplr": 0.0,
            "mosaic": 0.0,
            "translate": 0.0,
            "scale": 0.0,
            "degrees": 0.0,
        }
    return {
        "hsv_h": 0.0,
        "hsv_s": 0.12,
        "hsv_v": 0.12,
        "flipud": 0.0,
        "fliplr": 0.0,
        "mosaic": 0.0,
        "translate": 0.04,
        "scale": 0.12,
        "degrees": 1.0,
    }


def _detect_batch_size(device: str | int) -> int:
    """Detecta batch size seguro baseado na VRAM disponível."""
    if device == "cpu":
        return 8
    try:
        import torch
        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            if vram_gb >= 8:
                return 32
            elif vram_gb >= 6:
                return 16
            else:
                return 8
    except Exception:
        pass
    return 8


def _load_dataset_config(dataset_yaml: Path) -> dict[str, Any]:
    config: dict[str, Any] = {}
    names: dict[int, str] = {}
    current_key: str | None = None

    for raw_line in dataset_yaml.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        stripped = line.strip()
        if stripped.startswith("names:"):
            current_key = "names"
            config["names"] = names
            continue

        if current_key == "names" and stripped.startswith("-"):
            value = stripped.lstrip("- ").strip().strip("'\"")
            if value:
                names[len(names)] = value
            continue

        if current_key == "names" and line.startswith("  ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key.isdigit():
                names[int(key)] = value
            continue

        current_key = None
        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        config[key] = value

    if names:
        config["names"] = names
    return config


def _resolve_dataset_path(dataset_yaml: Path, value: str, dataset_root: str | None = None) -> Path:
    value_path = Path(value)
    if value_path.is_absolute():
        return value_path.resolve()

    # Preserve compatibility with the existing project YAML, whose split
    # paths are relative to the repository root.
    cwd_candidate = (Path.cwd() / value_path).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    root_path = Path(dataset_root or ".")
    if not root_path.is_absolute():
        root_path = (dataset_yaml.parent / root_path).resolve()
    return (root_path / value_path).resolve()


def _list_images(source: Path) -> list[Path]:
    if not source.exists():
        return []
    if source.is_file() and source.suffix.lower() == ".txt":
        images = []
        for line in source.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if not value:
                continue
            image = Path(value)
            if not image.is_absolute():
                image = source.parent / image
            if image.exists():
                images.append(image.resolve())
        return images
    return sorted([*source.glob("*.jpg"), *source.glob("*.jpeg"), *source.glob("*.png"), *source.glob("*.webp")])


def _label_for_image(image_path: Path) -> Path:
    parts = list(image_path.parts)
    image_part = next(
        (index for index in range(len(parts) - 1, -1, -1) if parts[index].lower() == "images"),
        None,
    )
    if image_part is None:
        return image_path.with_suffix(".txt")
    parts[image_part] = "labels"
    return Path(*parts).with_suffix(".txt")


def _count_label_files(label_files: list[Path], class_names: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for label_file in label_files:
        if not label_file.exists():
            continue
        for line in label_file.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            try:
                class_index = int(parts[0])
            except ValueError:
                continue
            if 0 <= class_index < len(class_names):
                counts[class_names[class_index]] += 1
    return counts


def _count_labels(label_dir: Path, class_names: list[str]) -> Counter[str]:
    if not label_dir.exists():
        return Counter()
    return _count_label_files(list(label_dir.glob("*.txt")), class_names)


def _validate_dataset(dataset_yaml: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = _load_dataset_config(dataset_yaml)

    class_names = config.get("names", [])
    if isinstance(class_names, dict):
        class_names = [class_names[key] for key in sorted(class_names, key=lambda value: int(value) if str(value).isdigit() else str(value))]
    if not isinstance(class_names, list) or not class_names:
        raise RuntimeError("Dataset YAML does not define a valid 'names' list.")

    split_info: dict[str, Any] = {}
    total_images = 0
    total_labels = 0

    for split in ("train", "val", "test"):
        split_value = config.get(split)
        if not isinstance(split_value, str) or not split_value:
            raise RuntimeError(f"Dataset YAML missing '{split}' path.")

        dataset_root = config.get("path")
        image_source = _resolve_dataset_path(
            dataset_yaml,
            split_value,
            str(dataset_root) if dataset_root is not None else None,
        )
        images = _list_images(image_source)
        if image_source.is_file():
            labels = [_label_for_image(image) for image in images if _label_for_image(image).exists()]
            class_counts = _count_label_files(labels, class_names)
        else:
            label_dir = image_source.parent.parent / "labels" / split
            labels = list(label_dir.glob("*.txt")) if label_dir.exists() else []
            class_counts = _count_labels(label_dir, class_names)
        image_stems = {path.stem for path in images}
        label_stems = {path.stem for path in labels}

        orphan_images = sorted(image_stems - label_stems)
        orphan_labels = sorted(label_stems - image_stems)

        split_info[split] = {
            "images": len(images),
            "labels": len(labels),
            "orphan_images": orphan_images,
            "orphan_labels": orphan_labels,
            "class_counts": class_counts,
        }

        total_images += len(images)
        total_labels += len(labels)

    summary = {
        "classes": class_names,
        "total_images": total_images,
        "total_labels": total_labels,
    }
    return summary, split_info


def _print_dataset_report(summary: dict[str, Any], split_info: dict[str, Any]) -> None:
    class_names = summary["classes"]
    print("[train] Dataset report")
    print(f"  Classes: {len(class_names)}")
    print(f"  Total images: {summary['total_images']}")
    print(f"  Total labels: {summary['total_labels']}")
    print("  Class list:")
    for index, class_name in enumerate(class_names):
        print(f"    {index:02d}: {class_name}")

    print("  Split summary:")
    for split, info in split_info.items():
        print(f"    {split}: {info['images']} images, {info['labels']} labels")
        if info["orphan_images"]:
            print(f"      orphan images: {len(info['orphan_images'])}")
        if info["orphan_labels"]:
            print(f"      orphan labels: {len(info['orphan_labels'])}")


def _ensure_dataset_is_trainable(dataset_yaml: Path, min_train_images: int = 20) -> tuple[dict[str, Any], dict[str, Any]]:
    if not dataset_yaml.exists():
        raise RuntimeError(f"Dataset YAML not found: {dataset_yaml}")

    summary, split_info = _validate_dataset(dataset_yaml)

    if split_info["train"]["images"] < min_train_images:
        raise RuntimeError(
            f"Training set too small: {split_info['train']['images']} images found, minimum recommended is {min_train_images}."
        )

    if split_info["train"]["labels"] == 0:
        raise RuntimeError("Training labels are missing.")

    return summary, split_info


def main():
    parser = argparse.ArgumentParser(description="Treina YOLOv8 para detecção de componentes arquiteturais")
    parser.add_argument("--device", default="0", help="Dispositivo: 0 (GPU), cpu (default: 0)")
    parser.add_argument("--epochs", type=int, default=EPOCHS, help=f"Épocas de treino (default: {EPOCHS})")
    parser.add_argument("--resume", action="store_true", help="Retomar treino interrompido")
    parser.add_argument("--model", default="yolov8n.pt", help="Modelo base: yolov8n.pt (nano), yolov8s.pt (small)")
    parser.add_argument("--data", type=Path, default=DATASET_YAML, help="Dataset YAML path")
    parser.add_argument("--imgsz", type=int, default=IMAGE_SIZE, help=f"Training image size (default: {IMAGE_SIZE})")
    parser.add_argument("--batch", type=int, help="Override automatic batch size")
    parser.add_argument("--workers", type=int, default=4, help="Data loader workers")
    parser.add_argument("--fraction", type=float, default=1.0, help="Fraction of training images to use")
    parser.add_argument("--project", default=PROJECT, help="Ultralytics output project directory")
    parser.add_argument("--run-name", default=RUN_NAME, help="Ultralytics run name")
    parser.add_argument("--patience", type=int, default=20, help="Early-stopping patience")
    parser.add_argument("--save-period", type=int, default=-1, help="Save a checkpoint every N epochs")
    parser.add_argument("--augmentation-profile", choices=("diagram", "none"), default="diagram")
    parser.add_argument("--cache", choices=("none", "ram", "disk"), default="none")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rect", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--optimizer", default="auto", help="Ultralytics optimizer, e.g. auto or AdamW")
    parser.add_argument("--lr0", type=float, help="Initial learning rate override")
    parser.add_argument("--lrf", type=float, help="Final learning-rate fraction override")
    parser.add_argument("--weight-decay", type=float, help="Weight-decay override")
    parser.add_argument("--no-dataset-report", action="store_true", help="Não imprime relatório do dataset")
    args = parser.parse_args()

    device: str | int = "cpu" if args.device == "cpu" else int(args.device)
    if not 0 < args.fraction <= 1:
        raise SystemExit("--fraction must be greater than 0 and at most 1")

    try:
        summary, split_info = _ensure_dataset_is_trainable(args.data)
    except Exception as exc:
        print(f"[train] Dataset validation failed: {exc}")
        print("[train] Execute primeiro:")
        print("  python scripts/prepare_dataset.py --source dataset/raw_hf --source dataset/raw_kaggle --source dataset/gcp_synthetic")
        return

    if not args.no_dataset_report:
        _print_dataset_report(summary, split_info)

    n_train = split_info["train"]["images"]

    batch = args.batch if args.batch is not None else _detect_batch_size(device)
    print(f"[train] Iniciando treino YOLOv8")
    print(f"  Modelo base:  {args.model}")
    print(f"  Épocas:       {args.epochs}")
    print(f"  Imagens:      {n_train} de treino")
    print(f"  Batch size:   {batch}")
    print(f"  Device:       {device}")
    print(f"  Image size:   {args.imgsz}")
    print(f"  Fraction:     {args.fraction}")
    print(f"  Augmentation: {args.augmentation_profile}")
    print(f"  Rect batches: {args.rect}")
    print(f"  Optimizer:    {args.optimizer}")
    if args.lr0 is not None:
        print(f"  Learning rate:{args.lr0}")

    class_names = summary["classes"]
    if len(class_names) < 8:
        print("[train] Warning: fewer than 8 classes found. This is acceptable for a minimal demo, but risky for generalization.")

    if args.resume:
        last_weights = Path(args.project) / args.run_name / "weights" / "last.pt"
        if last_weights.exists():
            model = YOLO(str(last_weights))
            print(f"[train] Retomando de: {last_weights}")
        else:
            print(f"[train] Peso 'last.pt' não encontrado — iniciando do zero.")
            model = YOLO(args.model)
    else:
        model = YOLO(args.model)

    augmentation = _augmentation_config(args.augmentation_profile)
    optimization = {"optimizer": args.optimizer}
    if args.lr0 is not None:
        optimization["lr0"] = args.lr0
    if args.lrf is not None:
        optimization["lrf"] = args.lrf
    if args.weight_decay is not None:
        optimization["weight_decay"] = args.weight_decay
    cache: bool | str = False if args.cache == "none" else args.cache
    results = model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=batch,
        device=device,
        workers=args.workers,
        fraction=args.fraction,
        project=args.project,
        name=args.run_name,
        patience=args.patience,
        save_period=args.save_period,
        seed=args.seed,
        deterministic=True,
        rect=args.rect,
        cache=cache,
        save=True,
        val=True,
        plots=True,
        **augmentation,
        **optimization,
    )

    save_dir = Path(getattr(results, "save_dir", Path(args.project) / args.run_name))
    best_weights = save_dir / "weights" / "best.pt"
    print(f"\n[train] Treino concluído!")
    print(f"[train] Melhores pesos: {best_weights}")
    print(f"\nAtualize o .env:")
    print(f"  YOLO_MODEL_PATH={best_weights}")

    metrics = results.results_dict
    print("\n=== Métricas finais ===")
    labels = {
        "metrics/precision(B)": "Precision",
        "metrics/recall(B)": "Recall",
        "metrics/mAP50(B)": "mAP@0.5",
        "metrics/mAP50-95(B)": "mAP@0.5:0.95",
    }
    for key, label in labels.items():
        if key in metrics:
            print(f"  {label:20s}: {metrics[key]:.4f}")

    print("\nPróximo passo: python scripts/evaluate_model.py --split test")


if __name__ == "__main__":
    main()
