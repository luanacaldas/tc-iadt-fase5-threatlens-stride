# TL-004A geometric event contract

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
