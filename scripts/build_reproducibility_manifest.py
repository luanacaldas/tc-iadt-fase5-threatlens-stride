"""Record immutable hashes, versions, seeds, and benchmark provenance."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/reproducibility.json"
TRACKED = [
    "models/threatlens-hybrid-v2/weights/best.pt",
    "models/arrowhead-logistic/model.json",
    "models/component-confidence-calibration.json",
    "dataset/hybrid_v2/architecture.yaml",
    "data/benchmarks/real-architecture/benchmark-expanded.json",
    "data/benchmarks/real-architecture/benchmark-fiap-corrected-v3.json",
    "data/benchmarks/real-architecture/benchmark-prospective-v12.json",
    "data/benchmarks/real-architecture/prospective-v12-seal.json",
    "data/benchmarks/real-architecture/prospective-v12-provenance-erratum.json",
    "data/benchmarks/structure/benchmark.json",
    "data/benchmarks/stride/golden-set.json",
    "data/results/end-to-end/end-to-end-blind_holdout-initial.json",
    "data/results/end-to-end-posthoc/end-to-end-blind_holdout.json",
    "data/results/ocr-geometry-ablation/stacked-labels-v7/end-to-end-development_tuning.json",
    "data/results/ocr-geometry-ablation/resolution-aware-v12/end-to-end-development_tuning.json",
    "data/results/ocr-geometry-ablation/semantic-abstention-v13/end-to-end-development_tuning.json",
    "data/results/ocr-geometry-ablation/semantic-fusion-v14/end-to-end-development_tuning.json",
    "data/results/ocr-geometry-ablation/semantic-arbitration-v15-conservative/end-to-end-development_tuning.json",
    "data/results/ocr-geometry-ablation/semantic-arbitration-v15/end-to-end-development_tuning.json",
    "data/results/end-to-end-prospective-v12/end-to-end-prospective_holdout.json",
    "data/results/end-to-end-prospective-v12/result-seal.json",
    "data/results/end-to-end-posthoc-v5-resolution-aware/end-to-end-blind_holdout.json",
    "data/results/end-to-end-prospective-v13-posthoc/end-to-end-prospective_holdout.json",
    "data/results/end-to-end-posthoc-v6-semantic-abstention/end-to-end-blind_holdout.json",
    "data/results/end-to-end-posthoc-v3/end-to-end-blind_holdout.json",
    "data/results/end-to-end-posthoc-v4-corrected-annotations/end-to-end-blind_holdout.json",
    "data/results/end-to-end-improvement-comparison.json",
    "data/sealed-code/detector-v12.py",
    "data/sealed-code/detector-v13.py",
    "data/sealed-code/detector-v15.py",
    "data/results/active-learning/model-comparison.json",
    "data/results/calibration/component-confidence.json",
    "data/results/benchmark-audit/real-benchmark-integrity.json",
    "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-inventory.json",
    "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-diagnostics-summary.json",
    "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-stratified-metrics.json",
    "data/results/flow-diagnostics-v1/isolated-ground-truth/flow-human-review.json",
    "data/results/flow-diagnostics-v1/end-to-end/flow-inventory.json",
    "data/results/flow-diagnostics-v1/end-to-end/flow-diagnostics-summary.json",
    "data/results/flow-diagnostics-v1/end-to-end/flow-stratified-metrics.json",
    "data/results/flow-diagnostics-v1/end-to-end/flow-human-review.json",
    "runs/detect/models/threatlens-active-v3/weights/best.pt",
    "backend/detector.py",
    "backend/config.py",
    "backend/analysis_quality.py",
    "backend/main.py",
    "backend/rag.py",
    "backend/diagram_structure.py",
    "backend/stride_engine.py",
    "backend/pdf_report.py",
    "backend/requirements.txt",
    "backend/requirements-lock.txt",
    "src/analysis_artifacts.mjs",
    "src/threatlens.mjs",
    "app/index.html",
    "app/main.js",
    "app/runtime-config.js",
    "app/styles.css",
    "app/ui-contract.mjs",
    "README.md",
    "VERSION",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "docs/architecture.md",
    "docs/model-development.md",
    "docs/api-contract.md",
    "docs/evaluation.md",
    "docs/limitations.md",
    "docs/sample-threat-model.md",
    "docs/frontend.md",
    "docs/mvp-hardening-001.md",
    "docs/demo-script.md",
    "docs/submission-evidence.md",
    "data/sample-diagrams/README.md",
    "data/sample-diagrams/01-simple-api.jpg",
    "data/sample-diagrams/02-mixed-components.jpg",
    "data/sample-diagrams/03-security-controls.jpg",
    "data/sample-diagrams/04-dense-pipeline.jpg",
    "docs/final-technical-evidence.md",
    "docs/real-architecture-benchmark.md",
    "docs/judging-brief-ptbr.md",
    "Dockerfile",
    "docker-compose.yml",
    "scripts/package_offline_demo.py",
    "scripts/evaluate_blind_end_to_end.py",
    "scripts/build_corrected_fiap_benchmark.py",
    "scripts/summarize_end_to_end_improvements.py",
    "scripts/check_v15_regression.py",
    "scripts/diagnose_flow_errors.py",
    "scripts/audit_prospective_v12.py",
    "scripts/audit_real_benchmark_integrity.py",
    "scripts/build_reproducibility_manifest.py",
    "scripts/verify_project.py",
    "scripts/smoke_test.py",
    "scripts/generate_sample_threat_model.py",
    "scripts/build_delivery_readiness.py",
    "scripts/build_frontend.mjs",
    "scripts/build_web_mvp_artifacts.py",
    "scripts/validate_mvp_hardening.py",
    "scripts/build_tl004a_artifacts.py",
    "scripts/build_tl004b_artifacts.py",
    "scripts/build_tl004c_artifacts.py",
    "scripts/build_tl004d_artifacts.py",
    "scripts/build_tl004e_artifacts.py",
    "scripts/build_tl004f_artifacts.py",
    "scripts/build_tl_struct_001a_artifacts.py",
    "tests/test_backend_pipeline.py",
    "tests/test_detection_alternatives.py",
    "tests/test_detection_alternatives.mjs",
    "tests/test_end_to_end_benchmark.py",
    "tests/test_frontend_contract.py",
    "tests/test_web_mvp.py",
    "tests/test_web_mvp.mjs",
    "tests/test_analysis_quality.py",
    "tests/test_v15_regression_gate.py",
    "tests/test_flow_diagnostics.py",
    "tests/test_reproducibility_manifest.py",
    "tests/test_review_submission.py",
    "tests/test_geometric_events.py",
    "tests/test_endpoint_validation.py",
    "tests/test_intersection_validation.py",
    "tests/test_shared_trunk_reconstruction.py",
    "tests/test_transitive_shortcut_validation.py",
    "tests/test_integrated_junction_strategy.py",
    "tests/test_structural_line_gate.py",
    "tests/fixtures/tl004a_geometric_events.json",
    "tests/fixtures/tl004c_intersections.json",
    "tests/fixtures/tl004d_shared_trunks.json",
    "tests/fixtures/tl004e_transitive_shortcuts.json",
    "tests/fixtures/tl004f_integration.json",
    "tests/fixtures/tl_struct_001a.json",
    "data/fixtures/tl004d_c04_shared_trunk.json",
    "backend/review_submission.py",
    "backend/geometric_events.py",
    "backend/endpoint_validation.py",
    "backend/intersection_validation.py",
    "backend/shared_trunk_reconstruction.py",
    "backend/transitive_shortcut_validation.py",
    "backend/integrated_junction_strategy.py",
    "backend/structural_line_gate.py",
    "backend/flow_strategy.py",
    "tests/test_flow_strategy_promotion.py",
    "tests/test_delivery_readiness.py",
    "server.mjs",
    "package.json",
    "data/results/web-mvp-001/frontend-inventory.json",
    "data/results/web-mvp-001/api-integration-report.json",
    "data/results/web-mvp-001/ui-smoke-test.json",
    "data/results/web-mvp-001/accessibility-checklist.json",
    "data/results/web-mvp-001/sample-analysis-report.json",
    "data/results/web-mvp-001/frontend-test-report.json",
    "data/results/web-mvp-001/production-build-report.json",
    "data/results/web-mvp-001/web-mvp-decision.json",
    "data/results/mvp-hardening-001/external-image-quality.json",
]
TRACKED.extend(
    str(path.relative_to(ROOT)).replace("\\", "/")
    for path in sorted((ROOT / "backend/knowledge").rglob("*.md"))
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build() -> dict:
    files = {}
    for relative in TRACKED:
        path = ROOT / relative
        files[relative] = {"sha256": sha256(path), "bytes": path.stat().st_size} if path.is_file() else None
    packages = {}
    for name in (
        "fastapi", "uvicorn", "python-dotenv", "google-genai", "groq", "chromadb",
        "sentence-transformers", "ultralytics", "opencv-python-headless", "pillow",
        "python-multipart", "scikit-learn", "torch", "pytesseract", "reportlab",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    benchmark = json.loads((ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json").read_text(encoding="utf-8"))
    evaluation = json.loads((ROOT / "data/results/end-to-end-improvement-comparison.json").read_text(encoding="utf-8"))
    return {
        "schemaVersion": "1.1",
        "integrityPolicy": {
            "algorithm": "sha256",
            "operationalMetadata": "excluded_from_sealed_artifacts",
        },
        "runtime": {"python": platform.python_version(), "platform": platform.platform(), "packages": packages},
        "seeds": {"detectorTraining": 42, "arrowheadClassifier": 42, "activeLearningSplit": 42},
        "remoteCallsRequired": False,
        "offlineFlags": {
            "ENABLE_GENERATIVE_REPORTS": False,
            "ENABLE_REMOTE_VALIDATION": False,
            "ENABLE_VISION_FALLBACK": False,
            "FLOW_STRATEGY": "legacy",
        },
        "benchmark": {
            "imageCount": benchmark["imageCount"],
            "splitCounts": benchmark["splitCounts"],
            "sealedAt": benchmark["sealedAt"],
            "providers": benchmark["providers"],
        },
        "endToEndEvidence": {
            name: {
                "protocol": result["protocol"],
                "f1": result["f1"],
                "meanComponentTypedRecall": result["meanComponentTypedRecall"],
                "source": result["source"],
            }
            for name, result in evaluation["results"].items()
        },
        "files": files,
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    manifest = build()
    OUTPUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written to {OUTPUT}")


if __name__ == "__main__":
    main()
