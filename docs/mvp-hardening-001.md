# MVP-HARDENING-001

## Objetivo

O gate de qualidade estrutural atua depois da estratégia de reconstrução e antes do
STRIDE, RAG, cálculo de risco e relatório. Ele não modifica o detector, thresholds,
modelo, dataset ou estratégias de conectividade.

## Decisões

`backend/analysis_quality.py` avalia uma cópia da arquitetura e retorna o contrato
`analysisQuality`. Os sinais são diagnósticos conservadores:

- componentes com nome e tipo duplicados;
- pares duplicados espacialmente alinhados, indicando painéis comparativos;
- nomes que parecem limites ou agrupamentos;
- provider incompatível com evidência textual explícita;
- fluxo entre componentes semanticamente idênticos sem confirmação explícita;
- aresta direcionada duplicada.

Self-loops sem evidência e arestas duplicadas são retirados da cópia antes do STRIDE.
Os componentes não são reclassificados silenciosamente. Casos duvidosos recebem
`review_required`; painéis múltiplos ou score inferior a `0.45` recebem `rejected`.

## Política fail-closed

Quando o status é `rejected`, `/analyze/json` e `/analyze/full` não executam STRIDE,
RAG nem geração de relatório. A resposta preserva a arquitetura para diagnóstico, mas
retorna `threats: []`, `score: null`, grafo vazio e `reportSuppressed: true`.
`/report/pdf` também recusa esse payload com 422.

A interface mostra a qualidade, as razões e a ação recomendada. Em uma rejeição,
ameaças, mitigação, risco e impressão ficam indisponíveis; a inspeção e o download JSON
continuam disponíveis.

## Caso externo

O comando abaixo executa somente o detector local e o gate sobre uma imagem explicitamente
informada. Ele não abre benchmarks ou holdouts.

```powershell
.venv\Scripts\python.exe scripts\validate_mvp_hardening.py --image E:\teste_aws.png
```

O resultado determinístico fica em
`data/results/mvp-hardening-001/external-image-quality.json` e não registra caminho
absoluto nem timestamp.

## Limitações

O gate detecta fortes indícios, não segmenta automaticamente uma imagem composta. Uma
arquitetura legítima com réplicas perfeitamente alinhadas pode exigir revisão humana.
Providers são comparados apenas quando existe evidência textual dominante; diagramas
multicloud com rótulos explícitos permanecem válidos.
