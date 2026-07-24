"""Bootstrap reviewable benchmark drafts and active-learning overlays from selected images."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.detector import detect, status


DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "benchmarks" / "real-architecture" / "expansion-candidates.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "benchmarks" / "real-architecture" / "draft-annotations.json"
DEFAULT_OVERLAYS = PROJECT_ROOT / "data" / "benchmarks" / "real-architecture" / "contact-sheets" / "overlays"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _overlay(image_path: Path, architecture: dict | None, output: Path) -> None:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    drawing = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for component in (architecture or {}).get("components") or []:
        bbox = tuple(component["bbox"])
        color = "#16a34a" if component.get("reviewStatus") == "auto_accepted" else "#dc2626"
        drawing.rectangle(bbox, outline=color, width=max(2, round(min(image.size) * 0.003)))
        label = f"{component['id']} {component['confidence']:.2f}"
        text_bbox = drawing.textbbox((bbox[0], bbox[1]), label, font=font)
        drawing.rectangle(text_bbox, fill="white")
        drawing.text((bbox[0], bbox[1]), label, fill=color, font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.thumbnail((1800, 1400))
    image.save(output, optimize=True)


def build(manifest_path: Path, output_path: Path, overlay_dir: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = []
    for index, selected in enumerate(manifest["entries"], start=1):
        image_path = PROJECT_ROOT / selected["image"]
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        with Image.open(image_path) as image:
            width, height = image.size
        print(f"[{index}/{len(manifest['entries'])}] {selected['id']}", flush=True)
        architecture = detect(str(image_path))
        overlay_path = overlay_dir / f"{selected['id']}.png"
        _overlay(image_path, architecture, overlay_path)
        entries.append(
            {
                **selected,
                "annotationSize": [width, height],
                "imageSha256": _sha256(image_path),
                "annotationStatus": "draft_model_proposal",
                "components": (architecture or {}).get("components") or [],
                "flows": (architecture or {}).get("flows") or [],
                "boundaries": (architecture or {}).get("trustBoundaries") or [],
                "protocols": [
                    {
                        "flowId": flow["id"],
                        "value": flow["protocol"],
                        "evidenceText": (flow.get("protocolEvidence") or {}).get("text"),
                    }
                    for flow in (architecture or {}).get("flows") or []
                    if str(flow.get("protocol") or "unknown").lower() != "unknown"
                ],
                "detectorDiagnostics": {
                    "componentCount": len((architecture or {}).get("components") or []),
                    "flowCount": len((architecture or {}).get("flows") or []),
                    "averageConfidence": (architecture or {}).get("avgDetectionConfidence"),
                    "structure": (architecture or {}).get("structureMetadata") or {},
                    "overlay": str(overlay_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                },
            }
        )
    result = {
        "schemaVersion": "1.0",
        "annotationMethod": "YOLO and geometric bootstrap; requires visual review before scoring.",
        "detector": status(),
        "entries": entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overlays", type=Path, default=DEFAULT_OVERLAYS)
    args = parser.parse_args()
    result = build(args.manifest.resolve(), args.output.resolve(), args.overlays.resolve())
    print(f"Drafted {len(result['entries'])} entries at {args.output}")


if __name__ == "__main__":
    main()
