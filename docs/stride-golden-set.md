# STRIDE Golden Set

## Purpose

The STRIDE golden set is a hand-authored acceptance contract for ThreatLens' deterministic
architecture rules. It answers a different question from model mAP or structure F1:

> Given a reviewed architecture graph, does the engine emit exactly the expected
> architecture-level findings without adding unsupported ones?

## Coverage

Six scenarios exercise positive and negative behavior for all seven current rules:

- Insecure protocol crossing a trust boundary.
- Unknown protocol crossing a trust boundary.
- External entry without a WAF.
- Internet-to-API authentication exposure.
- Compute-to-database sensitive data flow.
- Missing monitoring.
- Database without explicit backup.

The cases include both missing-control findings and control-present scenarios that must
suppress them. The source of truth is
`data/benchmarks/stride/golden-set.json`.

## Reproduction

```bash
npm.cmd run benchmark:stride
```

Results are written to `data/results/stride-golden` in JSON and Markdown formats. The
evaluator exits with a failure code when any scenario differs from its expected rule set or
when a rule has no positive coverage.

## Current Result

- Scenarios: 6.
- Architecture rules covered: 7/7 (100%).
- Precision: 1.0000.
- Recall: 1.0000.
- F1: 1.0000.
- Exact scenario matches: 6/6 (100%).

## Interpretation

This perfect score is expected for a deterministic regression suite and means that the
implemented rules satisfy the documented examples. It is not a claim of perfect threat
detection on unseen architecture images. End-to-end quality remains bounded by component
detection, flow direction, trust-boundary extraction, OCR evidence, and human confirmation.

Future evaluation should add independently reviewed real diagrams and compare the complete
set of reported threats against labels from security specialists.
