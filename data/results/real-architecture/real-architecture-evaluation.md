# Real Architecture Extraction Evaluation

- Images: 9
- Flow adjacency F1: 0.4883
- Flow directed F1: 0.4225
- Direction accuracy on matched flows: 0.8654
- Trust-boundary membership F1: 0.1250
- OCR protocol assignment F1: 0.8000

## Per image

- **azure-container-edge**: adjacency F1 1.0000; directed F1 1.0000; boundary F1 0.0000; protocol F1 0.6667.
- **azure-ai-foundry**: adjacency F1 0.8333; directed F1 0.8333; boundary F1 0.5000; protocol F1 1.0000.
- **aws-video-pipeline**: adjacency F1 0.4561; directed F1 0.4211; boundary F1 0.0000; protocol F1 1.0000.
- **gcp-secure-cloud-run**: adjacency F1 0.5714; directed F1 0.5714; boundary F1 0.0000; protocol F1 1.0000.
- **generic-cloud-api**: adjacency F1 0.5714; directed F1 0.3810; boundary F1 0.0000; protocol F1 1.0000.
- **aws-serverless-async**: adjacency F1 0.8000; directed F1 0.6000; boundary F1 0.0000; protocol F1 1.0000.
- **aws-eks-platform**: adjacency F1 0.2581; directed F1 0.2581; boundary F1 0.0000; protocol F1 1.0000.
- **azure-private-ai-platform**: adjacency F1 0.1379; directed F1 0.1379; boundary F1 1.0000; protocol F1 1.0000.
- **azure-hub-spoke**: adjacency F1 0.5714; directed F1 0.2857; boundary F1 1.0000; protocol F1 1.0000.

Ground-truth component boxes are supplied to isolate structure and OCR quality. The source images include dataset augmentation overlays; only visible primary-diagram content is annotated.
