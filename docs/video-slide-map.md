# Mapa do vídeo e dos slides

## Diagnóstico do deck atual

O arquivo `Tech Challenge IADT - Fase 4 - Aurora. Care AI.pptx` contém sete slides ThreatLens.
Apesar do nome histórico do arquivo, o conteúdo visual já está adaptado ao projeto atual.

| Slide atual | Função recomendada | Decisão |
| ---: | --- | --- |
| 1 | Capa e identificação | Manter |
| 2 | Pipeline técnico | Manter; usar como tese da solução |
| 3 | Composição do dataset híbrido | Manter |
| 4 | Split e ausência de vazamento | Manter |
| 5 | Replay balanceado | Manter |
| 6 | Três decisões de confiança | Manter; não repetir métricas |
| 7 | Cinco diferenciais | Manter; funcionar como síntese antes da demo |

Os slides 6 e 7 não devem dizer a mesma coisa. O slide 6 explica **por que** YOLO, OCR e quality
gate foram escolhidos. O slide 7 sintetiza **o que o produto entrega de diferente**.

## Sequência final recomendada

| Tempo | Visual | Função narrativa |
| --- | --- | --- |
| 00:00-00:30 | Slide 1 | Nome, problema e promessa |
| 00:30-01:35 | Slide 2 | Explicar a separação da pipeline |
| 01:35-02:10 | Slide 3 | Justificar as duas fontes do dataset |
| 02:10-02:45 | Slide 4 | Demonstrar prevenção de leakage |
| 02:45-03:15 | Slide 5 | Explicar replay balanceado |
| 03:15-04:00 | Slide 6 | Defender três decisões de engenharia |
| 04:00-05:10 | Slide 7 | Fechar os diferenciais |
| 05:10-08:35 | Dashboard | Demonstrar caminho válido |
| 08:35-11:10 | Dashboard | Demonstrar rejeição fail-closed |
| 11:10-12:15 | Novo slide 8 | Separar métricas por camada e split |
| 12:15-13:25 | Novo slide 9 | Limitações e proteções |
| 13:25-14:35 | Novo slide 10 | Síntese e próximos passos |
| 14:35-15:00 | Slide 10 | Margem para transições |

## Novos slides necessários

### Slide 8 - Evidência por camada

**Título:** Métricas fortes no detector; cautela no ponta a ponta

**Conteúdo visível:**

| Camada | Evidência |
| --- | --- |
| Detector, teste híbrido | precisão 0,9297; recall 0,8417; mAP50 0,9009 |
| Ameaças v15, desenvolvimento | F1 0,5296; recall 0,6786; 152 corretas; 198 extras |
| Junction-aware, desenvolvimento | 52 corretas; 75 falsas; 19 ausentes; recall 0,7324 |
| Engenharia | 350 testes; verificador global PASS; auditoria v12 PASS |

**Rodapé obrigatório:** Resultados de desenvolvimento não representam generalização.

### Slide 9 - Limitações com mecanismos de proteção

**Título:** O sistema explicita incerteza antes de produzir risco

**Lado esquerdo:** diagramas densos, arrowheads pequenos, classes desconhecidas e OCR difícil.

**Lado direito:** revisão humana, `detectionAlternatives`, status `review_required` e rejeição
fail-closed.

**Mensagem final:** ausência de alerta não equivale a ausência de risco.

### Slide 10 - Encerramento

**Título:** Automatizar onde há evidência; revisar onde há incerteza

**Fluxo final:** imagem -> arquitetura estruturada -> quality gate -> STRIDE rastreável ->
contramedidas.

**Próximos passos:** mais diagramas reais, dupla anotação e modelos de existência/direção de aresta.

## Transições entre slides e dashboard

Antes da demo:

> "Essas decisões só fazem sentido se aparecerem no comportamento do produto. Vou mostrar primeiro
> um caso válido e depois o caso em que o sistema decide não gerar o relatório."

Ao retornar aos slides:

> "A demonstração mostra o comportamento. Agora eu separo as métricas por camada para não misturar
> desempenho do detector com desempenho ponta a ponta."

## Arquivos que devem estar preparados

- `data/sample-diagrams/02-mixed-components.jpg`;
- `E:\teste_aws.png`;
- `data/results/mvp-hardening-001/external-image-quality.json`;
- `output/pdf/threatlens-sample-report.pdf`;
- `docs/sample-threat-model.md`;
- dashboard aberto em `http://127.0.0.1:4173`.

## Correções necessárias no conteúdo anterior

- Usar **ThreatLens**, nunca `ThreatsLens` ou `Threatles`.
- O frontend é JavaScript, HTML e CSS; não React ou Vue.
- Usar "MVP validado", não "pronto para produção".
- Não afirmar ganho de velocidade, percentual de automação ou capacidade diária sem benchmark.
- Não misturar detector, grafo e ameaças em uma única taxa de acerto.
- Identificar sempre quando a evidência vem de `development_tuning`.
