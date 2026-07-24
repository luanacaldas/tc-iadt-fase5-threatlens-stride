# Desenvolvimento do modelo supervisionado

## Escopo

O modelo supervisionado detecta componentes de arquitetura. Fluxos, direção, fronteiras,
STRIDE e risco são etapas separadas; não foram usados como rótulos do detector.

## Dados e origem

O baseline `dataset/hybrid_v2` reúne 300 diagramas do conjunto complementar do projeto e
73 arquiteturas independentes selecionadas do Software Architecture Dataset público no
Kaggle. O inventário remoto encontrou 8.700 imagens PNG, 8.700 XMLs Pascal VOC e 852
grupos de arquiteturas originais. Foi mantida apenas uma variante por grupo Kaggle porque
as demais eram augmentations da mesma arquitetura.

As anotações Kaggle em Pascal VOC foram convertidas para YOLO e mapeadas para a taxonomia
canônica. Objetos fora do escopo foram preservados na auditoria, mas não convertidos em
rótulos artificiais.

## Classes e divisões

O conjunto final possui 373 imagens e 3.048 objetos anotados:

| Split | Imagens | Labels |
| --- | ---: | ---: |
| Treino | 265 | 265 |
| Validação | 69 | 69 |
| Teste | 39 | 39 |

As 14 classes são `api_gateway`, `backup`, `cdn`, `compute`, `database`,
`identity_provider`, `internet`, `load_balancer`, `monitoring`, `queue`, `secrets_kms`,
`storage`, `user` e `waf`. Todas aparecem nos três splits. A auditoria não encontrou
imagens ou labels órfãos nem famílias Kaggle atravessando splits.

## Treinamento e registro

O detector registrado é um YOLOv8n em
`models/threatlens-hybrid-v2/weights/best.pt`. A etapa final utilizou replay balanceado
de 55 diagramas Kaggle e 55 diagramas da fonte anterior, validação balanceada de 9 + 9
imagens, resolução 640 e AdamW. O hash SHA-256 registrado do peso é
`2aebcd0611927505d60a10d23ce11d0e5211cf2e91ca0c4394921fac006c865d`.

## Métricas reais do detector

No teste híbrido de 39 imagens:

| Métrica | Valor |
| --- | ---: |
| Precisão | 0,9297 |
| Recall | 0,8417 |
| mAP50 | 0,9009 |
| mAP50-95 | 0,8666 |

Na fatia de 9 diagramas Kaggle, o modelo final alcançou mAP50 0,3598 e recall 0,3951.
Essa fatia é pequena e é tratada como alarme de domain shift, não como prova de cobertura
universal.

## Prevenção de vazamento

- A unidade de agrupamento Kaggle é a arquitetura original, não a imagem aumentada.
- Variantes da mesma arquitetura não cruzam treino, validação e teste.
- O replay usa manifestos explícitos e mantém o teste híbrido inalterado.
- Os holdouts end-to-end não foram executados durante `DELIVERY-001`.

## Limitações

O dataset é pequeno, contém uma fração relevante de diagramas gerados e cobre apenas 14
classes canônicas. Ícones desconhecidos, novos estilos visuais, texto pequeno e diagramas
densamente conectados podem reduzir o desempenho. As métricas do detector não medem a
qualidade dos fluxos ou do relatório STRIDE.

Evidências detalhadas: `docs/dataset-integration-results.md`,
`docs/model-evaluation-and-registration.md` e
`models/threatlens-hybrid-v2/model-card.json`.
