# Evidências para entrega e demonstração

Este documento é o índice operacional da entrega. Ele aponta para evidências já produzidas e evita
executar treinamento, holdouts ou Docker durante a apresentação.

## Mensagem central

O ThreatLens não gera ameaças diretamente da imagem. Ele detecta componentes com um modelo
supervisionado, reconstrói uma arquitetura revisável, aplica um gate de qualidade e somente então
executa regras STRIDE e recuperação local de contramedidas.

## Matriz dos requisitos

| Requisito do hackathon | Evidência demonstrável |
| --- | --- |
| Interpretar um diagrama em imagem | `data/sample-diagrams/02-mixed-components.jpg` e dashboard |
| Identificar componentes | boxes, classes, provider, confiança e `bbox` na resposta da API |
| Dataset de arquiteturas | `docs/dataset-integration-results.md` e manifestos em `data/manifests/` |
| Dataset anotado | 373 imagens, 3.048 objetos e 14 classes documentados no `README.md` |
| Modelo supervisionado treinado | `docs/model-development.md` e model card registrado |
| Relatório STRIDE | `docs/sample-threat-model.md` e JSON de amostra |
| Vulnerabilidades e contramedidas | referências CWE, CAPEC, OWASP e MITRE ATT&CK no dashboard e PDF |
| Documentação do fluxo | `docs/architecture.md` |
| Mais de uma visualização | dashboard, JSON, Markdown e PDF |

## Evidências quantitativas oficiais

### Detector supervisionado

| Métrica | Valor |
| --- | ---: |
| Precisão | 0,9297 |
| Recall | 0,8417 |
| mAP@50 | 0,9009 |
| mAP@50-95 | 0,8666 |

Fonte: model card e resultados registrados de `threatlens-hybrid-v2`.

### Gate de regressão v15

| Métrica | Valor |
| --- | ---: |
| F1 | 0,5296 |
| Precisão | 0,4343 |
| Recall | 0,6786 |
| Ameaças corretas | 152 |
| Falsos positivos | 198 |

Evidência: `data/results/v15-regression-gate/`. Esses valores pertencem ao split
`development_tuning`; não devem ser apresentados como novo resultado cego.

### Estratégia junction-aware controlada

| Métrica | Valor |
| --- | ---: |
| Conexões corretas | 52 |
| Falsos fluxos | 75 |
| Fluxos ausentes | 19 |
| Recall | 0,7324 |
| F1 | 0,5253 |
| Acurácia de direção | 0,8654 |
| Verdadeiros positivos bloqueados | 0 |

Evidências: `data/results/tl004f-integrated-ablation/` e
`data/results/tl-struct-001a-final-gate/`. A estratégia é experimental, opt-in e validada somente
em desenvolvimento; `legacy` permanece o padrão.

### Qualidade e engenharia

- 350 testes automatizados aprovados.
- Verificador global: `PASS`.
- Auditoria prospectiva v12: `PASS`.
- Controles C01-C07: `PASS`.
- Manifesto com hashes em `data/manifests/reproducibility.json`.

Os 85 testes encontrados em artefatos históricos são a baseline mínima preservada pela TL-001, não
o total atual da suíte.

## Rota de demonstração sem Docker

### Preparação

Na raiz do projeto:

```powershell
.venv\Scripts\python.exe -c "import cv2, fastapi, ultralytics; print('Dependências OK')"
npm.cmd run verify
npm.cmd run report:sample-pdf
npm.cmd run dev
```

Abra `http://127.0.0.1:4173` e mantenha o terminal aberto.

### Caso principal

1. Selecione `data/sample-diagrams/02-mixed-components.jpg`.
2. Mostre componentes detectados, confianças e bounding boxes.
3. Mostre fluxos, protocolos, fronteiras e itens pendentes de revisão.
4. Confirme a arquitetura revisada.
5. Gere STRIDE e abra a rastreabilidade de uma ameaça.
6. Mostre regra, componente ou fluxo de origem, fonte RAG e contramedida.
7. Exporte JSON, Markdown e PDF.

### Caso de segurança fail-closed

1. Envie `E:\teste_aws.png`, se disponível.
2. Mostre que o sistema identifica uma entrada comparativa ou estruturalmente inconsistente.
3. Destaque o status `rejected`, as razões e a ação recomendada.
4. Confirme que STRIDE, risco, contramedidas e PDF foram bloqueados.

Evidência de contingência: `data/results/mvp-hardening-001/external-image-quality.json`.

## Plano de contingência

| Falha durante a apresentação | Ação |
| --- | --- |
| Docker indisponível | Use `npm.cmd run dev`; Docker não faz parte da rota necessária. |
| Detector demora | Use `data/results/web-mvp-001/sample-analysis-report.json`. |
| Backend não inicia | Mostre `docs/sample-threat-model.md` e o PDF previamente gerado. |
| Arquivo externo indisponível | Abra `data/results/mvp-hardening-001/external-image-quality.json`. |
| Sem internet | Continue normalmente; detector, RAG e relatório base são locais. |
| Pergunta sobre generalização | Diferencie desenvolvimento, holdouts selados e resultados pós-hoc. |

## Evidências para deixar abertas antes da banca

1. Dashboard em `http://127.0.0.1:4173`.
2. `docs/sample-threat-model.md`.
3. `data/results/web-mvp-001/sample-analysis-report.json`.
4. `data/results/mvp-hardening-001/external-image-quality.json`.
5. `data/results/v15-regression-gate/` com o relatório mais recente.
6. `data/manifests/reproducibility.json`.
7. `output/pdf/threatlens-sample-report.pdf`.

## Frases de defesa técnica

- O supervisionado detecta componentes; o STRIDE é aplicado sobre o grafo revisado.
- A estratégia experimental não substituiu silenciosamente a baseline legacy.
- Resultado de desenvolvimento não é apresentado como generalização.
- Uma análise rejeitada preserva o diagnóstico, mas não produz risco ou ameaças enganosas.
- Ausência de alerta não significa ausência de risco; o produto apoia, mas não substitui revisão de segurança.

## O que não executar na apresentação

- treinamento ou fine-tuning;
- `blind_holdout` ou `prospective_holdout`;
- atualização de baseline ou manifesto;
- download de modelos ou datasets;
- alteração de thresholds ou de `FLOW_STRATEGY`;
- instalação ou diagnóstico do Docker.

## Critério de prontidão

A demonstração está pronta quando o frontend abre, `/api/ready` responde com sucesso, o caso de
amostra gera análise, o PDF de contingência existe e os quatro artefatos principais deste índice
podem ser abertos sem rede.
