# TL-004 - Analise da revisao humana do lote 01

- Revisor(a): Luana Caldas
- Casos concluidos: 18/18
- Falsos positivos confirmados: 14
- Controles validos confirmados: 4
- Confianca alta: 13
- Confianca media: 5

## Causas principais

- `ambiguous_endpoint`: 5
- `incorrect_bifurcation`: 1
- `structural_line`: 6
- `transitive_shortcut`: 2
- `valid_junction_or_branch`: 4

## Escopo da TL-004

- `inside`: 11
- `partial`: 7

## Decisao

Acao: `generate_batch_02`.
Motivos: `coverageGapsDeclared`.

Nao houve nova categoria principal. O subtipo relatado permanece sob `structural_line` e nao amplia a taxonomia neste ciclo.

A pipeline e os artefatos prospectivos nao foram alterados.