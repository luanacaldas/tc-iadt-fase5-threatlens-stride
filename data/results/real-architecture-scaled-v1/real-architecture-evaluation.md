# Real Architecture Extraction Evaluation

- Images: 3
- Flow adjacency F1: 0.6667
- Flow directed F1: 0.6032
- Direction accuracy on matched flows: 0.9048
- Trust-boundary membership F1: 0.2857
- OCR protocol assignment F1: 0.8000

## Per image

- **azure-container-edge**: adjacency F1 1.0000; directed F1 1.0000; boundary F1 0.0000; protocol F1 0.6667.
- **azure-ai-foundry**: adjacency F1 0.5455; directed F1 0.5455; boundary F1 0.5000; protocol F1 1.0000.
- **aws-video-pipeline**: adjacency F1 0.6364; directed F1 0.5455; boundary F1 0.0000; protocol F1 1.0000.

Ground-truth component boxes are supplied to isolate structure and OCR quality. The source images include dataset augmentation overlays; only visible primary-diagram content is annotated.
