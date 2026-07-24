# ThreatLens Model Evaluation

- Model SHA-256: `2aebcd0611927505d60a10d23ce11d0e5211cf2e91ca0c4394921fac006c865d`
- Dataset split: `test`
- Quality gate: **PASS**
- Precision: 0.9297
- Recall: 0.8417
- mAP50: 0.9009
- mAP50-95: 0.8666

## Per-Class Metrics

| Class | Support | Precision | Recall | AP50 | AP50-95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| api_gateway | 0 | 1.0000 | 0.8775 | 0.9170 | 0.9033 |
| backup | 0 | 0.9123 | 1.0000 | 0.9950 | 0.9950 |
| cdn | 0 | 0.9376 | 0.8333 | 0.8479 | 0.8415 |
| compute | 0 | 0.8387 | 0.6710 | 0.8139 | 0.7018 |
| database | 0 | 0.9270 | 0.7934 | 0.9320 | 0.8598 |
| identity_provider | 0 | 0.9091 | 0.7689 | 0.7683 | 0.7610 |
| internet | 0 | 0.9785 | 1.0000 | 0.9950 | 0.9887 |
| load_balancer | 0 | 0.7811 | 0.7857 | 0.8426 | 0.8226 |
| monitoring | 0 | 0.9224 | 0.6667 | 0.7867 | 0.7404 |
| queue | 0 | 1.0000 | 0.6871 | 0.8712 | 0.8183 |
| secrets_kms | 0 | 0.9064 | 0.8822 | 0.9399 | 0.9145 |
| storage | 0 | 0.9818 | 0.8182 | 0.9128 | 0.8252 |
| user | 0 | 0.9516 | 1.0000 | 0.9950 | 0.9656 |
| waf | 0 | 0.9697 | 1.0000 | 0.9950 | 0.9950 |

## Quality Gate

- PASS `aggregate_mAP50`: 0.9009 (minimum 0.2500)
- PASS `aggregate_recall`: 0.8417 (minimum 0.2500)
- PASS `critical_class_ap50:api_gateway`: 0.9170 (minimum 0.1000)
- PASS `critical_class_ap50:compute`: 0.8139 (minimum 0.1000)
- PASS `critical_class_ap50:database`: 0.9320 (minimum 0.1000)
- PASS `critical_class_ap50:internet`: 0.9950 (minimum 0.1000)
- PASS `critical_class_ap50:user`: 0.9950 (minimum 0.1000)
