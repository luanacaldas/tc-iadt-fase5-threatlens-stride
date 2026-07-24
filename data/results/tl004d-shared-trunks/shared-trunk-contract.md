# TL-004D shared-trunk and branch-pairing contract

## Scope

This strategy is experimental, opt-in, shadow-only, comparative, deterministic, and
reversible. Legacy flows remain the only official source for the graph, STRIDE, threats,
risk, APIs, and reports. Shadow relations are never eligible for official consumption.

## Inputs and dependencies

TL-004D consumes canonical geometric segments and local events from TL-004A, component
contacts and barriers from TL-004B, and allowed or blocked local branch pairs from TL-004C.
It does not duplicate or modify those classifiers. Direction associated with a reviewed or
legacy terminal is evidence for shadow pairing only and never changes official direction.

## Trunk and arm contract

A trunk has a deterministic ID, canonical segment IDs, segment provenance, local events,
junction arms, directionally supported input and output arms, unknown-direction arms,
connected ports, terminal components, confidence, reasons, parameters, allowed pairings,
blocked pairings, and review-only alternatives. A shared trunk is internal structure, not an
edge. Only supported source-to-destination terminal pairs become experimental relations.

## Safety rules

Unmarked crossings retain only TL-004C collinear continuity. Near but disconnected or
nearly parallel arms are not combined. Component barriers force adjacent relations and
prevent shortcuts. A single source with multiple destinations is fan-out; multiple sources
with one destination is fan-in. Ambiguous direction produces `review_only`, never an edge.
All unselected terminal permutations are recorded as prevented clique relations.

## C04 evidence boundary

C04 uses a separately identified human-reviewed connector trace to test whether the shadow
contract can represent the two reviewed private-bus edges. This is a supervised regression,
not evidence that the current detector independently recovered the missing pixels or edges.
