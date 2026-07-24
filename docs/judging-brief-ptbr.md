# ThreatLens AI - Briefing para a Banca

## Tese Central

O ThreatLens não pede que uma LLM adivinhe ameaças olhando uma imagem. Ele transforma o
diagrama em evidência estruturada, exige confirmação humana para inferências incertas e somente
então executa regras STRIDE e recuperação de conhecimento local.

Essa separação permite medir, explicar e corrigir cada etapa do processo.

## Abertura Recomendada

"Diagramas de arquitetura concentram decisões críticas de segurança, mas a modelagem de
ameaças costuma ser manual, tardia e difícil de repetir. O ThreatLens transforma uma imagem em
um grafo revisável e produz um relatório STRIDE em que cada conclusão aponta para a regra e a
evidência que a originaram."

## A Demonstração em Cinco Atos

1. **Imagem para componentes:** envie um diagrama reservado e mostre boxes, classes e confiança
   do detector supervisionado.
2. **Imagem para grafo:** mostre linhas, direção visual, OCR de protocolo e zonas candidatas.
3. **Humano no controle:** corrija um componente, confirme membros de uma fronteira e observe os
   cruzamentos serem recalculados.
4. **Grafo para STRIDE:** gere o relatório e abra `Ver rastreabilidade` em uma ameaça para mostrar
   regra, componentes, fluxo, fronteira e fonte RAG.
5. **Resultado utilizável:** mostre o painel técnico, o relatório executivo e as exportações JSON,
   Markdown e PDF com `analysisId` e `requestId`.

## Evidências Quantitativas

| Camada | Evidência atual |
| --- | --- |
| Detector híbrido | mAP50 0,9009 no teste híbrido; mAP50 0,3598 na fatia Kaggle real |
| Estrutura controlada | F1 de adjacência 0,8772; F1 direcionado 0,6216 |
| Estrutura real manual | F1 de adjacência 0,8163; F1 direcionado 0,7755 |
| Fronteiras reais | F1 de associação por membros 0,2857 |
| Protocolos reais | F1 de OCR + associação 0,8000 |
| Regras STRIDE | 7/7 regras cobertas; 6/6 cenários com correspondência exata |
| Ponta a ponta cego v12 | F1 0,3457; recall tipado 0,4225 em primeira execução selada |
| Desenvolvimento v12 | F1 0,4723; recall tipado 0,5926 |
| Desenvolvimento v13 | F1 0,5033; recall tipado 0,6176 |
| Desenvolvimento v15 | F1 0,5296; precisao 0,4343; recall tipado 0,6176 |
| Junction-aware controlado, desenvolvimento | 52 corretos; 75 falsos; 19 ausentes; recall 0,7324; F1 0,5253 |
| Proteção de recall | 0 verdadeiros positivos bloqueados; controles C01-C07 aprovados |
| Engenharia | 350 testes automatizados aprovados; verificador global PASS |

Os 85 testes citados em artefatos da TL-001 formam a baseline histórica. O total de 350 corresponde
à suíte consolidada atual, após preservação de alternativas, diagnóstico de fluxos, junction-aware,
interface web e quality gate.

## Como Explicar os Números Menores

"O benchmark controlado mede o algoritmo quando o desenho segue um padrão conhecido. A amostra
real mede fontes, escalas, linhas longas e ruído de diagramas encontrados no dataset. A diferença
entre os dois números identifica exatamente onde investir: associação em grafos densos e
detecção de fronteiras. Não escondemos essa diferença porque o human-in-the-loop existe para
controlar esse risco no MVP."

## Diferenciais que Merecem Ênfase

- Modelo supervisionado treinado e registrado com hash, thresholds e gates de qualidade.
- Dataset real integrado com separação por grupo para evitar vazamento entre treino e teste.
- Benchmark manual independente das anotações ruidosas do dataset.
- Protocolos nunca inventados: ficam `unknown` sem evidência explícita.
- Direção visual com score de arrowhead e fallback rastreável.
- Fronteiras editáveis e reconciliação autoritativa no backend.
- STRIDE determinístico com RAG local, funcionando sem API paga.
- Rastreabilidade por ameaça e auditoria preservada nas exportações.
- Duas visualizações além do JSON: dashboard técnico e relatório executivo/PDF.
- Quality gate fail-closed: entradas compostas ou estruturalmente incoerentes não recebem um
  relatório de ameaças com aparência de confiabilidade.

## Perguntas Difíceis

**A IA detecta ameaças diretamente?**

Não. O modelo supervisionado detecta componentes. Ameaças são derivadas do grafo revisado por
regras STRIDE auditáveis, enriquecidas por RAG local.

**Por que não usar apenas uma LLM multimodal?**

Porque isso dificultaria medir cada etapa e poderia inventar componentes, protocolos ou
controles. A LLM é opcional para redação; o relatório base independe dela.

**O resultado é totalmente automático?**

O sistema automatiza detecção e análise, mas exige revisão para inferências geométricas e baixa
confiança. Essa é uma decisão de segurança, não uma limitação escondida.

**Por que o resultado real é menor?**

Diagramas reais têm estilos e topologias muito mais variados. O benchmark revela esse domain
shift e fornece uma linha de base concreta para active learning e novas anotações.

## Fechamento Recomendado

"O MVP demonstra viabilidade técnica sem depender de serviços pagos: ele reconhece, estrutura,
revisa, modela e exporta. Mais importante, sabe mostrar de onde veio cada conclusão e onde ainda
precisa de confirmação humana."
