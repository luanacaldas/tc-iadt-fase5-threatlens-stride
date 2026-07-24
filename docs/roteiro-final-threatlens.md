# ThreatLens AI — Roteiro de Leitura para o Vídeo

**Duração alvo: 14–15 min | Formato: texto para ler em voz alta**

> Como usar este documento: o texto normal é para você **falar exatamente como está escrito**
> (foi calibrado para soar natural, com pausas nos lugares certos). Os blocos em `[AÇÃO NA TELA]`
> **não são para ler** — são só lembretes do que fazer no navegador enquanto fala.

---

## [00:00 – 01:30] Abertura

`[AÇÃO NA TELA: logo/slide de título por 3-4s, depois cortar para o diagrama do pipeline]`

[Referência técnica do orquestrador e da API: [backend/main.py#L139](../backend/main.py#L139), [backend/main.py#L168](../backend/main.py#L168), [backend/main.py#L187](../backend/main.py#L187), [backend/main.py#L212](../backend/main.py#L212).]

> Oi, eu sou [seu nome]. O ThreatLens AI resolve um problema bem específico: como
> transformar uma imagem de diagrama de arquitetura numa modelagem de ameaças STRIDE
> que um time de segurança consiga confiar de verdade.
>
> A primeira decisão que tomei foi _não_ fazer o caminho óbvio. Dava pra jogar a
> imagem direto num LLM multimodal e pedir "me dá as ameaças desse diagrama". Rápido de
> implementar... e péssimo de confiar. Sem rastreabilidade, sem controle sobre alucinação,
> sem forma de auditar por que uma ameaça foi gerada.
>
> Então construi uma pipeline com fronteiras bem definidas: detecção supervisionada,
> OCR determinístico, reconstrução de grafo, um quality gate estrutural, e só depois disso
> um motor de regras STRIDE. Cada etapa é testável e auditável isoladamente. E, o mais
> importante: o sistema sabe dizer "não sei" quando a entrada não é confiável.

---

## [01:30 – 05:30] Decisões de engenharia

`[AÇÃO NA TELA: slide com as 14 classes canônicas, depois tabela de métricas do detector]`

[Referência técnica de treino e taxonomia: [dataset/architecture.yaml#L7](../dataset/architecture.yaml#L7), [dataset/architecture.yaml#L11](../dataset/architecture.yaml#L11), [scripts/train_yolo.py#L29](../scripts/train_yolo.py#L29), [scripts/train_yolo.py#L370](../scripts/train_yolo.py#L370), [scripts/train_yolo.py#L394](../scripts/train_yolo.py#L394).]

> Vou passar rápido pelas decisões que mais importam, porque é isso que sustenta a
> confiabilidade do sistema.
>
> Primeiro: por que YOLOv8n? A gente precisava de um detector supervisionado — isso era
> requisito do desafio — com um bom equilíbrio entre precisão e custo computacional,
> rodando sem depender de GPU dedicada. Treinamos com 373 imagens, mais de três mil
> objetos anotados, em 14 classes canônicas, misturando diagramas do próprio projeto com
> uma parte do dataset público do Kaggle.
>
> E aqui teve um detalhe que quase passou despercebido: o Kaggle tinha várias variações
> da mesma arquitetura original. Se a gente não tratasse isso, teria data leakage —
> a mesma arquitetura aparecendo em treino e em teste, inflando artificialmente a métrica.
> Agrupamos por arquitetura original antes de dividir os dados. O resultado é real, sem
> número inflado: precisão de 0,93, recall de 0,84, mAP50 de 0,90.

`[AÇÃO NA TELA: tabela comparando "abordagem ingênua" vs "ThreatLens"]`

[Referência técnica de OCR determinístico: [backend/ocr.py#L1](../backend/ocr.py#L1), [backend/ocr.py#L39](../backend/ocr.py#L39), [backend/ocr.py#L81](../backend/ocr.py#L81), [backend/ocr.py#L169](../backend/ocr.py#L169).]

> Segundo ponto: por que OCR determinístico, e não deixar um modelo generativo decidir o
> texto? Porque um erro de OCR é rastreável e corrigível — eu sei exatamente qual trecho
> da imagem gerou qual leitura. E quando o OCR discorda do que o YOLO detectou, a gente
> não deixa um sobrescrever o outro silenciosamente. A hipótese alternativa fica
> registrada, mas fica de fora do grafo, fora do STRIDE, fora do cálculo de risco. Ela
> existe só pra revisão humana.
>
> E agora o terceiro ponto, que eu considero o verdadeiro diferencial do projeto: o
> Quality Gate. A pergunta que guiou essa decisão foi simples: o que acontece quando o
> diagrama é ambíguo, denso, ou tem duas arquiteturas lado a lado? A resposta ingênua
> seria gerar ameaças do jeito que der. A nossa resposta foi diferente: se a reconstrução
> estrutural não é coerente — duplicação suspeita, provider inconsistente, self-loop sem
> evidência — o sistema bloqueia _antes_ de chegar no STRIDE. Fail-closed. Eu prefiro não
> entregar relatório nenhum a entregar um relatório enganoso.

`[AÇÃO NA TELA: tabela reliable / review_required / rejected]`

[Referência técnica do quality gate fail-closed: [backend/analysis_quality.py#L58](../backend/analysis_quality.py#L58), [backend/analysis_quality.py#L151](../backend/analysis_quality.py#L151), [backend/analysis_quality.py#L157](../backend/analysis_quality.py#L157), [backend/analysis_quality.py#L160](../backend/analysis_quality.py#L160), [backend/main.py#L194](../backend/main.py#L194), [backend/main.py#L349](../backend/main.py#L349).]

---

## [05:30 – 12:00] Demonstração ao vivo

[Referência técnica do STRIDE, mitigação e rastreabilidade: [backend/stride_engine.py#L30](../backend/stride_engine.py#L30), [backend/stride_engine.py#L71](../backend/stride_engine.py#L71), [backend/stride_engine.py#L601](../backend/stride_engine.py#L601), [backend/stride_engine.py#L885](../backend/stride_engine.py#L885), [backend/pdf_report.py#L33](../backend/pdf_report.py#L33), [backend/pdf_report.py#L114](../backend/pdf_report.py#L114).]

### Caso válido (05:30 – 08:30)

`[AÇÃO: upload de 02-mixed-components.jpg, clicar em "Analisar arquitetura"]`

> Vou mostrar agora o sistema funcionando de verdade. Vou subir aqui um diagrama com
> componentes mistos — API, banco, fila, WAF — e clicar em analisar.
>
> Enquanto processa: primeiro roda a detecção do YOLO, depois o OCR, depois a
> reconstrução de fluxo via OpenCV, e o quality gate valida tudo isso antes de eu ver
> qualquer ameaça na tela.

`[AÇÃO: mostrar status "reliable" + bounding boxes + tabela de componentes]`

> Prontinho. Status "reliable", com o score de qualidade aqui. Reparem nos componentes
> detectados: cada um com o tipo, o provider, e a confiança calibrada. Esse WAF, por
> exemplo, foi detectado com 92% de confiança.

`[AÇÃO: mostrar tabela de fluxos]`

> Aqui embaixo, os fluxos reconstruídos: direção, protocolo, e o que ainda está pendente
> de revisão porque a confiança veio mais baixa.

`[AÇÃO: expandir 2 ameaças, uma Critical e uma High]`

> Agora o que interessa: as ameaças. Vou abrir essa aqui, de exposição de dados no banco.
> Reparem que não é uma ameaça genérica — ela aponta o componente exato que gerou o
> alerta, a evidência que sustentou essa conclusão, as contramedidas recomendadas, e as
> referências técnicas: CWE, OWASP, MITRE ATT&CK.

`[AÇÃO: mostrar matriz de risco inerente vs residual, depois gerar e abrir o PDF]`

> E aqui a matriz de risco: inerente e residual, mostrando o quanto as contramedidas
> reduzem a exposição. E, pra fechar esse caso, gero o PDF — relatório completo, pronto
> pra ser enviado pro time de segurança.

### Caso fail-closed (08:30 – 12:00)

`[AÇÃO: upload do diagrama comparativo/duplicado]`

> E agora o momento que eu mais quero mostrar. Esse diagrama aqui tem duas arquiteturas
> lado a lado, praticamente idênticas — um cenário clássico de diagrama comparativo.
> Vou subir e analisar.

`[AÇÃO: mostrar status "rejected" com os motivos listados]`

> E aqui está: o quality gate pegou. Componentes duplicados espacialmente alinhados,
> provider inconsistente entre o que o YOLO detectou e o que o OCR leu, self-loop sem
> confirmação. O sistema não tentou adivinhar.
>
> Zero ameaças geradas. Zero risco calculado. PDF desabilitado. O JSON de diagnóstico
> continua disponível, porque eu quero que o especialista veja exatamente por que foi
> rejeitado — mas ninguém recebe um relatório de segurança fabricado em cima de uma
> leitura ambígua.
>
> Pra mim, esse comportamento é a diferença entre uma demo bonita e um sistema que eu
> confiaria em produção.

---

## [12:00 – 13:45] Limitações, com honestidade

`[AÇÃO: slide com as limitações documentadas]`

[Referência de limitações e benchmarks: [final-technical-evidence.md#L125](final-technical-evidence.md#L125), [final-technical-evidence.md#L126](final-technical-evidence.md#L126), [final-technical-evidence.md#L127](final-technical-evidence.md#L127), [model-development.md#L55](model-development.md#L55), [model-development.md#L69](model-development.md#L69).]

> Rapidinho, com transparência total. Em benchmark real — não no recorte de teste do
> detector, no diagrama completo mesmo — a estrutura de fluxos fica com F1 na casa de
> 0,53. Não é perfeito, e eu não vou apresentar isso como se fosse.
>
> Diagrama muito denso ainda gera fluxo fantasma ou fluxo perdido. A taxonomia cobre 14
> classes, então um componente exótico vira uma aproximação. Texto pequeno ou rotacionado
> derruba o OCR.
>
> A resposta de engenharia pra isso não foi esconder o pior caso pra melhorar o número —
> foi o quality gate, e um mecanismo de abstenção: confiança abaixo de 0,90 não vira
> ameaça sozinha, ela vai pra revisão. O sistema é assistência técnica que conhece os
> próprios limites. Não é uma caixa preta fingindo certeza.

---

## [13:45 – 15:00] Encerramento

`[AÇÃO: tela final com o fluxo resumido]`

> Resumindo numa frase: o ThreatLens não tenta substituir o especialista de segurança.
> Ele automatiza o trabalho repetitivo de leitura de diagrama e a primeira triagem de
> ameaças — e sabe a hora de parar e pedir ajuda humana.
>
> Como próximos passos: mais dados reais de diagramas de cliente, um classificador
> dedicado pra existência de aresta, e integração com ferramentas de gestão de risco,
> tipo Jira ou Azure DevOps.
>
> Código aberto, documentação completa, pipeline reprodutível com hash de cada artefato.
> Obrigado por acompanhar — fico à disposição pra perguntas técnicas.

`[TELA FINAL, sem falar mais nada:]`

```
ThreatLens AI
Imagem → Arquitetura estruturada → STRIDE rastreável → Contramedidas
```

---

## Notas rápidas de ritmo (não ler em voz alta)

- Frases curtas propositalmente — respire nas vírgulas e pausas de reticências.
- As palavras em itálico/negrito no texto marcam onde naturalmente cai ênfase de voz.
- Se travar em algum trecho, pare, respire, e recomece a frase — é mais fácil cortar no
  editor do que tentar continuar uma frase capenga.
- Tempo total de fala (sem contar ações na tela) gira em torno de 11–12 min; os 3 min
  restantes são preenchidos naturalmente pelas ações/esperas na demo.
