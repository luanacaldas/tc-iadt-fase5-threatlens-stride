# Documentação técnica do ThreatLens AI

## 1. Objetivo técnico

O ThreatLens AI implementa um pipeline de modelagem de ameaças assistida por IA. A entrada
é uma imagem de arquitetura; a saída é uma representação estruturada acompanhada de
ameaças STRIDE, contramedidas, referências de segurança e relatório exportável.

A solução separa cinco responsabilidades:

1. detecção visual de componentes;
2. reconstrução de conectividade e fronteiras;
3. avaliação de qualidade estrutural;
4. inferência determinística de ameaças;
5. recuperação de conhecimento e geração do relatório.

Essa divisão reduz alucinações e permite testar e auditar cada etapa isoladamente.

## 2. Fluxo principal

```text
Imagem
-> validação e pré-processamento
-> detecção supervisionada de componentes
-> OCR e evidências visuais
-> reconstrução de fluxos e fronteiras
-> quality gate estrutural
-> representação JSON e grafo
-> revisão humana
-> motor STRIDE
-> RAG local de vulnerabilidades e controles
-> contramedidas, referências e relatório
```

## 3. Entrada e validação

`backend/main.py` expõe a API FastAPI. A camada de entrada valida tipo, bytes, quantidade
de pixels, cardinalidade e estrutura dos payloads. PNG, JPEG e WebP são aceitos; entradas
inválidas falham antes da inferência.

O middleware gera um `X-Request-ID` por requisição. O proxy em `server.mjs` publica a API
sob `/api`, serve o frontend e aplica Content Security Policy e demais cabeçalhos de
segurança.

| Serviço | Porta padrão | Responsabilidade |
| --- | ---: | --- |
| FastAPI | 8000 | detecção, análise, health, readiness e PDF |
| Node.js | 4173 | frontend estático e proxy `/api` |

`GET /health` é uma sonda leve. `GET /ready` valida detector, calibração e base RAG.

## 4. Pipeline de Visão Computacional

### 4.1 Detecção supervisionada

`backend/detector.py` carrega o peso registrado em
`models/threatlens-hybrid-v2/weights/best.pt`. O YOLOv8n detecta 14 classes canônicas e
retorna classe, confiança e bounding box.

```json
{
  "id": "api_1",
  "name": "API Gateway",
  "type": "api_gateway",
  "provider": "aws",
  "confidence": 0.91,
  "bbox": [120, 80, 220, 180]
}
```

As confianças passam pela calibração registrada. Providers são atribuídos somente quando
há evidência visual ou textual suficiente.

### 4.2 OCR e arbitragem semântica

O Tesseract local extrai labels, providers e protocolos explícitos. A geometria associa o
texto ao componente mais compatível, considerando distância, posição e âncora visual.

OCR não sobrescreve silenciosamente a classe supervisionada. Conflitos são registrados em
`detectionAlternatives`, incluindo tipo, provider, confiança, bbox, metadados e
`supersededBy`. Essas alternativas permanecem fora de componentes ativos, grafo, STRIDE e
risco.

### 4.3 Reconstrução de estrutura

`backend/diagram_structure.py` usa OpenCV para extrair segmentos, linhas e regiões
retangulares. A etapa reconstrói:

- linhas fragmentadas e cotovelos;
- associação de endpoints a componentes;
- direção por arrowheads;
- protocolos explícitos próximos aos conectores;
- fronteiras de confiança candidatas;
- cruzamentos, bifurcações e troncos compartilhados;
- barreiras e portas de componentes;
- atalhos transitivos e linhas estruturais.

`backend/flow_strategy.py` permite selecionar:

| Estratégia | Comportamento |
| --- | --- |
| `legacy` | Padrão estável e baseline preservada. |
| `junction_aware_controlled` | Estratégia experimental e reversível com validações junction-aware. |

A estratégia controlada combina `full_without_endpoint_redirect` com
`structural_line_gate`. Ela não reativa redirecionamento automático de endpoints e não
aplica decisões `review_only` como fatos.

No conjunto `development_tuning`, a estratégia preservou 52 conexões corretas e reduziu
falsos fluxos de 90 para 75, elevando o F1 de 0,4883 para 0,5253 sem perda de recall.

## 5. Quality gate estrutural

`backend/analysis_quality.py` atua depois da reconstrução e antes do STRIDE. O objetivo é
evitar que risco e ameaças sejam calculados sobre uma arquitetura inconsistente.

O gate avalia:

- componentes com nome e tipo duplicados;
- pares duplicados espacialmente alinhados, indicando diagramas comparativos;
- labels de contas, regiões ou agrupamentos classificados como componentes;
- provider incompatível com evidência textual dominante;
- self-loop sem confirmação explícita;
- arestas direcionadas duplicadas.

| Status | Decisão da pipeline |
| --- | --- |
| `reliable` | STRIDE e relatório podem prosseguir. |
| `review_required` | Resultado segue com alertas e revisão obrigatória. |
| `rejected` | STRIDE, RAG, risco, relatório e PDF são suprimidos. |

Em uma rejeição, a arquitetura detectada permanece disponível para diagnóstico e download
JSON, mas `threats` é vazio, `score` é nulo e `reportSuppressed` é verdadeiro.

## 6. Grafo e revisão humana

Após a normalização, componentes ativos tornam-se nós e fluxos aceitos tornam-se arestas.
Metadados de provider, protocolo, confiança, evidências e fronteiras acompanham o grafo.

A revisão humana é a fronteira entre inferência visual e decisão de segurança. Componentes
e fluxos pendentes são apresentados na interface com confiança e motivo da revisão.

## 7. Motor STRIDE e contramedidas

`backend/stride_engine.py` aplica regras determinísticas por tipo de componente, provider,
fluxo, protocolo e transição de fronteira.

| Evidência arquitetural | STRIDE relacionado | Exemplos de contramedidas |
| --- | --- | --- |
| API exposta sem autenticação explícita | Spoofing | MFA, identidade federada e validação de token |
| Fluxo sensível sem protocolo seguro | Information Disclosure | TLS, mTLS e gestão de certificados |
| Banco sem backup explícito | Denial of Service | backups, RTO/RPO e testes de restauração |
| Chave sem controle de acesso identificado | Elevation of Privilege | rotação, menor privilégio e auditoria |
| Operação sem trilha de auditoria | Repudiation | logs imutáveis e correlação de eventos |

Cada ameaça registra categoria STRIDE, severidade, confiança, evidência, componente ou
fluxo relacionado, contramedidas e referências como CWE, CAPEC, OWASP e MITRE ATT&CK,
quando aplicáveis.

O motor também mantém status de gestão da ameaça, responsável, justificativa, mitigação
escolhida e comparação entre risco inicial e residual.

## 8. RAG e geração de relatório

`backend/rag.py` consulta documentos versionados em `backend/knowledge`. A recuperação é
orientada por componentes e categorias STRIDE, com embeddings locais quando disponíveis e
fallback lexical determinístico.

O caminho padrão não exige cloud nem custos externos. Enriquecimento generativo e
validação remota são opt-in. Mesmo quando habilitada, a camada generativa não pode criar
componentes ou fluxos ausentes da arquitetura analisada.

`backend/pdf_report.py` gera o PDF nativo. A interface também permite baixar o JSON
completo e imprimir a visualização executiva.

## 9. Segurança e fronteiras de confiança

- upload para API: entrada não confiável, limitada e validada;
- imagem para modelo e OCR: conteúdo não confiável processado localmente;
- detecção para revisão: hipótese técnica, não fato confirmado;
- arquitetura revisada para STRIDE: principal fronteira decisória;
- serviços remotos opcionais: desabilitados por padrão e dependentes de opt-in explícito.

## 10. Reprodutibilidade e avaliação

O projeto registra hashes do modelo, datasets, configurações, código e artefatos no
manifesto `data/manifests/reproducibility.json`.

Controles disponíveis:

- gate automático da baseline v15;
- auditoria hash-selada da cadeia prospectiva v12;
- benchmark real com AWS, Azure, GCP, diagramas genéricos e estilos FIAP;
- benchmark estrutural e golden set STRIDE;
- testes unitários, integração, frontend e regressão;
- 350 testes aprovados e verificador global em estado `PASS`.

As métricas do detector, de fluxos e de ameaças são tratadas separadamente. Resultados de
desenvolvimento não são apresentados como evidência cega de generalização.

## 11. Limitações atuais

- diagramas densos ainda podem produzir fluxos extras ou ausentes;
- arrowheads pequenos, borrados ou sobrepostos reduzem a confiança de direção;
- bordas, grades e elementos internos de ícones podem parecer conectores;
- o detector cobre 14 classes canônicas;
- a diversidade de diagramas reais ainda é limitada;
- réplicas perfeitamente alinhadas podem exigir revisão do quality gate;
- as métricas do detector não medem diretamente a qualidade do relatório STRIDE;
- o resultado é assistência técnica e requer validação humana.

## 12. Trabalhos futuros

- active learning com falsos positivos reais;
- classificador supervisionado de existência de arestas;
- calibração separada de OCR, existência de fluxo e direção;
- maior cobertura de diagramas reais e estilos visuais;
- OCR para labels pequenos, rotacionados e de baixo contraste;
- fronteiras de confiança hierárquicas;
- integração com backlog corporativo de riscos e workflow de aprovação;
- nova avaliação prospectiva com diagramas ainda não observados.
