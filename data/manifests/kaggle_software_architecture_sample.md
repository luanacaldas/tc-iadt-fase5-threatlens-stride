# Kaggle Software Architecture Dataset Audit

- Complete manifest: False
- API pages fetched: 2
- Files: 400
- Images: 200
- XML annotations: 200
- Paired samples: 200
- Original augmentation groups: 20
- Primary filename classes: 2
- Missing images: 0
- Missing annotations: 0

## Image size

- Minimum: 130830 bytes
- Median: 872836 bytes
- P95: 24378265 bytes
- Maximum: 33671052 bytes

## Leakage control

All files sharing the same `group_id` must remain in the same split.
The group id is the filename stem without the `_aug_N` suffix.
