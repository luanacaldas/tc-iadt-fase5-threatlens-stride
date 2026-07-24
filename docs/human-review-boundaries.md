# Trust-Boundary Human Review

## Why It Exists

Rectangles in architecture diagrams can represent security boundaries, visual grouping, cloud
regions, availability zones, or decorative containers. ThreatLens therefore treats detected
zones as candidates and requires a person to confirm their membership before the final STRIDE
report.

## Review Workflow

The dashboard now supports three coordinated review tables:

1. Components can be included, renamed, and reclassified.
2. Flows can be included, redirected, and assigned an explicit protocol.
3. Trust boundaries can be included, named, and assigned internal components.

When membership is present, it becomes authoritative. A flow crosses a boundary when exactly
one of its endpoints belongs to that boundary. Confirmation recalculates:

- `trustBoundary` on every flow.
- `crossedBoundaryIds` with the exact confirmed zones.
- `reviewStatus` on components, flows, and boundaries.
- `reviewedByHuman` for the complete architecture.

If no boundary has explicit membership, the manual crossing checkbox remains available for
diagrams that do not draw a containing zone.

## Backend Safety

The API independently performs the same reconciliation before analysis. This prevents a JSON
client from claiming that an internal flow crosses a confirmed zone, or that an external flow
does not, when the reviewed membership proves otherwise.

## Verification

The automated suite proves that:

- External-to-internal membership sets the crossing flag and boundary ID.
- Internal-to-internal membership clears an inconsistent crossing flag.
- The input object is not mutated during reconciliation.

The browser workflow was also checked at desktop and mobile viewports. Wide review tables stay
inside horizontally scrollable containers and do not create page-level overflow.
