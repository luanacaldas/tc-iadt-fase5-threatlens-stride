"""Extract the two evaluation architectures from the official FIAP PDF page."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAGE = PROJECT_ROOT / "tmp" / "pdfs" / "fiap-hi-3.png"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "benchmarks" / "real-architecture" / "images"

# Pixel boxes on the reproducible 220-DPI rendering of PDF page 3 (1823x2575).
CROPS = {
    "fiap-architecture-1.png": (455, 400, 1360, 1170),
    "fiap-architecture-2.png": (440, 1330, 1365, 2000),
}


def extract(page_path: Path, output_dir: Path) -> list[Path]:
    with Image.open(page_path) as page:
        if page.size != (1823, 2575):
            raise ValueError(
                f"Expected a 1823x2575 page rendered at 220 DPI, received {page.size}."
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = []
        for filename, box in CROPS.items():
            output = output_dir / filename
            page.crop(box).save(output, optimize=True)
            outputs.append(output)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=Path, default=DEFAULT_PAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for output in extract(args.page, args.output):
        print(output.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
