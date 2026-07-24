"""Build labeled contact sheets for manual real-benchmark annotation review."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "benchmarks" / "real-architecture" / "expansion-candidates.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "benchmarks" / "real-architecture" / "contact-sheets"


def build(manifest_path: Path, output_dir: Path, use_overlays: bool = False) -> list[Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    outputs = []
    for split in ("development_tuning", "blind_holdout"):
        entries = [entry for entry in manifest["entries"] if entry["split"] == split]
        if not entries:
            continue
        columns = 2
        tile_width, tile_height, label_height = 720, 430, 36
        rows = math.ceil(len(entries) / columns)
        sheet = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), "white")
        drawing = ImageDraw.Draw(sheet)
        for index, entry in enumerate(entries):
            row, column = divmod(index, columns)
            left = column * tile_width
            top = row * (tile_height + label_height)
            overlay_path = (
                PROJECT_ROOT
                / "data"
                / "benchmarks"
                / "real-architecture"
                / "contact-sheets"
                / "overlays"
                / f"{entry['id']}.png"
            )
            image_path = overlay_path if use_overlays and overlay_path.is_file() else PROJECT_ROOT / entry["image"]
            with Image.open(image_path) as source:
                preview = source.convert("RGB")
                preview.thumbnail((tile_width - 20, tile_height - 20))
                x = left + (tile_width - preview.width) // 2
                y = top + (tile_height - preview.height) // 2
                sheet.paste(preview, (x, y))
            drawing.rectangle((left, top, left + tile_width - 1, top + tile_height - 1), outline="#94a3b8")
            drawing.text((left + 12, top + tile_height + 10), f"{entry['id']} | {entry['provider']}", fill="#111827", font=font)
        output = output_dir / f"{split}.png"
        sheet.save(output, optimize=True)
        outputs.append(output)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--use-overlays", action="store_true")
    args = parser.parse_args()
    for output in build(args.manifest.resolve(), args.output.resolve(), args.use_overlays):
        print(output.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
