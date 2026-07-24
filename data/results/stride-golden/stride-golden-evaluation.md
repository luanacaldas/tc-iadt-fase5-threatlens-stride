# STRIDE Golden Set Evaluation

- Status: **passed**
- Scenarios: 6
- Rule coverage: 7/7 (100.00%)
- Precision: 1.0000
- Recall: 1.0000
- F1: 1.0000
- Exact scenario matches: 6/6 (100.00%)

## Scenarios

- **PASS - public-api-unknown-boundary-protocol**: An Internet-facing API crosses a trust boundary without a WAF, while the transport protocol is unknown.
- **PASS - plaintext-edge-with-waf**: A WAF exists, but the external boundary flow explicitly uses plaintext HTTP.
- **PASS - database-without-backup**: A monitored compute tier reaches a database, but no recovery component is represented.
- **PASS - resilient-observed-data-tier**: Monitoring and backup controls suppress absence findings while the sensitive data flow remains reportable.
- **PASS - protected-public-api**: A public API with WAF, HTTPS, and monitoring should retain the authentication finding without absence or transport findings.
- **PASS - unmonitored-worker**: An internal worker without monitoring should produce only the missing-observability architecture rule.

This is a deterministic regression and acceptance benchmark. It does not measure visual model generalization or generative report quality.
