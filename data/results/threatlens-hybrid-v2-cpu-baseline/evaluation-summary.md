# ThreatLens Model Evaluation

- Model SHA-256: `bdc03c1fcd70ca8ae2e27f4047ca66ef892da8b1c2760722469eddfcefc25cf3`
- Dataset split: `test`
- Quality gate: **PASS**
- Precision: 0.9643
- Recall: 0.7640
- mAP50: 0.8309
- mAP50-95: 0.8060

## Per-Class Metrics

| Class | Support | Precision | Recall | AP50 | AP50-95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| api_gateway | 0 | 0.9911 | 0.8519 | 0.8550 | 0.8550 |
| backup | 0 | 0.9578 | 1.0000 | 0.9950 | 0.9950 |
| cdn | 0 | 0.9829 | 0.8333 | 0.8350 | 0.8350 |
| compute | 0 | 0.9956 | 0.4677 | 0.6446 | 0.5696 |
| database | 0 | 0.9923 | 0.6458 | 0.8234 | 0.7556 |
| identity_provider | 0 | 1.0000 | 0.6316 | 0.7794 | 0.7596 |
| internet | 0 | 0.9972 | 1.0000 | 0.9950 | 0.9950 |
| load_balancer | 0 | 0.7441 | 0.7143 | 0.7727 | 0.7392 |
| monitoring | 0 | 0.9809 | 0.6667 | 0.7031 | 0.6864 |
| queue | 0 | 0.9336 | 0.5000 | 0.6464 | 0.6002 |
| secrets_kms | 0 | 0.9445 | 0.8182 | 0.8578 | 0.8544 |
| storage | 0 | 1.0000 | 0.5667 | 0.7349 | 0.6542 |
| user | 0 | 0.9885 | 1.0000 | 0.9950 | 0.9897 |
| waf | 0 | 0.9917 | 1.0000 | 0.9950 | 0.9950 |

## Quality Gate

- PASS `aggregate_mAP50`: 0.8309 (minimum 0.2500)
- PASS `aggregate_recall`: 0.7640 (minimum 0.2500)
- PASS `critical_class_ap50:api_gateway`: 0.8550 (minimum 0.1000)
- PASS `critical_class_ap50:compute`: 0.6446 (minimum 0.1000)
- PASS `critical_class_ap50:database`: 0.8234 (minimum 0.1000)
- PASS `critical_class_ap50:internet`: 0.9950 (minimum 0.1000)
- PASS `critical_class_ap50:user`: 0.9950 (minimum 0.1000)
