# Dataset Integration Results

## Decision

`dataset/hybrid_v2` is the recommended supervised-learning baseline for ThreatLens.

It combines the existing 300-diagram dataset with 73 unique, annotated architecture diagrams selected from the Software Architecture Dataset on Kaggle. One variant is retained per original Kaggle architecture. Ultralytics performs online augmentation during training, so retaining three offline variants added class imbalance without adding independent architecture structures.

## Source Audit

The complete Kaggle inventory contains:

- 8,700 PNG images and 8,700 Pascal VOC XML annotations.
- 8,700 complete image/annotation pairs and no remote orphans.
- 852 original architecture groups.
- 87 primary service classes from AWS, Azure, and GCP.
- 33.5 GB of files.

An annotation-only sample covered 85 primary classes and 1,040 objects. The canonical ThreatLens mapping converted 879 objects, or 84.5%, with no invalid bounding boxes. Unmapped objects are primarily network boundaries, DNS, infrastructure-as-code, and DevOps concepts that are outside the initial 14-class MVP taxonomy.

## Baseline Comparison

| Dataset | Images | Kaggle variants per architecture | Imbalance ratio | Split leakage |
| --- | ---: | ---: | ---: | --- |
| Original complementary dataset | 300 | 0 | 5.77 | None detected |
| `hybrid_v1` exploration | 519 | 3 | 11.75 | None detected |
| `hybrid_v2` selected baseline | 373 | 1 | 5.92 | None detected |

The `v2` choice is not based only on storage or training speed. It makes the unit of evidence an independent architecture instead of a visual augmentation and gives a more defensible evaluation design.

## Hybrid V2 Profile

- Train: 265 images and 265 label files.
- Validation: 69 images and 69 label files.
- Test: 39 images and 39 label files.
- Total: 373 images, 373 labels, and 3,048 annotated objects.
- Classes: 14 of 14 represented in every split.
- Orphan images or labels: zero.
- Kaggle architecture groups crossing splits: zero.
- Provenance records: 373, one per image.

The most frequent class is `compute` with 551 objects. The least frequent class is `backup` with 93 objects. Class-aware metrics must therefore accompany aggregate mAP.

## Smoke Test

The end-to-end Ultralytics pipeline was executed locally with CPU-only PyTorch:

```powershell
.venv\Scripts\python.exe scripts\train_yolo.py `
  --data dataset\hybrid_v2\architecture.yaml `
  --device cpu --epochs 1 --imgsz 320 --batch 4 `
  --workers 0 --fraction 0.10 `
  --run-name threatlens-smoke-hybrid-v2
```

The run loaded all 14 classes, decoded 26 training images and all 69 validation images with zero corrupt files, completed training and validation, and wrote `best.pt` and `last.pt`. Precision, recall, and mAP were zero after one epoch on 10% of the training split; these values are not model-quality claims. The purpose of this run was to verify dataset loading, labels, model initialization, validation, and artifact generation before spending GPU time.

Smoke artifacts are under `runs/detect/models/threatlens-smoke-hybrid-v2`.

## Reproducibility

```powershell
npm.cmd run dataset:kaggle:prepare:unique
npm.cmd run dataset:hybrid:build
npm.cmd run dataset:hybrid:audit
.venv\Scripts\python.exe scripts\train_yolo.py `
  --data dataset\hybrid_v2\architecture.yaml `
  --device 0 --epochs 80 --imgsz 640 `
  --run-name threatlens-hybrid-v2
```

For the final report, record per-class precision, recall, AP50 and AP50-95, the confusion matrix, representative detections, and failure cases on diagrams that were never used for training decisions.

## Final Model Progression

Source-sliced evaluation exposed a domain gap hidden by the aggregate metric. The
416 px hybrid baseline achieved 0.8309 mAP50 overall but only 0.1492 on the 9 real
Kaggle test diagrams. Kaggle-only fine-tuning raised that slice to 0.3649 but caused
catastrophic forgetting on the complete split.

The final stage used a class-aware replay manifest with 55 Kaggle and 55 prior-source
training diagrams, plus a balanced 9 + 9 validation set. The unchanged complete test
split reached 0.9009 mAP50, 0.8417 recall, and 0.8666 mAP50-95. The Kaggle slice reached
0.3598 mAP50 and 0.3951 recall. See `model-evaluation-and-registration.md` for gates,
per-class evidence, commands, and model fingerprint.

## Free GPU Package

The CPU-only development machine should not be used for the final 100-epoch experiment. A portable Colab package can be rebuilt with:

```powershell
npm.cmd run training:bundle
```

Generated artifacts:

- `artifacts/threatlens-training-bundle.zip`: 73,267,445 bytes.
- `artifacts/threatlens-training-bundle.json`: file count, size, and SHA-256 manifest.
- `notebooks/train_threatlens_colab.ipynb`: T4 GPU training and held-out test evaluation.

The current bundle SHA-256 is `076319683ddc1c731179f6fe6d1ef5ee62e82985bc286d59857356e24dd6cfee`. Rebuilding after any dataset or script change intentionally produces a new manifest and should be recorded with the final experiment.
