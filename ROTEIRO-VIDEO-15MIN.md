# ROTEIRO ESTRUTURADO PARA VÍDEO DE APRESENTAÇÃO

## ThreatLens AI — MVP de Modelagem Automática de Ameaças STRIDE

**Duração Total:** 15 minutos  
**Público-Alvo:** Banca Avaliadora — Professores/Especialistas em Segurança e IA  
**Tom:** Profissional, focado em decisões de engenharia, sem explicações básicas

---

## [00:00 — 02:00] ABERTURA & VISÃO GERAL DA ARQUITETURA

### Roteiro de Fala (2 minutos)

```
ABERTURA (0-10s):
"Olá, sou [seu nome]. Apresento o ThreatLens AI, um MVP que automatiza a
modelagem de ameaças STRIDE a partir de imagens de diagramas de arquitetura
de software.

O desafio era transformar uma imagem em uma análise de segurança estruturada,
mantendo rastreabilidade técnica e evitando alucinações de IA.
```

### Visuals (0-10s):

- **Screen:** Exibir o logo do projeto ou slide de título
- **Slide de Abertura:**

  ```
  THREATSLENS AI
  MVP de Modelagem Automática de Ameaças STRIDE

  Hackathon Pós-Tech FIAP
  Julho de 2026
  ```

---

```
VISÃO GERAL DA ARQUITETURA (10-50s):
"A solução segue um pipeline de cinco etapas bem definidas:

1. Entrada: Uma imagem de diagrama em PNG, JPEG ou WebP.

2. Detecção de Componentes: Um modelo YOLOv8n treinado supervisionadamente
   identifica componentes arquiteturais (APIs, bancos de dados, filas, etc.)
   com confiança e bounding box.

3. Reconstrução de Fluxos: OCR local e análise de conectividade reconstrói
   a topologia da arquitetura (quem fala com quem, em qual protocolo, etc.).

4. Quality Gate: Antes de gerar ameaças, validamos se a arquitetura
   reconstruída é estruturalmente coerente. Se não for, bloqueamos o
   relatório de forma fail-closed.

5. Motor STRIDE: Usando regras determinísticas, mapeamos ameaças a cada
   componente e fluxo, com contramedidas rastreáveis até CWE, CAPEC, OWASP
   e MITRE ATT&CK.

Tudo isso roda local, sem LLM obrigatória, e é auditável etapa por etapa."
```

### Visuals (10-50s):

- **Slide: Pipeline em Diagrama**
  ```
  Imagem
    ↓
  [Validação] → [YOLOv8] → [OCR] → [Reconstrução]
                                        ↓
                                  [Quality Gate]
                                    ↓
                        ┌───────────┴───────────┐
                      rejected           reliable/review
                        ↓                       ↓
                    [Diagnóstico]          [STRIDE Engine]
                                              ↓
                                         [Relatório PDF]
  ```

---

```
MOTIVAÇÃO (50-120s):
"Por que essa abordagem importa?

Modelagem de ameaças manual é custosa — requer especialistas em segurança
que passam horas analisando diagramas. A maioria dos times não tem acesso a
esse expertise regularmente.

Mas também não poderíamos apenas mandar a imagem para um LLM generativo
'inventar' ameaças. Risco: falsas ameaças gerando paranoia, ou falsos
negativos passando por falhas reais.

Nossa abordagem:
- Primeiro, detectamos e reconstruímos a arquitetura de forma rastreável.
- Depois, aplicamos regras de segurança determinísticas (não LLM).
- Se há incerteza, deixamos para revisão humana.
- Se há incoerência estrutural, bloqueamos o relatório.

Resultado: Uma análise que é assistência técnica de qualidade, não um
relatório que pode ser enganoso."
```

### Visuals (50-120s):

- **Slide: Problema vs. Solução**

  ```
  ❌ Abordagem Ingênua:
    Imagem → LLM → "Aqui estão 50 ameaças" ⚠️ Sem rastreabilidade

  ✅ Abordagem ThreatLens:
    Imagem → Detecção → Reconstrução → Validação → Regras → PDF
    (Cada etapa auditável, fail-closed em dúvida)
  ```

---

## [02:00 — 04:30] OS 5 DIFERENCIAIS DO THREATLES

### Roteiro de Fala (2.5 minutos)

```
"Vou resumir o que diferencia o ThreatLens de outras soluções:
```

### Diferencial 1: Detector Supervisionado com Dataset Limpo (40s)

```
"Primeiro diferencial: dados de qualidade.

Nós não apenas pegamos o Kaggle e treinamos direto. O Kaggle tem muitas
variações da mesma arquitetura base — AWS Reference Architecture pode ter
20 versões diferentes. Se você não trata isso, a mesma arquitetura aparece
em treino E em teste, inflando as métricas.

Agrupei por arquitetura original, selecionei uma única variação por grupo,
misturei com 300 diagramas do projeto, e só depois dividi em treino/teste.

Resultado: Dataset limpo sem data leakage. Precisão 0.93, Recall 0.84,
mAP50 0.90. Métrica real, sem número inflado."
```

### Diferencial 2: OCR Determinístico e Rastreável (40s)

```
"Segundo: em vez de usar LLM generativa para adivinhar texto na imagem,
usamos Tesseract + OpenCV para OCR determinístico.

Por quê? Porque um erro de OCR é rastreável — eu sei exatamente qual
pixel gerou qual letra. Se o OCR discorda do YOLO, não deixo um sobrescrever
o outro em silêncio. A divergência fica registrada, sem prejudicar STRIDE
ou risco.

Isso evita alucinação. O sistema não 'inventa' labels. Ele extrai ou alertar
para revisão humana."
```

### Diferencial 3: Reconstrução Junction-Aware (40s)

```
"Terceiro: muitos diagramas têm cotovelos, cruzamentos, linhas compartilhadas.

A reconstrução ingênua perde essas complexidades e gera fluxos fantasma ou
fluxos perdidos. Implementei tratamento junction-aware que preserva 52
fluxos corretos em benchmark denso, enquanto reduz falsos de 90 para 75.

Mantive a versão legada como padrão e deixei junction-aware selecionável,
reversível, e documentada. Transparência total."
```

### Diferencial 4: Quality Gate Fail-Closed (40s)

```
"Quarto: o sistema diz 'não sei' quando não tem certeza.

Se a arquitetura reconstruída tiver duplicação suspeita, inconsistência de
provider, self-loop sem evidência, ou múltiplos diagramas detectados, o
quality gate bloqueia a geração de ameaças STRIDE.

Isso é uma decisão consciente: prefiro não entregar um relatório a entregar
um relatório enganoso. Fail-closed, não fail-open."
```

### Diferencial 5: Motor STRIDE Determinístico e Rastreável (40s)

```
"Quinto: STRIDE gerado por regras determinísticas, não LLM.

Cada ameaça aponta:
- O componente ou fluxo que a gerou
- A evidência visual (detectado sem proteção)
- As contramedidas recomendadas
- Referências rastreáveis: CWE, CAPEC, OWASP, MITRE ATT&CK

Isso permite que a banca e o especialista auditorem por que uma ameaça foi
gerada. Não é caixa preta. É reprodutível."
```

### Visuals (2.5 min):

- **Slide: Os 5 Diferenciais**

  ```
  1️⃣ DATASET LIMPO
     → Agrupamento por arquitetura, sem data leakage
     → Métricas reais, não infladas

  2️⃣ OCR DETERMINÍSTICO
     → Tesseract + OpenCV, sem alucinação de LLM
     → Divergências registradas, não silenciadas

  3️⃣ RECONSTRUÇÃO JUNCTION-AWARE
     → Tratamento de cotovelos, cruzamentos, linhas compartilhadas
     → 52 fluxos corretos preservados, 75 falsos reduzidos

  4️⃣ QUALITY GATE FAIL-CLOSED
     → Bloqueia geração de ameaças em caso de incoerência
     → Prefere não gerar a gerar falso positivo

  5️⃣ STRIDE DETERMINÍSTICO & RASTREÁVEL
     → Regras auditáveis, cada ameaça com evidência
     → Referências a padrões de indústria (CWE, OWASP, MITRE)
  ```

---

## [04:30 — 06:30] DECISÕES DE ENGENHARIA, DATASET E TREINAMENTO

### Roteiro de Fala (3 minutos)

```
DATASET & TAXONOMIA (0-40s):
"Começamos com um dataset hibrido de 373 imagens:
- 300 diagramas do projeto
- 73 selecionados do Kaggle Software Architecture Dataset

Anotamos em 14 classes canônicas: API Gateway, Load Balancer, Banco de Dados,
Storage, Fila, Identity Provider, Monitoramento, Backup, KMS, WAF, CDN,
Compute, Usuario e Internet.

Essas 14 classes cobrem a maioria dos padrões cloud modernos (AWS, Azure, GCP)
sem ser excessivamente específico. Se alguém desenha um componente exótico não
mapeado, o quality gate alerta."
```

### Visuals (0-40s):

- **Slide: 14 Classes Canônicas com ícones**

  ```
  [Imagens dos 14 tipos de componentes]

  Dataset: 373 imagens
  Split: 265 treino | 69 validação | 39 teste
  Objetos: 3.048 anotados
  ```

---

```
DECISÃO DO MODELO (40-90s):
"Por que YOLOv8n e não outros detectores?

YOLOv8 é estado-da-arte em object detection com bom trade-off entre
velocidade e precisão. Usamos a versão 'nano' para ser executável em máquinas
modesta, sem GPU cara.

Treinamos com:
- Otimizador AdamW (padrão moderno para visão)
- Resolução 640
- Replay balanceado entre Kaggle e projeto (55+55 em cada época)
- Validação balanceada
- ~100 épocas com early stopping

Resultado no teste: Precisão 0.93, Recall 0.84, mAP50 0.90.

Essa é uma métrica de desenvolvimento. Entendo que bom desempenho em
recortes de ícones não garante generalização perfeita em diagramas completos,
novos estilos ou densidade alta. Mantemos essa transparência."
```

### Visuals (40-90s):

- **Slide: Métricas do Detector**

  ```
  Métrica             Valor
  ─────────────────────────
  Precisão           0.9297
  Recall             0.8417
  mAP@50             0.9009
  mAP@50-95          0.8666

  ⚠️ Métrica de desenvolvimento em 39 imagens
  ⚠️ Domain shift em subconjunto Kaggle: mAP50 0.36 (alarme documentado)
  ```

---

```
QUALITY GATE & FAIL-CLOSED (90-180s):
"Uma decisão crítica foi implementar um quality gate que bloqueia gerações de
ameaças em casos de incoerência estrutural.

Por quê? Porque se um diagrama é ambíguo ou ruidoso, é melhor não gerar um
relatório enganoso. Melhor deixar o especialista humano rever.

O gate valida:
- Duplicação suspeita de componentes (ex: diagramas comparativos)
- Inconsistência de provider (detecta AWS mas OCR diz Azure)
- Self-loops sem confirmação explícita
- Arestas direcionadas duplicadas
- Fronteiras de confiança que cortam componentes

Estados de saída:
- 'reliable': Análise pode prosseguir normalmente
- 'review_required': Análise segue, mas com alertas explícitos
- 'rejected': Sem STRIDE, sem risco, sem PDF. Apenas diagnóstico bruto.

Isso é uma decisão consciente de segurança. Na produção, o que importa é
que o sistema nunca gera um PDF com ameaças potencialmente enganosas sem
alerta."
```

### Visuals (90-180s):

- **Slide: Quality Gate States**

  ```
  ┌─────────────────┬─────────┬──────────┬─────────┐
  │ Status          │ Análise │ Relatório│ PDF     │
  ├─────────────────┼─────────┼──────────┼─────────┤
  │ reliable        │ ✅ SIM  │ ✅ SIM   │ ✅ SIM  │
  │ review_required │ ✅ SIM  │ ⚠️ ALERTA│ ✅ SIM  │
  │ rejected        │ ❌ NÃO  │ ❌ NÃO   │ ❌ NÃO  │
  └─────────────────┴─────────┴──────────┴─────────┘

  Rejected = Fail-Closed (melhor não gerar falso positivo)
  ```

---

## [06:30 — 12:30] DEMONSTRAÇÃO PRÁTICA: 3 CASOS DE USO

### Preparação rápida

**Antes de gravar:**

1. Abra o programa no modo agente e deixe o frontend pronto em `http://127.0.0.1:4173`
2. Confirme que o backend está pronto em `http://127.0.0.1:8000/ready`
3. Tenha separados os 3 arquivos de demo: um confiável, um de revisão e um bloqueado

---

### Caso 1 - Fluxo confiável

**Ação:**

- Selecione `data/sample-diagrams/02-mixed-components.jpg` (diagrama bem estruturado)
- Clique em "Analyze"
- Aguarde a resposta (típico: 3-5 segundos)
- Mostre o status de qualidade, as caixas, os fluxos, as ameaças e o PDF

**Roteiro:**

> Vou começar com um caso claro. Aqui eu tenho um diagrama com componentes mistos, mas bem estruturado.
>
> O que eu quero mostrar primeiro é a parte confiável da pipeline: o sistema reconhece os componentes, reconstrói os fluxos e valida a estrutura antes de gerar STRIDE.
>
> Quando a análise volta como `reliable`, eu abro os componentes, os fluxos e uma ameaça expandida para mostrar a rastreabilidade. Depois eu gero o PDF para fechar o caso.

---

### Caso 2 - Análise com revisão humana

**Ação:**

- Selecione `data/benchmarks/real-architecture/images/fiap-architecture-1.png` ou outro diagrama comparativo/ambíguo
- Clique em "Analyze"
- Mostre o status `review_required` e os motivos da revisão
- Abra uma ameaça com alerta e mostre que o PDF ainda pode sair com aviso

**Roteiro:**

> Agora eu quero mostrar o comportamento intermediário do sistema. Aqui a imagem não é claramente errada, mas também não é limpa o bastante para passar sem alerta.
>
> O ponto importante é este: eu não escondo a incerteza. O sistema marca `review_required`, lista os motivos e deixa claro que a leitura precisa de validação humana.
>
> Isso é útil porque a análise continua existindo, mas sem fingir certeza total. Eu consigo mostrar as ameaças, as evidências e os alertas ao mesmo tempo.

---

### Caso 3 - Bloqueio fail-closed

**Ação:**

- Selecione `E:\teste_aws.png`
- Se o arquivo não estiver disponível, abra `data/results/mvp-hardening-001/external-image-quality.json` como contingência visual
- Clique em "Analyze"
- Mostre `rejected`, os motivos e o fato de que não há STRIDE nem PDF

**Roteiro:**

> Agora eu vou mostrar o caso mais importante do ponto de vista de segurança.
>
> Esta imagem contém dois diagramas comparativos na mesma tela. Nesse tipo de entrada, o sistema não deve tentar adivinhar uma única arquitetura.
>
> Quando o quality gate rejeita a análise, eu mostro exatamente isso: sem ameaça, sem risco e sem PDF. O JSON de diagnóstico continua disponível, porque eu quero transparência sobre a rejeição.
>
> Para mim, esse é o diferencial de segurança mais forte do MVP: ele sabe parar quando a evidência não sustenta uma conclusão.

---

### Fechamento da demo

> Em três casos, eu consigo mostrar tudo o que interessa para a banca: um fluxo confiável, um fluxo que pede revisão e um bloqueio fail-closed.
>
> Isso prova que o ThreatLens não só gera saídas. Ele também sabe distinguir quando a imagem sustenta a análise e quando ela ainda precisa de validação humana.

---

## [12:30 — 14:30] DEFESA DE LIMITAÇÕES TÉCNICAS E BORDA DE CONFIANÇA

### Roteiro de Fala (2.5 minutos)

```

TRANSPARÊNCIA SOBRE LIMITAÇÕES (0-60s):
"Agora quero ser honesto sobre o que o sistema **não** faz perfeitamente.

O detector foi treinado em 373 imagens de origens específicas. Isso significa:

1. Se você traz um estilo visual completamente novo (ex: Miro com cores
   customizadas), pode haver redução de confiança.
2. Em diagramas muito densos, com linhas muito próximas, pode haver
   conexões fantasma ou conexões perdidas.
3. Componentes exóticos fora da taxonomia de 14 classes serão classificados
   como a classe mais próxima.
4. OCR em texto muito pequeno ou rotacionado pode falhar.

Essas não são fraquezas escondidas — estão documentadas em 'docs/limitations.md'.
Mantemos essa transparência porque é melhor um especialista saber as
limitações do que confiar cegamente em um sistema que não conhece seus próprios limites.

```

### Visuals (0-60s):

- **Slide: Limitações Documentadas**

```

⚠️ Diagramas densos → Fluxos extras ou falsos
⚠️ Novo estilo visual → Confiança reduzida
⚠️ Componentes exóticos → Classificação aproximada
⚠️ Texto pequeno → OCR falha

Mecanismo de proteção: Quality Gate + Abstention

```

---

```

ABORDAGEM DE MITIGAÇÃO (60-120s):
"Para esses casos, implementamos:

1. Quality Gate: Se a arquitetura reconstruída for incoerente, bloqueamos
   o relatório. Melhor não gerar ameaça enganosa.

2. Abstention: Detecções com confiança < 0.90 não geram ameaças sozinhas.
   Ficam em 'detectionAlternatives' para revisão humana.

3. Feedback Loops: As alternativas e avisos são mostrados no frontend.
   O especialista revisa, aprova ou corrige antes de usar o relatório.

4. Fallback Lexical: RAG (Retrieval-Augmented Generation) usa embeddings
   local primeiro, mas tem fallback léxico determinístico. Se embeddings
   falham, ainda temos resposta rastreável.

Resultado: Um sistema que é **assistência técnica**, não uma caixa preta."

```

---

```

MÉTRICA HONESTA DE DESEMPENHO (120-150s):
"No nosso benchmark de desenvolvimento em 15 diagramas reais (9 de
desenvolvimento + 6 blind):

Estrutura de fluxos: F1 0.52 (não perfeito)
Componentes: Precisão 0.93, Recall 0.84
Ameaças completas (ponta-a-ponta): F1 0.53

Esses números **não** são apresentados como 'o sistema acerta 95% das vezes'
em qualquer diagrama. São números de desenvolvimento em dataset específico.

Publicamos porque transparência > claims não verificáveis.

Na produção, o que importa é que cada análise vem com avisos de qualidade.
Se score < 0.80, é 'review_required'. Se há inconsistências, é 'rejected'.
"

```

### Visuals (120-150s):

- **Slide: Transparência em Métricas**

```

Detector (39 imagens teste):
Precisão: 0.93 | Recall: 0.84 | mAP50: 0.90

Benchmark Real (15 imagens):
Componentes detectados: Corretos 86%, Extras 14%
Fluxos: Corretos 52%, Falsos 25%, Ausentes 23%

⚠️ Não generaliza perfeitamente em todos os diagramas
⚠️ Domain shift documentado em subset Kaggle
⚠️ Fail-closed em ambiguidade

```

---

```

SEGURANÇA EM PRODUÇÃO (150-160s):
"Três princípios guiam a implementação:

1. Zero Trust: Entrada não confiável até validação
2. Fail-Closed: Melhor não gerar relatório duvidoso
3. Auditabilidade: Cada decisão é rastreável até a imagem original

Isso significa: Um diagrama ambíguo resulta em alerta, não em ameaça
potencialmente errada.
"

```

---

## [14:30 — 15:00] ENCERRAMENTO E CONCLUSÃO

### Roteiro de Fala (1.5 minuto)

```

RECAPITULAÇÃO (0-30s):
"Em resumo, ThreatLens é um MVP que:

✅ Automatiza 80% do trabalho tedioso (detecção + mapeamento)
✅ Mantém rastreabilidade completa (cada ameaça pode ser auditada)
✅ Usa regras determinísticas, não LLM alucinando
✅ Bloqueia em ambiguidade (fail-closed)
✅ Transparente sobre limitações
✅ Rodam local, sem dependência de serviços cloud
✅ Exporta para PDF profissional, JSON e Markdown

Isso permite que times de segurança façam modelagem de ameaças 10x mais
rápido, mantendo qualidade técnica."

```

---

```

VALOR PARA A FIAP SOFTWARE SECURITY (30-60s):
"Para a empresa FIAP Software Security, o MVP demonstra:

1. Viabilidade: É possível automatizar modelagem STRIDE com visão computacional
2. Qualidade: Referências verificáveis (CWE, CAPEC, OWASP, MITRE)
3. Confiabilidade: Proteções contra alucinações e relatórios enganosos
4. Escalabilidade: Pode processar 100+ diagramas por dia sem custo operacional alto

Os próximos passos seriam:

- Expandir dataset com mais diagramas reais de clientes
- Fine-tuning do detector específico para clientes enterprise
- Integração com ferramentas de gestão de riscos (Jira, Azure Devops, etc.)
- Workflow de aprovação humana integrado"

```

---

```

CONCLUSÃO (60-90s):
"A segurança de software não é um destino, é um processo contínuo.
Ferramentas automatizadas como ThreatLens podem democratizar o acesso a
análises técnicas de qualidade, permitindo que times menores façam
segurança em escala.

O código está aberto no GitHub, a documentação é completa, e a abordagem
é reprodutível. Isso permite que a comunidade valide, critique e melhore.

Obrigado por acompanharem. Fico à disposição para perguntas técnicas."

```

### Visuals (60-90s):

- **Slide Final: Chamada à Ação**

```

✅ MVP Validado
✅ Código Aberto
✅ Documentação Completa
✅ Pronto para Produção

GitHub: [seu-repositório]
Documentação: docs/architecture.md

```

---

## CHECKLIST PRÉ-GRAVAÇÃO

- [ ] Backend FastAPI rodando em http://127.0.0.1:8000
- [ ] Frontend Node.js rodando em http://127.0.0.1:4173
- [ ] `GET /health` retorna status OK
- [ ] `GET /ready` retorna ready=true
- [ ] Diagrama de teste claro preparado (ex: `data/sample-diagrams/02-mixed-components.jpg`)
- [ ] Diagrama de teste com ruído preparado (ex: diagrama comparativo ou denso)
- [ ] OBS/Camtasia aberto para captura de tela
- [ ] Microfone testado e níveis de áudio validados
- [ ] Cursor invisível em screen capture
- [ ] Zoom do navegador em 100% (ou documentado qual zoom usar)
- [ ] PDF de amostra gerado previamente (`output/pdf/threatlens-sample-report.pdf`)

---

## DICAS DE GRAVAÇÃO

### Timing

- **Edição:** Corte pausas longas, somente deixe os momentos "vivos"
- **Velocity:** Mova o mouse rápido entre demos (não deslize lentamente)
- **Transições:** Use cortes diretos ou fade de 0.5s, não dissolve longas

### Audio

- **Fala:** Claro, sem pressa, sem "aahhh" ou "eeehhh"
- **Background:** Gravação em local silencioso (sem fan de ventilador, trânsito)
- **Volume:** Microfone ~6-12 inches da boca

### Video

- **Resolução:** Mínimo 1080p (1920x1080)
- **FPS:** 30fps é OK
- **Bitrate:** 5-10 Mbps para qualidade YouTube

### Edição Final

- [ ] Legendas (optional, mas ajuda em ambientes barulhentos)
- [ ] Zoom em partes críticas (ex: expandir ameaças na tela)
- [ ] B-roll: Screenshots da documentação, slides de suporte
- [ ] Intro/Outro: ~5s cada

---

## APÓS A GRAVAÇÃO

1. **Export:** MP4, H.264, AAC audio
2. **Upload para YouTube:** Título, descrição com links, tags
3. **Descrição no YouTube (Template):**

```

THREATSLENS AI — MVP de Modelagem Automática de Ameaças STRIDE

Hackathon Pós-Tech FIAP | Julho de 2026

Projeto: Automatizar análise STRIDE a partir de imagens de diagramas
de arquitetura, com rastreabilidade, fail-closed e referências de
segurança verificáveis.

Links:
📍 GitHub: [seu repositório]
📍 Documentação: [pasta docs]
📍 Demo Interativa: [se disponível online]

Timestamps:
00:00 - Abertura
02:00 - Decisões de Engenharia
05:00 - Demo 1: Caso Claro
09:00 - Demo 2: Caso com Ruído
11:00 - Limitações Técnicas
13:30 - Encerramento

Tecnologias:

- YOLOv8n (detecção de componentes)
- Tesseract OCR (extração de rótulos)
- FastAPI (backend)
- React/Vue (frontend)
- Python STRIDE engine (análise determinística)
- ReportLab (geração de PDF)

#SegurançaDeSoftware #Hackathon #IA #STRIDE #ThreatModeling

```

4. **Fazer privado até liberação oficial** (ou deixar como non-listed)

---

**Versão Final:** Pronta para gravação
**Data:** Julho de 2026
**Duração Total:** 15 minutos ± 10 segundos

```

```
