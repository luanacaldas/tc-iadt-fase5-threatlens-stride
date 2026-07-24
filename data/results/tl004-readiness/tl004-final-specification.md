# Especificação técnica final da TL-004

## 1. Objetivo e limites

Implementar uma estratégia experimental `junction_aware` para reduzir falsas adjacências geradas por conectores fragmentados, cruzamentos, bifurcações, troncos compartilhados e associação geométrica de endpoints. A estratégia deve ser opt-in e comparada em modo shadow contra a estratégia `legacy`.

Esta especificação não altera código, thresholds, métricas ou baselines. Somente `development_tuning` poderá ser usado durante a implementação. `blind_holdout`, `prospective_holdout` e a cadeia prospectiva v12 são proibidos.

## 2. Estado atual confirmado no código

- `backend/diagram_structure.py::_candidate_line_segments` extrai segmentos com Canny, máscara de traços neutros e `HoughLinesP`.
- `backend/diagram_structure.py::_segment_graph_candidates` agrega endpoints próximos, cria uma adjacência não direcionada e usa `shortest_path` entre pares de componentes.
- A associação atual considera até os dois componentes geometricamente mais próximos de cada nó e aceita distâncias até `attachment_limit`.
- `_segment_graph_candidates` retém `pathPoints`, `segmentHops` e `routeEfficiency`, mas não retém IDs de segmentos, graus dos nós ou tipos de interseção.
- `backend/diagram_structure.py::detect_flows` combina `detected_line`, `pixel_line_support` e `segment_graph`, deduplica pelo par de componentes e aplica `MINIMUM_FLOW_SCORE`.
- `backend/diagram_structure.py::extract_structure` chama `detect_flows` sem seleção de estratégia.
- `backend/detector.py::detect` chama `extract_structure` e usa os fluxos produzidos na arquitetura.
- `scripts/diagnose_flow_errors.py::_flow_diagnostic` declara explicitamente que identidades e graus dos nós do segment graph não são preservados.
- `scripts/evaluate_real_architecture_benchmark.py::evaluate` e `scripts/diagnose_flow_errors.py::evaluate` já fornecem pontos de avaliação no `development_tuning`.
- `scripts/check_v15_regression.py::run_gate` protege a baseline v15 e a integridade prospectiva v12.

## 3. Contrato de estratégia

1. `legacy` permanece o padrão em produção e em toda chamada sem parâmetro explícito.
2. `junction_aware` somente pode ser ativada explicitamente em desenvolvimento.
3. O modo `shadow` executa as duas estratégias sobre a mesma imagem e os mesmos componentes, sem usar o resultado experimental na análise STRIDE.
4. Resultados de ablação devem ser gravados em diretórios separados e identificar estratégia, split, hashes e timestamp.
5. A comparação deve incluir snapshot das decisões de fluxo, métricas estruturais, C01-C07 e gate v15.
6. A promoção exige decisão humana posterior; nenhum código deve trocar automaticamente o padrão.

## 4. Dentro da TL-004

- contrato de eventos geométricos do segment graph;
- portas, barreiras e contato de endpoints;
- primeiro componente atingido;
- cruzamentos versus junções;
- pareamento de braços em X, T e Y;
- continuidade geométrica;
- decomposição de troncos compartilhados;
- prevenção de clique entre terminais de um barramento;
- supressão de atalhos transitivos;
- preservação de fan-in e fan-out.

## 5. Fora ou parcialmente dentro

Criar `TL-005 — Supressão de linhas estruturais e artefatos visuais` para grades, bordas de containers/subnets, linhas internas de ícones e decoração. Essa tarefa deverá atuar antes ou durante `_candidate_line_segments` e será avaliada separadamente.

OCR, ontologia, direção e componentes ausentes não pertencem à TL-004. A direção continua sob a lógica já existente de arrowheads; a TL-004 apenas deve preservar a direção das arestas que sobreviverem.

## 6. TL-004A — Contrato de eventos geométricos e fixtures

**Problema:** o grafo atual perde identidade de segmentos, ângulos, graus e natureza das interseções, impedindo decisões junction-aware auditáveis.

**Casos humanos:** E06, E13, E15 e E16; controles C02-C07.

**Arquivos e funções existentes afetados:**

- `backend/diagram_structure.py::_segment_graph_candidates`;
- `backend/diagram_structure.py::detect_flows`;
- `scripts/diagnose_flow_errors.py::_flow_diagnostic` e `build_diagnostics`;
- `tests/test_backend_pipeline.py`;
- `tests/test_flow_diagnostics.py`.

**Alteração proposta:** introduzir um contrato interno de eventos contendo ID estável do segmento, endpoints originais, orientação, comprimento, nó agregado, grau, braços incidentes, contatos com componentes e interseções. Nesta etapa, o contrato será apenas observado; os fluxos `legacy` devem permanecer byte-equivalentes no snapshot de decisão.

**Dependências:** nenhuma.

**Testes sintéticos:** linha reta, cotovelo, cruzamento X sem junção, T, Y, quatro braços com junção, segmentos paralelos, lacuna pequena e tronco compartilhado.

**Regressão real:** E06, E13, E15, E16 e C02-C07.

**Aceite:** eventos determinísticos; IDs estáveis; diagnóstico completo; snapshot `legacy` idêntico; todos os testes aprovados.

**Risco:** aumento de memória e alteração acidental da agregação. **Rollback:** desativar emissão de eventos e manter o caminho `legacy` intacto.

**Esforço:** 1 a 1,5 dia.

## 7. TL-004B — Portas, barreiras e endpoints

**Problema:** proximidade geométrica pode associar um caminho a componentes que ele não toca ou permitir que atravesse um componente intermediário.

**Casos humanos:** E03, E05, E07-E11, E15 e E16; controles C01-C07.

**Arquivos e funções existentes afetados:**

- `backend/diagram_structure.py::_point_rect_distance`;
- `backend/diagram_structure.py::_blocked_by_component`;
- `backend/diagram_structure.py::_segment_graph_candidates`;
- `backend/diagram_structure.py::detect_flows`;
- `tests/test_backend_pipeline.py`.

**Alteração proposta:** no caminho `junction_aware`, exigir contato verificável entre terminal e borda/porta; registrar margem e tipo de contato; encerrar ou particionar o caminho no primeiro componente atingido; rejeitar passagem pelo interior de componente sem evento de entrada/saída válido. Não alterar `attachment_limit` do legado.

**Dependência:** TL-004A.

**Testes sintéticos:** endpoint próximo sem contato; contato em cada lado do bbox; caminho tangente; caminho atravessando um, dois e nenhum componente; componente sobreposto; porta compartilhada.

**Regressão real:** E03, E09-E11, E15-E16 como correções obrigatórias; E05, E07-E08 como casos parciais; C01-C07 como proteção.

**Aceite:** rejeitar os casos obrigatórios sem remover arestas dos controles; nenhum aumento de `missedEdgeCount`; `legacy` inalterado.

**Risco:** recall menor em diagramas com conectores que terminam antes do ícone. **Rollback:** selecionar `legacy`; manter tolerância de porta apenas em `junction_aware`.

**Esforço:** 1,5 a 2 dias.

## 8. TL-004C — Cruzamentos e junções

**Problema:** cruzamentos podem permitir troca de ramo e junções reais podem ser quebradas.

**Casos humanos:** E04, E06, E12-E13, E17-E20; controles C04-C07.

**Arquivos e funções existentes afetados:**

- `backend/diagram_structure.py::_segment_graph_candidates`;
- `backend/diagram_structure.py::detect_flows`;
- `scripts/diagnose_flow_errors.py::_flow_diagnostic`;
- `tests/test_backend_pipeline.py`;
- `tests/test_flow_diagnostics.py`.

**Alteração proposta:** classificar interseções por continuidade, terminação de braços e evidência de nó. Em X sem marcador, manter pares colineares independentes. Em T/Y ou junção explícita, permitir ramificação. Cada decisão deve registrar evidência e confiança diagnóstica, sem um classificador supervisionado nesta tarefa.

**Dependência:** TL-004A; usa contatos da TL-004B quando disponíveis.

**Testes sintéticos:** X ortogonal e oblíquo sem junção; X com nó; T; Y; sobreposição curta; linhas quase paralelas; cruzamento junto a componente.

**Regressão real:** E06 e E13 são correções obrigatórias; E04, E12 e E17-E20 permanecem também associados à TL-005; C04-C07 protegem junções reais e densas.

**Aceite:** impedir troca de braço em X sem junção; preservar T/Y válidos; C04-C07 aprovados; direção das arestas corretas preservada.

**Risco:** convenções visuais sem ponto de junção variam entre ferramentas. **Rollback:** manter classificação shadow e retornar ao `legacy`.

**Esforço:** 1,5 a 2,5 dias.

## 9. TL-004D — Troncos compartilhados e pareamento de braços

**Problema:** um barramento pode gerar clique entre terminais ou perder fan-in/fan-out legítimo.

**Casos humanos:** E06, E13, E15 e E16; controles C02-C07, principalmente C04 e C07.

**Arquivos e funções existentes afetados:**

- `backend/diagram_structure.py::_segment_graph_candidates`;
- `backend/diagram_structure.py::detect_flows`;
- `tests/test_backend_pipeline.py`.

**Alteração proposta:** decompor tronco e braços como eventos separados; parear braços por continuidade e portas; impedir produto cartesiano entre todos os terminais; preservar múltiplas arestas que compartilham origem ou destino quando cada braço tem evidência própria.

**Dependências:** TL-004A e TL-004C; integração com TL-004B.

**Testes sintéticos:** fan-in 2x1 e 3x1; fan-out 1x2 e 1x3; barramento com quatro terminais; tronco compartilhado com uma ramificação inválida; conectores paralelos próximos.

**Regressão real:** C02-C07; E06, E13, E15 e E16.

**Aceite:** zero clique espúrio nos fixtures; todas as arestas dos controles preservadas ou recuperadas; nenhuma aresta entre irmãos sem conector próprio.

**Risco:** decomposição excessiva pode duplicar arestas. **Rollback:** ignorar decomposição e usar candidatos `legacy`.

**Esforço:** 1 a 2 dias.

## 10. TL-004E — Supressão de atalhos transitivos

**Problema:** caminhos compostos podem criar A-C quando o diagrama contém apenas A-B e B-C.

**Casos humanos:** E03 e E14; E05, E07-E10 como evidência de componentes atravessados.

**Arquivos e funções existentes afetados:**

- `backend/diagram_structure.py::_segment_graph_candidates`;
- `backend/diagram_structure.py::detect_flows`;
- `tests/test_backend_pipeline.py`.

**Alteração proposta:** rejeitar aresta transitiva quando o caminho toca componente intermediário e pode ser particionado em adjacências suportadas. Uma aresta direta independente só sobrevive com caminho próprio que toca origem e destino sem reutilizar o componente intermediário.

**Dependências:** TL-004B e TL-004D.

**Testes sintéticos:** A-B-C linear; A-C direto independente; ciclo triangular real; componente apenas tangenciado; cadeia com quatro componentes.

**Regressão real:** E03 e E14 obrigatórios; C01-C07 como proteção.

**Aceite:** E03 e E14 removidos; adjacências intermediárias preservadas; nenhum aumento de fluxos ausentes.

**Risco:** remover conexão direta legítima em topologias com redundância. **Rollback:** desativar somente a supressão transitiva no caminho experimental.

**Esforço:** 0,5 a 1 dia.

## 11. TL-004F — Shadow, ablação e promoção controlada

**Problema:** uma mudança estrutural não pode ser promovida sem comparação isolada, ponta a ponta e proteção da v15.

**Casos humanos:** E01-E20 e C01-C07.

**Arquivos e funções existentes afetados:**

- `backend/config.py` para seleção opt-in, mantendo `legacy` como padrão;
- `backend/diagram_structure.py::detect_flows` e `extract_structure`;
- `backend/detector.py::detect`;
- `scripts/evaluate_real_architecture_benchmark.py::evaluate`;
- `scripts/diagnose_flow_errors.py::evaluate` e `build_diagnostics`;
- `scripts/check_v15_regression.py::run_gate`;
- `tests/test_flow_diagnostics.py`;
- `tests/test_v15_regression_gate.py`.

**Alteração proposta:** executar `legacy` e `junction_aware` lado a lado no `development_tuning`; gravar artefatos separados; comparar decisões e métricas; executar a v15 usando o candidato somente em avaliação explícita; nunca alterar o padrão automaticamente.

**Dependências:** TL-004A-E.

**Testes:** snapshots por estratégia, matriz E01-E20/C01-C07, diagnóstico isolado, avaliação end-to-end de desenvolvimento, gate v15, auditoria v12 somente pelo mecanismo existente e sem executar holdouts.

**Aceite técnico mínimo:** falsos fluxos abaixo de 90, adjacências corretas pelo menos 52, ausentes no máximo 19, recall pelo menos 0,7324, F1 maior que 0,4883, C01-C07 aprovados e gate v15 aprovado.

**Aceite para justificar promoção:** `falsePositiveEdgeCount <= 81` (redução mínima de 10%), `edgeExistenceF1 >= 0,5083` (ganho absoluto mínimo de 0,02), `directionAccuracy >= 0,8654`, `reversedEdgeCount <= 7`, nenhum holdout, todos os testes e auditorias aprovados. Apenas reduzir 90 para 89 não justifica promoção.

**Risco:** melhora isolada sem melhora end-to-end ou regressão de ameaças. **Rollback:** manter `legacy` padrão e descartar artefatos experimentais, sem migração de dados.

**Esforço:** 1 a 1,5 dia.

## 12. Controles obrigatórios

- C01: preservar `armor -> load_balancer` e `internet -> load_balancer`; proibir aresta criada entre as origens.
- C02: preservar `api_handler -> queue` e `api_handler -> database`; proibir `queue <-> database` sem evidência.
- C03: preservar `foundry_agent -> openai_model` e `foundry_agent -> ai_search` em alta densidade.
- C04: recuperar `app_service -> key_vault` e `app_service -> storage`; proibir clique entre os destinos.
- C05: preservar `database -> storage` e `monitoring -> storage`; proibir aresta entre as origens.
- C06: preservar `app_service -> foundry_agent` e `foundry_account -> foundry_agent`; proibir aresta entre as origens.
- C07: preservar `mobile -> api` e `mobile -> cognito`; proibir aresta entre os destinos.

## 13. Critérios globais e rollback

Todos os critérios serão calculados sobre `development_tuning`. A cadeia prospectiva v12 deve permanecer selada. O snapshot das decisões `legacy` deve continuar idêntico à baseline. O rollback é imediato por seleção de estratégia e não requer reversão de dados, pois `junction_aware` não será padrão nem persistirá estado.

Estimativa total para uma pessoa: 7 a 10,5 dias úteis, incluindo implementação, fixtures, shadow, diagnóstico e documentação da ablação.

## 14. Ordem de execução

`TL-004A -> TL-004B -> TL-004C -> TL-004D -> TL-004E -> TL-004F`.

Cada subtarefa deve ser implementada e validada separadamente. A autorização atual cobre somente esta especificação; nenhuma subtarefa foi iniciada.
