# 🎯 ROADMAP DE EXECUÇÃO - PRÓXIMAS 2 SEMANAS

Plano tático dia a dia para transformar análise crítica em demonstração de sucesso.

---

## 📅 SEMANA 1: Dataset & Preparação

### 🟠 Dia 1-2: Estratégia de Dataset GCP

**Objetivo:** Fechar a lacuna GCP sem depender de um dataset nativo perfeito

**Tarefas:**

1. **Gerar GCP sintético com diagrams (2h)**

   ```bash
   # gerar imagens sintéticas com layouts GCP-equivalentes
   python scripts/generate_synthetic_dataset.py --count 120
   ```

   - Usa `mingrammer/diagrams` como base para gerar cenários tri-cloud
   - Preserva rótulos canônicos no mesmo schema do projeto
   - Revisão manual: remover layouts pouco realistas

2. **Integração do dataset Hugging Face (2h)**
   - Usa `guillherms/stride-architecture-components-v1` como base principal
   - Mantém AWS/Azure como núcleo supervisionado
   - Normaliza classes para o schema canônico do projeto

3. **Complemento com Kaggle (1h)**
   - Baixa o dataset de arquitetura para ampliar diversidade visual
   - Usa apenas o que for compatível com a taxonomia do projeto
   - Rejeita imagens com ruído ou classes fora do escopo

4. **Validação Inicial (30min)**
   - Total alvo: 200+ imagens úteis após consolidação
   - Split recomendado: 70 train, 15 val, 15 test
   - Commit sugerido: `git add dataset/ && git commit -m "Consolidate tri-cloud dataset strategy"`

**Deliverable:** ✅ Base de treino tri-cloud com GCP sintético + dataset real consolidado

---

### 🟠 Dia 3: Data Augmentation Específica

**Objetivo:** Aumentar dataset via augmentation para diagramas

**Tarefas:**

1. **Implementar Augmentation Pipeline (2h)**

   ```bash
   # Edite scripts/train_yolo.py - seção de augmentation
   # Troque config genérica por diagram-specific
   ```

   Mudanças em `scripts/train_yolo.py`:

   ```python
   # ANTES
   hsv_h=0.015, hsv_s=0.7, hsv_v=0.4, flipud=0.1, fliplr=0.5, mosaic=1.0, ...

   # DEPOIS
   perspective=0.05, erasing=0.3, coarse_dropout=0.2, rotate=45,
   shear=10, elastic=0.2, grid_distortion=0.1, ...
   ```

2. **Verificar Balanceamento de Classes (1h)**

   ```bash
   python scripts/analyze_dataset_balance.py
   ```

   - Deve mostrar distribuição de classes
   - Alvo: cada classe com 30-50 imagens

3. **Aplicar Augmentation (1.5h)**
   ```bash
   python scripts/augment_dataset.py --multiplier 3
   ```

   - Gera 3x aumentação de imagens existentes
   - Dataset vai de ~200 para ~600 imagens

**Deliverable:** ✅ ~600 imagens totais (com augmentation)

---

### 🟠 Dia 4-5: Integração de Dataset Hugging Face

**Objetivo:** Consolidar AWS + Azure + GCP em um único dataset

**Tarefas:**

1. **Download do Hugging Face principal (2h)**

   ```bash
   # baixar manualmente ou via script equivalente
   # priorizar guillherms/stride-architecture-components-v1
   ```

   - Base principal do treinamento supervisionado
   - Mantém foco em AWS/Azure com rótulos consistentes

2. **Integração do Kaggle (1.5h)**
   - Adiciona somente exemplos úteis para completar classes e estilos
   - Exclui classes muito fora do schema canônico

3. **Validação de Anotações (1.5h)**
   - Verificar se labels estão em formato YOLO
   - Converter se necessário (PyYAML + formato YOLO)
   - Exemplo conversão se necessário

4. **Criação de Dataset YAML (30min)**

   ```bash
   # dataset/architecture.yaml
   path: ../dataset
   train: images/train
   val: images/val
   test: images/test

   nc: 14  # Número de classes
   names: ['user', 'internet', 'identity_provider', 'waf', 'cdn', 'api_gateway',
           'load_balancer', 'compute', 'database', 'storage', 'queue',
           'monitoring', 'backup', 'secrets_kms']
   ```

5. **Split Estratificado (1h)**
   ```bash
   python scripts/create_stratified_splits.py --ratio 0.7:0.15:0.15
   ```

   - Garante distribuição igual de classes em train/val/test

**Deliverable:** ✅ Dataset consolidado tri-cloud pronto para treino, com GCP coberto por geração sintética e consolidação real

---

## 📅 SEMANA 2: Implementação & Treinamento

### 🟠 Dia 6-7: Correções de Código Críticas (P1-P5)

**Objetivo:** Implementar as 5 correções críticas

**Dia 6 - Manhã:**

1. **P2 + P3: Threshold Dinâmico + OCR (2h)**

   ```bash
   # Edite backend/detector.py com código de CODIGO-READY-TO-USE.md
   # Copie:
   # - _calculate_confidence_threshold()
   # - _extract_text_from_box()
   ```

   Testes:

   ```bash
   python -c "from backend.detector import _calculate_confidence_threshold; print(_calculate_confidence_threshold(10000, 200000))"
   # Esperado: 0.75
   ```

2. **P5: Fallback Robusto (1h)**
   ```bash
   # Edite backend/main.py
   # Substitua analyze_image_endpoint() com cascata: YOLO → Gemini → Placeholder
   ```

**Dia 6 - Tarde:**

3. **P8: Provider-Specific Rules (1.5h)**

   ```bash
   # Edite backend/stride_engine.py
   # Adicione COMPONENT_KNOWLEDGE_AWS, _GCP, _AZURE
   # Modifique _build_component_threats() para considerar provider
   ```

4. **Testes (1h)**
   ```bash
   python scripts/test_critical_fixes.py
   # Verificar todos os testes passarem
   ```

**Dia 7 - Dia Inteiro:**

5. **P1: Web Scraping + Síntese GCP (4h)**
   ```bash
   python scripts/scrape_gcp_architectures.py --limit 100 --output dataset/images/train
   # Isto pode levar tempo se houver throttling de API
   ```

**Deliverable:** ✅ Código pronto para produção com P1-P5

---

### 🟠 Dia 8-9: Treino de Modelo YOLO

**Objetivo:** Treinar YOLOv8 com novo dataset

**Dia 8:**

1. **Inspeção de Dataset (30min)**

   ```bash
   python scripts/inspect_dataset.py
   # Verifica formato, tamanho de imagens, distribuição de classes
   ```

2. **Treino YOLO (3-6h, depends on hardware)**

   ```bash
   python scripts/train_yolo.py --device 0 --epochs 100
   # Se CPU: --device cpu --epochs 50 (mais rápido, menos acurado)
   ```

   Durante treino, monitore:
   - Precision/Recall por classe
   - mAP (target: >0.75)
   - Gráficos de loss (devem descer)

3. **Salve Melhores Pesos**
   - Verificar `models/threatlens-v1/weights/best.pt`
   - Atualizar `.env`: `YOLO_MODEL_PATH=models/threatlens-v1/weights/best.pt`

**Dia 9:**

4. **Avaliação do Modelo (2h)**

   ```bash
   python scripts/evaluate_model.py --model models/threatlens-v1/weights/best.pt --save-plots
   ```

   Gera:
   - Matriz de confusão (visualizar erros por classe)
   - Precision/Recall por classe
   - Exemplos de detecções bem/malsucedidas

   Se mAP < 0.70:
   - Aumentar dataset (~300 imagens mais)
   - Reficar augmentation
   - Tentar YOLOv8s em vez de YOLOv8n

   Se mAP > 0.75:
   - ✅ Modelo aprovado para demo

**Deliverable:** ✅ Modelo YOLO treinado com mAP > 0.75

---

### 🟠 Dia 10-11: Integração & Testes E2E

**Objetivo:** Validar pipeline completo image→report

**Dia 10:**

1. **Testes Unitários (1h)**

   ```bash
   pytest backend/tests/test_detector.py -v
   pytest backend/tests/test_stride_engine.py -v
   pytest backend/tests/test_rag.py -v
   ```

   Se não existem testes, criar mínimos:

   ```python
   # backend/tests/test_detector.py
   def test_detector_loads():
       from backend.detector import is_available
       assert is_available()

   def test_threshold_dynamic():
       from backend.detector import _calculate_confidence_threshold
       assert _calculate_confidence_threshold(10000, 200000) == 0.75
   ```

2. **Testes de Integração (2h)**

   ```bash
   # Start backend
   uvicorn backend.main:app --reload --port 8000

   # Em outro terminal, testar:
   curl -X POST "http://localhost:8000/health"
   # Esperado: {"status": "ok", "yolo_available": true, "rag_chunks": 42}

   # Testar com imagem real:
   curl -X POST "http://localhost:8000/analyze/image" \
     -F "image=@data/sample-architecture.json" \
     -H "Content-Type: multipart/form-data"
   ```

**Dia 11:**

3. **Testes E2E com 5 Arquiteturas (2h)**

   Prepare 5 imagens de teste:
   - `test_aws_simple.png` (3 componentes)
   - `test_aws_complex.png` (8+ componentes)
   - `test_azure.png` (Azure native)
   - `test_gcp.png` (GCP native)
   - `test_tricloud.png` (AWS + GCP + Azure)

   Para cada:

   ```bash
   # Enviar para /analyze/image
   # Verificar:
   # ✓ Detecta componentes corretos
   # ✓ Confidence scores razoáveis
   # ✓ Sem hallucinations
   # ✓ STRIDE report gerado
   # ✓ Validação passa
   ```

4. **Benchmark de Performance (1h)**

   ```bash
   # Latência esperada:
   # Image upload + YOLO: 2-4s
   # STRIDE analysis: 0.5s
   # RAG query: 1-2s
   # LLM report: 3-5s (Gemini)
   # Validation: 2-3s (Groq)
   # TOTAL: 8-17s

   # Se > 20s, otimizar (ver P11: cache RAG)
   ```

**Deliverable:** ✅ Pipeline completo testado e validado

---

## 📅 SEMANA 3: Polish & Demo

### 🟠 Dia 12-13: Refatoração Importante (P6-P10)

Prioridade: **escolha 2-3 de P6-P10** que mais impactam demo

**Recomendado:**

1. **P6: Detecção de Trust Boundaries** (4h)
   - Adiciona ~30% mais profundidade à análise

2. **P8: Provider-Specific Rules** (se ainda não feito) (4h)
   - Torna relatório específico a AWS/GCP/Azure

3. **P9: Timeout Gemini** (1h)
   - Garante demo não congela

**Dia 13 - Testes Finais (3h)**

- Re-testar 5 arquiteturas com P6-P10 implementados
- Verificar qualidade dos relatórios

**Deliverable:** ✅ P6-P10 parcialmente implementados (max impact)

---

### 🟠 Dia 14: Demo Rehearsal & Documentation

**Objetivo:** Ensaio geral e documentação final

**Manhã (2h):**

1. **Preparar 3 Arquiteturas de Demo**
   - 1 AWS (conhecida, simple)
   - 1 GCP (mostra cobertura GCP nova)
   - 1 Híbrida (AWS + GCP, mostra provider-specific rules)

2. **Script de Demo Automatizado**

   ```bash
   # scripts/demo.sh
   #!/bin/bash
   echo "=== ThreatLens AI - Demonstração ===="
   echo ""
   echo "1. Analisando arquitetura AWS..."
   curl -X POST "http://localhost:8000/analyze/image" \
     -F "image=@demo/aws_simple.png" > /tmp/demo_aws.json
   echo "✓ Arquitetura AWS analisada"

   echo ""
   echo "2. Analisando arquitetura GCP..."
   # ... similar

   echo ""
   echo "3. Gerando relatório STRIDE..."
   # POST /analyze/json com arquitetura JSON
   ```

**Tarde (3h):**

3. **Documentação Final**
   - README.md: instruções de uso
   - SETUP.md: como configurar ambiente
   - RESULTS.md: exemplos de outputs
   - LIMITATIONS.md: o que funciona e o que não

4. **Video/Screenshots**
   - Capturar telas do dashboard
   - Gravar GIF do pipeline completo (image upload → report)

5. **Apresentação em PowerPoint**
   - Slide 1: Problem Statement
   - Slide 2: Solução (pipeline)
   - Slide 3: Demo (imagem real → detecção → STRIDE)
   - Slide 4: Resultados (metrics)
   - Slide 5: Roadmap futuro

**Deliverable:** ✅ Demo ensaiada, documentação completa, presentation pronta

---

## ✅ CHECKLIST FINAL PRÉ-APRESENTAÇÃO

```
CÓDIGO & ML:
[ ] Todos P1-P5 implementados e testados
[ ] YOLO treinado com mAP > 0.75
[ ] Pipeline E2E funcionando (<20s latência)
[ ] Relatórios STRIDE sem hallucinations
[ ] Modelo salvo e versionado em Git

DATASET:
[ ] 200+ imagens tri-cloud (AWS/Azure/GCP)
[ ] Balanceamento de classes verificado
[ ] Train/Val/Test splits estratificados
[ ] Data augmentation aplicado

DEMO:
[ ] 3 arquiteturas de teste preparadas
[ ] Dashboard funcionando
[ ] Relatórios markdown exportáveis
[ ] Screenshots/videos gravados

DOCUMENTAÇÃO:
[ ] README com quick start
[ ] SETUP.md com environment
[ ] RESULTS.md com exemplos
[ ] Análise Crítica incluída
[ ] Código comentado

APRESENTAÇÃO:
[ ] PowerPoint/Slides prontos
[ ] Demo script funcionando
[ ] Backup plan (se tudo quebrar)
[ ] Time sincronizado na narrativa

LAST MINUTE:
[ ] Testar com novas imagens (não no dataset)
[ ] Verificar credenciais de API (.env)
[ ] Ter internet de backup (hotspot)
[ ] Salvar relatórios offline como evidência
```

---

## 🎬 DIA DE APRESENTAÇÃO

### Antes (1h antes):

1. **Verificar Setup**
   - Backend rodando: `http://localhost:8000/health` → 200 OK
   - Frontend acessível: `http://localhost:4173`
   - Dataset carregado: histórico de modelos visível

2. **Testar Pipeline Rápido**
   - Enviar uma imagem de teste
   - Gerar um relatório STRIDE
   - Verificar latência (<20s)

3. **Preparar Backup**
   - Screenshots pré-gravadas de relatórios
   - JSON sample pronto para /analyze/json endpoint
   - Apresentação offline (PDF)

### Durante Apresentação (10-15min):

**Narrativa Sugerida:**

```
"Olá! Somos o ThreatLens AI.

[Problema] Threat modeling manual leva horas. Qual é o risco da sua arquitetura?

[Solução] IA supervisionada detecta componentes de diagramas,
         STRIDE engine gera ameaças baseadas em regras,
         LLM com RAG produz relatório estruturado.

[Demo] Vamos analisar uma arquitetura real.
       [Upload imagem → Detector YOLO → Output JSON]
       "Detectamos 8 componentes com 86% de confiança"
       [Mostra bounding boxes na imagem]

       [STRIDE Analysis → Relatório]
       "Identificamos 24 ameaças em 6 categorias STRIDE"
       "Risk score: 7.8/10"

       [Mostra relatório com countermeasures específicos]

[Resultados] Precision/Recall por classe, cobertura tri-cloud (AWS/GCP/Azure)

[Roadmap] Multimodal LLM, active learning, compliance mapping
```

**Tempo:**

- Problema: 1 min
- Solução: 2 min
- Demo: 7 min
- Resultados: 2 min
- Q&A: 3 min

---

## 📊 SUCCESS METRICS

Seu projeto é bem-sucedido se:

| Métrica                     | Target          | Crítico?      |
| --------------------------- | --------------- | ------------- |
| Detecção YOLO (mAP)         | >0.75           | ✅ SIM        |
| Latência P95                | <20s            | ✅ SIM        |
| Relatório sem hallucination | 100%            | ✅ SIM        |
| Cobertura tri-cloud         | AWS/GCP/Azure   | ✅ SIM        |
| Teste real (5 arquiteturas) | 80%+ acurácia   | ⚠️ IMPORTANTE |
| Dashboard funcionando       | UI responsivo   | ⚠️ IMPORTANTE |
| Documentação                | Setup + Results | ⚠️ IMPORTANTE |

---

## 🚨 CONTINGÊNCIA: Se Algo Quebrar

| Cenário                 | Fallback                                          |
| ----------------------- | ------------------------------------------------- |
| YOLO não treina         | Use modelo pré-treinado + Gemini Vision como demo |
| GCP dataset vazio       | Use apenas AWS + Azure (2 clouds)                 |
| API Gemini/Groq offline | Use mocks/fixtures com relatórios pré-gerados     |
| Dashboard não carrega   | Mostrar JSON + markdown report direto             |
| Computador trava        | Abra video pré-gravado da demo                    |

---

**Boa sorte! 🚀 Você vai conseguir! Foco nas P1-P5 primeira, depois o resto.**
