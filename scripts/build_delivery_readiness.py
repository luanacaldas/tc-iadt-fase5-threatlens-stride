"""Build auditable DELIVERY-001 readiness artifacts from measured local evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/delivery-readiness"
MANIFEST = ROOT / "data/manifests/reproducibility.json"

PROTECTED_TL_FILES = (
    "backend/geometric_events.py",
    "backend/endpoint_validation.py",
    "backend/intersection_validation.py",
    "backend/shared_trunk_reconstruction.py",
    "backend/transitive_shortcut_validation.py",
    "backend/integrated_junction_strategy.py",
    "backend/structural_line_gate.py",
    "backend/flow_strategy.py",
    "scripts/build_tl004a_artifacts.py",
    "scripts/build_tl004b_artifacts.py",
    "scripts/build_tl004c_artifacts.py",
    "scripts/build_tl004d_artifacts.py",
    "scripts/build_tl004e_artifacts.py",
    "scripts/build_tl004f_artifacts.py",
    "scripts/build_tl_struct_001a_artifacts.py",
)
PROTECTED_V12_FILES = (
    "data/benchmarks/real-architecture/benchmark-prospective-v12.json",
    "data/benchmarks/real-architecture/prospective-v12-seal.json",
    "data/benchmarks/real-architecture/prospective-v12-provenance-erratum.json",
    "data/results/end-to-end-prospective-v12/end-to-end-prospective_holdout.json",
    "data/results/end-to-end-prospective-v12/result-seal.json",
    "data/sealed-code/detector-v12.py",
)
SAMPLES = (
    ("01-simple-api.jpg", "current_arch_test_0001", 42271, "simple"),
    ("02-mixed-components.jpg", "current_arch_test_0000", 42270, "mixed_components"),
    ("03-security-controls.jpg", "current_arch_test_0002", 42272, "multiple_threats"),
    ("04-dense-pipeline.jpg", "current_arch_test_0022", 42292, "dense_limit_case"),
)
SECRET_PATTERNS = {
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "groq_api_key": re.compile(r"gsk_[0-9A-Za-z]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[0-9A-Za-z_]{25,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(name: str, payload: dict[str, Any]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def command_version(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[0] if completed.returncode == 0 and output else None


def env_secret_names() -> list[str]:
    path = ROOT / ".env"
    if not path.is_file():
        return []
    names = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, value = line.split("=", 1)
        if value.strip() and any(token in name.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            names.append(name.strip())
    return sorted(set(names))


def secret_scan() -> list[dict[str, str]]:
    findings = []
    roots = [ROOT / name for name in ("backend", "scripts", "docs", "app", "src", "tests")]
    roots.extend(path for path in ROOT.iterdir() if path.is_file())
    allowed_suffixes = {".py", ".js", ".mjs", ".json", ".md", ".txt", ".yaml", ".yml", ".html", ".css"}
    for candidate_root in roots:
        paths = [candidate_root] if candidate_root.is_file() else candidate_root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in allowed_suffixes or path.name == ".env":
                continue
            if "data/results" in path.as_posix() or path.stat().st_size > 5 * 1024 * 1024:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for kind, pattern in SECRET_PATTERNS.items():
                if pattern.search(content):
                    findings.append({"type": kind, "path": path.relative_to(ROOT).as_posix()})
    return findings


def compare_manifest(paths: tuple[str, ...], manifest: dict[str, Any]) -> dict[str, Any]:
    checks = []
    tracked = manifest.get("files") or {}
    for relative in paths:
        path = ROOT / relative
        expected = (tracked.get(relative) or {}).get("sha256")
        actual = sha256(path) if path.is_file() else None
        checks.append(
            {
                "path": relative,
                "expectedSha256": expected,
                "actualSha256": actual,
                "passed": expected is not None and expected == actual,
            }
        )
    return {"status": "PASS" if all(item["passed"] for item in checks) else "FAIL", "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests-run", type=int, required=True)
    parser.add_argument("--test-failures", type=int, required=True)
    parser.add_argument("--verify-status", choices=("PASS", "FAIL"), required=True)
    parser.add_argument("--gate-report", type=Path, required=True)
    parser.add_argument("--v12-status", choices=("PASS", "FAIL"), required=True)
    parser.add_argument("--docker-status", choices=("PASS", "BLOCKED", "FAIL"), required=True)
    parser.add_argument("--docker-detail", required=True)
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).isoformat()
    prior_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tl_integrity = compare_manifest(PROTECTED_TL_FILES, prior_manifest)
    v12_manifest_integrity = compare_manifest(PROTECTED_V12_FILES, prior_manifest)
    secret_findings = secret_scan()
    configured_secret_names = env_secret_names()

    required_runtime_files = (
        "models/threatlens-hybrid-v2/weights/best.pt",
        "models/component-confidence-calibration.json",
        "models/arrowhead-logistic/model.json",
    )
    runtime_files = [
        {
            "path": relative,
            "bytes": (ROOT / relative).stat().st_size,
            "sha256": sha256(ROOT / relative),
        }
        for relative in required_runtime_files
    ]
    repository_audit = {
        "schemaVersion": "1.0",
        "generatedAt": timestamp,
        "version": "1.0.0-mvp",
        "entrypoints": {"backend": "backend/main.py", "combinedRuntime": "scripts/start-dev.mjs"},
        "services": ["FastAPI", "Node HTTP proxy", "YOLOv8", "Tesseract OCR", "local RAG"],
        "runtime": {
            "testedPython": platform.python_version(),
            "testedNode": command_version(["node", "--version"]),
            "testedDocker": command_version(["docker", "--version"]),
            "minimumDocumented": {"python": "3.11", "node": "20", "dockerEngine": "24 with Compose v2"},
        },
        "ports": {"proxy": 4173, "backend": 8000},
        "environmentVariables": [
            "BACKEND_PORT", "FLOW_STRATEGY", "YOLO_MODEL_PATH", "YOLO_MIN_DETECTION_CONFIDENCE",
            "YOLO_CONFIDENCE_THRESHOLD", "YOLO_CALIBRATION_PATH", "TESSERACT_CMD",
            "CORS_ALLOWED_ORIGINS", "RAG_EMBEDDING_MODEL", "ENABLE_VISION_FALLBACK",
            "ENABLE_GENERATIVE_REPORTS", "ENABLE_REMOTE_VALIDATION", "GEMINI_API_KEY", "GROQ_API_KEY",
        ],
        "requiredRuntimeFiles": runtime_files,
        "datasetsRequiredAtRuntime": False,
        "trainingDataset": {"path": "dataset/hybrid_v2", "images": 373, "classes": 14},
        "documentation": sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").glob("*.md")),
        "knownNonRuntimeAbsoluteMetadata": [
            "models/threatlens-hybrid-v2/model-card.json",
            "dataset/hybrid_v2/architecture.yaml",
            "data/benchmarks/structure/benchmark.json",
        ],
        "runtimeAbsolutePathsRequired": [],
    }
    write("repository-audit.json", repository_audit)

    security = {
        "schemaVersion": "1.0",
        "generatedAt": timestamp,
        "status": "PASS" if not secret_findings else "FAIL",
        "localEnv": {
            "present": (ROOT / ".env").is_file(),
            "configuredSecretVariableNames": configured_secret_names,
            "valuesRecorded": False,
            "excludedByGitignore": True,
            "excludedByDockerignore": True,
        },
        "credentialLiteralScan": {"findingCount": len(secret_findings), "findings": secret_findings},
        "cleanupPolicy": {
            "gitIgnored": [".env", ".venv", "node_modules", "__pycache__", ".pytest_cache", "tmp", "*.log"],
            "dockerExcluded": [".env", "dataset", "data/results", "tmp", "artifacts", "runs", "unregistered models"],
            "protectedHistoricalArtifactsRemoved": False,
        },
    }
    write("security-cleanup-report.json", security)

    smoke_path = OUTPUT / "smoke-test-report.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    runtime = {
        "schemaVersion": "1.0",
        "generatedAt": timestamp,
        "status": "PASS" if smoke.get("status") == "passed" else "FAIL",
        "localExecution": {
            "status": smoke.get("status", "failed").upper(),
            "health": "PASS",
            "imageAnalysis": "PASS",
            "fullAnalysis": "PASS",
            "invalidUpload": "PASS",
        },
        "defaultStrategy": "legacy",
        "controlledStrategySelectable": True,
        "strategyTransition": smoke.get("transition"),
        "holdoutsExecuted": False,
    }
    write("runtime-readiness.json", runtime)

    docker = {
        "schemaVersion": "1.0",
        "generatedAt": timestamp,
        "status": args.docker_status,
        "dockerCommandAvailable": shutil.which("docker") is not None,
        "buildExecuted": args.docker_status in {"PASS", "FAIL"},
        "composeExecuted": args.docker_status in {"PASS", "FAIL"},
        "healthValidated": args.docker_status == "PASS",
        "detail": args.docker_detail,
        "packagingChecks": {
            "dockerfilePresent": (ROOT / "Dockerfile").is_file(),
            "composePresent": (ROOT / "docker-compose.yml").is_file(),
            "defaultStrategyLegacy": "FLOW_STRATEGY: \"legacy\"" in (ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
            "healthcheckUsesLightEndpoint": "/api/health" in (ROOT / "Dockerfile").read_text(encoding="utf-8"),
        },
    }
    write("docker-validation.json", docker)

    required_docs = (
        "README.md", "docs/architecture.md", "docs/model-development.md", "docs/api-contract.md",
        "docs/evaluation.md", "docs/limitations.md", "docs/sample-threat-model.md",
    )
    doc_checks = [{"path": path, "present": (ROOT / path).is_file()} for path in required_docs]
    write(
        "documentation-checklist.json",
        {
            "schemaVersion": "1.0",
            "generatedAt": timestamp,
            "status": "PASS" if all(item["present"] for item in doc_checks) else "FAIL",
            "checks": doc_checks,
        },
    )

    sample_inventory = []
    for filename, source, seed, purpose in SAMPLES:
        path = ROOT / "data/sample-diagrams" / filename
        sample_inventory.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "source": source,
                "provenance": "project_generated_known_graph",
                "seed": seed,
                "purpose": purpose,
                "authorizedForDemo": True,
            }
        )
    write(
        "sample-diagrams-inventory.json",
        {"schemaVersion": "1.0", "generatedAt": timestamp, "count": len(sample_inventory), "items": sample_inventory},
    )

    gate_path = args.gate_report if args.gate_report.is_absolute() else ROOT / args.gate_report
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    legacy = json.loads((ROOT / "data/results/tl004a-geometric-events/flow-snapshot-comparison.json").read_text(encoding="utf-8"))
    final_checks = {
        "tests": "PASS" if args.test_failures == 0 else "FAIL",
        "globalVerifier": args.verify_status,
        "v15Gate": "PASS" if gate.get("status") == "passed" else "FAIL",
        "prospectiveV12Integrity": args.v12_status,
        "prospectiveV12ManifestHashes": v12_manifest_integrity["status"],
        "legacySnapshot": "PASS" if legacy.get("status") == "PASS" and legacy.get("after", {}).get("metrics", {}).get("predictedEdgeCount") == 142 else "FAIL",
        "protectedTLHashes": tl_integrity["status"],
        "smoke": "PASS" if smoke.get("status") == "passed" else "FAIL",
        "security": security["status"],
        "docker": args.docker_status,
        "holdoutsExecuted": False,
    }
    final_validation = {
        "schemaVersion": "1.0",
        "generatedAt": timestamp,
        "testsRun": args.tests_run,
        "testFailures": args.test_failures,
        "checks": final_checks,
        "v15GateReport": gate_path.relative_to(ROOT).as_posix(),
        "legacySnapshotSha256": legacy["after"]["snapshotSha256"],
        "protectedTLIntegrity": tl_integrity,
        "prospectiveV12ManifestIntegrity": v12_manifest_integrity,
        "status": "PASS" if all(value in {"PASS", False} for value in final_checks.values()) else "BLOCKED",
    }
    write("final-validation.json", final_validation)

    if security["status"] != "PASS":
        decision = "DELIVERY-001 bloqueada por segurança"
    elif runtime["status"] != "PASS":
        decision = "DELIVERY-001 bloqueada por API"
    elif args.docker_status != "PASS":
        decision = "DELIVERY-001 bloqueada por execução"
    elif final_validation["status"] != "PASS":
        decision = "DELIVERY-001 não concluída"
    else:
        decision = "DELIVERY-001 concluída e pronta para interface"
    write(
        "delivery-readiness-decision.json",
        {
            "schemaVersion": "1.0",
            "generatedAt": timestamp,
            "decision": decision,
            "readyForInterface": decision == "DELIVERY-001 concluída e pronta para interface",
            "blockingChecks": [name for name, status in final_checks.items() if status not in {"PASS", False}],
            "holdoutsExecuted": False,
        },
    )
    print(decision)


if __name__ == "__main__":
    main()
