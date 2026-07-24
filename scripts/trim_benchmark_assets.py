"""Trim browser-rendered benchmark assets to their visible diagram bounds."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops


def trim(path: Path, margin: int = 24) -> tuple[int, int]:
    with Image.open(path) as source:
        image = source.convert("RGB")
        white = Image.new("RGB", image.size, "white")
        difference = ImageChops.difference(image, white).convert("L")
        difference = difference.point(lambda value: 255 if value > 8 else 0)
        bbox = difference.getbbox()
        if bbox is None:
            raise ValueError(f"No visible content found in {path}")
        left = max(0, bbox[0] - margin)
        top = max(0, bbox[1] - margin)
        right = min(image.width, bbox[2] + margin)
        bottom = min(image.height, bbox[3] + margin)
        trimmed = image.crop((left, top, right, bottom))
        trimmed.save(path, optimize=True)
        return trimmed.size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        print(f"{path}: {trim(path)}")


if __name__ == "__main__":
    main()
