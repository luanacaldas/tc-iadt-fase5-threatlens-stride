"""Generate the deterministic sample PDF used in the offline demo package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.pdf_report import generate_pdf
from backend.stride_engine import analyze_architecture


def main() -> None:
    architecture = json.loads((ROOT / "data/sample-architecture.json").read_text(encoding="utf-8"))
    analysis = analyze_architecture(architecture)
    output = ROOT / "output/pdf/threatlens-sample-report.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(generate_pdf(analysis))
    print(output)


if __name__ == "__main__":
    main()
