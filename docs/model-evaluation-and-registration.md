# Model Evaluation and Registration

## Final Decision

The registered ThreatLens detector is `models/threatlens-hybrid-v2/weights/best.pt`.
It is a YOLOv8n checkpoint trained with supervised architecture-component labels and
qualified by two independent gates: the complete hybrid test split and a diagnostic
slice containing only real Kaggle diagrams.

- Registry status: `qualified`.
- Model SHA-256: `2aebcd0611927505d60a10d23ce11d0e5211cf2e91ca0c4394921fac006c865d`.
- Test images: 39, including 9 Kaggle diagrams.
- Test objects: 323 across all 14 canonical classes.
- Precision: 0.9297.
- Recall: 0.8417.
- mAP50: 0.9009.
- mAP50-95: 0.8666.
- CPU inference: 51.5 ms per image in the Ultralytics test run.

## Why Aggregate Metrics Were Not Enough

The first hybrid baseline looked strong on the complete test split but failed on the
real-diagram slice. ThreatLens therefore treats source-level evaluation as a required
model-registry gate rather than optional analysis.

| Experiment | Complete mAP50 | Complete recall | Kaggle mAP50 | Kaggle recall | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Hybrid baseline, 416 px | 0.8309 | 0.7640 | 0.1492 | 0.1423 | Rejected for domain shift |
| Kaggle-only fine-tune, 640 px | 0.2909 | 0.2447 | 0.3649 | 0.3676 | Rejected for catastrophic forgetting |
| Balanced replay, 640 px | 0.9009 | 0.8417 | 0.3598 | 0.3951 | Qualified |

The final stage started from the real-domain checkpoint and replayed 55 class-aware
examples from the prior source together with all 55 Kaggle training diagrams. Model
selection used a balanced validation manifest with 9 diagrams from each source. The
original 39-image test split was not changed by replay.

## Critical-Class Gate

| Critical class | Test AP50 | Minimum | Result |
| --- | ---: | ---: | --- |
| `api_gateway` | 0.9170 | 0.1000 | PASS |
| `compute` | 0.8139 | 0.1000 | PASS |
| `database` | 0.9320 | 0.1000 | PASS |
| `internet` | 0.9950 | 0.1000 | PASS |
| `user` | 0.9950 | 0.1000 | PASS |

The aggregate gate also requires mAP50 and recall of at least 0.25. The source gate
requires `kaggle_unique` mAP50 of at least 0.25 and recall of at least 0.20. Every check
is stored in `models/threatlens-hybrid-v2/model-card.json`.

## Reproduce the Final Stage

```powershell
npm.cmd run dataset:replay:build
.venv\Scripts\python.exe scripts\train_yolo.py `
  --data dataset\hybrid_v2\architecture-replay.yaml `
  --model models\threatlens-kaggle-finetune-640\weights\best.pt `
  --device cpu --epochs 20 --imgsz 640 --batch 4 --workers 0 `
  --cache disk --patience 8 --save-period 5 --no-rect `
  --project models --run-name threatlens-balanced-replay-v2-640 `
  --optimizer AdamW --lr0 0.0002 --lrf 0.1 --weight-decay 0.0005

.venv\Scripts\python.exe scripts\evaluate_model.py `
  --model models\threatlens-balanced-replay-v2-640\weights\best.pt `
  --data dataset\hybrid_v2\architecture.yaml `
  --output-dir data\results\threatlens-final-balanced-replay `
  --split test --device cpu --imgsz 640 --batch 4

.venv\Scripts\python.exe scripts\evaluate_source_slices.py `
  --model models\threatlens-balanced-replay-v2-640\weights\best.pt `
  --output-dir data\results\threatlens-hybrid-v2-source-slices `
  --split test --device cpu --imgsz 640 --batch 4

.venv\Scripts\python.exe scripts\register_model.py `
  --evaluation data\results\threatlens-final-balanced-replay\evaluation-summary.json `
  --source-comparison data\results\threatlens-hybrid-v2-source-slices\source-comparison.json
```

## Evidence and Limits

Machine-readable metrics, per-class results, plots, source manifests, and the model
card are preserved under `data/results` and `models/threatlens-hybrid-v2`. The Kaggle
test slice contains only 9 diagrams, so its metrics are a domain-shift alarm, not a
claim of universal cloud-icon recognition. The official hackathon diagrams remain an
external evaluation, and uncertain detections are intentionally routed to human review.

