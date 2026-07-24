# TL-004B ports and barriers contract

## Scope

This contract is experimental, opt-in, shadow-only, and reversible. `legacy` remains the
default strategy and the only source for STRIDE, threats, risk, and official API responses.

## Component ports

A port is derived only from TL-004A `component_port` or
`component_boundary_intersection` evidence. Each port records the component, coordinate,
bounding-box side, distance from both path endpoints, arrival/departure angle, responsible
segment, confidence, and geometric evidence. Tangential contact remains low-confidence and
does not create a component barrier.

## Endpoint decisions

Endpoint classifications are `confirmed_contact`, `ambiguous_contact`, `proximity_only`,
`no_contact`, and `wrong_component_contact`. Path-point reversal is internal to the shadow
analysis and never mutates the candidate. Proximity without visual contact cannot confirm a
port.

## Component barriers

A verified interior crossing of a component that is not an endpoint stops the experimental
path at the first such component. Declared source and destination components are never
barriers. Adjacent relations may be proposed for review, but no shadow relation is promoted
to the official graph.

## Exclusions

TL-004B does not classify X/T/Y junctions, pair arms, reconstruct shared trunks, filter
structural lines, rank edges, mine hard negatives, or change legacy thresholds, direction,
or arrowhead evidence.
