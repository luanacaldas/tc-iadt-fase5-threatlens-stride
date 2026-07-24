# Consolidação da revisão humana da TL-004

Gerado em: `2026-07-21T14:52:18Z`  
Split autorizado: `development_tuning`  
Escopo: consolidação documental; nenhuma alteração de pipeline foi executada.

## Classificação das evidências

- **Confirmado por revisão humana:** decisões, causas, escopo, confiança, observações e correções registrados nos dois lotes.
- **Confirmado por artefato:** metadados dos casos, provider, densidade, fluxos previstos, métricas e integridade dos snapshots da TL-003.
- **Hipótese técnica:** desenho proposto para a futura estratégia `junction_aware`.
- **Necessita validação:** comportamento e métricas que somente poderão ser confirmados após implementação shadow no `development_tuning`.

## Validação dos 27 casos

| Validação | Resultado |
|---|---:|
| Casos esperados | 27 |
| Casos encontrados | 27 |
| IDs únicos | 27 |
| Erros E01-E20 | 20 |
| Controles C01-C07 | 7 |
| IDs ausentes, inesperados ou duplicados | 0 |
| Decisões conflitantes | 0 |
| Campos obrigatórios de decisão ausentes | 0 |
| Datas de revisão ausentes | 0 |
| Erros classificados como conexão válida | 0 |
| Controles classificados como erro | 0 |

Os 27 campos `response.review.reviewer` estão vazios. O revisor `Luana Caldas` está registrado em `batchAssessment.reviewer` nos dois resultados finais. A consolidação herda esse valor para cada caso e registra `reviewerSource = batchAssessment.reviewer`; os JSONs originais não foram alterados.

## Resultado consolidado

- **Confirmado por revisão humana:** 20 falsos fluxos, 7 conexões válidas e 0 casos ambíguos.
- **Confirmado por revisão humana:** 16 casos dentro da TL-004, 11 parcialmente dentro e 0 fora.
- **Confirmado por artefato:** todos os casos pertencem a `development_tuning`.

### Causa principal

| Causa | Quantidade | Casos |
|---|---:|---|
| `structural_line` | 10 | E01, E02, E04, E05, E07, E12, E17, E18, E19, E20 |
| `ambiguous_endpoint` | 7 | E08, E09, E10, E11, E13, E15, E16 |
| `transitive_shortcut` | 2 | E03, E14 |
| `incorrect_bifurcation` | 1 | E06 |
| `valid_junction_or_branch` | 7 | C01-C07 |

### Causas contribuintes

| Causa | Quantidade | Casos |
|---|---:|---|
| `ambiguous_endpoint` | 10 | E01, E02, E04, E05, E07, E12, E17, E18, E19, E20 |
| `crossing_without_junction` | 8 | E04, E06, E12, E13, E17, E18, E19, E20 |
| `component_passthrough` | 6 | E03, E05, E07, E08, E09, E10 |
| `incorrect_bifurcation` | 3 | E14, E15, E16 |
| `parallel_connector_merge` | 2 | E06, E13 |
| `structural_line` | 1 | E08 |

### Provider, densidade, confiança e escopo

| Dimensão | Distribuição |
|---|---|
| Provider | AWS 11; Azure 8; GCP 4; genérico 4 |
| Densidade | alta 11; média 16; baixa 0 |
| Confiança | alta 21; média 6; baixa 0 |
| Escopo TL-004 | dentro 16; parcial 11; fora 0 |

Os casos de confiança média são E06, E07, E13, E14, E15 e C03. Eles não são ambíguos, mas devem receber atenção explícita nos testes shadow.

## Causas confirmadas

1. **Associação ambígua de endpoints:** causa principal em sete erros e contribuinte em outros dez. E09-E11 e E15-E16 demonstram que proximidade não equivale a contato com porta ou borda.
2. **Linhas estruturais:** causa principal em dez erros. Inclui grades, bordas de containers, subnets, agrupamentos e o subtipo de traço interno de ícone observado em E08.
3. **Passagem por componente:** contribuinte em seis erros. E03, E09 e E10 mostram que o primeiro componente atingido deve encerrar ou particionar o caminho.
4. **Atalho transitivo:** causa principal em E03 e E14.
5. **Troca de ramo:** E06 é a causa principal; E14-E16 são evidências contribuintes.
6. **Cruzamento sem junção:** aparece em oito casos como causa contribuinte.
7. **Mescla de conectores paralelos:** aparece em E06 e E13, ambos com confiança média.
8. **Fan-in, fan-out e junções reais:** C01-C07 confirmam conexões que precisam ser preservadas ou recuperadas.

## Saturação

- O lote 1 apresentou quatro causas principais de erro: `structural_line`, `ambiguous_endpoint`, `transitive_shortcut` e `incorrect_bifurcation`.
- O lote 2 apresentou apenas `structural_line` e `ambiguous_endpoint`, ambas já presentes no lote 1.
- O subtipo de linha interna de ícone é uma variação de `structural_line`, não uma nova categoria principal.
- Dois lotes consecutivos não apresentaram nova causa relevante.

**Decisão:** não é necessário um terceiro lote humano. Bifurcações e conectores paralelos possuem menos exemplos, mas devem ser aprofundados com fixtures sintéticas determinísticas e avaliação shadow, sem ampliar a revisão manual neste momento.

## Separação de escopo

### Dentro da TL-004

- portas e barreiras de componentes;
- término no primeiro componente atingido;
- validação de contato entre endpoint e componente;
- cruzamento versus junção;
- continuidade geométrica e pareamento de braços X, T e Y;
- decomposição de troncos compartilhados sem criar cliques;
- supressão de atalhos transitivos;
- preservação de fan-in, fan-out e junções reais.

### Parcial ou fora do núcleo junction-aware

- remoção de grades, bordas de containers e subnets;
- supressão de traços internos de ícones e elementos decorativos;
- OCR e componentes não detectados;
- direção incorreta;
- problemas de anotação ou ontologia.

Esses itens devem ser tratados em `TL-005 — Supressão de linhas estruturais e artefatos visuais`, com OCR, direção e detecção de componentes permanecendo em seus módulos próprios.

## Baselines preservadas

- Estrutural isolada: 71 esperados, 142 previstos, 52 adjacências corretas, 90 falsos fluxos, 19 ausentes, `edgeExistenceF1 = 0,4883` e `directionAccuracy = 0,8654`.
- v15: F1 `0,5296`, precisão `0,4343`, recall `0,6786`, 152 ameaças corretas e 198 falsos positivos.
- Cadeia prospectiva v12: não executada nem modificada nesta consolidação.

## Conclusão

Os dados humanos estão completos, as causas atingiram saturação amostral e os controles cobrem fan-in, fan-out, junções densas e troncos compartilhados. A TL-004 está pronta para implementação incremental, começando pela TL-004A e mantendo `legacy` como estratégia padrão.
