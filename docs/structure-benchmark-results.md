# Structure Benchmark Results

## Goal

This benchmark measures whether ThreatLens recovers the connections and direction of flows
drawn in architecture diagrams. It evaluates the structure extractor independently from the
component detector by supplying ground-truth component boxes.

The first benchmark contains 30 reserved diagrams and 200 directed flows. The diagrams come
from the project's deterministic generator and were never used to tune the component model.
Their random seeds and graph construction are recorded in
`data/benchmarks/structure/benchmark.json`.

This controlled benchmark is useful for regression testing because every expected edge and
direction is known. It does not replace a manually annotated benchmark of real diagrams,
which remains required to estimate production generalization.

## Reproduction

```bash
npm.cmd run benchmark:structure:build
npm.cmd run benchmark:structure:evaluate
```

The baseline is frozen in `data/results/structure-baseline`. The current precision-oriented
implementation is recorded in `data/results/structure-current`; the earlier arrowhead-only
experiment remains in `data/results/structure-arrowhead-v4`.

## Results

| Metric | Layout baseline | Arrowhead v4 | Current |
| --- | ---: | ---: | ---: |
| Undirected precision | 0.8429 | 0.8429 | 0.8794 |
| Undirected recall | 0.8850 | 0.8850 | 0.8750 |
| Undirected F1 | 0.8634 | 0.8634 | 0.8772 |
| Directed precision | 0.5810 | 0.6190 | 0.6231 |
| Directed recall | 0.6100 | 0.6500 | 0.6200 |
| Directed F1 | 0.5951 | 0.6341 | 0.6216 |
| Direction accuracy on matched edges | 68.93% | 73.45% | 70.86% |
| Reversed matched edges | 55 | 47 | 51 |

The current version deliberately trades some generated-diagram direction recall for higher
association precision and substantially stronger real-diagram generalization. It filters
colorful icon edges, rejects candidate pairs below the calibrated geometric score, and keeps
the arrowhead-only experiment visible instead of selecting a single favorable benchmark.

## Direction Contract

For each detected connection, the extractor compares arrowhead evidence at both ends of the
line. A visual direction is accepted only when the strongest endpoint score and the margin
between endpoints pass calibrated thresholds. Otherwise, the extractor falls back to an
explicit semantic source (`user`, `internet`, or identity) and then to layout.

The output preserves the decision trail:

- `directionEvidence`: `visual_arrowhead`, semantic source, or layout fallback.
- `directionConfidence`: normalized confidence in the direction decision.
- `arrowheadScores`: evidence score at both candidate endpoints.
- `pathPoints`: image coordinates that support the inferred connection.
- `reviewStatus`: remains `pending` until confirmed by a person.

## Known Limits

- The benchmark uses generated diagrams with known graphs, not manually labeled real images.
- Trust-boundary precision and recall are not measured yet.
- Thin, stylized, curved, or partially occluded arrowheads can still fall back to layout.
- Dense diagrams can still produce false line associations before direction is evaluated.

These limits are visible in the report and human-review workflow instead of being hidden by
an unsupported generative conclusion.
