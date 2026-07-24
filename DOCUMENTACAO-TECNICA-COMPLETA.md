# DOCUMENTAÇÃO TÉCNICA COMPLETA

## ThreatLens AI — MVP de Modelagem de Ameaças Automatizada via Visão Computacional e IA

---

## CABEÇALHO DO DOCUMENTO

| Item                      | Valor                                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| **Projeto**               | MVP de Modelagem de Ameaças Automatizada a partir de Diagramas de Arquitetura de Software |
| **Evento**                | Hackathon Pós-Tech FIAP — Fase 5                                                          |
| **Empresa Desafiante**    | FIAP Software Security                                                                    |
| **Data de Entrega**       | Julho de 2026                                                                             |
| **Repositório GitHub**    | [Link do seu repositório]                                                                 |
| **Vídeo de Demonstração** | [Link do vídeo no YouTube]                                                                |
| **Status Geral**          | MVP Validado — 7 de 7 Requisitos Atendidos                                                |

---

## 1. MATRIZ DE CONFORMIDADE E RASTREABILIDADE DE REQUISITOS

A tabela abaixo mapeia cada requisito oficialmente solicitado no edital do Hackathon com o status de implementação, localização no código e evidência técnica.

| Requisito do Edital                                            | Status      | Evidência e Implementação no Projeto                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| -------------------------------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Detecção e Leitura do Diagrama**                          | ✅ Atendido | **Pipeline de Análise:** A entrada do sistema é uma imagem de diagrama de arquitetura. O fluxo começa em `backend/main.py` (função `analyze_image_and_detect()` e `POST /analyze/image`), que valida a imagem antes de processamento. A detecção de componentes é feita por `backend/detector.py`, que carrega o modelo registrado em `models/threatlens-hybrid-v2/weights/best.pt` (YOLOv8n treinado). O OCR local é implementado em `backend/ocr.py` usando Tesseract para extrair labels, nomes de serviços e protocolos. A reconstrução de fluxos e fronteiras acontece em `backend/diagram_structure.py` usando OpenCV para análise de linhas, conectores e setas. Resultado: cada componente retorna id, nome, tipo, provider, confiança (0.0-1.0) e bounding box (x, y, w, h).                                                                                                                                                                                                                                                   |
| **2. Dataset de Arquiteturas de Software**                     | ✅ Atendido | **Dataset Híbrido Registrado:** O dataset final é `dataset/hybrid_v2`, contendo 373 imagens e 3.048 objetos anotados em 14 classes canônicas. Origem: 300 diagramas do projeto + 73 selecionados do Software Architecture Dataset (Kaggle, 8.700 imagens originais). Splits: 265 treino, 69 validação, 39 teste. Configuração oficializada em `dataset/architecture.yaml` com nc=14 e mapeamento de nomes de classes. Diversidade: inclui diagramas de AWS, Azure, GCP e estilos genéricos. Sem vazamento entre splits — a agrupação por arquitetura original garantiu que variantes aumentadas não cruzassem treino/validação/teste.                                                                                                                                                                                                                                                                                                                                                                                                   |
| **3. Anotação de Dados (Rótulos/Labels)**                      | ✅ Atendido | **Processo de Anotação Auditável:** O dataset Kaggle vinha em formato Pascal VOC (.xml). Conversão para YOLO (.txt) em `scripts/build_dataset.py` com mapeamento para a taxonomia canônica (14 classes). O processo de auditoria de anotações está em `scripts/audit_voc_annotations.py`, que verifica orfandade, integridade e balanceamento. Dados reais derivados de 9 diagramas de desenvolvimento e 6 blind benchmark foram anotados com `scripts/bootstrap_real_benchmark_annotations.py`, que registra `annotationStatus: "draft_model_proposal"` e exige revisão visual explícita (`annotationMethod: "YOLO and geometric bootstrap; requires visual review before scoring."`). Rastreabilidade completa: cada imagem tem metadados de origem, método e status de validação.                                                                                                                                                                                                                                                    |
| **4. Treinamento do Modelo Supervisionado**                    | ✅ Atendido | **Treinamento YOLOv8n com Reprodutibilidade:** Script de treino em `scripts/train_yolo.py` implementa: (a) carregamento do dataset via `dataset/architecture.yaml`, (b) uso de YOLOv8n (nano) para eficiência, (c) otimizador AdamW conforme README, (d) resolução 640, (e) replay balanceado entre fontes Kaggle e projeto (55+55 diagramas), (f) validação balanceada (9+9 imagens), (g) epochs configurável (padrão 100), (h) checkpoint automático do melhor peso em `models/threatlens-hybrid-v2/weights/best.pt`. Hash SHA-256 do peso registrado: `2aebcd0611927505d60a10d23ce11d0e5211cf2e91ca0c4394921fac006c865d`. Model card completo em `models/threatlens-hybrid-v2/model-card.json` com métricas, data, versão e hiperparâmetros.                                                                                                                                                                                                                                                                                         |
| **5. Mapeamento de Ameaças STRIDE e Contramedidas Associadas** | ✅ Atendido | **Engine STRIDE Determinístico:** `backend/stride_engine.py` implementa um catálogo de regras rastreáveis por tipo de componente (user, internet, api_gateway, load_balancer, waf, compute, database, storage, queue, identity_provider, monitoring, backup, secrets_kms, cdn). Para cada tipo, há um dicionário `COMPONENT_KNOWLEDGE` com regras STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege). Cada ameaça tem: (a) STRIDE category, (b) title, (c) severity (Critical/High/Medium/Low), (d) confiança calculada a partir de detecção, (e) contramedidas objetivas (lista de ações), (f) referências a CWE (Common Weakness Enumeration), CAPEC (Common Attack Pattern Expression Language), OWASP Top 10 2021 e MITRE ATT&CK. Exemplo: Spoofing em api_gateway → CWE-287 (Improper Authentication), CAPEC-115 (Authentication Bypass), OWASP A07:2021, MITRE T1078 (Valid Accounts). Todas as 6 categorias STRIDE cobertas com referências de segurança verificáveis. |
| **6. Geração de Relatório STRIDE Consolidado**                 | ✅ Atendido | **Pipeline de Relatório Multicanal:** A saída consolida ameaças, contramedidas e risco em três formatos: (1) JSON estruturado com grafo de arquitetura, ameaças com status de gestão e matriz de risco, (2) Markdown com seções de resumo executivo, ameaças priorizadas e plano de mitigação, (3) PDF profissional gerado por `backend/pdf_report.py` usando ReportLab. O PDF inclui: página de cobertura, tabela de risco inerente vs. residual, matriz de severidade/status, resumo executivo, 12+ ameaças principais priorizadas por risco, plano de mitigação com responsáveis e datas, rodapé com referências. A geração é determinística — não requer LLM externa por padrão (modo generativo é opcional e desabilitado por padrão). Exemplo de saída em `docs/sample-threat-model.md` com 15+ ameaças e referências anotadas.                                                                                                                                                                                                   |
| **7. Entregáveis e Documentação Técnica**                      | ✅ Atendido | **Repositório GitHub Versionado + Documentação Completa:** (a) Código-fonte 100% disponível e versionado em GitHub com histórico de commits e rastreabilidade. (b) README.md com visão geral, pré-requisitos, instrução de execução (local e Docker) e exemplos. (c) Documentação técnica detalhada em `docs/architecture.md` descrevendo pipeline, componentes, quality gate, STRIDE engine, RAG e segurança. (d) Documentação de dataset em `docs/dataset-integration-results.md` e `docs/model-development.md` com tabelas, origens e limitações explícitas. (e) Documentação de modelo em `docs/model-evaluation-and-registration.md` com métricas do detector (mAP50 0.9009, Recall 0.8417). (f) Índice operacional de demonstração em `docs/submission-evidence.md` com roteiro passo a passo para banca. (g) Esta documentação técnica completa pronta para exportação em PDF. (h) Vídeo de demonstração de até 15 minutos no YouTube com live demo e explicação das decisões de engenharia.                                     |

---

## 2. PIPELINE TÉCNICO DE IA E VISÃO COMPUTACIONAL

### 2.1 Arquitetura de Alto Nível

O ThreatLens implementa uma cadeia de processamento com separação clara de responsabilidades:

```
┌─────────────────────┐
│  ENTRADA: Imagem    │
│   (PNG/JPEG/WebP)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Validação e Pré-processamento      │
│  - Tamanho, pixels, tipo            │
│  - Limites de cardinalidade         │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Detecção Supervisionada (YOLOv8n)  │
│  - 14 classes canônicas             │
│  - Confiança 0.0-1.0                │
│  - Bounding box (x, y, w, h)        │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  OCR Local + Arbitragem Semântica   │
│  - Tesseract (labels, providers)    │
│  - Geometry-aware text association  │
│  - Detection Alternatives (conflitos)│
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Reconstrução de Fluxos & Fronteiras│
│  - OpenCV para linhas e conectores  │
│  - Arrowhead classification         │
│  - Protocolos explícitos            │
│  - Trust boundaries e gates         │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Quality Gate Estrutural            │
│  - Validação fail-closed            │
│  - Status: reliable/review/rejected │
└──────────┬──────────────────────────┘
           │
      ┌────┴────┬────────────┐
      │          │            │
   rejected  review      reliable
      │       required      │
      │          │          │
      ▼          ▼          ▼
    ┌──┬────────┴─┬──────────┐
    │  │          │          │
    │  ▼          ▼          ▼
    │ Motor    Revisão   Motor STRIDE
    │Diagnóstico Humana  + RAG Local
    │                      │
    │                      ▼
    │                  Contramedidas
    │                   + Referências
    │                      │
    │  ┌──────────────────┘
    │  │
    ▼  ▼
┌──────────────────────────┐
│  Relatório (JSON/MD/PDF) │
│  - Matriz de Risco       │
│  - 12+ Ameaças Priorit.  │
│  - Plano de Mitigação    │
└──────────────────────────┘
```

### 2.2 Detecção Supervisionada de Componentes

**Responsável:** `backend/detector.py`

O detector carrega o modelo YOLOv8n registrado e o executa sobre a imagem da arquitetura.

```python
# Carregamento do modelo
model = YOLO("models/threatlens-hybrid-v2/weights/best.pt")

# Detecção
results = model.predict(source=image_path, conf=YOLO_MIN_DETECTION_CONFIDENCE)

# Processamento de resultados
for detection in results[0].boxes:
    class_id = int(detection.cls)
    confidence = float(detection.conf)
    bbox = detection.xyxy[0]  # [x1, y1, x2, y2]

    # Calibração de confiança (regressão logística treinada)
    calibrated_conf = _calibrate_confidence(confidence, area_ratio)
```

**Métricas do Detector no Teste Híbrido (39 imagens):**

| Métrica   | Valor  |
| --------- | ------ |
| Precisão  | 0.9297 |
| Recall    | 0.8417 |
| mAP@50    | 0.9009 |
| mAP@50-95 | 0.8666 |

**Saída por componente:**

```json
{
  "id": "api_1",
  "name": "API Gateway",
  "type": "api_gateway",
  "provider": "aws",
  "confidence": 0.91,
  "bbox": [120, 80, 220, 180],
  "detectedBy": "yolov8",
  "detectionAlternatives": []
}
```

**Classes Suportadas (14 canônicas):**

`api_gateway`, `backup`, `cdn`, `compute`, `database`, `identity_provider`, `internet`, `load_balancer`, `monitoring`, `queue`, `secrets_kms`, `storage`, `user`, `waf`

### 2.3 OCR e Reconhecimento de Contexto

**Responsável:** `backend/ocr.py`

O OCR local usando Tesseract extrai texto diretamente da imagem e associa geometricamente aos componentes detectados.

**Fluxo:**

1. **Extração de texto:** Tesseract processa a imagem inteira e retorna:
   - Linhas de texto com bounding boxes
   - Confiança de cada linha
   - Posição (x, y, w, h)

2. **Associação geometry-aware:** O texto é mapeado ao componente mais próximo, considerando:
   - Distância euclidiana
   - Alinhamento vertical/horizontal
   - Âncora visual preferida (abaixo de ícone, dentro de retângulo, etc.)

3. **Arbitragem Semântica:** Se OCR detecta tipo ou provider que conflita com a classe YOLO:
   - Conflito é registrado em `detectionAlternatives`
   - Não sobrescreve silenciosamente a classe supervisionada
   - Fica disponível para revisão humana
   - Exemplo: YOLO detecta `compute`, OCR vê "RDS" → alternativa `database` registrada

**Exemplo de Saída:**

```json
{
  "id": "db_1",
  "name": "RDS Primary",
  "type": "database",
  "provider": "aws",
  "textEvidences": [
    {
      "text": "RDS Primary",
      "confidence": 0.87,
      "bbox": [125, 185, 220, 210],
      "associationMethod": "geometry_aware_below_icon"
    }
  ],
  "detectionAlternatives": [
    {
      "type": "storage",
      "evidence": "OCR detected 'S3 Bucket' nearby",
      "confidence": 0.42,
      "supersededBy": "database"
    }
  ]
}
```

### 2.4 Engine de Qualidade Estrutural (Fail-Closed & Quality Gate)

**Responsável:** `backend/analysis_quality.py`

O Quality Gate é acionado após reconstrução e **antes** do cálculo de STRIDE. Seu objetivo é evitar que análises baseadas em diagramas estruturalmente inválidos geguem produzir ameaças enganosas.

**Critérios de Validação:**

| Controle                               | Descrição                                                                                                           | Ação se Falhar                           |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| **C01:** Duplicação de componentes     | Componentes com mesmo id, nome e tipo em posições diferentes (ex: diagramas comparativos AWS vs. Azure lado a lado) | Sinaliza `review_required` ou `rejected` |
| **C02:** Alinhamento suspeito          | Pares de componentes idênticos alinhados perfeitamente (indicador de comparação não intencional)                    | Alerta com motivo e coordenadas          |
| **C03:** Agrupamentos como componentes | Labels de "região", "subnet", "cluster" classificadas como componentes isolados                                     | Marcar para revisão                      |
| **C04:** Inconsistência de provider    | Provider detectado (ex: `aws`) conflita com evidência textual dominante (ex: "Azure")                               | Sinaliza divergência                     |
| **C05:** Self-loops sem confirmação    | Componente conectado a si mesmo sem evidência de ciclo explícito                                                    | Alerta de possível erro de OCR           |
| **C06:** Arestas duplicadas            | Múltiplos fluxos idênticos entre os mesmos componentes                                                              | Detecta e consolida ou marca como erro   |
| **C07:** Fronteiras cruzadas anômalas  | Trust boundary que engloba ou corta através de componentes de forma incoerente                                      | Sinaliza para revisão                    |

**Estados de Saída:**

```json
{
  "status": "review_required", // reliable | review_required | rejected
  "score": 0.82, // 0.0-1.0
  "reasons": [
    "Possible comparative architecture detected: components 'api_1' and 'api_2' are spatially identical.",
    "Provider inconsistency: YOLO detected 'aws' but OCR found 'Azure' in labels."
  ],
  "recommendedAction": "Review the flagged items before accepting the report."
}
```

**Comportamento por Status:**

| Status            | STRIDE                | Risco        | Relatório     | PDF           |
| ----------------- | --------------------- | ------------ | ------------- | ------------- |
| `reliable`        | ✅ Gerado             | ✅ Calculado | ✅ Completo   | ✅ Exportável |
| `review_required` | ✅ Gerado com alertas | ✅ Calculado | ✅ Com avisos | ✅ Exportável |
| `rejected`        | ❌ Não                | ❌ Não       | ❌ Não        | ❌ Bloqueado  |

Quando `rejected`:

- Arquitetura detectada permanece acessível (diagnóstico bruto)
- JSON pode ser baixado (para análise interna)
- STRIDE, ameaças, risco e PDF são bloqueados
- `reportSuppressed: true` no response

Essa abordagem **fail-closed** é uma decisão deliberada de segurança: melhor não gerar um relatório enganoso do que gerar um falso positivo de segurança.

---

## 3. MAPEAMENTO STRIDE E GERAÇÃO DE CONTRAMEDIDAS

### 3.1 Catálogo Determinístico de Ameaças

**Responsável:** `backend/stride_engine.py`

O motor STRIDE não usa LLM para gerar ameaças. Todas as regras são explícitas e rastreáveis. Para cada tipo de componente e padrão arquitetural, há um conjunto de ameaças conhecidas com contramedidas associadas.

**Estrutura de uma Ameaça:**

```python
{
    "stride": "Spoofing",              # Categoria STRIDE
    "title": "User identity can be impersonated",
    "severity": "Medium",              # Critical | High | Medium | Low
    "componentId": "user_1",
    "evidence": "User node detected in architecture without explicit MFA requirement.",
    "countermeasures": [
        "Require strong authentication with MFA for privileged flows.",
        "Use short-lived sessions and secure cookie attributes.",
        "Bind sensitive actions to re-authentication."
    ],
    "confidence": 0.85,                # Baseado em detecção + provider
    "securityReferences": [
        {
            "framework": "CWE",
            "id": "CWE-287",
            "title": "Improper Authentication",
            "url": "https://cwe.mitre.org/data/definitions/287.html"
        },
        {
            "framework": "OWASP",
            "id": "A07:2021",
            "title": "Identification and Authentication Failures",
            "url": "https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/"
        }
        // ... CAPEC, MITRE ATT&CK ...
    ],
    "management": {
        "status": "open",              // open | mitigated | accepted | false_positive
        "owner": null,                 // Nome do responsável
        "justification": null,         // Texto da decisão
        "selectedCountermeasure": null,// Qual contramedida foi escolhida
        "mitigationDate": null,        // Quando será mitigada
        "residualRisk": null           // Risco após mitigação
    }
}
```

### 3.2 Regras por Tipo de Componente

**Exemplo 1: Componente `api_gateway`**

```
Ameaça: Spoofing
├─ Evidência: API endpoint detectado sem autenticação explícita
├─ Severidade: High
├─ Contramedidas:
│  ├─ Validar JWT issuer, audience, expiration, signature
│  ├─ Usar OAuth2/OIDC para confiabilidade
│  ├─ Implementar mTLS para service-to-service
│  └─ Least privilege scopes por endpoint
└─ Referências: CWE-287, CAPEC-115, OWASP A07:2021, MITRE T1078

Ameaça: Tampering
├─ Evidência: Payload pode ser alterado antes de chegar ao backend
├─ Severidade: High
├─ Contramedidas:
│  ├─ Validar schema na gateway e no backend
│  ├─ Rejeitar campos inesperados
│  └─ Enforcar content-type restrictions
└─ Referências: CWE-20, CAPEC-153, OWASP A08:2021, MITRE T1565

Ameaça: Denial of Service
├─ Evidência: Endpoint exposto pode ser sobrecarregado
├─ Severidade: High
├─ Contramedidas:
│  ├─ Throttling e quotas
│  ├─ Circuit breakers
│  ├─ Request size limits
│  └─ Alertas de latência e volume anômalo
└─ Referências: CWE-400, CAPEC-125, OWASP API4:2023, MITRE T1499
```

**Exemplo 2: Componente `database`**

```
Ameaça: Information Disclosure
├─ Evidência: Banco de dados pode expor registros sensíveis
├─ Severidade: Critical ⚠️
├─ Contramedidas:
│  ├─ Criptografia em repouso com chaves gerenciadas
│  ├─ Acesso de rede restrito
│  ├─ Least privilege em roles do banco
│  ├─ Masking ou tokenização de dados sensíveis
│  └─ Auditoria de acesso
└─ Referências: CWE-200, CAPEC-118, OWASP A02:2021, MITRE T1530

Ameaça: Tampering
├─ Evidência: Dados podem ser alterados sem controles de integridade
├─ Severidade: High
├─ Contramedidas:
│  ├─ Transações e constraints
│  ├─ Audit trail para tabelas sensíveis
│  ├─ Change history
│  └─ Monitoramento de volume de writes anômalo
└─ Referências: CWE-20, CAPEC-153, OWASP A08:2021, MITRE T1565
```

### 3.3 Matriz de Risco Inerente vs. Residual

Após STRIDE, o motor calcula dois scores:

**Risco Inerente (antes de mitigação):**

```
Fórmula: weighted_sum(severity_weight[ameaça] * confiança[ameaça]) / total_ameaças
Escala: 0-100 (Low / Medium / High / Critical)
```

**Risco Residual (após decisões de mitigação):**

```
Fórmula: weighted_sum(severity_weight[ameaça] * confiança[ameaça] * factor_mitigação) / total_ameaças
Factor de mitigação: 1.0 (open) | 0.5 (mitigated) | 0.1 (accepted)
```

**Exemplo:**

| Ameaça                | Severidade | Confiança | Fator Inerente | Fator Residual  |
| --------------------- | ---------- | --------- | -------------- | --------------- |
| API sem autenticação  | High (8)   | 0.9       | 7.2            | 3.6 (mitigated) |
| DB sem backup         | High (8)   | 0.7       | 5.6            | 0.56 (accepted) |
| Log sem imutabilidade | Medium (5) | 0.6       | 3.0            | 3.0 (open)      |
| **Total**             |            |           | **15.8**       | **7.16**        |

**Interpretação:**

- Risco inerente: 15.8 → **High**
- Risco residual: 7.16 → **Medium**
- Redução: 55% de mitigação implementada

### 3.4 Rastreabilidade de Referências de Segurança

Toda ameaça conecta-se a bases de segurança externas:

- **CWE (Common Weakness Enumeration):** Fraqueza de software subjacente
- **CAPEC (Common Attack Pattern Expression Language):** Padrão de ataque que explora a fraqueza
- **OWASP Top 10 2021:** Top vulnerabilities em aplicações web e APIs
- **MITRE ATT&CK:** Tática e técnica de ataque conhecida

**Exemplo completo:**

```
Ameaça: "Spoofing — User identity can be impersonated"

Rastreabilidade:
├─ Componente: user_1 (tipo: user)
├─ Fluxo relacionado: user_1 → api_1 (sem TLS)
├─ Evidência: Usuário detectado comunicando com API sem evidência de autenticação
├─ Referências:
│  ├─ CWE-287 → Improper Authentication
│  │   URL: https://cwe.mitre.org/data/definitions/287.html
│  ├─ CAPEC-115 → Authentication Bypass
│  │   URL: https://capec.mitre.org/data/definitions/115.html
│  ├─ OWASP-A07:2021 → Identification and Authentication Failures
│  │   URL: https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/
│  └─ MITRE-T1078 → Valid Accounts
│      URL: https://attack.mitre.org/techniques/T1078/
└─ Contramedidas com mapeamento direto a esses controles
```

---

## 4. PIPELINE DE GERAÇÃO DE RELATÓRIO

### 4.1 Formato de Saída: Multicanal

Após STRIDE e RAG, a análise é exportável em três formatos:

#### 4.1.1 JSON Estruturado

Contém grafo completo de arquitetura, todas as ameaças com status de gestão, matriz de risco e metadados de qualidade.

```json
{
  "analysisId": "tl-2026-07-22-abc123",
  "timestamp": "2026-07-22T14:30:00Z",
  "analysisQuality": {
    "status": "review_required",
    "score": 0.82,
    "reasons": ["Possible comparative architecture detected."]
  },
  "architecture": {
    "components": [
      {
        "id": "api_1",
        "name": "API Gateway",
        "type": "api_gateway",
        "provider": "aws",
        "confidence": 0.91,
        "bbox": [120, 80, 220, 180]
      }
    ],
    "flows": [
      {
        "id": "flow_1",
        "from": "user_1",
        "to": "api_1",
        "protocol": "HTTPS",
        "isEncrypted": true,
        "confidence": 0.84
      }
    ]
  },
  "threats": [
    {
      "id": "threat_1",
      "stride": "Spoofing",
      "title": "User identity can be impersonated",
      "severity": "Medium",
      "componentId": "api_1",
      "evidence": "API endpoint without explicit authentication.",
      "countermeasures": ["Require MFA", "Use short-lived sessions"],
      "confidence": 0.85,
      "securityReferences": [
        {
          "framework": "CWE",
          "id": "CWE-287",
          "url": "https://cwe.mitre.org/data/definitions/287.html"
        }
      ],
      "management": {
        "status": "open",
        "owner": null,
        "justification": null
      }
    }
  ],
  "score": {
    "value": 65,
    "label": "High",
    "summary": "Architecture has significant security gaps requiring immediate mitigation."
  },
  "riskComparison": {
    "inherent": { "value": 75, "label": "High" },
    "residual": { "value": 42, "label": "Medium" },
    "reduction": 44
  }
}
```

#### 4.1.2 Markdown Estruturado

Versão legível para documentação e integração em wikis:

```markdown
# Threat Analysis Report

## Architecture Overview

| Metric           | Value |
| ---------------- | ----- |
| Components       | 12    |
| Flows            | 18    |
| Trust Boundaries | 3     |

## Executive Summary

The analyzed architecture contains **18 threats**, with **8 Critical/High severity**. Immediate actions:

1. Implement authentication on exposed APIs
2. Enable encryption on sensitive data flows
3. Configure database backups and monitoring

## Threats Prioritized by Risk

### 1. Database Information Disclosure (Critical)

- **Component:** database_1
- **Severity:** Critical
- **Evidence:** Database detected without encryption at rest
- **Countermeasures:**
  - Enable encryption with managed keys
  - Restrict network access
  - Apply least privilege roles
- **References:** CWE-200, OWASP-A02:2021

[... 11+ ameaças ordenadas por risco ...]
```

#### 4.1.3 PDF Profissional

Gerado por `backend/pdf_report.py` usando ReportLab. Inclui:

1. **Página de Cobertura:** Logo, data, identificador da análise
2. **Sumário Executivo:** Risco inerente vs. residual, recomendações
3. **Matriz de Risco:** Severidade × Status (open/mitigated/accepted/false_positive)
4. **12+ Ameaças Priorizadas:** Cada uma com evidência, contramedidas e referências
5. **Plano de Mitigação:** Roadmap de ações, responsáveis, datas esperadas
6. **Apêndice:** Detalhes técnicos, componentes completos, fluxos

---

## 5. LIMITAÇÕES TÉCNICAS ASSUMIDAS E ENGENHARIA DE PRODUÇÃO

### 5.1 Domain Shift e Generalizacao

O detector foi treinado em 373 imagens de origens específicas (Kaggle + projeto). Isso não significa que funcionará perfeitamente em **todos** os diagramas de arquitetura do mundo.

**Limitações documentadas:**

1. **Diagramas densos:** Linhas muito próximas, componentes sobrepostos ou linhas fragmentadas podem levar a:
   - Fluxos extras (falsos positivos de conectividade)
   - Fluxos ausentes (falsos negativos)
   - Ambiguidade em direção (arrowheads pequenos ou múltiplos possíveis)

2. **Estilos visuais não vistos:** O modelo viu principalmente:
   - Icons: AWS, Azure, GCP, genéricos
   - Layouts: diagrama único, sem comparativas (até os holdouts)
   - Cores e fontes: padrão em ferramentas como Lucidchart, Draw.io, Visio

   **Risco:** Novo estilo visual (ex: estilo customizado Miro, Mural ou design próprio) pode reduzir confiança.

3. **Texto pequeno ou rotacionado:** OCR tem dificuldade com:
   - Labels dentro de ícones minúsculos
   - Texto rotacionado ou em ângulos estranhos
   - Baixo contraste

4. **Componentes fora da taxonomia:** Se o diagrama usar componentes não mapeados (ex: "custom middleware", "IoT gateway", "quantum processor"), o detector falhará ou classificará como a classe mais próxima.

**Evidência no projeto:**

```
Benchmark real (9 imagens de desenvolvimento + 6 blind):
  - F1 de fluxos: 0.4225 (estrutural) a 0.5296 (v15 com arbitragem)
  - Recall tipado: 0.6786
  - Domain shift em Kaggle Subset (9 imagens): mAP50 0.3598 (alarm)
```

### 5.2 Mecanismo de Proteção: Quality Gate e Abstention

Para evitar que análises ruins sejam apresentadas como fatos:

1. **Quality Gate Estrutural:** Valida antes de STRIDE
   - Se `rejected`: Sem ameaças, sem PDF, sem relatório
   - Se `review_required`: Ameaças são geradas com alertas
   - Se `reliable`: Fluxo normal

2. **Abstention e Confiança Calibrada:**
   - Detecções com confiança < 0.90 são abstraídas (não geram ameaças sozinhas)
   - Aparecem em `detectionAlternatives` para revisão
   - OCR conflitante também em alternativas, não substitui silenciosamente

3. **Fail-Closed para PDF:**
   - Se análise é `rejected`, PDF não é gerado
   - Impede relatório enganoso

### 5.3 Transparência sobre Desenvolvimento vs. Generalização

O projeto separa claramente:

- **Desenvolvimento (`development_tuning`):** Resultados usados para ajuste de hiperparâmetros e seleção de estratégia
- **Holdout Prospectivo (`prospective_holdout`):** Resultado selado ANTES da abertura, prova de não viés
- **Holdout Blind Inicial:** 6 imagens anotadas post-hoc, não usadas para treino

**Métrica de Desenvolvimento v15:** F1 0.5296, Recall 0.6786
**Interpretação:** Essa métrica é compartilhada para transparência, mas **não** é apresentada como evidência de generalização universal. A metodologia está documentada em `docs/final-technical-evidence.md`.

### 5.4 Configuração de Confiança e Limiares

O operador pode ajustar:

```bash
# Arquivo: .env
YOLO_MIN_DETECTION_CONFIDENCE=0.30    # Confiança mínima bruta do YOLO
YOLO_CONFIDENCE_THRESHOLD=0.90        # Limiar de aceitação após calibração
FLOW_STRATEGY=legacy                  # ou junction_aware_controlled
```

**Comportamento:**

- Se `YOLO_CONFIDENCE_THRESHOLD` é 0.90: Apenas detecções calibradas > 0.90 geram ameaças
- Se `YOLO_MIN_DETECTION_CONFIDENCE` é 0.30: Até 0.30 bruta é considerada para alternativas
- Esse design permite trade-off entre recall (mais ameaças) e precisão (menos falsos positivos)

### 5.5 Roadmap de Melhoria

Limitações sabidas e próximas iterações:

| Limitação                     | Estratégia de Melhoria                                 |
| ----------------------------- | ------------------------------------------------------ |
| Domain shift em estilos novos | Active learning com mais diagramas reais               |
| Fluxos em diagramas densos    | Classificador supervisionado de arestas                |
| Arrowhead ambíguo             | Calibração separada de direção                         |
| OCR em texto pequeno          | Modelo de OCR treinado ou pre-processamento adaptativo |
| Componentes fora da taxonomia | Extensão de classes (15+) com retraining               |

---

## 6. SEGURANÇA E CONFORMIDADE

### 6.1 Princípios de Design

1. **Zero Trust na Entrada:** Toda entrada é não confiável até validação
2. **Separation of Concerns:** Cada etapa é auditável isoladamente
3. **Fail-Closed:** Melhor não gerar ameaça enganosa do que gerar uma falsa
4. **Local-First:** Sem chamadas remotas obrigatórias
5. **Transparência:** Todas as decisões são rastreáveis

### 6.2 Fronteiras de Confiança na Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                     ThreatLens MVP                           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Entrada Não Confiável (User Upload)                │   │
│  │ - Validação de tipo, tamanho, pixels               │   │
│  │ - Rate limiting, CSP headers                       │   │
│  └──────────────────────────────────────────────────────┘   │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Processamento Local Confiável                       │   │
│  │ - YOLO (modelo treinado verificado)                │   │
│  │ - OCR (Tesseract sandbox)                          │   │
│  │ - OpenCV (sem rede)                                │   │
│  │ - STRIDE engine (determinístico)                   │   │
│  └──────────────────────────────────────────────────────┘   │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Revisão Humana (Fronteira decisória)               │   │
│  │ - Componentes questionáveis                        │   │
│  │ - Fluxos com baixa confiança                       │   │
│  │ - Quality gate warnings                            │   │
│  └──────────────────────────────────────────────────────┘   │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Saída (JSON/PDF/Markdown)                          │   │
│  │ - Rastreável até a origem visual                   │   │
│  │ - Sem dados de treinamento inclusos                │   │
│  │ - Pronto para integração em SOAR/SIEM             │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 6.3 Serviços Remotos Opcionais

Por padrão, **todas** as chamadas remotas estão **desabilitadas**:

```bash
ENABLE_GENERATIVE_REPORTS=false   # Sem Gemini obrigatório
ENABLE_REMOTE_VALIDATION=false    # Sem Groq para validação
ENABLE_VISION_FALLBACK=false      # Sem Gemini Vision fallback
```

Isso significa:

- Detector: ✅ Local
- OCR: ✅ Local (Tesseract)
- STRIDE: ✅ Local (determinístico)
- RAG: ✅ Local (embeddings + lexical fallback)
- PDF: ✅ Local (ReportLab)

Se quiser LLM generativo para enriquecer relatório:

- Deve ativar explicitamente `ENABLE_GENERATIVE_REPORTS=true` **e** fornecer `GEMINI_API_KEY`
- Relatório base permanece determinístico sem isso

---

## 7. ENTREGÁVEIS FINAIS

Este documento é parte de um conjunto de entregáveis para o Hackathon:

| Entregável                  | Localização                   | Formato           | Propósito                           |
| --------------------------- | ----------------------------- | ----------------- | ----------------------------------- |
| **Código-Fonte**            | GitHub                        | `.git` repository | Implementação completa e versionada |
| **README**                  | `README.md`                   | Markdown          | Visão geral, setup e exemplos       |
| **Documentação Técnica**    | Este arquivo                  | Markdown + PDF    | Detalhamento arquitetural           |
| **Documentação de Dataset** | `docs/dataset-*.md`           | Markdown          | Origens, splits, anotações          |
| **Documentação de Modelo**  | `docs/model-*.md`             | Markdown          | Métricas, treino, limitações        |
| **Índice Operacional**      | `docs/submission-evidence.md` | Markdown          | Roteiro de demonstração para banca  |
| **Vídeo Demonstrativo**     | YouTube                       | 15 min video      | Live demo + explicações técnicas    |

---

## 8. CONCLUSÃO

O ThreatLens AI implementa um MVP robusto de modelagem automática de ameaças STRIDE. A solução:

✅ Atende todos os 7 requisitos oficiais do hackathon  
✅ Implementa defesas contra alucinações (quality gate, fail-closed)  
✅ Mantém rastreabilidade completa de detecção até ameaça  
✅ Oferece múltiplos canais de saída (JSON, Markdown, PDF)  
✅ Usa referências externas verificáveis (CWE, CAPEC, OWASP, MITRE)  
✅ Transparência sobre limitações e domain shift  
✅ Código aberto, documentação completa, reprodutível

**Recomendações para uso em produção:**

1. Expandir dataset com mais diagramas reais e estilos visuais
2. Implementar active learning com falsos positivos reais
3. Adicionar classificador supervisionado de existência de arestas
4. Integrar com workflow corporativo de aprovação de riscos
5. Realizar nova avaliação prospectiva com holdout ainda não observado

---

## Links de Referência

- **CWE (Common Weakness Enumeration):** https://cwe.mitre.org
- **CAPEC (Common Attack Pattern Expression Language):** https://capec.mitre.org
- **OWASP Top 10 2021:** https://owasp.org/Top10
- **MITRE ATT&CK:** https://attack.mitre.org
- **STRIDE (Microsoft):** https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats
- **YOLOv8 Documentation:** https://docs.ultralytics.com
- **Tesseract OCR:** https://github.com/UB-Mannheim/tesseract
- **FastAPI:** https://fastapi.tiangolo.com
- **ReportLab (PDF):** https://www.reportlab.com/

---

**Documento preparado em:** Julho de 2026  
**Versão:** 1.0 — Entrega Final  
**Status:** Pronto para Exportação em PDF e Submissão à Banca
