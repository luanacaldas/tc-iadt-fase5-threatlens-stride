"""Build reproducible TL-004A catalogs from deterministic synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.geometric_events import EVENT_TYPES, GeometryParameters, extract_geometric_event_catalog


DEFAULT_FIXTURES = ROOT / "tests/fixtures/tl004a_geometric_events.json"
DEFAULT_OUTPUT = ROOT / "data/results/tl004a-geometric-events"


CONTRACT_MARKDOWN = """# TL-004A geometric event contract

The module `backend/geometric_events.py` is pure and shadow-only. It does not create,
accept, remove, direct, score, or reorder flows.

## Catalog

Each catalog records `schemaVersion`, extractor revision, configured/effective
parameters, canonical segments, geometric events, counts, and invariants.

## Canonical event fields

- `id`: SHA-256-derived deterministic identifier.
- `type`: one of endpoint, continuation, elbow, crossing, explicit_junction,
  bifurcation, component_port, or component_boundary_intersection.
- `coordinates`: quantized event coordinates.
- `sourceSegments`: sorted deterministic segment IDs.
- `armAngles`: sorted arm angles in degrees.
- `provenance`: extractor revision, shadow flag, and input provenance.
- `nearbyComponents`: sorted component IDs within the configured diagnostic radius.
- `classification`: semantic geometric classification, not a flow decision.
- `confidence`: deterministic evidence level; not a calibrated model probability.
- `parameters`: effective tolerance snapshot used by the event.
- `geometricEvidence`: arm, marker, intersection, contact, or barrier evidence.

## Connectivity boundary

`crossing` has `transverseConnectivityAllowed = false`. Only an
`explicit_junction` records transverse connectivity evidence. The catalog never
converts events into graph edges, so it cannot create an A-to-C shortcut.

## Parameters

All spatial tolerances live in the frozen `GeometryParameters` data class. Effective
tolerances account for image scale and line width and are emitted in every catalog.
No value was calibrated from the human TL-004 review cases.

## Compatibility

The legacy pipeline remains the only active flow strategy. No function in
`backend/diagram_structure.py` imports or depends on this module in TL-004A.
"""


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _fixture_result(fixture: dict, catalog: dict) -> dict:
    counts = Counter(event["type"] for event in catalog["events"])
    checks = []
    expected = fixture.get("expected") or {}
    for event_type, minimum in (expected.get("required") or {}).items():
        checks.append(
            {
                "name": f"minimum_{event_type}",
                "actual": counts[event_type],
                "operator": ">=",
                "expected": minimum,
                "passed": counts[event_type] >= minimum,
            }
        )
    for event_type in expected.get("forbidden") or []:
        checks.append(
            {
                "name": f"forbidden_{event_type}",
                "actual": counts[event_type],
                "operator": "==",
                "expected": 0,
                "passed": counts[event_type] == 0,
            }
        )
    for field in ("canonicalSegmentCount", "inputSegmentCount"):
        if field in expected:
            checks.append(
                {
                    "name": field,
                    "actual": catalog["summary"][field],
                    "operator": "==",
                    "expected": expected[field],
                    "passed": catalog["summary"][field] == expected[field],
                }
            )
    return {
        "fixtureId": fixture["id"],
        "title": fixture["title"],
        "topologyRole": fixture.get("topologyRole"),
        "status": "PASS" if all(check["passed"] for check in checks) else "FAIL",
        "checks": checks,
        "eventCountByType": {event_type: counts.get(event_type, 0) for event_type in EVENT_TYPES},
        "canonicalSegmentCount": catalog["summary"]["canonicalSegmentCount"],
    }


def build_artifacts(
    output_dir: Path = DEFAULT_OUTPUT,
    fixtures_path: Path = DEFAULT_FIXTURES,
    *,
    generated_at: str | None = None,
) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"TL-004A output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    payload = json.loads(fixtures_path.read_text(encoding="utf-8"))
    parameters = GeometryParameters()
    catalogs = []
    results = []
    for fixture in payload["fixtures"]:
        catalog = extract_geometric_event_catalog(
            fixture["segments"],
            fixture.get("components") or [],
            fixture.get("explicitJunctions") or [],
            parameters=parameters,
            scale=float(payload["parameters"]["scale"]),
            line_width=float(payload["parameters"]["lineWidth"]),
        )
        catalogs.append(
            {
                "fixtureId": fixture["id"],
                "title": fixture["title"],
                "topologyRole": fixture.get("topologyRole"),
                "catalog": catalog,
            }
        )
        results.append(_fixture_result(fixture, catalog))

    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    status = "PASS" if len(results) == 15 and all(item["status"] == "PASS" for item in results) else "FAIL"
    event_catalog = {
        "schemaVersion": "1.0",
        "generatedAt": timestamp,
        "split": "synthetic_fixtures_only",
        "pipelineIntegration": "none_shadow_only",
        "sourceFixtures": relative_path(fixtures_path),
        "fixtureCount": len(catalogs),
        "catalogs": catalogs,
    }
    fixture_results = {
        "schemaVersion": "1.0",
        "generatedAt": timestamp,
        "status": status,
        "fixtureCount": len(results),
        "passedFixtureCount": sum(item["status"] == "PASS" for item in results),
        "failedFixtureCount": sum(item["status"] != "PASS" for item in results),
        "results": results,
    }
    parameter_payload = {
        "schemaVersion": "1.0",
        "generatedAt": timestamp,
        "configured": parameters.__dict__,
        "effectiveAtFixtureDefaults": parameters.effective(
            float(payload["parameters"]["scale"]),
            float(payload["parameters"]["lineWidth"]),
        ),
        "calibrationSource": "documented_engineering_defaults_not_human_review",
        "source": "backend/geometric_events.py::GeometryParameters",
    }
    artifacts = {
        "eventCatalog": output_dir / "event-catalog.json",
        "fixtureResults": output_dir / "fixture-results.json",
        "parameters": output_dir / "parameters.json",
        "contract": output_dir / "geometric-event-contract.md",
    }
    artifacts["eventCatalog"].write_text(
        json.dumps(event_catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    artifacts["fixtureResults"].write_text(
        json.dumps(fixture_results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    artifacts["parameters"].write_text(
        json.dumps(parameter_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    artifacts["contract"].write_text(CONTRACT_MARKDOWN, encoding="utf-8")
    return {
        "status": status,
        "fixtureCount": len(results),
        "artifacts": {name: relative_path(path) for name, path in artifacts.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_artifacts(ROOT / args.output if not args.output.is_absolute() else args.output, ROOT / args.fixtures if not args.fixtures.is_absolute() else args.fixtures)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
