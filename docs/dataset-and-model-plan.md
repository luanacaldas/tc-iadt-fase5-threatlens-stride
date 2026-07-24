# Dataset and Supervised Model Plan

## Dataset Strategy

The dataset should prioritize real or realistic architecture diagrams, as requested by the professor.

Recommended sources:

- Public cloud architecture reference diagrams.
- Public diagrams from technical blogs and documentation.
- GitHub repositories containing architecture diagrams.
- Author-created diagrams that reproduce realistic AWS/Azure/GCP patterns.

Synthetic diagrams may be used only as support for class balancing or augmentation, not as the main dataset story.

## Selected Real Dataset

Primary source:

```text
https://www.kaggle.com/datasets/carlosrian/software-architecture-dataset
```

The ThreatLens audit collected metadata for the complete public dataset and measured:

- 17,400 files: 8,700 PNG and 8,700 Pascal VOC XML files.
- 8,700 complete image/annotation pairs.
- 852 original architecture groups and 87 primary service classes.
- AWS, Azure, and GCP coverage.
- No orphan image or annotation in the remote manifest.

The split unit is the original architecture group, never the augmented file. For example, all variants below must remain together:

```text
aws_amazon_api_gateway_0000_aug_0
aws_amazon_api_gateway_0000_aug_1
...
aws_amazon_api_gateway_0000_aug_9
```

An annotation-only sample of 85 real XML files contained 1,040 objects. The current canonical mapping covered 879 objects (84.5%) with no invalid bounding boxes. The main unmapped labels represent network boundaries, DNS, deployment/IaC, and DevOps rather than accidental spelling variants.

The Kaggle data is strongest in compute, database, and storage. The existing 300-image project dataset supplies the weak Kaggle classes: user, internet, WAF, and backup. The final training dataset is therefore hybrid:

```text
Kaggle real multicloud diagrams
+ current complementary dataset for sparse architectural roles
+ held-out real evaluation diagrams
```

The selected baseline is `dataset/hybrid_v2`. It keeps one downloaded variant per original Kaggle architecture and relies on online training augmentation for additional variation. This avoids tripling already frequent compute and database examples while preserving all 73 selected real architecture groups.

Baseline measurements:

- 373 diagrams: 265 train, 69 validation, and 39 test.
- 14 canonical component classes.
- 73 unique real multicloud architecture groups plus 300 complementary diagrams.
- No image/label orphans.
- No Kaggle architecture group shared across splits.
- Class imbalance ratio of 5.92, down from 11.75 in the three-augmentation prototype.
- Per-image source provenance in `dataset/hybrid_v2/reports/provenance.csv`.

Generated audit artifacts:

- `data/manifests/kaggle_software_architecture.json`
- `data/manifests/kaggle_software_architecture.md`
- `data/manifests/kaggle_software_architecture_groups.csv`
- `data/manifests/kaggle_annotation_sample_audit.json`
- `data/manifests/kaggle_annotation_sample_audit.md`
- `dataset/hybrid_v2/reports/merge-summary.json`
- `dataset/hybrid_v2/reports/provenance.csv`
- `docs/dataset-integration-results.md`

## Annotation Format

Recommended annotation type:

- Object detection bounding boxes.

Suggested tools:

- Label Studio.
- CVAT.
- Roboflow free tier, if acceptable.

Each annotation should include:

- Component class.
- Bounding box.
- Optional provider metadata.
- Optional label text extracted by OCR.

## Initial Classes

Start with fewer classes and high consistency:

```text
user
internet
identity_provider
waf
cdn
api_gateway
load_balancer
compute
database
storage
queue
monitoring
backup
secrets_kms
```

Optional advanced classes:

```text
trust_boundary
data_flow
network_zone
```

## Dataset Quality Goals

Minimum useful target for the first trained model:

- 80 to 150 diagrams.
- 10 to 14 component classes.
- At least 20 examples per frequent class.
- Separate train, validation, and test splits.
- Include AWS and Azure styles because the evaluation examples show both.

High-quality target:

- 200+ diagrams.
- More than 500 annotated components.
- Balanced examples for public entry points, databases, APIs, identity, WAF, and monitoring.

## Training Approach

Recommended model:

- YOLO fine-tuning for object detection.

Why:

- Strong object detection baseline.
- Easy to demonstrate.
- Provides bounding boxes and confidence.
- Works well with transfer learning.
- Metrics are understandable for the evaluation: precision, recall, mAP.

## Metrics To Report

The documentation should include:

- Precision.
- Recall.
- mAP.
- Confusion matrix.
- Class distribution.
- Example detections.
- Failure cases.

## Inference Output Contract

The detector should produce output compatible with the application:

```json
{
  "name": "Detected Architecture",
  "components": [
    {
      "id": "component_1",
      "name": "API Gateway",
      "type": "api_gateway",
      "provider": "aws",
      "confidence": 0.91,
      "bbox": [382, 110, 455, 172]
    }
  ],
  "flows": []
}
```

## Human Review

The user should be allowed to review detections before final report generation.

This is important because:

- Security reports should not blindly trust low-confidence detections.
- It reduces hallucination risk in the LLM layer.
- It demonstrates product maturity.
