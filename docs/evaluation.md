# Avaliação do MVP

## Reconstrução de fluxos em development_tuning

| Estratégia | Corretos | Falsos positivos | Ausentes | Recall | F1 | Acurácia de direção |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `legacy` | 52 | 90 | 19 | 0,7324 | 0,4883 | 0,8654 |
| `junction_aware_controlled` | 52 | 75 | 19 | 0,7324 | 0,5253 | 0,8654 |

A configuração controlada corresponde a
`full_without_endpoint_redirect + structural_line_gate`. Ela bloqueou 15 falsos fluxos,
sem bloquear verdadeiros positivos na amostra de desenvolvimento, e preservou os
controles humanos C01-C07.

## Interpretação correta

Os números acima foram obtidos somente no split `development_tuning` e com apoio das
revisões humanas da TL-004. Eles validam integração controlada e reversível, mas não são
evidência de generalização. A estratégia permanece opt-in e `legacy` continua padrão.

O detector de componentes tem avaliação separada no teste híbrido de 39 imagens:
precisão 0,9297, recall 0,8417, mAP50 0,9009 e mAP50-95 0,8666. Essas métricas não devem
ser confundidas com F1 de fluxos ou F1 de ameaças.

## Evidências preservadas

- Gate v15: F1 0,5296, precisão 0,4343, recall 0,6786, 152 ameaças corretas e 198 extras.
- Auditoria prospectiva v12: cadeia hash-selada verificada separadamente.
- Snapshot `legacy`: 142 fluxos no contrato de promoção, mantido imutável.
- `DELIVERY-001`: não executa `blind_holdout` nem `prospective_holdout`.

Os resultados históricos permanecem em `data/results/`; o manifesto de
reprodutibilidade registra hashes, versões e seeds.
