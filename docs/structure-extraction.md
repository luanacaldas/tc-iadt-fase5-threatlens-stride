# Flow and Trust-Boundary Extraction

## Purpose

Component detection alone is not enough for STRIDE. ThreatLens therefore adds a local,
auditable structure-extraction stage after YOLO. It looks for visual line evidence between
detected component boxes and for large rectangular zones that may represent VPCs, resource
groups, subnets, availability zones, or other trust boundaries.

No paid API or generative model is used in this stage.

## Pipeline

1. YOLO returns component classes, confidence values, and bounding boxes.
2. OpenCV isolates neutral strokes before Canny and probabilistic Hough transforms, reducing
   confusion from colorful provider icons and augmentation overlays.
3. Segment endpoints are associated with the nearest component boxes; aligned fragmented
   lines can be recovered from continuous pixel support.
4. Duplicate component pairs are collapsed to the strongest visual candidate, lines cannot
   skip an intermediate component, and weak geometric pairs are rejected.
5. A Canny ray-support detector compares arrowhead wings at both ends of each line.
6. Direction uses qualified visual arrowhead evidence first, then explicit source semantics
   (`user`, `internet`, identity), and finally left-to-right or top-to-bottom layout.
7. Large rectangular contours become reviewable trust-zone candidates.
8. A flow is marked as boundary-crossing when its endpoints have different zone membership
   or when an external node connects to an internal node.
9. If no line can be associated, the old adjacency heuristic remains as a low-confidence
   fallback.

## Evidence Contract

Every inferred flow contains:

- `evidence`: `detected_line`, `pixel_line_support`, or `layout_adjacency`.
- `directionEvidence`: visual arrowhead, semantic source, horizontal layout, or vertical layout.
- `directionConfidence`: normalized confidence in the selected direction.
- `arrowheadScores`: visual support measured at both candidate endpoints.
- `pathPoints`: supporting image coordinates for visual audit and overlays.
- `pixelSupport` and `maximumGap`: coverage evidence when a fragmented line is recovered.
- `confidence`: confidence in the geometric association, not in the protocol.
- `crossedBoundaryIds`: candidate zones crossed by the flow.
- `reviewStatus`: always `pending` until a human confirms it.

Protocols are never fabricated. They remain `unknown` unless supplied by explicit input or
confirmed during review. STRIDE raises a high-priority finding when an unknown protocol
crosses a trust boundary and a critical finding when a known plaintext protocol does so.

## Verification Evidence

The automated suite creates a diagram with three components, two lines, and one enclosing
zone. It verifies component-pair association, external-to-internal direction, boundary
membership, and the resulting STRIDE rule.

An additional smoke test was run on one reserved Kaggle diagram:

- Components detected: 4.
- Visual flows associated: 1.
- Flow evidence: `detected_line`.
- Layout-only fallback flows avoided: 3 previously inferred adjacent connections.

Five reserved project diagrams were also sampled. Every diagram produced line-backed flows
(4 to 11 per image) and one trust-zone candidate.

A reproducible controlled benchmark covers 30 reserved generated diagrams and 200 known
directed flows. The current precision-oriented extractor reaches adjacency F1 0.8772,
directed F1 0.6216, and direction accuracy 70.86%. On the separate manual real-image benchmark,
it reaches adjacency F1 0.8163, directed F1 0.7755, and direction accuracy 95.00%. Full results,
including the stronger arrowhead-only synthetic experiment, are recorded in
`docs/structure-benchmark-results.md`.

## Limitations

- Arrowhead direction is classified when the visual evidence passes calibrated thresholds;
  uncertain cases still fall back to semantics or layout and remain reviewable.
- Dense decorative lines may produce false associations.
- Light, incomplete, or non-rectangular zones can be missed.
- Nested zones are candidates, not automatically accepted security boundaries.
- The real benchmark has only three manually annotated diagrams and must be expanded before
  making production generalization claims.
- OCR is an optional implemented stage and requires the open-source Tesseract runtime; structure
  extraction continues safely when it is absent.

These limitations are surfaced through confidence, evidence provenance, and the human-review
gate rather than hidden behind a generative answer.
