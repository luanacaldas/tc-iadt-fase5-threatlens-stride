"""Shared helpers for the Kaggle software architecture dataset."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUGMENTED_STEM_PATTERN = re.compile(r"^(?P<group>.+)_aug_(?P<augmentation>\d+)$")
GROUP_PATTERN = re.compile(r"^(?P<primary_class>.+)_(?P<source_index>\d+)$")


@dataclass(frozen=True)
class AugmentedFileInfo:
    path: str
    stem: str
    extension: str
    group_id: str
    primary_class: str
    source_index: str | None
    augmentation_index: int | None
    provider_hint: str


@dataclass(frozen=True)
class VocObject:
    raw_class: str
    canonical_class: str | None
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def valid(self) -> bool:
        return self.xmax > self.xmin and self.ymax > self.ymin


@dataclass(frozen=True)
class VocAnnotation:
    width: int
    height: int
    objects: tuple[VocObject, ...]

    @property
    def valid(self) -> bool:
        return self.width > 0 and self.height > 0


def parse_augmented_filename(path: str) -> AugmentedFileInfo:
    """Parse the provider class, source group, and augmentation index."""
    normalized_path = path.replace("\\", "/")
    pure_path = PurePosixPath(normalized_path)
    extension = pure_path.suffix.lower()
    stem = pure_path.stem

    augmentation_match = AUGMENTED_STEM_PATTERN.match(stem)
    if augmentation_match:
        group_id = augmentation_match.group("group")
        augmentation_index = int(augmentation_match.group("augmentation"))
    else:
        group_id = stem
        augmentation_index = None

    group_match = GROUP_PATTERN.match(group_id)
    if group_match:
        primary_class = group_match.group("primary_class")
        source_index = group_match.group("source_index")
    else:
        primary_class = group_id
        source_index = None

    provider_hint = infer_provider(primary_class)
    return AugmentedFileInfo(
        path=normalized_path,
        stem=stem,
        extension=extension,
        group_id=group_id,
        primary_class=primary_class,
        source_index=source_index,
        augmentation_index=augmentation_index,
        provider_hint=provider_hint,
    )


def infer_provider(class_name: str) -> str:
    key = class_name.lower()
    if key.startswith("aws_"):
        return "aws"
    if key.startswith("azure_"):
        return "azure"
    if key.startswith("gcp_") or key.startswith("google_"):
        return "gcp"
    return "generic"


def deterministic_split(
    group_id: str,
    stratum: str,
    train_ratio: float,
    val_ratio: float,
    seed: str,
) -> str:
    """Assign a whole augmentation family to a stable dataset split."""
    digest = hashlib.sha256(f"{seed}:{stratum}:{group_id}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") / float(2**64)
    if value < train_ratio:
        return "train"
    if value < train_ratio + val_ratio:
        return "val"
    return "test"


def parse_voc_annotation(
    xml_path: Path,
    normalize_class: Callable[[str], str | None],
) -> VocAnnotation:
    root = ET.parse(xml_path).getroot()
    width = _read_int(root.findtext("size/width"))
    height = _read_int(root.findtext("size/height"))
    objects: list[VocObject] = []

    for node in root.findall("object"):
        raw_class = (node.findtext("name") or "").strip()
        bbox = node.find("bndbox")
        if not raw_class or bbox is None:
            continue
        objects.append(
            VocObject(
                raw_class=raw_class,
                canonical_class=normalize_class(raw_class),
                xmin=_read_float(bbox.findtext("xmin")),
                ymin=_read_float(bbox.findtext("ymin")),
                xmax=_read_float(bbox.findtext("xmax")),
                ymax=_read_float(bbox.findtext("ymax")),
            )
        )

    return VocAnnotation(width=width, height=height, objects=tuple(objects))


def annotation_to_yolo_lines(
    annotation: VocAnnotation,
    canonical_classes: list[str],
) -> tuple[list[str], dict[str, int]]:
    lines: list[str] = []
    rejected = {
        "unmapped": 0,
        "invalid_bbox": 0,
        "outside_image": 0,
    }
    if not annotation.valid:
        return lines, rejected

    for item in annotation.objects:
        if item.canonical_class not in canonical_classes:
            rejected["unmapped"] += 1
            continue
        if not item.valid:
            rejected["invalid_bbox"] += 1
            continue

        xmin = max(0.0, min(float(annotation.width), item.xmin))
        ymin = max(0.0, min(float(annotation.height), item.ymin))
        xmax = max(0.0, min(float(annotation.width), item.xmax))
        ymax = max(0.0, min(float(annotation.height), item.ymax))
        if xmax <= xmin or ymax <= ymin:
            rejected["outside_image"] += 1
            continue

        class_index = canonical_classes.index(item.canonical_class)
        x_center = ((xmin + xmax) / 2.0) / annotation.width
        y_center = ((ymin + ymax) / 2.0) / annotation.height
        box_width = (xmax - xmin) / annotation.width
        box_height = (ymax - ymin) / annotation.height
        lines.append(
            f"{class_index} {x_center:.6f} {y_center:.6f} "
            f"{box_width:.6f} {box_height:.6f}"
        )

    return lines, rejected


def _read_int(value: str | None) -> int:
    try:
        return int(float(value or "0"))
    except (TypeError, ValueError):
        return 0


def _read_float(value: str | None) -> float:
    try:
        return float(value or "0")
    except (TypeError, ValueError):
        return 0.0
