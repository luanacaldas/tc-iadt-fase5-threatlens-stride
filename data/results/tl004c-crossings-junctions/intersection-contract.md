# TL-004C crossing and junction contract

## Scope

The classifier is experimental, opt-in, shadow-only, comparative, and reversible. Legacy
flows remain the only official input for the graph, STRIDE, threats, risk, and APIs.

## Local classifications

Events are classified as `continuation`, `elbow`, `crossing_without_junction`,
`explicit_junction`, `bifurcation`, or `ambiguous_intersection`. The implementation reuses
TL-004A arms and marker evidence and TL-004B component contacts and barriers.

At an unmarked X, only approximately collinear pairs are allowed locally; transverse branch
switches are recorded as blocked. A qualified visual marker allows local junction
connectivity. T and Y events preserve all observed arms but defer source-destination trunk
decomposition. Ambiguous evidence is always `review_only`.

## Safety boundaries

No shadow decision changes, removes, redirects, or accepts an official edge. This task does
not implement global arm pairing, shared-trunk decomposition, missing fan-in or fan-out
reconstruction, structural-line filtering, ranking, hard-negative mining, direction changes,
arrowhead changes, legacy thresholds, promotion, or TL-004D behavior.
