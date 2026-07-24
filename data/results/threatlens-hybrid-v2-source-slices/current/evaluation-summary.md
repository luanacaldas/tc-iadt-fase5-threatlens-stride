# ThreatLens Model Evaluation

- Model SHA-256: `2aebcd0611927505d60a10d23ce11d0e5211cf2e91ca0c4394921fac006c865d`
- Dataset split: `test`
- Quality gate: **PASS**
- Precision: 0.9906
- Recall: 1.0000
- mAP50: 0.9950
- mAP50-95: 0.9924

## Per-Class Metrics

| Class | Support | Precision | Recall | AP50 | AP50-95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| api_gateway | 0 | 0.9927 | 1.0000 | 0.9950 | 0.9950 |
| backup | 0 | 0.9819 | 1.0000 | 0.9950 | 0.9950 |
| cdn | 0 | 0.9875 | 1.0000 | 0.9950 | 0.9950 |
| compute | 0 | 0.9944 | 1.0000 | 0.9950 | 0.9950 |
| database | 0 | 0.9956 | 1.0000 | 0.9950 | 0.9950 |
| identity_provider | 0 | 0.9956 | 1.0000 | 0.9950 | 0.9950 |
| internet | 0 | 0.9959 | 1.0000 | 0.9950 | 0.9887 |
| load_balancer | 0 | 0.9927 | 1.0000 | 0.9950 | 0.9950 |
| monitoring | 0 | 0.9874 | 1.0000 | 0.9950 | 0.9950 |
| queue | 0 | 0.9802 | 1.0000 | 0.9950 | 0.9950 |
| secrets_kms | 0 | 0.9849 | 1.0000 | 0.9950 | 0.9950 |
| storage | 0 | 0.9876 | 1.0000 | 0.9950 | 0.9950 |
| user | 0 | 0.9993 | 1.0000 | 0.9950 | 0.9656 |
| waf | 0 | 0.9932 | 1.0000 | 0.9950 | 0.9950 |

## Quality Gate

- PASS `aggregate_mAP50`: 0.9950 (minimum 0.0000)
- PASS `aggregate_recall`: 1.0000 (minimum 0.0000)
- PASS `critical_class_ap50:api_gateway`: 0.9950 (minimum 0.0000)
- PASS `critical_class_ap50:compute`: 0.9950 (minimum 0.0000)
- PASS `critical_class_ap50:database`: 0.9950 (minimum 0.0000)
- PASS `critical_class_ap50:internet`: 0.9950 (minimum 0.0000)
- PASS `critical_class_ap50:user`: 0.9950 (minimum 0.0000)
