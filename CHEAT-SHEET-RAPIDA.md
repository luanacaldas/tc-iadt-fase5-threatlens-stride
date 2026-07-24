# 🔧 CHEAT SHEET EXECUTIVA - Referência Rápida

**Documento para impressão/referência rápida durante implementação**

---

## 📋 OS 5 PROBLEMAS CRÍTICOS (P1-P5)

```
┌─ P1: GCP Dataset Fraco
│  Status: GCP nativo insuficiente para treino supervisionado
│  Ação:   gerar GCP sintético + consolidar HF/Kaggle
│  Tempo:  6-8 horas (consolidação + validação)
│
├─ P2: Threshold 0.70 Muito Alto
│  Status: Detecta apenas componentes grandes
│  Ação:   Usar threshold dinâmico em backend/detector.py
│  Código:  _calculate_confidence_threshold(bbox_area, image_area)
│  Tempo:   2 horas (implementar + testar)
│
├─ P3: Sem OCR de Labels
│  Status: Perde 15-25% de contexto (nomes dos componentes)
│  Ação:   Adicionar pytesseract em backend/detector.py
│  Código:  _extract_text_from_box(image_path, bbox)
│  Tempo:   3 horas (implementar + configurar Tesseract)
│
├─ P4: Dataset Desbalanceado
│  Status: Classes raras (queue, monitoring) detectadas mal
│  Ação:   Data augmentation + balanceamento em train_yolo.py
│  Tempo:   6 horas (augmentation + novo treino)
│
└─ P5: Sem Fallback Robusto
   Status: YOLO falha → sem erro tratado
   Ação:   Cascata: YOLO → Gemini Vision → Placeholder
   Código:  analyze_image_endpoint() em backend/main.py
   Tempo:   2 horas (implementar + testar)
```

**TOTAL ESFORÇO P1-P5: 19-21 horas** ✅ **Viável em 1 semana**

---

## 🎯 ROADMAP 7 DIAS (COMPRESS0)

```
DIA 1: P1 (GCP sintético + consolidação HF/Kaggle) + P4 (dataset prep)
DIA 2: P4 (augmentation + treino YOLO)
DIA 3: Treino YOLO (3-6h, em background)
DIA 4: P2 (threshold) + P3 (OCR) + P5 (fallback)
DIA 5: Testes E2E + Debug
DIA 6: P6-P8 (Important fixes) + Polish
DIA 7: Demo Rehearsal + Docs + Backup Plan
```

---

## 🔴 TOP 3 COISAS QUE VÃO QUEBRAR A DEMO

1. **Threshold 0.70** — componentes pequenos não detectados
   - **Fix:** Implementar threshold dinâmico (2h)
   - **Evidência:** Sua arquitetura tem "queue"? Provavelmente falhará.

2. **Dataset pequeno/desbalanceado** — mAP baixo (<0.70)
   - **Fix:** Consolidar HF + Kaggle + GCP sintético (10h)
   - **Evidência:** Se não fizer isso, demo mostra só AWS/Azure e falha em componentes menores

3. **Sem Fallback** — API Gemini falha → aplicação quebra
   - **Fix:** Cascata YOLO → Gemini → Placeholder (2h)
   - **Evidência:** Testando quando API está lenta

**Se consertar esses 3, demo funciona. Ponto.**

---

## ⚡ QUICK FIXES (Copy/Paste)

### Fix P2: Threshold Dinâmico

```python
# backend/detector.py - ADICIONE ISTO:

def _calculate_confidence_threshold(bbox_area: float, image_area: float) -> float:
    size_ratio = bbox_area / image_area if image_area > 0 else 0.01
    if size_ratio > 0.05:
        return 0.75
    elif size_ratio > 0.02:
        return 0.70
    elif size_ratio > 0.01:
        return 0.65
    else:
        return 0.55

# Em detect(), substitua:
if conf < dynamic_threshold:  # em vez de YOLO_CONFIDENCE_THRESHOLD
    continue
```

### Fix P3: OCR

```bash
# Terminal
pip install pytesseract

# Windows: baixe de https://github.com/UB-Mannheim/tesseract/wiki
# Instale em C:\Program Files\Tesseract-OCR\
```

```python
# backend/detector.py - ADICIONE ISTO:

import pytesseract

def _extract_text_from_box(image_path: str, bbox: list[int]) -> str:
    from PIL import Image
    img = Image.open(image_path)
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2 = min(img.width, x2)
    y2 = min(img.height, y2)
    if x2 - x1 < 10 or y2 - y1 < 10:
        return ""
    cropped = img.crop((x1, y1, x2, y2))
    return pytesseract.image_to_string(cropped).strip()
```

### Fix P5: Fallback Robusto

```python
# backend/main.py - substitua analyze_image_endpoint():

@app.post("/analyze/image")
async def analyze_image_endpoint(image: UploadFile = File(...)):
    image_bytes = await image.read()

    # Nível 1: YOLO
    yolo_result = detector.detect(temp_path)
    if yolo_result and yolo_result.get("components"):
        return yolo_result

    # Nível 2: Gemini Vision
    try:
        gemini_result = await _detect_with_timeout(image_bytes, timeout=15)
        if gemini_result:
            return gemini_result
    except:
        pass

    # Nível 3: Placeholder
    return {
        "components": [],
        "flows": [],
        "error": "Both detectors failed",
        "requiresManualInput": True,
    }
```

---

## 📊 MÉTRICAS ESPERADAS (Checklist)

Seu modelo deve ter:

```
✅ mAP > 0.75          (Precision/Recall balanceado)
✅ Latência < 20s       (Image→Report completo)
✅ 0% hallucinations    (Relatório só menciona componentes detectados)
✅ Cobertura tri-cloud  (AWS + GCP + Azure)
✅ 5+ componentes detectados por arquitetura
```

Se algum falha:

| Falha                               | Causa Provável                | Fix                                    |
| ----------------------------------- | ----------------------------- | -------------------------------------- |
| mAP < 0.70                          | Dataset pequeno/desbalanceado | Aumentar dados + augmentation          |
| Latência > 20s                      | RAG ou LLM lento              | Cache RAG + timeout curto              |
| Hallucinations                      | LLM inventando componentes    | Refinar prompt system                  |
| Só AWS/Azure                        | GCP pouco representado        | GCP sintético + consolidação HF/Kaggle |
| Componentes pequenos não detectados | Threshold alto                | Threshold dinâmico                     |

---

## 🔧 ARQUIVOS-CHAVE PARA EDITAR

### Ordem de Prioridade:

1. **backend/detector.py** (P2, P3)
   - Adicionar `_calculate_confidence_threshold()`
   - Adicionar `_extract_text_from_box()`
   - Chamar ambas em `detect()`

2. **backend/main.py** (P5, P9)
   - Substituir `analyze_image_endpoint()`
   - Adicionar cascata de fallback
   - Adicionar timeout

3. **scripts/train_yolo.py** (P4)
   - Mudar augmentation params (line ~75)
   - Adicionar balanceamento de classes

4. **backend/stride_engine.py** (P8)
   - Adicionar `COMPONENT_KNOWLEDGE_AWS`, `_GCP`, `_AZURE`
   - Modificar `_build_component_threats()`

5. **backend/requirements.txt** (P3, web scraping)
   - Adicionar `pytesseract>=0.3.10`
   - Adicionar `aiohttp>=3.8.0`
   - Adicionar `beautifulsoup4>=4.12.0`

---

## 🧪 TESTE RÁPIDO (3 LINHAS)

```bash
# Backend running?
curl http://localhost:8000/health

# YOLO loaded?
# Esperado: {"status": "ok", "yolo_available": true, ...}

# STRIDE engine works?
curl -X POST http://localhost:8000/analyze/json \
  -H "Content-Type: application/json" \
  -d @data/sample-architecture.json
```

---

## 🚨 BACKUP PLANS (Se der Ruim)

### Se YOLO não treina:

```bash
# Use modelo pré-treinado nano
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
python scripts/train_yolo.py --model yolov8n.pt --epochs 10  # Fast fine-tune
```

### Se GCP dataset não encontrado:

```bash
# Use mock data
cp data/sample-architecture.json dataset/mock_gcp.json
echo "Note: Demo uses synthetic GCP architecture"
```

### Se API Gemini/Groq offline:

```bash
# Use fixtures pré-gerados
curl -X POST http://localhost:8000/analyze/json \
  -d @tests/fixtures/expected_output.json
```

### Se tudo quebrar 2h antes de demo:

1. Mostrar código + arquitetura no GitHub
2. Mostrar screenshots/videos pré-gravados
3. Rodar offline com dados de teste preparados
4. Apresentar análise escrita + resultados

---

## 📱 COMANDOS ESSENCIAIS

```bash
# Setup ambiente
python -m venv venv
source venv/Scripts/activate  # Windows
pip install -r backend/requirements.txt

# Treinar modelo
python scripts/train_yolo.py --epochs 100

# Testar detector
python scripts/evaluate_model.py --model models/threatlens-v1/weights/best.pt

# Rodar backend
uvicorn backend.main:app --reload --port 8000

# Rodar frontend
npm start

# Teste local (sem API)
npm run analyze:sample

# Debug STRIDE engine
python -c "from backend.stride_engine import analyze_architecture; import json; print(analyze_architecture(json.load(open('data/sample-architecture.json'))))"
```

---

## 🎯 ANTES DE APRESENTAR (Checklist 30min)

```
CÓDIGO:
[ ] Backend rodando: curl http://localhost:8000/health → OK
[ ] Frontend acessível: http://localhost:4173 → Carrega
[ ] YOLO model loaded: {"yolo_available": true}

DATA:
[ ] Dataset consolidado: train/val/test splits OK
[ ] Modelo treinado: models/threatlens-v1/weights/best.pt existe
[ ] Sample arquiteturas prontas: 3+ exemplos de teste

DEMO:
[ ] Testar pipeline completo (image → JSON → report)
[ ] Latência < 20s confirmada
[ ] Screenshots/vídeos gravados (backup)
[ ] Apresentação offline pronta (PDF)

CREDENCIAIS:
[ ] .env com GEMINI_API_KEY e GROQ_API_KEY
[ ] APIs testadas (não 401 ou 429)
[ ] Internet estável (ou hotspot como backup)

DOCUMENTAÇÃO:
[ ] README.md atualizado
[ ] RESULTS.md com exemplos
[ ] ANALISE-CRITICA-COMPLETA.md incluída
[ ] Código comentado (crítico)
```

---

## 📞 TROUBLESHOOTING RÁPIDO

```
P: "YOLO detecta componentes, mas confidence muito baixa"
R: Threshold dinâmico ativado? Se não: implementar P2

P: "Relatório menciona componentes que não existem na imagem"
R: Alucinação do LLM. Checar system prompt em report.py

P: "Latência muito alta (>20s)"
R: RAG? Cache habilitado? Gemini offline? Testar cada etapa

P: "GCP componentes não reconhecidos"
R: Dataset GCP vazio. Executar web scraping (P1)

P: "Modelo treina mal (mAP < 0.65)"
R: Classes desbalanceadas? Augmentation fraca? Aumentar dataset

P: "Falha ao carregar Tesseract (OCR)"
R: Instalado em C:\Program Files\Tesseract-OCR\ ? Windows?
```

---

## 📈 PROGRESSION CHECKLIST

```
Semana 1:
[ ] P1: GCP dataset coletado (~100 imgs)
[ ] P4: Dataset aumentado via augmentation (~600 imgs)
[ ] ✅ Dataset consolidado tri-cloud pronto

Semana 2:
[ ] P2: Threshold dinâmico implementado
[ ] P3: OCR funcional
[ ] P5: Fallback em cascata
[ ] YOLO treinado com novo dataset
[ ] ✅ Modelo e código pronto

Semana 3:
[ ] P6-P8: Important fixes (escolha 2)
[ ] Testes E2E validam 5 arquiteturas
[ ] Demo ensaiada 3x
[ ] ✅ Tudo pronto para apresentação
```

---

**Imprime isto, deixa à mão, e vai fundo! 🚀**

---

## 🎬 TL;DR (1 Minuto)

**Seu projeto é muito bom. Mas tem 5 bugs críticos:**

1. **Threshold alto** → componentes pequenos não detectados (**Fix: 2h**)
2. **Dataset vazio para GCP** → demo incompleta (**Fix: 8h web scraping**)
3. **Sem OCR** → perde contexto (**Fix: 3h**)
4. **Dataset desbalanceado** → classes raras falhame (**Fix: 6h augmentation + treino**)
5. **Sem fallback** → erro não tratado (**Fix: 2h**)

**Total: 21 horas de trabalho → Demo sólido**

**Prioridade:** P1 (dataset) → P2 (threshold) → P3 (OCR) → P5 (fallback) → Treinar

**Se conseguir isso, você ganha. Ponto.**
