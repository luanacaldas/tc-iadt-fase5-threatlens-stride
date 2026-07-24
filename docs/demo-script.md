# Roteiro para vídeo de apresentação

**Duração alvo:** 13 a 15 minutos  
**URL local:** `http://127.0.0.1:4173/`

## Regra de apresentação

Não explicar conceitos básicos de STRIDE ou de diagramas de arquitetura. O vídeo deve
mostrar como o desafio foi resolvido, quais decisões técnicas foram tomadas, quais
evidências sustentam o MVP e como o sistema se comporta quando não pode confiar na entrada.

## 1. Introdução e arquitetura — 0:00 a 1:30

### Fala sugerida

> “Este é o ThreatLens AI, um MVP para automatizar a modelagem de ameaças a partir de
> diagramas de arquitetura. A principal decisão foi não solicitar a uma IA generativa que
> interpretasse a imagem e criasse um relatório diretamente. Construímos uma pipeline
> rastreável: detecção supervisionada, OCR, reconstrução de fluxos, validação estrutural,
> motor STRIDE e recuperação local de contramedidas.”

### Mostrar na tela

- página inicial com versão, status do backend e estratégia ativa;
- fluxo resumido imagem → YOLO → OpenCV/OCR → grafo → STRIDE → relatório;
- execução local e estratégia `legacy` como padrão.

## 2. Diferenciais e decisões técnicas — 1:30 a 6:00

### 2.1 Modelo supervisionado — 1:30 a 2:30

> “O requisito pedia um modelo supervisionado. Treinamos e registramos um YOLOv8n com 14
> classes arquiteturais. O dataset final possui 373 imagens e 3.048 objetos anotados,
> combinando dados do projeto com arquiteturas independentes selecionadas do dataset
> público do Kaggle.”

Mostrar:

- as 14 classes canônicas;
- precisão 0,9297, recall 0,8417, mAP@50 0,9009 e mAP@50-95 0,8666;
- peso registrado e manifesto de reprodutibilidade.

### 2.2 Dataset e prevenção de leakage — 2:30 a 3:15

> “O dataset Kaggle possui muitas augmentations da mesma arquitetura. Para evitar que
> variações do mesmo desenho aparecessem em treino e teste, agrupamos os arquivos pela
> arquitetura original e mantivemos apenas uma variante por grupo selecionado.”

Mostrar a divisão 265/69/39 e mencionar que as anotações Pascal VOC foram convertidas para
YOLO e mapeadas para a taxonomia canônica.

### 2.3 OCR e estrutura — 3:15 a 4:30

> “O YOLO identifica componentes. OCR e OpenCV extraem labels, providers, protocolos,
> linhas e zonas. Quando OCR e detector discordam, preservamos a hipótese alternativa para
> revisão, mas ela não participa do grafo, do STRIDE nem do risco.”

Mostrar:

- bounding boxes sobre a imagem;
- tabela de componentes e fluxos;
- confiança e `detectionAlternatives`;
- protocolo ou direção com evidência explícita.

### 2.4 Reconstrução junction-aware — 4:30 a 5:15

> “Diagramas densos exigiram tratamento de cotovelos, cruzamentos, bifurcações, troncos
> compartilhados e linhas estruturais. Mantivemos a versão legada como padrão e integramos
> a estratégia junction-aware de forma selecionável e reversível.”

Apresentar somente os números necessários: 52 fluxos corretos preservados, falsos fluxos
reduzidos de 90 para 75 e recall mantido em 0,7324 no desenvolvimento.

### 2.5 Quality gate — 5:15 a 6:00

> “Também adicionamos uma barreira antes do STRIDE. Se a imagem contiver múltiplos
> diagramas, duplicações, agrupamentos classificados como componentes, provider
> inconsistente ou self-loop sem evidência, o sistema bloqueia risco e relatório.”

Não demonstrar ainda; apenas antecipar que esse comportamento será mostrado após o cenário
principal.

## 3. Demonstração prática — 6:00 a 12:00

## 3.1 Cenário válido — 6:00 a 10:30

Usar `data/sample-diagrams/02-mixed-components.jpg` ou o exemplo **Componentes mistos**.

### Passos

1. selecionar a imagem e mostrar o preview;
2. destacar que o arquivo só é enviado após clicar em **Analisar arquitetura**;
3. iniciar a análise;
4. mostrar o status de qualidade retornado;
5. mostrar a imagem com bounding boxes;
6. percorrer componentes, tipos, providers e confiança;
7. mostrar fluxos, direção, protocolo e itens pendentes de revisão;
8. abrir ameaças agrupadas por STRIDE;
9. selecionar uma ameaça e relacionar ativo, evidência e contramedidas;
10. mostrar referências e risco antes/depois da mitigação;
11. abrir **Detalhes da análise** e mostrar ID, versão e estratégia;
12. demonstrar download JSON e opção de PDF.

### Fala sugerida

> “O relatório não é apenas uma lista genérica. Cada finding aponta o ativo ou fluxo
> relacionado, a evidência utilizada, a regra aplicada e as contramedidas recomendadas.”

## 3.2 Cenário fail-closed — 10:30 a 12:00

Usar `E:\teste_aws.png`, que contém dois diagramas comparativos na mesma imagem.

### Passos

1. enviar a imagem comparativa;
2. mostrar o status **Análise estrutural rejeitada**;
3. destacar as duplicações, painéis alinhados, agrupamentos, provider inconsistente e
   self-loop bloqueado;
4. mostrar 5 componentes detectados, 0 fluxos aceitos e 0 ameaças;
5. mostrar **Risco não calculado** e PDF desabilitado;
6. reforçar que o JSON permanece disponível para diagnóstico.

### Fala sugerida

> “Neste caso, entregar um relatório seria tecnicamente incorreto. A pipeline detecta que
> a reconstrução não representa uma arquitetura única e interrompe STRIDE, RAG, risco e
> relatório. Esse comportamento evita que uma saída visualmente convincente seja tratada
> como uma conclusão de segurança.”

## 4. Gargalos superados e conclusão — 12:00 a 14:00

### Fala sugerida

> “O principal gargalo não era apenas reconhecer ícones. Era impedir que uma detecção
> visual imperfeita se transformasse automaticamente em uma conclusão de segurança. Por
> isso separamos detector, estrutura, quality gate, revisão, STRIDE e relatório.”

> “Na baseline v15 de desenvolvimento, preservamos F1 0,5296, precisão 0,4343, recall
> 0,6786, 152 ameaças corretas e 198 extras. O projeto possui 350 testes aprovados, gate de
> regressão, cadeia prospectiva hash-selada e verificador global em estado PASS.”

> “Como próximos passos, ampliaríamos o benchmark real, aplicaríamos active learning nos
> falsos positivos recorrentes e treinaríamos um classificador específico de existência de
> arestas. O MVP já demonstra a viabilidade da funcionalidade: transformar uma imagem em
> uma arquitetura estruturada e em uma modelagem STRIDE rastreável.”

## 5. Encerramento — 14:00 a 14:30

Manter na tela:

```text
ThreatLens AI
Imagem -> Arquitetura estruturada -> STRIDE rastreável -> Contramedidas
```

Finalizar sem reexplicar STRIDE e sem abrir novos benchmarks.

## Contingência da gravação

- iniciar `npm.cmd run dev` antes de gravar;
- confirmar `http://127.0.0.1:4173/api/health`;
- usar o exemplo **Componentes mistos** no cenário principal;
- não executar `blind_holdout` ou `prospective_holdout` durante a apresentação;
- se o backend falhar, reiniciar o serviço e manter o roteiro em um exemplo local;
- não substituir a análise real por um JSON estático sem declarar a contingência;
- manter uma gravação de backup da demonstração válida e da rejeição fail-closed.
