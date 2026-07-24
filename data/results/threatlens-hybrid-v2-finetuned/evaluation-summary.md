# ThreatLens Model Evaluation

- Model SHA-256: `7dfcb27c9d36ca4b3404b7a2fdff54e11133ac0fb9093b468b90c96540583e5c`
- Dataset split: `test`
- Quality gate: **FAIL**
- Precision: 0.4723
- Recall: 0.2447
- mAP50: 0.2909
- mAP50-95: 0.1571

## Per-Class Metrics

| Class | Support | Precision | Recall | AP50 | AP50-95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| api_gateway | 0 | 0.1261 | 0.0370 | 0.1030 | 0.0574 |
| backup | 0 | 1.0000 | 0.0000 | 0.1392 | 0.0835 |
| cdn | 0 | 0.0000 | 0.0000 | 0.0010 | 0.0006 |
| compute | 0 | 0.3553 | 0.7581 | 0.6846 | 0.3129 |
| database | 0 | 0.6704 | 0.8958 | 0.9153 | 0.3260 |
| identity_provider | 0 | 0.0532 | 0.0769 | 0.0387 | 0.0204 |
| internet | 0 | 1.0000 | 0.0000 | 0.6668 | 0.3571 |
| load_balancer | 0 | 0.1581 | 0.1429 | 0.1433 | 0.0763 |
| monitoring | 0 | 0.3567 | 0.0667 | 0.1441 | 0.0933 |
| queue | 0 | 0.1304 | 0.3571 | 0.1199 | 0.0803 |
| secrets_kms | 0 | 0.2790 | 0.1818 | 0.3284 | 0.1876 |
| storage | 0 | 0.4827 | 0.9091 | 0.6593 | 0.5370 |
| user | 0 | 1.0000 | 0.0000 | 0.1241 | 0.0625 |
| waf | 0 | 1.0000 | 0.0000 | 0.0050 | 0.0040 |

## Quality Gate

- PASS `aggregate_mAP50`: 0.2909 (minimum 0.2500)
- FAIL `aggregate_recall`: 0.2447 (minimum 0.2500)
- PASS `critical_class_ap50:api_gateway`: 0.1030 (minimum 0.1000)
- PASS `critical_class_ap50:compute`: 0.6846 (minimum 0.1000)
- PASS `critical_class_ap50:database`: 0.9153 (minimum 0.1000)
- PASS `critical_class_ap50:internet`: 0.6668 (minimum 0.1000)
- PASS `critical_class_ap50:user`: 0.1241 (minimum 0.1000)
