# ThreatLens Model Evaluation

- Model SHA-256: `2aebcd0611927505d60a10d23ce11d0e5211cf2e91ca0c4394921fac006c865d`
- Dataset split: `test`
- Quality gate: **PASS**
- Precision: 0.4550
- Recall: 0.3951
- mAP50: 0.3598
- mAP50-95: 0.2759

## Per-Class Metrics

| Class | Support | Precision | Recall | AP50 | AP50-95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| api_gateway | 0 | 1.0000 | 0.0000 | 0.1026 | 0.0805 |
| cdn | 0 | 0.0000 | 0.0000 | 0.0236 | 0.0118 |
| compute | 0 | 0.4863 | 0.5000 | 0.5142 | 0.3692 |
| database | 0 | 0.5733 | 0.5556 | 0.6764 | 0.5235 |
| identity_provider | 0 | 0.2360 | 0.2500 | 0.1336 | 0.1202 |
| load_balancer | 0 | 0.1847 | 0.5000 | 0.1457 | 0.1227 |
| monitoring | 0 | 0.2823 | 0.1129 | 0.2896 | 0.1430 |
| queue | 0 | 0.5528 | 0.7143 | 0.5828 | 0.4914 |
| secrets_kms | 0 | 0.3373 | 0.5000 | 0.3189 | 0.2656 |
| storage | 0 | 0.8974 | 0.8182 | 0.8104 | 0.6310 |

## Quality Gate

- PASS `aggregate_mAP50`: 0.3598 (minimum 0.0000)
- PASS `aggregate_recall`: 0.3951 (minimum 0.0000)
- PASS `critical_class_ap50:api_gateway`: 0.1026 (minimum 0.0000)
- PASS `critical_class_ap50:compute`: 0.5142 (minimum 0.0000)
- PASS `critical_class_ap50:database`: 0.6764 (minimum 0.0000)
- PASS `critical_class_ap50:internet`: 0.0000 (minimum 0.0000)
- PASS `critical_class_ap50:user`: 0.0000 (minimum 0.0000)
