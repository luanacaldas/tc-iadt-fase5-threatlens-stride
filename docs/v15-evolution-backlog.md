# 1. Resumo executivo

A v15 e a melhor versao atual para o conjunto de desenvolvimento e deve permanecer como baseline.
Ela reduziu ameacas extras de 228 para 198, manteve 152 ameacas corretas e elevou o F1 ponta a
ponta de 0,5033 para 0,5296. A cadeia prospectiva v12 nao deve ser executada novamente para selecao
de mudancas e seus artefatos devem continuar imutaveis.

Os proximos ganhos nao dependem de outra regra ampla de supressao de componentes. O maior gargalo
confirmado e a existencia de fluxos: no benchmark real de desenvolvimento, com caixas de componentes
fornecidas pelo ground truth, existem 71 fluxos esperados e 142 previstos. A precisao direcionada e
0,3169, o recall e 0,6338 e o F1 e 0,4225. Em arestas sem direcao, a precisao e 0,3662, o recall e
0,7324 e o F1 e 0,4883. A direcao, quando a aresta correta e encontrada, ja atinge 0,8654 de acuracia.
Logo, a prioridade e decidir se uma conexao existe antes de investir mais na ponta da seta.

Ha ainda um bloqueador de rastreabilidade: o detector produz `detectionAlternatives`, mas
`normalize_architecture()` nao preserva esse campo. A resposta final e o dashboard tambem nao o
exibem. A alternativa existe na resposta de `/analyze/image`, mas se perde no fluxo completo
`/analyze/full`. Isso precisa ser corrigido antes de ampliar a arbitragem.

# 2. Diagnostico tecnico da v15

## Fatos confirmados

- A v15 usa arbitragem espacial entre OCR e YOLO, resolve interpretacoes semanticas que compartilham
  ancora e preserva hipoteses suprimidas no retorno direto do detector.
- O desenvolvimento v15 possui 224 ameacas esperadas, 350 previstas, 152 corretas, 72 ausentes e
  198 extras: precisao 0,4343, recall 0,6786 e F1 0,5296.
- O benchmark possui 92 componentes esperados e 142 previstos; 62 foram localizados e 60 tiveram
  tipo correto. A precisao de localizacao micro e 0,4366 e o recall tipado micro e 0,6522; o recall
  tipado medio oficial permanece 0,6176.
- Com caixas corretas fornecidas, o extrator estrutural ainda superestima fluxos: 142 previstos para
  71 esperados. Os piores casos sao `azure-private-ai-platform` (8/21; F1 direcionado 0,138),
  `aws-eks-platform` (10/21; 0,258) e `aws-video-pipeline` (16/41; 0,421).
- O benchmark controlado de estrutura e consideravelmente melhor: F1 nao direcionado 0,8772 e F1
  direcionado 0,6216. A mudanca de dominio e densidade e relevante.
- Fronteiras de confianca no benchmark real expandido possuem F1 0,125. Protocolos possuem precisao
  1,0, recall 0,6667 e F1 0,8.
- O RAG possui 100 trechos e fallback lexical, mas nao existe benchmark de recuperacao com Recall@k,
  MRR ou nDCG. Os testes atuais verificam disponibilidade e formato, nao relevancia.
- A observabilidade atual registra `request_id`, status HTTP e duracao total. Nao ha tempos por etapa,
  contadores por origem de evidencia nem distribuicao de candidatos podados.
- O golden set STRIDE cobre as regras implementadas. A avaliacao ponta a ponta gera o esperado e o
  previsto com o mesmo motor STRIDE; portanto, mede consistencia da percepcao com as regras, nao
  validacao independente da qualidade de ameacas por especialistas.

## Hipoteses tecnicas

- Cruzamentos geometricos e a associacao de ate dois componentes aos nos de segmentos fazem o
  `segment_graph` criar caminhos entre pares que nao estao semanticamente conectados.
- Um classificador de existencia de aresta com features geometricas pode reduzir falsos fluxos sem
  impor limite fixo de grau, que seria perigoso em topologias hub-and-spoke.
- A associacao global um-para-um entre rotulos e ancoras deve reduzir duplicatas antes da arbitragem
  v15 e preservar mais informacao que novas regras de supressao posteriores.
- Hard negatives reais, especialmente icones inseridos por augmentation e elementos sem conexao,
  podem melhorar a precisao do detector sem sacrificar recall.

## Necessita investigacao

- Quantos erros de OCR decorrem de inclinacao global e quantos decorrem de baixa resolucao ou texto
  sobreposto.
- Quais features separam arestas verdadeiras e falsas de `segment_graph` de forma estavel por diagrama.
- Se componentes perifericos considerados falsos pelo benchmark sao realmente irrelevantes ou apenas
  estao fora da politica de anotacao de componentes principais.
- Se o ganho do RAG vetorial e superior ao fallback lexical para consultas reais do produto.

# 3. Gargalos atuais

1. **P0 - perda de alternativas no pipeline completo:** quebra a promessa de rastreabilidade da v15.
2. **P0 - explosao combinatoria de fluxos densos:** a precisao de arestas reais e o principal limite
   estrutural, mesmo quando a deteccao de componentes e isolada.
3. **P1 - componentes extras:** 142 previsoes para 92 componentes esperados ainda amplificam ameacas.
4. **P1 - fronteiras de confianca:** F1 0,125 limita regras dependentes de transicao entre zonas.
5. **P1 - avaliacao insuficiente do RAG:** disponibilidade nao comprova relevancia nem grounding.
6. **P2 - observabilidade por etapa:** regressao de OCR, YOLO ou geometria nao e localizada rapidamente.
7. **P2 - validacao STRIDE circular:** falta um conjunto de ameacas revisado por AppSec e independente
   do motor que esta sendo avaliado.

# 4. Melhorias recomendadas

## Visao computacional

### Hard-negative mining orientado pelos erros v15

* Problema: o detector ainda produz 142 componentes para 92 esperados.
* Evidencia: precisao de localizacao micro 0,4366; fine-tuning anterior foi rejeitado por perda de recall.
* Solucao: anotar apenas falsos positivos recorrentes e componentes ausentes no desenvolvimento,
  incluindo overlays de augmentation como classe de fundo, mantendo split por `sourceGroup`.
* Impacto esperado: reduzir componentes e ameacas extras sem nova supressao heuristica.
* Risco: overfitting nas nove imagens e queda de recall de classes raras.
* Metricas: precisao/localizacao, recall tipado, mAP por classe, 152 acertos e 198 extras.
* Prioridade: P1.

### Inferencia em tiles como experimento, nao como padrao

* Problema: icones pequenos em diagramas de alta resolucao podem ser perdidos.
* Evidencia: necessita investigacao; tiles tambem podem multiplicar falsos positivos.
* Solucao: testar tiles sobrepostos com NMS global e comparar somente em imagens densas.
* Impacto esperado: aumentar recall de componentes pequenos.
* Risco: duplicatas e custo de inferencia.
* Metricas: recall tipado por tamanho, duplicatas por imagem, latencia p50/p95.
* Prioridade: P3.

## OCR

### Matching global entre rotulos e ancoras

* Problema: a associacao gulosa permite que varios rotulos usem a mesma regiao visual.
* Evidencia: a v15 precisou resolver conflitos depois que propostas ja haviam sido criadas.
* Solucao: gerar uma matriz de custo com distancia, alinhamento, tamanho, provedor e compatibilidade
  semantica; resolver matching bipartido e preservar candidatos nao escolhidos como alternativas.
* Impacto esperado: menos duplicatas e melhor localizacao sem reduzir cobertura OCR.
* Risco: diagramas com um rotulo descrevendo um grupo de replicas.
* Metricas: acuracia label-ancora, propostas por componente, recall tipado e F1 ponta a ponta.
* Prioridade: P1.

### Deskew e orientacao com transformacao reversivel

* Problema: OCR nao corrige inclinacao global antes do Tesseract.
* Evidencia: o codigo atual apenas redimensiona, aplica contraste e nitidez; impacto real necessita
  investigacao.
* Solucao: estimar angulo por linhas dominantes, aplicar deskew somente acima de um limiar e mapear
  caixas de OCR de volta por matriz inversa.
* Impacto esperado: recuperar rotulos e protocolos em imagens inclinadas.
* Risco: degradar diagramas com varias orientacoes locais.
* Metricas: CER/WER em rotulos anotados, recall de protocolos, IoU das caixas remapeadas.
* Prioridade: P2.

## Reconstrucao de fluxos

### Grafo de conectores consciente de cruzamentos e juncoes

* Problema: caminhos entre fragmentos conectam pares demais em desenhos densos.
* Evidencia: 142 fluxos previstos para 71 esperados; `azure-private-ai-platform` preve 21 para 8.
* Solucao: construir polylines por continuidade angular/cor, classificar no de grau alto como
  cruzamento, T-junction ou bifurcacao e iniciar travessia somente em endpoints ligados a componentes.
* Impacto esperado: maior precisao de existencia de aresta mantendo fan-out legitimo.
* Risco: interromper linhas que realmente se bifurcam.
* Metricas: precisao/recall/F1 de arestas, FP por evidencia, recall em hubs e bifurcacoes.
* Prioridade: P0.

### Ranker supervisionado de candidatos de aresta

* Problema: `MINIMUM_FLOW_SCORE` usa score geometrico fixo e pouco discriminativo.
* Evidencia: scores dos falsos e verdadeiros podem se sobrepor; necessita validacao experimental.
* Solucao: treinar regressao logistica ou gradient boosting pequeno com distancia de ancoragem,
  eficiencia, hops, continuidade angular, suporte de pixels, grau de juncao, cruzamentos e arrowhead.
* Impacto esperado: reduzir FP sem limite arbitrario de grau.
* Risco: poucos diagramas e leakage entre variantes.
* Metricas: PR-AUC de candidatos, ECE, F1 de arestas e recall por diagrama.
* Prioridade: P1.

### Fronteiras por contorno e hierarquia de zonas

* Problema: a associacao de membros a fronteiras possui F1 0,125.
* Evidencia: 8 esperadas, 8 previstas e apenas 1 correta no benchmark expandido.
* Solucao: separar contornos de container de linhas de fluxo, admitir zonas aninhadas e calcular
  membership por centro/area de intersecao com diagnostico auditavel.
* Impacto esperado: regras de trust boundary mais confiaveis.
* Risco: cards e grupos visuais confundidos com fronteiras de seguranca.
* Metricas: F1 de membership, FP de zonas e ameacas de protocolo em fronteira.
* Prioridade: P1.

## Arbitragem e fusao de evidencias

### Contrato unico para candidatos ativos e alternativos

* Problema: `detectionAlternatives` se perde ao normalizar a arquitetura.
* Evidencia: o campo so e referenciado no detector e na documentacao.
* Solucao: preservar e validar alternativas em normalizacao, API, historico e exportacoes; criar
  `flowAlternatives` com os mesmos campos de proveniencia para arestas podadas.
* Impacto esperado: rastreabilidade real de todas as decisoes automaticas.
* Risco: payload maior e ids inconsistentes apos edicao humana.
* Metricas: cobertura de proveniencia, alternativas orfas e testes de round-trip.
* Prioridade: P0.

### Calibracao por fonte de evidencia

* Problema: apenas confianca de componentes YOLO possui calibracao formal.
* Evidencia: OCR, `segment_graph`, pixel support e direcao usam formulas manuais.
* Solucao: calibrar separadamente componente OCR, existencia de fluxo e direcao; nunca misturar as
  probabilidades como se medissem o mesmo evento.
* Impacto esperado: limiares de revisao e abstencao mais interpretaveis.
* Risco: amostra pequena gerar calibracao instavel.
* Metricas: Brier, ECE, cobertura e precisao por fonte.
* Prioridade: P2.

## Modelagem STRIDE

### Estado draft para ameacas dependentes de evidencia nao revisada

* Problema: componentes/fluxos pendentes geram ameacas com a mesma presenca estrutural de fatos
  confirmados.
* Evidencia: o motor usa todos os componentes e fluxos ativos; a confianca afeta score, nao elegibilidade.
* Solucao: marcar ameacas como `draft` quando dependem exclusivamente de evidencia pendente e promover
  para `open` apos confirmacao; nao remover ameacas silenciosamente.
* Impacto esperado: reduzir confusao no MVP sem esconder risco potencial.
* Risco: usuario interpretar `draft` como seguro.
* Metricas: ameacas draft/open, tempo de revisao, falsos positivos aceitos e cobertura STRIDE.
* Prioridade: P2.

### Golden set independente de especialistas

* Problema: o benchmark atual valida regras implementadas, nao suficiencia de ameacas reais.
* Evidencia: esperado e previsto ponta a ponta usam o mesmo `analyze_architecture()`.
* Solucao: obter anotacao AppSec de ameacas aplicaveis, nao aplicaveis e contramedidas para um pequeno
  conjunto de arquiteturas, com justificativa e severidade.
* Impacto esperado: evidencia de qualidade de seguranca, nao apenas de consistencia de software.
* Risco: divergencia legitima entre especialistas.
* Metricas: precision/recall por STRIDE, concordancia e cobertura de contramedidas.
* Prioridade: P1.

## RAG

### Benchmark de recuperacao antes de mudar o retriever

* Problema: nao ha evidencia quantitativa de relevancia dos 100 trechos.
* Evidencia: existem testes de disponibilidade/formato, mas nenhum golden set de retrieval.
* Solucao: criar consultas por componente, provedor, STRIDE e controle, com documentos relevantes e
  hard negatives anotados.
* Impacto esperado: permitir decisao objetiva entre vector, lexical e hibrido.
* Risco: golden set reproduzir exatamente os termos dos documentos.
* Metricas: Recall@3/5, MRR, nDCG@5 e taxa de ameacas sem fonte relevante.
* Prioridade: P1.

### Recuperacao hibrida com metadados

* Problema: a consulta vetorial concatena tipos e STRIDE e nao usa filtros de provedor/categoria.
* Evidencia: `rag.query()` retorna documentos sem score e a associacao posterior usa tokens de
  `source` e `section`.
* Solucao: adicionar metadados estruturados, combinar BM25/lexical e cosseno por reciprocal rank
  fusion e devolver score/proveniencia.
* Impacto esperado: fontes mais especificas e rastreaveis.
* Risco: complexidade sem ganho se o golden set for pequeno.
* Metricas: somente as definidas no benchmark RAG.
* Prioridade: P2, dependente do benchmark.

## Backend

### Telemetria por etapa e execucao fora do event loop

* Problema: existe apenas duracao total; inferencia/OCR/estrutura sao sincronas dentro de endpoint async.
* Evidencia: middleware registra uma linha por requisicao e `_detect_components()` chama o detector
  sincrono diretamente.
* Solucao: medir YOLO, OCR, estrutura, STRIDE, RAG e PDF; executar inferencia CPU em threadpool com
  limite de concorrencia; nao registrar imagem nem texto sensivel.
* Impacto esperado: diagnostico e demonstracao mais previsiveis.
* Risco: concorrencia aumentar memoria e latencia.
* Metricas: p50/p95 por etapa, memoria, erros e fila.
* Prioridade: P2.

## Frontend e dashboard

### Painel de alternativas e evidencia de fluxo

* Problema: o usuario nao consegue inspecionar hipoteses suprimidas nem o caminho geometrico da aresta.
* Evidencia: o dashboard edita ativos, mas nao referencia `detectionAlternatives`, `pathPoints` ou
  `arrowheadScores`.
* Solucao: camada alternavel para candidatos, motivo de supressao e restauracao; filtros por origem e
  confianca; caminho do fluxo sobre a imagem com tooltip de evidencia.
* Impacto esperado: human-in-the-loop demonstravel e revisao mais rapida.
* Risco: poluicao visual em diagramas densos.
* Metricas: tempo/cliques de revisao, restauracoes, rejeicoes e erros de UI.
* Prioridade: P1, depois do contrato backend.

## Testes e avaliacao

### Gate congelado da v15 e metricas estratificadas

* Problema: nao existe um unico gate que impeça regressao das metricas v15 ao aceitar um experimento.
* Evidencia: resultados existem, mas a verificacao geral nao compara a implementacao corrente ao
  baseline v15.
* Solucao: criar comando de ablation gate no desenvolvimento e relatorio por densidade, provedor,
  origem de evidencia, tamanho e status de revisao.
* Impacto esperado: evolucao incremental e rollback objetivo.
* Risco: tornar testes locais lentos; separar suite rapida de gate experimental.
* Metricas: todas as baselines registradas neste documento.
* Prioridade: P0 e quick win.

## Documentacao e governanca tecnica

### Ledger de experimentos e revisao independente

* Problema: varias ablations estao preservadas, mas falta uma tabela unica com hipotese, hash, decisao
  e motivo de rollback; anotacoes prospectivas ainda aguardam verificacao independente.
* Evidencia: a proveniencia prospectiva declara assistencia do Codex e a pendencia humana.
* Solucao: ledger append-only, model/data cards e protocolo de segunda anotacao com concordancia.
* Impacto esperado: defesa tecnica mais forte perante a banca.
* Risco: nenhum risco de runtime; exige tempo humano.
* Metricas: cobertura de hashes, experimentos com decisao e concordancia entre anotadores.
* Prioridade: P1.

# 5. Backlog tecnico

Classificacao usada: **P0 - bloqueador**, **P1 - alta prioridade**, **P2 - media prioridade** e
**P3 - melhoria futura**. P0 impede evolucao segura ou viola um contrato declarado do produto.

| ID | Prioridade | Tarefa | Objetivo | Esforco | Dependencias | Criterio de aceite |
| -- | ---------- | ------ | -------- | ------- | ------------ | ------------------ |
| TL-001 | P0 | Gate de regressao v15 | Bloquear mudancas que degradam o baseline | Pequeno | Nenhuma | F1 >= 0,5296; recall >= 0,6786; corretas >= 152; testes e auditoria v12 passam |
| TL-002 | P0 | Round-trip de alternativas | Preservar `detectionAlternatives` em full pipeline/export | Pequeno | TL-001 | Alternativas sobrevivem detectar, normalizar, analisar, historico e exportar |
| TL-003 | P0 | Diagnostico estratificado de fluxos | Medir erros por evidencia e densidade | Pequeno | TL-001 | JSON/Markdown com TP/FP/FN por `segment_graph`, linha, pixel, hops e juncoes |
| TL-004 | P0 | Grafo junction-aware | Separar cruzamentos, bifurcacoes e cotovelos | Grande | TL-003 | Precisao de aresta aumenta sem perda de recall maior que 0,02 |
| TL-005 | P1 | Ranker de candidatos | Classificar existencia de aresta | Medio | TL-003, TL-004 | PR-AUC e F1 superam score fixo em validacao por diagrama |
| TL-006 | P1 | Matching global OCR-ancora | Evitar varias propostas para a mesma ancora | Medio | TL-001 | Menos duplicatas sem reduzir recall tipado medio 0,6176 |
| TL-007 | P2 | Deskew reversivel | Melhorar OCR em imagens inclinadas | Medio | Dataset OCR anotado | CER/WER melhora e caixas remapeadas mantem IoU acordado |
| TL-008 | P1 | Hard-negative active learning | Reduzir componentes falsos | Grande | TL-001 | Extras caem; recall >= 0,6786 e corretas >= 152 |
| TL-009 | P1 | Fronteiras hierarquicas | Elevar F1 de membership acima de 0,125 | Grande | TL-003 | F1 melhora no desenvolvimento sem aumentar ameacas indevidas |
| TL-010 | P2 | Calibracao por fonte | Tornar confiancas comparaveis por evento | Medio | TL-003, TL-006 | Brier/ECE reportados e menores que baseline da respectiva fonte |
| TL-011 | P1 | Golden set RAG | Medir relevancia da recuperacao | Medio | Revisao humana | Recall@k, MRR e nDCG reproduziveis para vector e lexical |
| TL-012 | P2 | Retriever hibrido | Melhorar fontes recuperadas | Medio | TL-011 | Ganha no golden set; rollback se nao superar baseline |
| TL-013 | P1 | Golden set AppSec | Validar ameacas e controles independentemente | Grande | Especialista | Concordancia registrada e metricas por STRIDE calculadas |
| TL-014 | P2 | Estado de ameaca draft | Distinguir inferencia pendente de fato revisado | Medio | TL-002, TL-013 | Nenhuma ameaca e perdida; transicao draft/open e auditavel |
| TL-015 | P2 | Telemetria por etapa | Observar custo e falha de cada modulo | Medio | Nenhuma | p50/p95 e contadores sem dados sensiveis; health permanece compativel |
| TL-016 | P1 | UI de alternativas e caminhos | Tornar a revisao visual explicavel | Medio | TL-002, TL-003 | Restaurar/rejeitar alternativa e inspecionar evidencia em desktop/mobile |
| TL-017 | P1 | Ledger e segunda anotacao | Fortalecer governanca experimental | Medio | Humano independente | Hash, hipotese, decisao e concordancia presentes para todo resultado promovido |

## Detalhamento executavel das tarefas

### TL-001 - Gate de regressao v15

- **Contexto/objetivo:** transformar as metricas aceitas em contrato automatizado.
- **Descricao tecnica:** comparar a saida corrente de `development_tuning` com o JSON v15 e falhar
  quando os limites forem violados; a execucao deve usar protocolo `development`, nunca `blind`.
- **Arquivos:** novo `scripts/check_v15_regression.py`, `package.json`, `scripts/verify_project.py`, testes.
- **Etapas:** carregar baseline; validar protocolo/split; calcular deltas; emitir JSON; adicionar comando.
- **Dependencias:** nenhuma. **Esforco:** pequeno. **Risco:** tempo de execucao.
- **Aceite/testes:** testes unitarios de cada condicao; 85 testes existentes passam; auditoria v12 passa.
- **Antes/depois:** antes sem gate; depois F1 >= 0,5296, recall >= 0,6786, corretas >= 152 e extras
  nao aumentam, salvo excecao documentada com ganho aprovado. **Prioridade:** P0.

### TL-002 - Round-trip de alternativas

- **Contexto/objetivo:** corrigir a perda confirmada de rastreabilidade da v15.
- **Descricao tecnica:** validar e preservar alternativas no normalizador, `_build_response`, JSON, PDF,
  historico; manter ids, `supersededBy`, razao e fonte; nao gerar ameacas automaticamente delas.
- **Arquivos:** `backend/stride_engine.py`, `backend/main.py`, `backend/pdf_report.py`, `app/main.js`, testes.
- **Etapas:** definir schema; normalizar; validar referencias; expor API; persistir; testar round-trip.
- **Dependencias:** TL-001. **Esforco:** pequeno. **Risco:** payload e ids orfaos.
- **Aceite/testes:** alternativa criada no detector chega identica ao resultado/exportacao e pode ser
  restaurada; ativa e alternativa nunca geram ameaca duplicada.
- **Antes/depois:** cobertura full-pipeline 0% -> 100% para campos obrigatorios. **Prioridade:** P0.

### TL-003 - Diagnostico estratificado de fluxos

- **Contexto/objetivo:** identificar precisamente por que 90 arestas nao direcionadas sao extras.
- **Descricao tecnica:** armazenar candidatos aceitos/rejeitados e calcular TP/FP/FN por evidencia,
  hops, eficiencia, distancia, suporte, grau de no, cruzamento e densidade da imagem.
- **Arquivos:** `backend/diagram_structure.py`, `scripts/evaluate_real_architecture_benchmark.py`, testes.
- **Etapas:** definir schema; preservar `flowAlternatives`; mapear candidatos ao gold; gerar PR e buckets.
- **Dependencias:** TL-001. **Esforco:** pequeno. **Risco:** crescimento dos artefatos.
- **Aceite/testes:** relatorio reproduz 71/142/52 TP nao direcionados e explica 100% dos candidatos.
- **Antes/depois:** sem estratificacao -> metricas por fonte e densidade. **Prioridade:** P0.

### TL-004 - Grafo junction-aware

- **Contexto/objetivo:** impedir conectividade falsa em linhas cruzadas.
- **Descricao tecnica:** unir segmentos por continuidade angular e pixel/cor; detectar cruzamento sem
  conexao; modelar T-junction/bifurcacao; percorrer de endpoint anexado a endpoint anexado.
- **Arquivos:** `backend/diagram_structure.py`, fixtures de estrutura, testes.
- **Etapas:** extrair primitives; classificar nos; montar polylines; associar endpoints; ablation isolada.
- **Dependencias:** TL-003. **Esforco:** grande. **Risco:** cortar fan-out valido.
- **Aceite/testes:** FP cai >= 20% como meta experimental, recall nao cai mais de 0,02, e fixtures de
  cotovelo, crossing, T e branch passam.
- **Antes/depois:** P/R/F1 nao direcionado 0,3662/0,7324/0,4883; comparar formalmente. **Prioridade:** P0.

### TL-005 - Ranker supervisionado de arestas

- **Contexto/objetivo:** substituir apenas a decisao final do score fixo.
- **Descricao tecnica:** criar dataset de candidatos do TL-003, treinar modelo pequeno e calibravel,
  validado deixando um diagrama/grupo fora; manter regra atual como fallback.
- **Arquivos:** novo `scripts/train_flow_candidate_classifier.py`, `backend/flow_classifier.py`, modelo.
- **Etapas:** extrair features; dividir por grupo; treinar; calibrar; comparar; registrar hash.
- **Dependencias:** TL-003 e, preferencialmente, TL-004. **Esforco:** medio. **Risco:** overfitting.
- **Aceite/testes:** PR-AUC e F1 de aresta maiores em validacao por grupo, com recall dentro do gate.
- **Antes/depois:** score manual vs modelo versionado; E2E deve manter 152 acertos. **Prioridade:** P1.

### TL-006 - Matching global OCR-ancora

- **Contexto/objetivo:** resolver conflito antes da arbitragem v15.
- **Descricao tecnica:** matching bipartido com custo auditavel, suporte a grupos/replicas e alternativas.
- **Arquivos:** `backend/detector.py`, `backend/ocr.py`, testes e ablation OCR.
- **Etapas:** gerar candidatos; definir custo; matching; grupo de replicas; comparar com greedy.
- **Dependencias:** TL-001. **Esforco:** medio. **Risco:** rotulos de grupos.
- **Aceite/testes:** duplicatas caem, recall tipado medio >= 0,6176, 152 corretas preservadas.
- **Antes/depois:** registrar propostas/duplicatas/matches por imagem. **Prioridade:** P1.

### TL-007 - Deskew reversivel

- **Contexto/objetivo:** validar se inclinacao limita OCR.
- **Descricao tecnica:** estimador conservador de angulo, transformacao de imagem e inversa de caixas.
- **Arquivos:** `backend/ocr.py`, novo benchmark OCR, testes geometricos.
- **Etapas:** anotar amostra; estimar angulo; aplicar limiar; inverter coordenadas; ablation.
- **Dependencias:** anotacao OCR. **Esforco:** medio. **Risco:** orientacoes mistas.
- **Aceite/testes:** melhora CER/WER e nao reduz protocolo F1 0,8 ou metricas v15.
- **Antes/depois:** necessita baseline CER/WER antes da implementacao. **Prioridade:** P2.

### TL-008 - Hard-negative active learning

- **Contexto/objetivo:** reduzir componentes extras sem depender de filtro pos-hoc.
- **Descricao tecnica:** selecionar falsos positivos de alta confianca e misses por classe; anotar
  fundo/componentes; fine-tuning curto com replay do dataset hibrido e split por origem.
- **Arquivos:** `scripts/build_active_learning_dataset.py`, treino, manifesto e model comparison.
- **Etapas:** minerar; revisar; treinar seeds repetidas; avaliar; promover somente pelo gate.
- **Dependencias:** TL-001. **Esforco:** grande. **Risco:** esquecimento catastrofico.
- **Aceite/testes:** precisao sobe, recall >= 0,6786, corretas >= 152; checkpoint rejeitado se falhar.
- **Antes/depois:** 142/92 componentes, precisao de localizacao 0,4366, recall tipado medio 0,6176.
  **Prioridade:** P1.

### TL-009 - Fronteiras hierarquicas

- **Contexto/objetivo:** melhorar membership real de 0,125.
- **Descricao tecnica:** classificar contornos, permitir nesting e usar centro mais cobertura de area.
- **Arquivos:** `backend/diagram_structure.py`, benchmark real e testes.
- **Etapas:** catalogar erros; extrair contornos; excluir cards; membership; avaliar isoladamente.
- **Dependencias:** TL-003. **Esforco:** grande. **Risco:** zonas visuais nao semanticas.
- **Aceite/testes:** F1 > 0,125 com zero regressao de protocolo/fluxo e alternativas preservadas.
- **Antes/depois:** 8/8/1 TP -> registrar nova matriz. **Prioridade:** P1.

### TL-010 - Calibracao por fonte

- **Contexto/objetivo:** transformar scores manuais em confiancas auditaveis.
- **Descricao tecnica:** datasets e calibradores distintos para OCR, existencia e direcao de fluxo.
- **Arquivos:** novos scripts de calibracao, modelos JSON, modulos de OCR/estrutura.
- **Etapas:** definir evento; montar labels; group CV; calibrar; curva cobertura/precisao; registrar.
- **Dependencias:** TL-003, TL-006. **Esforco:** medio. **Risco:** amostra insuficiente.
- **Aceite/testes:** Brier/ECE melhoram para cada fonte; fallback permanece deterministico.
- **Antes/depois:** necessita investigacao/baseline por fonte. **Prioridade:** P2.

### TL-011 - Golden set RAG

- **Contexto/objetivo:** medir relevancia, hoje desconhecida.
- **Descricao tecnica:** consultas naturais com ids de trechos relevantes e hard negatives; avaliar
  vector e lexical sem alterar o retriever.
- **Arquivos:** novo `data/benchmarks/rag/golden-set.json`, script e testes.
- **Etapas:** amostrar casos; anotar; validar ids; medir Recall@k/MRR/nDCG; documentar.
- **Dependencias:** revisao humana. **Esforco:** medio. **Risco:** viés lexical.
- **Aceite/testes:** benchmark reproduzivel, cobertura de componentes/provedores/STRIDE e duas baselines.
- **Antes/depois:** sem metricas -> metricas formais. **Prioridade:** P1.

### TL-012 - Retriever hibrido

- **Contexto/objetivo:** melhorar retrieval somente apos TL-011.
- **Descricao tecnica:** metadados e reciprocal rank fusion entre lexical e vetor; retornar scores.
- **Arquivos:** `backend/rag.py`, knowledge metadata, testes.
- **Etapas:** schema; indexacao; ranking; filtro; ablation; fallback.
- **Dependencias:** TL-011. **Esforco:** medio. **Risco:** nenhuma melhora objetiva.
- **Aceite/testes:** supera ambas as baselines no golden; rollback caso contrario.
- **Antes/depois:** registrar Recall@5, MRR e nDCG@5. **Prioridade:** P2.

### TL-013 - Golden set AppSec

- **Contexto/objetivo:** remover circularidade da validacao de ameacas.
- **Descricao tecnica:** esquema de ameaca aplicavel/nao aplicavel, alvo, STRIDE, severidade,
  contramedida e justificativa, anotado sem consultar a saida do motor.
- **Arquivos:** novo benchmark, avaliador e protocolo de anotacao.
- **Etapas:** selecionar diagramas; anotar; adjudicar; mapear taxonomia; medir.
- **Dependencias:** especialista humano. **Esforco:** grande. **Risco:** discordancia.
- **Aceite/testes:** concordancia e metricas por STRIDE publicadas; nenhuma alegacao baseada so no
  golden de regras. **Antes/depois:** necessita investigacao. **Prioridade:** P1.

### TL-014 - Estado draft

- **Contexto/objetivo:** comunicar dependencia de evidencia pendente.
- **Descricao tecnica:** derivar status sem alterar fatos; manter `draft`, `open`, tratamentos e trilha.
- **Arquivos:** `backend/stride_engine.py`, `backend/main.py`, PDF e dashboard.
- **Etapas:** regra de status; propagacao; revisao; exportacao; testes.
- **Dependencias:** TL-002, TL-013. **Esforco:** medio. **Risco:** falsa sensacao de seguranca.
- **Aceite/testes:** toda ameaca draft aponta candidatos; confirmacao promove sem mudar id.
- **Antes/depois:** zero perda de ameacas e cobertura STRIDE. **Prioridade:** P2.

### TL-015 - Telemetria por etapa

- **Contexto/objetivo:** localizar custo e falhas sem coletar conteudo sensivel.
- **Descricao tecnica:** timers/counters estruturados, ids de correlacao e threadpool limitado.
- **Arquivos:** `backend/main.py`, detector/OCR/estrutura, testes de contrato.
- **Etapas:** instrumentar; sanitizar; expor resumo; testar concorrencia; documentar.
- **Dependencias:** nenhuma. **Esforco:** medio. **Risco:** overhead/memoria.
- **Aceite/testes:** p50/p95 por etapa e nenhum texto/imagem no log; readiness inalterada.
- **Antes/depois:** apenas duracao HTTP total -> seis etapas. **Prioridade:** P2.

### TL-016 - UI de alternativas e caminhos

- **Contexto/objetivo:** tornar a rastreabilidade utilizavel.
- **Descricao tecnica:** painel sem cards aninhados, filtros, toggle de candidatos e overlay de paths.
- **Arquivos:** `app/index.html`, `app/main.js`, `app/styles.css`.
- **Etapas:** estado; lista; restaurar/rejeitar; overlay; exportar; QA responsivo.
- **Dependencias:** TL-002, TL-003. **Esforco:** medio. **Risco:** excesso visual.
- **Aceite/testes:** fluxo completo por teclado e mobile; nenhuma alternativa some do historico.
- **Antes/depois:** 0 alternativas visiveis -> 100% das recebidas. **Prioridade:** P1.

### TL-017 - Ledger e segunda anotacao

- **Contexto/objetivo:** consolidar governanca e reduzir vies de anotacao.
- **Descricao tecnica:** ledger append-only com hash, hipotese, split, resultado, decisao e revisor;
  protocolo de segunda anotacao independente.
- **Arquivos:** `docs/experiments.md`, manifests, protocolo e auditorias.
- **Etapas:** schema; migrar ablations; segunda anotacao; adjudicar; atualizar docs.
- **Dependencias:** humano independente. **Esforco:** medio. **Risco:** calendario.
- **Aceite/testes:** todo modelo promovido tem evidencia e rollback; v12 continua hash-identica.
- **Antes/depois:** medir cobertura do ledger e concordancia. **Prioridade:** P1.

# 6. Plano experimental

## EXP-01 - Diagnostico de conectividade

- **Hipotese:** `segment_graph` concentra FP em caminhos com muitos hops, nos de alto grau ou baixa
  continuidade angular.
- **Alteracao isolada:** nenhuma mudanca de inferencia; apenas telemetria/categorizacao.
- **Dados:** nove diagramas `development_tuning` com caixas gold.
- **Baseline:** 71 esperados, 142 previstos, 52 TP nao direcionados.
- **Metricas:** TP/FP/FN e PR por feature/evidencia/densidade.
- **Sucesso:** ao menos uma feature ou combinacao separa FP com ganho de precisao e perda de recall
  estimada <= 0,02. **Rollback:** nao aplicavel.
- **Artefatos:** candidatos JSONL, resumo JSON/Markdown, hashes e comando.

## EXP-02 - Juncoes e cruzamentos

- **Hipotese:** impedir transicao em crossing sem evidencia de juncao reduz >= 20% dos FP.
- **Alteracao isolada:** somente regra de travessia no grafo; score e detector permanecem iguais.
- **Dados:** desenvolvimento real mais fixtures controladas de crossing/T/branch/elbow.
- **Baseline:** F1 nao direcionado 0,4883; recall 0,7324.
- **Metricas:** P/R/F1, FP por imagem e recall de bifurcacoes.
- **Sucesso:** F1 aumenta e recall >= 0,7124; E2E mantem 152 corretas e recall 0,6786.
- **Rollback:** qualquer violacao do gate ou falha em branch fixture.
- **Artefatos:** pasta de ablation, snapshot do codigo e diff de erros.

## EXP-03 - Classificador de arestas

- **Hipotese:** features geometricas supervisionadas superam o score fixo.
- **Alteracao isolada:** substituir apenas aceite/rejeicao do candidato.
- **Dados:** candidatos do EXP-01, validacao leave-one-diagram/source-group-out.
- **Baseline:** regra `MINIMUM_FLOW_SCORE` atual.
- **Metricas:** PR-AUC, Brier, ECE, P/R/F1 de aresta e E2E.
- **Sucesso:** melhora F1 e calibracao sem perder mais de 0,02 de recall estrutural.
- **Rollback:** leakage, variancia alta entre folds ou gate v15 violado.
- **Artefatos:** dataset manifest, modelo/hash, folds, curvas e model card.

## EXP-04 - Matching global OCR

- **Hipotese:** matching bipartido reduz duplicatas sem reduzir cobertura.
- **Alteracao isolada:** trocar associacao label-ancora; manter taxonomia e v15.
- **Dados:** nove diagramas de desenvolvimento e fixtures de replicas/grupos.
- **Baseline:** matching guloso + arbitragem v15.
- **Metricas:** duplicatas, matches corretos, recall tipado e E2E.
- **Sucesso:** menos propostas extras, recall tipado medio >= 0,6176 e 152 corretas.
- **Rollback:** qualquer perda sem reducao proporcional aprovada de extras.
- **Artefatos:** pares label-ancora antes/depois, JSON de ablation e testes.

## EXP-05 - Deskew

- **Hipotese:** diagramas com inclinacao acima do limiar melhoram CER/WER.
- **Alteracao isolada:** pre-processamento de OCR, sem mudar parser semantico.
- **Dados:** subconjunto anotado por faixas de angulo; nao usar v12.
- **Baseline:** OCR atual sem rotacao.
- **Metricas:** CER, WER, IoU remapeado e protocolo F1.
- **Sucesso:** ganho no estrato inclinado, sem regressao no estrato reto.
- **Rollback:** erro de remapeamento ou protocolo F1 < 0,8.
- **Artefatos:** anotacoes, matrizes, visualizacoes e relatorio.

## EXP-06 - Hard negatives

- **Hipotese:** negativos reais de alta confianca reduzem componentes extras.
- **Alteracao isolada:** fine-tuning do detector; OCR/fluxos/v15 congelados.
- **Dados:** erros de desenvolvimento mais replay hibrido; split por grupo e seeds >= 3.
- **Baseline:** `threatlens-hybrid-v2` atual.
- **Metricas:** source-slice mAP/recall, componente micro/medio e E2E.
- **Sucesso:** extras < 198, corretas >= 152 e recall E2E >= 0,6786 em todas as seeds aceitas.
- **Rollback:** qualquer gate falha; preservar checkpoint como resultado negativo.
- **Artefatos:** manifests, pesos, hashes, comparacao e decisao.

## EXP-07 - RAG hibrido

- **Hipotese:** fusao lexical-vetorial com metadados melhora relevancia.
- **Alteracao isolada:** ranking, sem mudar knowledge base ou relatorio.
- **Dados:** golden set TL-011.
- **Baseline:** vector atual e lexical fallback.
- **Metricas:** Recall@3/5, MRR, nDCG@5 e latencia.
- **Sucesso:** superar ambas as baselines sem degradar p95 de forma material acordada.
- **Rollback:** nenhum ganho ou perda de operacao offline.
- **Artefatos:** resultados por consulta, configuracao, hash do indice e decisao.

# 7. Quick wins

1. TL-001: gate v15 com criterios explicitos.
2. TL-002: preservar `detectionAlternatives` no round-trip.
3. TL-003: relatorio de fluxo por fonte/evidencia e densidade.
4. Adicionar `pipelineRevision` e hashes ao historico/exportacao, alem do health ja existente.
5. Corrigir documentacao para distinguir alternativa presente no detector de alternativa preservada
   no pipeline completo, ate TL-002 ser concluida.
6. Registrar contagem de candidatos ativos, alternativos e podados em `structureMetadata`.

# 8. Ordem recomendada de implementacao

1. TL-001, para congelar o contrato v15.
2. TL-002, para corrigir o bloqueador de rastreabilidade.
3. TL-003 e EXP-01, sem alterar inferencia.
4. TL-004 e EXP-02, uma unica mudanca estrutural por vez.
5. TL-005 somente se os diagnosticos mostrarem separabilidade suficiente.
6. TL-006 e EXP-04, isolados das mudancas de fluxo.
7. TL-008 e EXP-06, com modelo atual preservado e seeds repetidas.
8. TL-009, pois fronteiras sao fracas, mas afetam menos casos que existencia de arestas.
9. TL-011 antes de TL-012; nunca trocar o retriever sem benchmark.
10. TL-013 antes de alegacoes sobre qualidade semantica STRIDE.
11. TL-015 e TL-016 para polimento observavel e demonstracao do human-in-the-loop.
12. TL-007, TL-010 e TL-014 conforme a evidencia dos diagnosticos.

# 9. Riscos e regressoes possiveis

- **Overfitting de desenvolvimento:** nove imagens ja orientaram varias versoes. Usar validacao por
  grupo, seeds e declarar todo resultado como desenvolvimento.
- **Poda agressiva de hubs:** limites de grau ou MST podem apagar fan-out legitimo. Preferir evidencia
  de juncao e ranker calibrado.
- **Aumento aparente de F1 por anotacao incompleta:** nao alterar gold apos observar predicoes sem
  protocolo de revisao e nova versao explicitamente pos-hoc.
- **Alternativas orfas:** restaurar componente pode invalidar ids de fluxos/fronteiras. Validar grafo.
- **Calibracao enganosa:** scores de classe, existencia e direcao representam eventos diferentes.
- **Circularidade STRIDE:** manter separado o golden de regras do futuro golden de especialistas.
- **RAG com citacao irrelevante:** disponibilidade de fonte nao equivale a grounding; medir retrieval.
- **Concorrencia CPU:** tiles, OCR e threadpool podem elevar memoria e p95.
- **Privacidade:** observabilidade nao deve registrar imagens, OCR bruto, arquitetura ou segredos.
- **Deriva documental:** dashboard, comparativo e manifesto devem ser atualizados apenas quando uma
  versao e promovida pelo gate.

## Protecao obrigatoria contra regressao

- Nao aceitar mudanca com recall E2E < 0,6786 ou ameacas corretas < 152 sem decisao humana formal,
  justificativa e nova linha de baseline.
- Nao aceitar aumento de extras acima de 198 sem beneficio mensuravel predefinido.
- Manter os 85 testes existentes e adicionar testes do novo contrato.
- Executar `audit_prospective_v12.py` somente como verificacao de hashes, nunca para tuning.
- Nao reescrever benchmark, resultado, seal ou detector arquivado da v12.
- Preservar alternativas, razoes, ids e fonte de evidencia em API e exportacoes.
- Atualizar comparativo e manifesto somente depois da promocao; ablations rejeitadas ficam separadas.

# 10. Pontos que precisam de validacao humana

1. Segunda anotacao independente do holdout prospectivo v12 e calculo de concordancia.
2. Revisao das 92 anotacoes de componentes para decidir o que e componente principal, replica,
   endpoint, subnet, decoracao ou distractor de augmentation.
3. Anotacao de cruzamentos, T-junctions, bifurcacoes, setas e protocolos nos diagramas densos.
4. Confirmacao por especialista de quais retangulos representam trust boundary e quais sao apenas
   agrupamentos visuais.
5. Golden set RAG com relevancia por consulta, evitando copiar apenas palavras dos documentos.
6. Golden set AppSec independente com ameacas aplicaveis, severidade, justificativa e controles.
7. Definicao de tolerancia de latencia e memoria aceitavel para a demonstracao offline.
8. Teste de usabilidade: restaurar alternativa, corrigir fluxo e confirmar revisao sem orientacao do
   desenvolvedor.
9. Aprovacao explicita antes de qualquer trade-off que reduza recall ou as 152 ameacas corretas.
