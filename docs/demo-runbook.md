# ThreatLens Demo Runbook

## Preflight no Windows, sem Docker

```powershell
npm.cmd run verify
npm.cmd run dev
```

O Docker nao e necessario para a demonstracao. O comando `npm.cmd run dev` inicia frontend e
backend com o ambiente virtual local. Mantenha o terminal aberto durante a apresentacao.

Open `http://127.0.0.1:4173` and confirm:

- Backend status is ready, with YOLO, calibration, and local RAG available.
- The report and validator modes returned by `/health` are deterministic.
- `Backend pronto | YOLO + RAG local` is shown when all required local dependencies are ready.
- The sample loads with 8 components, 7 flows, and all six STRIDE categories.

## Qualified Model

The registered detector already uses this path in `.env`:

```dotenv
YOLO_MODEL_PATH=models/threatlens-hybrid-v2/weights/best.pt
YOLO_MIN_DETECTION_CONFIDENCE=0.35
YOLO_CONFIDENCE_THRESHOLD=0.70
```

Restart `npm.cmd run dev` and verify `/health` includes:

```json
{
  "detector": {
    "available": true,
    "modelSha256": "2aebcd0611927505d60a10d23ce11d0e5211cf2e91ca0c4394921fac006c865d",
    "classes": ["api_gateway", "backup", "cdn"]
  }
}
```

Also verify that `/ready` returns HTTP 200 and `{"status":"ready","ready":true,"reasons":[]}`.

## Demonstracao principal

1. Upload a diagram from a reserved real-image group and show boxes with confidence.
2. Show visual flows, arrow direction, OCR protocol evidence, and trust-zone candidates.
3. Correct one label, assign components to a trust boundary, and confirm the review.
4. Generate STRIDE and open `Ver rastreabilidade` on a flow rule.
5. Point to its rule ID, supporting flow/component IDs, boundary IDs, and RAG source.
6. Export JSON, Markdown, and PDF; show `analysisId` and `requestId` in JSON.

## Demonstracao do quality gate

1. Envie `E:\teste_aws.png`, caso o arquivo esteja disponivel na maquina da apresentacao.
2. Mostre que a imagem contem dois cenarios comparativos e nao representa uma unica arquitetura.
3. Destaque `analysisQuality.status = rejected` e as razoes estruturadas.
4. Confirme que ameacas, risco, contramedidas e impressao foram suprimidos.
5. Explique que o sistema prefere recusar uma conclusao insegura a produzir um relatorio convincente
   sobre uma reconstrucao inconsistente.

Se o arquivo externo nao estiver disponivel, use
`data/results/mvp-hardening-001/external-image-quality.json`.

## What To Say

- The supervised model detects architecture components; it does not directly invent threats.
- Every threat is produced by an auditable STRIDE rule and references detected evidence.
- Low-confidence detections and inferred flows remain visible for human confirmation.
- The model SHA-256, thresholds, detector source, report mode, and validator mode are preserved in the output.
- Controlled and manually annotated real-image benchmarks are reported separately.
- The current real-image baseline exposes dense-flow and boundary limitations instead of hiding them.
- The MVP works locally without paid APIs. Generative models are optional enrichment and validation layers.

## Contingency

If the final weights are unavailable, use `Carregar exemplo` to demonstrate review, STRIDE, RAG, validation, graph, and exports. State clearly that this path begins from previously structured JSON and is not live image inference.

If an uploaded diagram produces uncertain detections, keep them in the review table rather than hiding them. This is the intended safety behavior and a product differentiator.

If remote services are unavailable, keep all three `ENABLE_*` flags false. The deterministic report remains complete and the health endpoint records the active mode.

Se o Docker estiver indisponivel, nao tente corrigi-lo durante a apresentacao. Use a execucao local.
Se o backend nao iniciar, apresente `data/results/web-mvp-001/sample-analysis-report.json`,
`docs/sample-threat-model.md` e `output/pdf/threatlens-sample-report.pdf`.

## Evidence Checklist

- Dataset audit and provenance files.
- Hybrid-v2 class distribution and leakage report.
- Colab `results.csv`, confusion matrix, PR curves, and test metrics.
- Qualified model card and source-level gate in `docs/model-evaluation-and-registration.md`.
- Three successful exports from the reviewed architecture.
- `/health` response showing model fingerprint and local execution modes.
- One failure case with the human correction recorded.
- `data/results/structure-current/structure-evaluation.json`.
- `data/results/real-architecture/real-architecture-evaluation.json`.
- `data/results/stride-golden/stride-golden-evaluation.json`.
- One expanded threat trace and one exported audit object.
- `data/results/v15-regression-gate/` com gate aprovado e hashes de rastreabilidade.
- `data/results/tl004f-integrated-ablation/` com a comparacao da estrategia controlada.
- `data/results/tl-struct-001a-final-gate/` com controles C01-C07 aprovados.
- `data/results/mvp-hardening-001/external-image-quality.json` com rejeicao fail-closed.
- `docs/submission-evidence.md` como indice unico para a banca.
