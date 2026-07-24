"""HTTP smoke test for the packaged ThreatLens MVP.

The default mode validates an already running instance. ``--strategy-matrix``
starts three temporary backend processes to prove legacy, controlled, and the
return to legacy without touching any benchmark or holdout.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = ROOT / "data/sample-diagrams/02-mixed-components.jpg"
DEFAULT_ARCHITECTURE = ROOT / "data/sample-architecture.json"
DEFAULT_OUTPUT = ROOT / "data/results/delivery-readiness/smoke-test-report.json"


def _json_request(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=180) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return exc.code, parsed


def _multipart_request(url: str, filename: str, content_type: str, content: bytes) -> tuple[int, Any]:
    boundary = f"----ThreatLensSmoke{uuid.uuid4().hex}"
    body = b"".join(
        (
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        )
    )
    request = Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=300) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"detail": raw}
        return exc.code, parsed


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def validate_health(payload: Any, expected_strategy: str) -> list[dict[str, Any]]:
    value = payload if isinstance(payload, dict) else {}
    return [
        _check("healthStatus", value.get("status") == "ok", value.get("status")),
        _check("version", value.get("version") == "1.0.0-mvp", value.get("version")),
        _check("flowStrategy", value.get("flowStrategy") == expected_strategy, value.get("flowStrategy")),
    ]


def validate_image_analysis(payload: Any, expected_strategy: str) -> list[dict[str, Any]]:
    value = payload if isinstance(payload, dict) else {}
    return [
        _check("imageComponents", len(value.get("components") or []) > 0, len(value.get("components") or [])),
        _check("imageFlows", len(value.get("flows") or []) > 0, len(value.get("flows") or [])),
        _check("imageStrategy", value.get("flowStrategy") == expected_strategy, value.get("flowStrategy")),
    ]


def validate_full_analysis(payload: Any, expected_strategy: str) -> list[dict[str, Any]]:
    value = payload if isinstance(payload, dict) else {}
    architecture = value.get("architecture") if isinstance(value.get("architecture"), dict) else {}
    threats = value.get("threats") if isinstance(value.get("threats"), list) else []
    has_countermeasures = any(isinstance(item, dict) and item.get("countermeasures") for item in threats)
    pipeline = value.get("pipeline") if isinstance(value.get("pipeline"), dict) else {}
    return [
        _check("fullComponents", len(architecture.get("components") or []) > 0, len(architecture.get("components") or [])),
        _check("fullFlows", len(architecture.get("flows") or []) > 0, len(architecture.get("flows") or [])),
        _check("strideThreats", len(threats) > 0, len(threats)),
        _check("vulnerabilitiesOrCountermeasures", has_countermeasures, has_countermeasures),
        _check("fullStrategy", pipeline.get("flowStrategy") == expected_strategy, pipeline.get("flowStrategy")),
        _check("flowStrategyTrace", isinstance(pipeline.get("flowStrategyTrace"), dict), type(pipeline.get("flowStrategyTrace")).__name__),
    ]


def sample_analysis_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep the real result needed for the sample report without host-local metadata."""
    architecture = payload.get("architecture") or {}
    pipeline = payload.get("pipeline") or {}
    return {
        "architecture": {
            "name": architecture.get("name"),
            "components": [
                {
                    key: component.get(key)
                    for key in ("id", "name", "type", "provider", "confidence", "bbox", "reviewStatus")
                }
                for component in architecture.get("components") or []
            ],
            "flows": [
                {
                    key: flow.get(key)
                    for key in (
                        "id", "from", "to", "protocol", "trustBoundary", "confidence",
                        "inferred", "reviewStatus", "evidence", "directionEvidence",
                    )
                }
                for flow in architecture.get("flows") or []
            ],
            "trustBoundaries": architecture.get("trustBoundaries") or [],
        },
        "threats": payload.get("threats") or [],
        "score": payload.get("score") or {},
        "riskComparison": payload.get("riskComparison") or {},
        "humanReviewItems": payload.get("humanReviewItems") or [],
        "pipeline": {
            "detectorUsed": pipeline.get("detectorUsed"),
            "detectorModel": pipeline.get("detectorModel"),
            "flowStrategy": pipeline.get("flowStrategy"),
            "flowStrategyTrace": pipeline.get("flowStrategyTrace") or {},
            "alternativeTrace": pipeline.get("alternativeTrace") or {},
            "ragDocsRetrieved": pipeline.get("ragDocsRetrieved"),
            "reportApproved": pipeline.get("reportApproved"),
            "reviewRequired": pipeline.get("reviewRequired"),
        },
    }


def run_against_instance(
    base_url: str,
    expected_strategy: str,
    image_path: Path = DEFAULT_IMAGE,
    full_pipeline: bool = True,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    checks: list[dict[str, Any]] = []

    status, health = _json_request(f"{base}/health")
    checks.append(_check("healthHttp200", status == 200, status))
    checks.extend(validate_health(health, expected_strategy))

    image_bytes = image_path.read_bytes()
    status, image_analysis = _multipart_request(
        f"{base}/analyze/image", image_path.name, "image/jpeg", image_bytes
    )
    checks.append(_check("analyzeImageHttp200", status == 200, status))
    checks.extend(validate_image_analysis(image_analysis, expected_strategy))

    full_analysis: dict[str, Any] | None = None
    if full_pipeline:
        status, full_response = _multipart_request(
            f"{base}/analyze/full", image_path.name, "image/jpeg", image_bytes
        )
        full_analysis = sample_analysis_snapshot(full_response) if isinstance(full_response, dict) else None
        checks.append(_check("analyzeFullHttp200", status == 200, status))
        checks.extend(validate_full_analysis(full_response, expected_strategy))

        invalid_status, invalid_response = _multipart_request(
            f"{base}/analyze/image", "invalid.txt", "text/plain", b"not an image"
        )
        detail = invalid_response.get("detail") if isinstance(invalid_response, dict) else invalid_response
        checks.append(_check("invalidImageRejected", invalid_status in {400, 415, 422}, invalid_status))
        checks.append(_check("invalidImageErrorIsReadable", isinstance(detail, str) and bool(detail.strip()), detail))

    return {
        "baseUrl": base_url,
        "expectedStrategy": expected_strategy,
        "image": image_path.relative_to(ROOT).as_posix(),
        "checks": checks,
        "status": "passed" if all(item["passed"] for item in checks) else "failed",
        "sampleAnalysis": full_analysis,
    }


def _wait_for_health(base_url: str, process: subprocess.Popen[Any], timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Backend exited before health check with code {process.returncode}")
        try:
            status, payload = _json_request(f"{base_url.rstrip('/')}/health")
            if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
                return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Backend did not become healthy at {base_url}")


def _run_strategy_phase(strategy: str, port: int, full_pipeline: bool) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "FLOW_STRATEGY": strategy,
            "ENABLE_GENERATIVE_REPORTS": "false",
            "ENABLE_REMOTE_VALIDATION": "false",
            "ENABLE_VISION_FALLBACK": "false",
        }
    )
    command = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base_url, process)
        return run_against_instance(base_url, strategy, full_pipeline=full_pipeline)
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run_strategy_matrix(port_base: int) -> dict[str, Any]:
    phases = [
        _run_strategy_phase("legacy", port_base, full_pipeline=True),
        _run_strategy_phase("junction_aware_controlled", port_base + 1, full_pipeline=False),
        _run_strategy_phase("legacy", port_base + 2, full_pipeline=False),
    ]
    transition = [phase["expectedStrategy"] for phase in phases]
    return {
        "transition": transition,
        "expectedTransition": ["legacy", "junction_aware_controlled", "legacy"],
        "phases": phases,
        "status": "passed" if all(phase["status"] == "passed" for phase in phases) else "failed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4173/api")
    parser.add_argument("--expected-strategy", default="legacy", choices=("legacy", "junction_aware_controlled"))
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strategy-matrix", action="store_true")
    parser.add_argument("--port-base", type=int, default=8121)
    args = parser.parse_args()

    result = (
        run_strategy_matrix(args.port_base)
        if args.strategy_matrix
        else run_against_instance(args.base_url, args.expected_strategy, args.image.resolve())
    )
    report = {
        "schemaVersion": "1.0",
        "version": "1.0.0-mvp",
        "executedAt": datetime.now(timezone.utc).isoformat(),
        "holdoutsExecuted": False,
        **result,
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
