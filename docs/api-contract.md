# Contrato da API

Versão: `1.0.0-mvp`. O backend FastAPI escuta por padrão em `127.0.0.1:8000`; no pacote
Docker, o proxy Node expõe a API em `http://127.0.0.1:4173/api`.

## GET /health

Sonda leve de processo. Não carrega o detector, não executa inferência e não abre
benchmarks.

```json
{"status":"ok","version":"1.0.0-mvp","flowStrategy":"legacy"}
```

O objeto adicional `flowStrategies` informa estratégia selecionada, padrão e opções.
`GET /ready` é a sonda profunda: verifica detector, calibração e RAG e pode retornar 503.

## POST /analyze/image

Entrada `multipart/form-data`, campo obrigatório `image`. Tipos aceitos: PNG, JPEG e
WebP. O limite padrão é 25 MB e 40 milhões de pixels. A resposta é a arquitetura
detectada com `components`, `flows`, `trustBoundaries`, `detectionAlternatives`,
`flowStrategy`, `flowStrategyTrace` e `analysisQuality`. Não gera o relatório STRIDE.

## POST /analyze/json

Entrada JSON com `components`, `flows` e, opcionalmente, `trustBoundaries`, metadados e
decisões de mitigação. Limites padrão: 2 MB, 200 componentes, 1.000 fluxos e 100
fronteiras. A resposta contém `architecture`, `threats`, `score`, `riskComparison`,
`graph`, `coverage`, `reportMarkdown`, rastreabilidade e `pipeline`.

## Qualidade estrutural

Todas as respostas de análise expõem `analysisQuality`:

```json
{
  "analysisQuality": {
    "status": "reliable",
    "score": 1.0,
    "reasons": [],
    "recommendedAction": "A estrutura passou pelo gate automático; mantenha a revisão humana antes da aprovação final."
  }
}
```

Os status aceitos são `reliable`, `review_required` e `rejected`. Uma rejeição impede
STRIDE, RAG, risco e relatório; a resposta usa `reportSuppressed: true`, `threats: []` e
`score: null`, preservando a arquitetura e as razões para diagnóstico. `/report/pdf`
recusa resultados rejeitados com 422.

## POST /analyze/full

Entrada `multipart/form-data` com `image`, `architecture_json` ou ambos. A imagem é
prioritária; o JSON funciona como fallback quando a detecção falha. Executa detecção,
estratégia de fluxo, STRIDE, RAG e relatório. `pipeline.flowStrategy` e
`pipeline.flowStrategyTrace` registram a estratégia e as decisões aplicadas.

## Estratégias

`FLOW_STRATEGY` é lida na inicialização. Sem a variável, o sistema usa `legacy`.
`junction_aware_controlled` é experimental, reversível, não redireciona endpoints e não
aplica automaticamente decisões `review_only`. Valor desconhecido falha fechado com 422
quando a análise tenta aplicar a estratégia.

## Códigos e erros

| Código | Significado |
| ---: | --- |
| 200 | Requisição concluída |
| 400 | Imagem corrompida ou payload inválido em nível de conteúdo |
| 413 | Corpo ou imagem acima do limite |
| 415 | Tipo de imagem não suportado |
| 422 | Estrutura, IDs, bbox, estratégia ou formulário inválido |
| 503 | Detector supervisionado indisponível e fallback visual desativado |

Erros são JSON no formato `{"detail":"mensagem"}` e as respostas recebem
`X-Request-ID` para correlação.
