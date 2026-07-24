# Kaggle Software Architecture Dataset Audit

- Complete manifest: True
- API pages fetched: 87
- Files: 17400
- Images: 8700
- XML annotations: 8700
- Paired samples: 8700
- Original augmentation groups: 852
- Primary filename classes: 87
- Primary classes mapped to ThreatLens: 73
- Primary classes left unmapped: 14
- Missing images: 0
- Missing annotations: 0

## Image size

- Minimum: 99211 bytes
- Median: 941216 bytes
- P95: 24546506 bytes
- Maximum: 59194004 bytes

## Leakage control

All files sharing the same `group_id` must remain in the same split.
The group id is the filename stem without the `_aug_N` suffix.
