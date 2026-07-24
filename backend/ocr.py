"""Optional local OCR with explicit evidence and geometry-aware text association."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


STANDARD_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)

PROTOCOL_ALIASES = {
    "http": "HTTP",
    "https": "HTTPS",
    "tls": "TLS",
    "mtls": "mTLS",
    "grpc": "gRPC",
    "rest": "REST",
    "soap": "SOAP",
    "tcp": "TCP",
    "udp": "UDP",
    "mqtt": "MQTT",
    "amqp": "AMQP",
    "ssh": "SSH",
    "sql": "SQL",
    "jdbc": "JDBC",
    "odbc": "ODBC",
    "kafka": "Kafka",
    "sqs": "SQS",
    "websocket": "WebSocket",
    "wss": "WSS",
}


def find_tesseract() -> Path | None:
    configured = os.getenv("TESSERACT_CMD", "").strip()
    candidates = [Path(configured)] if configured else []
    discovered = shutil.which("tesseract")
    if discovered:
        candidates.append(Path(discovered))
    candidates.extend(STANDARD_TESSERACT_PATHS)
    return next((path for path in candidates if path.is_file()), None)


def status() -> dict:
    executable = find_tesseract()
    try:
        import pytesseract  # noqa: F401

        package_available = True
    except Exception:
        package_available = False
    return {
        "available": bool(executable and package_available),
        "engine": "tesseract" if executable and package_available else None,
        "executable": str(executable) if executable else None,
        "packageAvailable": package_available,
        "language": "eng",
    }


def _configure_pytesseract():
    import pytesseract

    executable = find_tesseract()
    if executable is None:
        raise RuntimeError("Tesseract executable was not found")
    pytesseract.pytesseract.tesseract_cmd = str(executable)
    return pytesseract


def _clean_token(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_./:+-]", "", str(value or "")).strip("._:/+-")
    return value if any(character.isalnum() for character in value) else ""


def extract_text_lines(image_path: str | Path, minimum_confidence: float = 0.25) -> list[dict]:
    """Run sparse-text OCR once and return original-image text line coordinates."""
    if not status()["available"]:
        return []

    try:
        from PIL import Image, ImageEnhance, ImageOps

        pytesseract = _configure_pytesseract()
        image = Image.open(image_path).convert("RGB")
        longest_side = max(image.size)
        scale = min(3.0, max(1.5, 2200 / max(1, longest_side)))
        resized = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )
        prepared = ImageOps.grayscale(resized)
        prepared = ImageOps.autocontrast(prepared)
        prepared = ImageEnhance.Sharpness(prepared).enhance(1.8)
        data = pytesseract.image_to_data(
            prepared,
            lang="eng",
            config="--oem 3 --psm 11",
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return []

    grouped: dict[tuple[int, int, int], list[dict]] = {}
    for index, raw_text in enumerate(data.get("text", [])):
        token = _clean_token(raw_text)
        try:
            confidence = float(data["conf"][index]) / 100
        except (TypeError, ValueError, KeyError):
            continue
        if not token or confidence < minimum_confidence:
            continue
        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )
        grouped.setdefault(key, []).append(
            {
                "text": token,
                "confidence": confidence,
                "bbox": [
                    float(data["left"][index]) / scale,
                    float(data["top"][index]) / scale,
                    float(data["left"][index] + data["width"][index]) / scale,
                    float(data["top"][index] + data["height"][index]) / scale,
                ],
            }
        )

    phrases: list[dict] = []
    for words in grouped.values():
        words.sort(key=lambda word: word["bbox"][0])
        current: list[dict] = []
        for word in words:
            if current:
                previous = current[-1]
                average_height = sum(item["bbox"][3] - item["bbox"][1] for item in current) / len(current)
                gap = word["bbox"][0] - previous["bbox"][2]
                if gap > max(14, average_height * 2.2):
                    phrases.append(_merge_words(current))
                    current = []
            current.append(word)
        if current:
            phrases.append(_merge_words(current))
    return sorted(phrases, key=lambda line: (line["bbox"][1], line["bbox"][0]))


def _merge_words(words: list[dict]) -> dict:
    return {
        "text": " ".join(word["text"] for word in words)[:96],
        "confidence": round(sum(word["confidence"] for word in words) / len(words), 3),
        "bbox": [
            round(min(word["bbox"][0] for word in words), 1),
            round(min(word["bbox"][1] for word in words), 1),
            round(max(word["bbox"][2] for word in words), 1),
            round(max(word["bbox"][3] for word in words), 1),
        ],
        "engine": "tesseract",
    }


def match_component_label(lines: list[dict], bbox: list[int]) -> dict | None:
    """Choose nearby text while preferring labels directly below a component icon."""
    x1, y1, x2, y2 = bbox
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    center_x = (x1 + x2) / 2
    candidates = []

    for line in lines:
        if line["confidence"] < 0.55:
            continue
        compact_text = re.sub(r"[^A-Za-z0-9]", "", line.get("text", ""))
        if len(compact_text) < 2 or (len(compact_text) == 2 and not (compact_text.isupper() or any(char.isdigit() for char in compact_text))):
            continue
        lx1, ly1, lx2, ly2 = line["bbox"]
        line_center_x = (lx1 + lx2) / 2
        horizontal_distance = abs(line_center_x - center_x)
        if horizontal_distance > max(width * 1.7, 45):
            continue

        below_distance = ly1 - y2
        below = -height * 0.15 <= below_distance <= max(height * 1.8, 55)
        above = 0 <= y1 - ly2 <= max(height * 0.9, 28)
        overlaps_interior = ly1 < y2 - height * 0.12 and ly2 > y1 + height * 0.12
        if overlaps_interior or not (below or above):
            continue

        relation_bonus = 0.24 if below else 0.06
        horizontal_penalty = horizontal_distance / max(width * 2.0, 80) * 0.22
        vertical_distance = min(abs(below_distance), abs(y1 - ly2))
        vertical_penalty = vertical_distance / max(height * 2.0, 80) * 0.20
        score = line["confidence"] + relation_bonus - horizontal_penalty - vertical_penalty
        candidates.append((score, line))

    if not candidates:
        return None
    score, selected = max(candidates, key=lambda candidate: candidate[0])
    if score < 0.42:
        return None
    return {**selected, "associationScore": round(score, 3), "relation": "near_component"}


def _normalize_protocol_text(text: str) -> str | None:
    normalized = str(text or "").lower()
    url_scheme = re.search(r"\b(https?|ftp|ssh)\s*://", normalized)
    if url_scheme:
        return PROTOCOL_ALIASES[url_scheme.group(1)]
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    if compact in PROTOCOL_ALIASES:
        return PROTOCOL_ALIASES[compact]
    for alias in sorted(PROTOCOL_ALIASES, key=len, reverse=True):
        if compact.startswith(alias) and len(compact) <= len(alias) + 2:
            canonical = PROTOCOL_ALIASES[alias]
            return canonical
    return None


def _point_segment_distance(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> tuple[float, float]:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5, 0.0
    projection = ((px - x1) * dx + (py - y1) * dy) / length_squared
    clipped = max(0.0, min(1.0, projection))
    closest = (x1 + clipped * dx, y1 + clipped * dy)
    distance = ((px - closest[0]) ** 2 + (py - closest[1]) ** 2) ** 0.5
    return distance, projection


def apply_protocol_evidence(flows: list[dict], components: list[dict], lines: list[dict]) -> None:
    component_by_id = {component["id"]: component for component in components}
    protocol_lines = [
        (line, _normalize_protocol_text(line.get("text", "")))
        for line in lines
        if _normalize_protocol_text(line.get("text", ""))
    ]
    for flow in flows:
        source = component_by_id.get(flow.get("from"))
        target = component_by_id.get(flow.get("to"))
        if not source or not target or not source.get("bbox") or not target.get("bbox"):
            continue
        source_center = _bbox_center(source["bbox"])
        target_center = _bbox_center(target["bbox"])
        flow_length = ((target_center[0] - source_center[0]) ** 2 + (target_center[1] - source_center[1]) ** 2) ** 0.5
        maximum_distance = max(18, min(85, flow_length * 0.22))
        candidates = []
        for line, protocol in protocol_lines:
            line_center = _bbox_center(line["bbox"])
            distance, projection = _point_segment_distance(line_center, source_center, target_center)
            if 0.12 <= projection <= 0.88 and distance <= maximum_distance:
                score = line["confidence"] - distance / maximum_distance * 0.25
                candidates.append((score, protocol, line))
        if not candidates:
            continue
        score, protocol, line = max(candidates, key=lambda candidate: candidate[0])
        if score < 0.35:
            continue
        flow["protocol"] = protocol
        flow["protocolEvidence"] = {
            "text": line["text"],
            "ocrConfidence": line["confidence"],
            "bbox": line["bbox"],
            "engine": line.get("engine", "tesseract"),
        }


def _bbox_center(bbox: list[float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
