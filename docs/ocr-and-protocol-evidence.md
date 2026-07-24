# Local OCR and Protocol Evidence

## Goal

ThreatLens uses optional local OCR to recover service labels and explicit protocol names from
architecture diagrams. OCR enriches supervised detections; it never replaces the component
detector and never silently changes a component type.

The implementation uses Tesseract 5.5 and `pytesseract`. Both run locally without API calls,
tokens, accounts, or usage charges.

## Evidence Pipeline

1. The runtime is discovered from `TESSERACT_CMD`, the system path, or standard Windows paths.
2. The image is enlarged, converted to grayscale, sharpened, and processed in sparse-text mode.
3. Words are grouped into phrases with original-image bounding boxes.
4. A phrase can label a component only when it is above or below its box, has sufficient OCR
   confidence, and passes text-quality checks.
5. Known service terms are checked against the supervised class. A conflicting label is retained
   as rejected evidence and sent to human review; it is not applied.
6. Protocol terms are accepted only when they match a protocol allowlist and lie close to the
   middle portion of a detected flow.

Every accepted protocol contains `protocolEvidence` with the original OCR text, confidence,
bounding box, and engine name.

## Semantic Safety Gate

Examples:

- `database` + `Amazon RDS`: compatible.
- `compute` + `Amazon SageMaker`: compatible.
- `user` + `Customer`: compatible.
- `database` + `CDN`: rejected and exposed for review.

Unknown product names are not automatically treated as conflicts. The human-review table remains
the final decision point for names, directions, and protocols.

## Measured Smoke Tests

Reserved project diagram `current_arch_test_0000.jpg`:

- 13 OCR text regions.
- 7 component labels accepted.
- 1 nearby label rejected because it conflicted with the supervised class.
- Accepted labels included `Internet`, `User`, `API Gateway`, `Compute`, `Storage`, and
  `Monitoring`.

Reserved Kaggle diagram:

- 15 OCR text regions, including `AWS Lambda`, `Amazon S3`, and `Amazon SageMaker`.
- No component label was applied because the detected component boxes did not have a sufficiently
  close, compatible phrase.
- A low-confidence icon reading (`Lt`) was rejected after calibration.

Protocol fixture rendered with real text:

- OCR text: `HTTPS`.
- OCR confidence: 0.96.
- Result: protocol attached to the flow with evidence provenance.

These are smoke-test results, not OCR precision/recall metrics. A manually annotated text and
protocol benchmark remains the correct next step for formal evaluation.

## Installation

Windows runtime:

```powershell
winget install --id tesseract-ocr.tesseract --exact --source winget
.venv\Scripts\python.exe -m pip install pytesseract==0.3.13
```

The feature degrades safely when OCR is absent: component detection, flow extraction, STRIDE,
RAG, and deterministic reporting continue to work.
