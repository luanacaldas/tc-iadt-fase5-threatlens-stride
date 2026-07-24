# ThreatLens AI - roteiro consolidado do vídeo

**Duração alvo:** 14 a 15 minutos  
**Formato:** slides + demonstração gravada  
**Objetivo:** demonstrar como o desafio foi resolvido, quais decisões tornam o resultado auditável
e onde o MVP deliberadamente exige revisão humana.

Os blocos marcados como **Tela** são instruções de gravação e não devem ser lidos.

## 00:00-00:30 - Abertura

**Tela:** slide 1, capa.

> Olá, eu sou Luana Caldas e este é o ThreatLens AI, um MVP que transforma uma imagem de
> arquitetura de software em uma modelagem de ameaças STRIDE rastreável.
>
> O problema não era apenas reconhecer ícones. Era reconstruir evidências suficientes para gerar
> uma análise de segurança sem transformar incerteza visual em uma conclusão convincente, mas errada.

## 00:30-01:35 - Arquitetura da solução

**Tela:** slide 2, arquitetura.

> Por isso, eu não enviei a imagem diretamente para uma LLM multimodal pedindo ameaças.
>
> A pipeline separa responsabilidades. O detector YOLOv8n identifica componentes. OCR e OpenCV
> extraem rótulos, protocolos e conectores. A reconstrução estrutural transforma essas evidências
> em componentes e fluxos. Antes do STRIDE, um quality gate verifica se essa arquitetura é coerente.
>
> Quando a análise é confiável ou revisável, o motor STRIDE aplica regras determinísticas e recupera
> contramedidas de uma base local. Quando a estrutura é inconsistente, o relatório é bloqueado.
> Assim, cada etapa pode ser medida, testada e auditada separadamente.

## 01:35-03:15 - Escolha e governança do dataset

### 01:35-02:10 - Composição híbrida

**Tela:** slide 3, dataset híbrido.

> O modelo supervisionado foi treinado com um dataset híbrido. Mantive 300 diagramas complementares
> do projeto porque eles cobriam classes pouco representadas no Kaggle, como usuário, internet, WAF
> e backup. A segunda fonte trouxe 73 arquiteturas multicloud selecionadas do Kaggle, com exemplos
> de AWS, Azure e GCP.
>
> A composição final ficou com 373 imagens, 3.048 objetos anotados e 14 classes canônicas.

### 02:10-02:45 - Split sem vazamento

**Tela:** slide 4, split.

> O Kaggle possuía várias augmentations de uma mesma arquitetura. Se uma variante fosse para treino
> e outra para teste, a métrica seria artificialmente otimista. Por isso, a unidade do split foi a
> família arquitetural original, e não o arquivo aumentado.
>
> O resultado foi 265 imagens de treino, 69 de validação e 39 de teste, com zero grupos Kaggle
> atravessando os splits.

### 02:45-03:15 - Replay balanceado

**Tela:** slide 5, replay.

> Na adaptação final, usei replay balanceado: 55 imagens Kaggle e 55 da fonte anterior no treino,
> mais nove de cada fonte na validação. Isso reduziu o risco de o modelo aprender o novo domínio e
> esquecer padrões úteis das classes complementares.

## 03:15-05:10 - Decisões e diferenciais

### 03:15-04:00 - Três decisões de confiança

**Tela:** slide 6, decisões de engenharia.

> Três decisões orientaram o projeto. Primeiro, YOLOv8n pelo equilíbrio entre detecção supervisionada,
> custo computacional e execução local. Segundo, OCR determinístico: uma leitura incorreta continua
> ligada à sua região da imagem e pode ser revisada.
>
> Quando OCR e detector discordam, a hipótese alternativa é preservada em `detectionAlternatives`,
> mas não entra no grafo, não gera ameaça e não afeta o risco. Terceiro, o quality gate: se a
> reconstrução não sustenta uma análise segura, o sistema para antes do STRIDE.

### 04:00-05:10 - Diferenciais consolidados

**Tela:** slide 7, diferenciais.

> Esses princípios aparecem em cinco diferenciais. Dados com proveniência e controle de vazamento.
> OCR rastreável. Reconstrução junction-aware experimental para cruzamentos, cotovelos e troncos
> compartilhados. Quality gate fail-closed. E um motor STRIDE determinístico, em que cada ameaça
> aponta para componentes, fluxos, regra, contramedidas e referências como CWE, CAPEC, OWASP e
> MITRE ATT&CK.
>
> A estratégia junction-aware não substituiu silenciosamente a implementação anterior. Ela é
> selecionável, reversível e validada apenas no conjunto de desenvolvimento; `legacy` permanece o
> padrão.

## 05:10-08:35 - Demonstração do caso válido

**Tela:** trocar dos slides para `http://127.0.0.1:4173`. Selecionar
`data/sample-diagrams/02-mixed-components.jpg`.

> Agora eu vou mostrar o fluxo completo. Seleciono um diagrama com componentes mistos e inicio a
> análise. O backend executa detector, OCR, reconstrução e quality gate antes de produzir ameaças.

**Tela:** mostrar preview, status de qualidade, componentes e boxes.

> O resultado apresenta o status de qualidade e os motivos associados. Cada componente mantém tipo,
> provider, confiança e bounding box. As alternativas de detecção ficam separadas para revisão e
> não contaminam o grafo.

**Tela:** mostrar tabela de fluxos e uma ameaça expandida.

> Nos fluxos, eu consigo revisar origem, destino, direção e protocolo. Na ameaça expandida, a
> rastreabilidade mostra exatamente qual componente ou fluxo acionou a regra. A recomendação não é
> apenas texto: ela inclui contramedida e referências técnicas verificáveis.

**Tela:** mostrar risco inerente e residual; exportar JSON e PDF.

> Depois das decisões de tratamento, o painel compara risco inerente e residual. A análise pode ser
> exportada em JSON, Markdown e PDF para públicos técnicos e executivos.

## 08:35-11:10 - Demonstração fail-closed

**Tela:** analisar `E:\teste_aws.png`. Se o arquivo não estiver disponível, abrir
`data/results/mvp-hardening-001/external-image-quality.json`.

> O segundo caso é intencionalmente problemático. Esta imagem contém dois cenários comparativos e
> não deveria ser interpretada como uma única arquitetura.

**Tela:** mostrar `analysisQuality.status = rejected`, razões e ação recomendada.

> O quality gate identifica sinais como múltiplos painéis, duplicações suspeitas, inconsistência de
> provider, agrupamentos tratados como componentes ou self-loop sem evidência explícita.
>
> O comportamento mais importante está aqui: ameaças, risco, contramedidas e PDF são suprimidos.
> O JSON diagnóstico permanece disponível para explicar a rejeição, mas o sistema não entrega um
> relatório com aparência de certeza sobre uma estrutura incoerente.
>
> Este fail-closed é um diferencial de segurança: o sistema sabe quando não deve concluir.

## 11:10-12:15 - Evidências quantitativas

**Tela:** novo slide 8, evidências.

> No teste híbrido do detector, a precisão foi 0,9297, o recall 0,8417 e o mAP50 0,9009.
>
> Na avaliação ponta a ponta v15, restrita ao `development_tuning`, o F1 de ameaças foi 0,5296,
> com recall 0,6786, 152 ameaças corretas e 198 extras. Esses números são evidência de
> desenvolvimento, não uma nova avaliação cega.
>
> Na configuração junction-aware controlada, também em desenvolvimento, foram 52 conexões corretas,
> 75 falsas e 19 ausentes, com recall 0,7324 e acurácia de direção 0,8654. Os controles C01 a C07
> passaram sem bloquear verdadeiros positivos.

## 12:15-13:25 - Limitações e proteções

**Tela:** novo slide 9, limitações.

> O MVP ainda tem limitações importantes. Diagramas densos podem produzir fluxos extras ou ausentes.
> Arrowheads pequenos reduzem a confiança da direção. Componentes fora das 14 classes exigem
> aproximação ou revisão. Texto pequeno ou rotacionado ainda prejudica o OCR.
>
> Em vez de esconder esses casos, a solução combina três proteções: abstém quando a evidência é
> insuficiente, envia hipóteses para revisão humana e rejeita reconstruções estruturalmente
> incoerentes. O ThreatLens apoia a modelagem de ameaças; ele não substitui pentest, revisão de
> configuração cloud ou validação de controles em produção.

## 13:25-14:35 - Encerramento

**Tela:** novo slide 10, encerramento.

> Em resumo, o ThreatLens demonstra a viabilidade de automatizar a primeira camada da modelagem de
> ameaças sem transformar a IA em uma caixa preta.
>
> O supervisionado reconhece componentes. A reconstrução cria um grafo revisável. O quality gate
> decide se existe base estrutural para continuar. O STRIDE gera ameaças e contramedidas rastreáveis.
>
> Como próximos passos, eu ampliaria a diversidade de diagramas reais, faria dupla anotação humana
> dos benchmarks e treinaria modelos específicos para existência e direção de arestas.
>
> O resultado é um MVP local, reprodutível e honesto sobre seus limites: ele automatiza onde há
> evidência e pede revisão onde ainda existe incerteza. Obrigada.

## 14:35-15:00 - Margem de segurança

Use estes segundos para espera de inferência, transição entre telas ou uma pausa natural. Não acrescente
novas alegações para preencher o tempo.

## Alegações removidas dos roteiros anteriores

As frases abaixo não devem aparecer no vídeo porque não possuem evidência registrada suficiente ou
contradizem o estágio do projeto:

- "automatiza 80% do trabalho";
- "modelagem dez vezes mais rápida";
- "processa mais de cem diagramas por dia";
- "pronto para produção";
- "componentes corretos 86%, extras 14%";
- frontend em React ou Vue;
- qualquer métrica de desenvolvimento apresentada como generalização ou resultado cego.
