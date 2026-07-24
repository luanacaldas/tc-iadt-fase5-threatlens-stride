# Real Architecture Benchmark

## Scope

The expanded benchmark contains 15 human-verified diagrams: AWS, Azure, GCP, generic styles,
and the two architecture styles supplied in the FIAP brief. Nine images form the development
split and six form the final holdout. The holdout was sealed before the first end-to-end run.

Annotations use normalized coordinates and include components, directed flows, protocols, and
trust-boundary membership. Every image has a SHA-256 hash. The benchmark builder refuses to
infer primary-diagram labels from Kaggle XML because visual inspection showed that many XMLs
describe icons pasted by augmentation instead of the original architecture.

## Reproduction

```bash
npm.cmd run benchmark:real:build
npm.cmd run benchmark:real
npm.cmd run benchmark:blind
```

The source of truth is `data/benchmarks/real-architecture/benchmark-expanded.json`. The initial
blind result is preserved as `data/results/end-to-end/end-to-end-blind_holdout-initial.json`.

## Development Structure Results

| Capability | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| Flow adjacency | 0.3662 | 0.7324 | 0.4883 |
| Directed flow | 0.3169 | 0.6338 | 0.4225 |
| Trust-boundary membership | 0.1250 | 0.1250 | 0.1250 |
| OCR protocol assignment | 1.0000 | 0.6667 | 0.8000 |

The supervised arrowhead classifier reached F1 0.9747 on its generated holdout, but this number
measures arrowhead-shape discrimination, not full flow extraction on real diagrams. Segment-graph
assembly joins long lines and elbows before component association and deliberately avoids joining
mid-segment crossings.

## End-to-End Results

The first sealed holdout run produced threat F1 0.0254 and mean typed-component recall 0.0000.
This exposed severe domain shift from augmented cloud icons to complete real diagrams. That result
is immutable and remains the historical blind baseline.

Development-only iterations added provider-aware label geometry, a broader component taxonomy, and
vertical OCR phrase reconstruction. On the nine development images, the current pipeline reaches
threat F1 0.4188 and typed-component recall 0.5056. Resolution-aware visual anchors and auditable
replica grouping then raised development F1 to 0.4723 and typed recall to 0.5926. The earlier detector reaches post-hoc F1 0.2143
against the original holdout annotations.

Visual inspection also found systematic coordinate drift in the original FIAP AWS annotation. The
sealed benchmark was not overwritten. `benchmark-fiap-corrected-v3.json` is generated from the
original, records its parent SHA-256, and is explicitly marked `posthoc_corrected_annotations_not_blind`.
With the same detector and provider-aware scoring contract, correcting only those boxes raises the
post-hoc aggregate from F1 0.2143 to 0.3205. FIAP AWS reaches F1 0.5900 and FIAP Azure reaches 0.3256.
These are product diagnostics, not replacement blind scores.

## Prospective v12 Holdout

Three previously unused source groups were annotated from visible architecture content with Codex
visual assistance and still require independent human verification.
The benchmark, image hashes, and detector hash were sealed before the first inference. That first
pass reached threat precision 0.3111, recall 0.3889, F1 0.3457, and mean typed-component recall
0.4225. Its result hash is preserved in `data/results/end-to-end-prospective-v12/result-seal.json`.
Run `npm.cmd run benchmark:prospective:audit` to verify the complete immutable chain.

The new score is blind evidence for v12, while the original 0.0254 remains the historical blind
baseline for the earlier pipeline. A larger, independently double-annotated external holdout is
still required for a stronger generalization claim.

The v13 semantic-abstention layer preserves conflicting YOLO hypotheses as review alternatives
instead of allowing them to generate automatic threats. Development F1 reaches 0.5033 with typed
recall 0.6176. Its replay on the already-opened prospective set remains F1 0.3457, exactly matching
v12; this replay is post-hoc and does not create a second blind claim.

The v15 semantic-arbitration layer resolves competing OCR interpretations that share one visual
anchor and suppresses nearby conflicting YOLO hypotheses while retaining every alternative for
review. On development it keeps the same 152 correct threats and typed recall 0.6176, reduces extra
threats from 228 to 198, and raises F1 to 0.5296. No v15 holdout score is claimed; this is development
evidence only.

These results make the product boundary explicit: ThreatLens is an assistive MVP with mandatory
review for uncertain components and flows, not an autonomous security authority.
