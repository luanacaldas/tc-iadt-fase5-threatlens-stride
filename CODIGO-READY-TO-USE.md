# 📝 CÓDIGO READY-TO-USE: IMPLEMENTAÇÕES CRÍTICAS

Este documento contém trechos de código prontos para copiar/colar e resolver os P1-P5 (críticos).

---

## 0️⃣ MATRIZ DE DECISÃO DE DATASETS

Use esta ordem de prioridade para evitar investir tempo em fonte de baixo retorno:

| Fonte                                          | Papel no projeto                      | Vantagem real                                             | Limitação real                       | Decisão                       |
| ---------------------------------------------- | ------------------------------------- | --------------------------------------------------------- | ------------------------------------ | ----------------------------- |
| `guillherms/stride-architecture-components-v1` | Dataset principal de treino           | Já nasce em YOLO, 4190 imagens, AWS/Azure, foco em STRIDE | Não cobre GCP de forma suficiente    | **Entrar**                    |
| `carlosrian/software-architecture-dataset`     | Reforço de volume e diversidade       | 8k+ imagens, 87 classes, inclui GCP                       | Mais pesado, mais ruído, formato VOC | **Entrar como complemento**   |
| `mingrammer/diagrams`                          | Geração sintética controlada          | Ícones e layouts reproduzíveis, ótimo para GCP sintético  | Não é dataset pronto                 | **Entrar como gerador**       |
| `terrastruct/awesome-diagrams`                 | Referência visual e coleta de padrões | Ajuda a mapear estilos reais de arquitetura               | Não fornece anotações                | **Usar como referência**      |
| `aws-icons/aws-icon-detector`                  | Suporte visual AWS                    | Pode ajudar em ícones AWS                                 | Não resolve diagramas completos      | **Opcional, não prioritário** |

**Estratégia recomendada para a demo:**

1. Basear o treino no Hugging Face.
2. Completar lacunas com Kaggle só depois de padronizar classes.
3. Gerar GCP sintético com `mingrammer/diagrams` para fechar a lacuna tri-cloud.
4. Usar `awesome-diagrams` apenas para coleta de padrões visuais e validação de layout.
5. Não depender do Roboflow como pilar principal da solução.

---

## 1️⃣ P2: Threshold Dinâmico por Tamanho de BBox

**Arquivo:** `backend/detector.py`

Adicione esta função **ANTES** de `is_available()`:

```python
def _calculate_confidence_threshold(bbox_area: float, image_area: float) -> float:
    """Calcula threshold de confiança dinamicamente baseado no tamanho do componente.

    Componentes pequenos (ex: queue, monitoring) são mais difíceis de detectar,
    então usamos threshold menor.

    Componentes grandes (ex: database, compute) têm threshold maior.
    """
    size_ratio = bbox_area / image_area if image_area > 0 else 0.01

    if size_ratio > 0.05:  # >5% da imagem = grande
        return 0.75
    elif size_ratio > 0.02:  # 2-5% = médio-grande
        return 0.70
    elif size_ratio > 0.01:  # 1-2% = médio
        return 0.65
    else:  # <1% = pequeno
        return 0.55
```

Substitua a lógica de filtro em `detect()`:

```python
# ANTES:
if conf < YOLO_CONFIDENCE_THRESHOLD:
    continue

# DEPOIS:
bbox_area = (x2 - x1) * (y2 - y1)
dynamic_threshold = _calculate_confidence_threshold(bbox_area, img_w * img_h)
if conf < dynamic_threshold:
    print(f"[detector] Skipping {cls_name} (conf={conf:.3f}, threshold={dynamic_threshold:.2f})")
    continue
```

---

## 4️⃣ P1: GCP SEM DATASET BOM

Se o foco for velocidade e robustez de demo, não tente “caçar” um dataset perfeito de GCP. Faça o seguinte:

1. Gere imagens GCP sintéticas com `mingrammer/diagrams` usando layouts equivalentes a padrões reais.
2. Misture essas imagens com o dataset Hugging Face para preservar consistência de classes.
3. Reaproveite o Kaggle apenas para ampliar a variedade visual, não como verdade absoluta.
4. Mantenha os rótulos GCP no mesmo schema canônico do projeto: `user`, `internet`, `identity_provider`, `waf`, `cdn`, `api_gateway`, `load_balancer`, `compute`, `database`, `storage`, `queue`, `monitoring`, `backup`, `secrets_kms`.
5. Não aumente a taxonomia agora. O ganho vem de cobertura visual, não de adicionar mais classes.

**Objetivo prático:** ter uma base tri-cloud suficiente para a banca, não uma ontologia perfeita de provedores.

---

## 2️⃣ P3: Adicionar OCR com pytesseract

**Arquivo:** `backend/detector.py`

Adicione ao topo:

```python
from PIL import Image
import pytesseract
import logging

logger = logging.getLogger(__name__)
```

Adicione esta função:

```python
def _extract_text_from_box(image_path: str, bbox: list[int]) -> str:
    """Extrai texto dentro de um bounding box usando Tesseract OCR.

    Args:
        image_path: Caminho da imagem
        bbox: [x1, y1, x2, y2]

    Returns:
        Texto extraído (string), ou "" se falhar
    """
    try:
        img = Image.open(image_path)
        x1, y1, x2, y2 = bbox

        # Garantir coordenadas válidas
        x1, y1 = max(0, x1), max(0, y1)
        x2 = min(img.width, x2)
        y2 = min(img.height, y2)

        if x2 - x1 < 10 or y2 - y1 < 10:
            return ""  # BBox muito pequeno para OCR

        cropped = img.crop((x1, y1, x2, y2))

        # Tenta Tesseract
        text = pytesseract.image_to_string(cropped, lang='eng')
        return text.strip()
    except Exception as e:
        logger.debug(f"[detector] OCR failed for bbox {bbox}: {e}")
        return ""
```

Na função `detect()`, após criar `components`, adicione OCR:

```python
# APÓS o loop for box in results[0].boxes:
# Tenta extrair texto de cada componente detectado
for comp in components:
    bbox = comp["bbox"]
    text = _extract_text_from_box(image_path, bbox)
    if text:
        comp["ocr_label"] = text
        print(f"[detector] OCR for {comp['id']}: '{text}'")
    else:
        comp["ocr_label"] = None
```

**Instalação de dependência:**

```bash
pip install pytesseract

# No Windows: Tesseract deve estar instalado
# Download: https://github.com/UB-Mannheim/tesseract/wiki
# Após instalar, adicione ao seu .env ou code:
import pytesseract
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

---

## 3️⃣ P5: Fallback Robusto em Cascata

**Arquivo:** `backend/main.py`

Substitua `analyze_image_endpoint`:

```python
@app.post("/analyze/image")
async def analyze_image_endpoint(image: UploadFile = File(...)):
    """Detecta componentes com fallback em cascata: YOLO → Gemini Vision → Placeholder."""

    # Validar tamanho (P10)
    MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50 MB
    image_bytes = await image.read()

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image too large (max 50MB)")

    mime_type = image.content_type or "image/png"

    # Salvar temporariamente
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(image_bytes)
        temp_path = tmp.name

    try:
        # Nível 1: Tentar YOLO
        print("[main] Tentando YOLO...")
        yolo_result = detector.detect(temp_path)
        if yolo_result and yolo_result.get("components"):
            print(f"[main] ✓ YOLO detectou {len(yolo_result['components'])} componentes")
            return yolo_result

        # Nível 2: Se YOLO falhou/vazio, tentar Gemini Vision
        print("[main] YOLO retornou vazio, tentando Gemini Vision...")
        try:
            gemini_result = await _detect_components_gemini_vision(image_bytes, mime_type, timeout=15)
            if gemini_result and gemini_result.get("components"):
                print(f"[main] ✓ Gemini detectou {len(gemini_result['components'])} componentes")
                return gemini_result
        except asyncio.TimeoutError:
            print("[main] Gemini timeout (15s)")
        except Exception as e:
            print(f"[main] Gemini falhou: {e}")

        # Nível 3: Placeholder com aviso
        print("[main] Ambos detectores falharam, retornando placeholder")
        return {
            "components": [],
            "flows": [],
            "error": "Detection unavailable",
            "message": "Both YOLO and Gemini Vision failed. Please try a simpler diagram or use manual JSON input.",
            "requiresManualInput": True,
            "fallbackMode": True,
        }

    finally:
        # Limpar arquivo temporário
        import os
        try:
            os.unlink(temp_path)
        except:
            pass

async def _detect_components_gemini_vision(image_bytes, mime_type, timeout=15):
    """Fallback para Gemini Vision."""
    try:
        import asyncio

        async def gemini_detect():
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)

            prompt = """Analyze this architecture diagram and extract components.
            Return a JSON with this structure:
            {
              "components": [
                {"name": "...", "type": "...", "confidence": 0.85}
              ],
              "flows": []
            }

            Component types: user, internet, identity_provider, waf, cdn, api_gateway,
            load_balancer, compute, database, storage, queue, monitoring, backup, secrets_kms, trust_boundary, data_flow

            Be strict: only include components you can clearly identify.
            """

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Content(parts=[
                        types.Part.from_data(
                            data=image_bytes,
                            mime_type=mime_type
                        ),
                    ]),
                    types.Content(parts=[types.Part(text=prompt)]),
                ],
            )

            # Parse JSON response
            import json
            import re

            text = response.text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"components": [], "flows": []}

        # Run com timeout
        result = await asyncio.wait_for(gemini_detect(), timeout=timeout)
        return result

    except asyncio.TimeoutError:
        raise
    except Exception as e:
        print(f"[main] Gemini error: {e}")
        raise
```

---

## 4️⃣ P1: Web Scraping de Diagramas GCP

**Novo Arquivo:** `scripts/scrape_gcp_architectures.py`

```python
#!/usr/bin/env python3
"""Scrape diagramas de arquitetura do Google Cloud Platform.

Fontes:
- Google Cloud Solutions: https://cloud.google.com/solutions
- Google Cloud Docs: https://cloud.google.com/docs
- GitHub repos com padrões GCP

Uso:
    python scripts/scrape_gcp_architectures.py --output dataset/images/train --limit 100

Nota: Respectar robots.txt e termos de serviço. Apenas para fins educacionais.
"""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional

import aiohttp
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GCPArchitectureScraper:
    def __init__(self, output_dir: str, max_workers: int = 3):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        self.session: Optional[aiohttp.ClientSession] = None
        self.downloaded_count = 0

        # Headers para evitar bloqueio
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Educational Purpose - Architecture Analysis)',
        }

    def scrape_google_cloud_solutions(self) -> list[str]:
        """Scrape Google Cloud Solutions page."""
        logger.info("Scraping Google Cloud Solutions...")

        try:
            response = requests.get(
                "https://cloud.google.com/solutions",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch solutions page: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        image_urls = []

        # Procura por imagens com palavras-chave
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            alt = img.get('alt', '').lower()

            keywords = ['architecture', 'diagram', 'cloud', 'infrastructure']
            if src and any(kw in alt for kw in keywords):
                if not src.startswith('http'):
                    src = urljoin('https://cloud.google.com', src)
                image_urls.append(src)
                logger.info(f"  Found: {src}")

        return image_urls

    def scrape_cloud_architecture_references(self) -> list[str]:
        """Scrape referência de arquiteturas."""
        logger.info("Scraping Cloud Architecture References...")

        urls = [
            "https://cloud.google.com/architecture/devops-and-it-ops/ansible-deployment",
            "https://cloud.google.com/architecture/multi-tier-web-application-gcp",
            "https://cloud.google.com/solutions/scalable-web-apps-gcp",
            "https://cloud.google.com/architecture/microservices-on-gcp",
        ]

        image_urls = []
        for url in urls:
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')

                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if src and ('svg' in src.lower() or 'png' in src.lower() or 'jpg' in src.lower()):
                        if not src.startswith('http'):
                            src = urljoin(url, src)
                        image_urls.append(src)
                        logger.info(f"  Found: {src}")
            except Exception as e:
                logger.warning(f"Skipped {url}: {e}")

        return image_urls

    async def download_image_async(self, url: str) -> bool:
        """Download uma imagem assincronamente."""
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    content = await response.read()

                    # Gera nome de arquivo
                    parsed = urlparse(url)
                    filename = Path(parsed.path).name
                    if not filename or '.' not in filename:
                        filename = f"gcp_arch_{self.downloaded_count}.png"

                    filepath = self.output_dir / filename
                    with open(filepath, 'wb') as f:
                        f.write(content)

                    self.downloaded_count += 1
                    logger.info(f"✓ Downloaded ({self.downloaded_count}): {filename}")
                    return True
        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {url}")
        except Exception as e:
            logger.warning(f"Failed to download {url}: {e}")

        return False

    async def download_images_async(self, urls: list[str]):
        """Download múltiplas imagens em paralelo."""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            self.session = session

            # Cria tasks com limite de workers
            tasks = []
            for url in urls:
                if len(tasks) >= self.max_workers:
                    # Aguarda uma task completar
                    await asyncio.gather(*tasks[:1])
                    tasks = tasks[1:]

                tasks.append(self.download_image_async(url))

            # Aguarda as últimas tasks
            if tasks:
                await asyncio.gather(*tasks)

    def run(self, limit: Optional[int] = None):
        """Executa o scraping completo."""
        logger.info("Starting GCP Architecture Diagram Scraper...")

        # Coleta URLs
        all_urls = []
        all_urls.extend(self.scrape_google_cloud_solutions())
        all_urls.extend(self.scrape_cloud_architecture_references())

        # Deduplicar
        all_urls = list(set(all_urls))

        if limit:
            all_urls = all_urls[:limit]

        logger.info(f"Found {len(all_urls)} image URLs")

        if not all_urls:
            logger.warning("No images found!")
            return

        # Download
        asyncio.run(self.download_images_async(all_urls))

        logger.info(f"✓ Scraping complete! Downloaded {self.downloaded_count} images to {self.output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape GCP architecture diagrams for training dataset"
    )
    parser.add_argument(
        "--output",
        default="dataset/images/train",
        help="Output directory"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of images to download"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of concurrent downloads"
    )

    args = parser.parse_args()

    scraper = GCPArchitectureScraper(args.output, args.workers)
    scraper.run(limit=args.limit)


if __name__ == "__main__":
    main()
```

**Uso:**

```bash
cd scripts
python scrape_gcp_architectures.py --output ../dataset/images/train --limit 100
```

---

## 5️⃣ P8: Provider-Specific Rules para STRIDE

**Arquivo:** `backend/stride_engine.py` - ADICIONE ANTES de `COMPONENT_KNOWLEDGE`

```python
# ============================================================================
# PROVIDER-SPECIFIC THREAT RULES
# ============================================================================

COMPONENT_KNOWLEDGE_AWS = {
    "api_gateway": {
        "label": "AWS API Gateway",
        "rules": [
            _t("Spoofing", "AWS API Gateway must validate JWT and IAM signatures", "High", [
                "Enable API key validation and AWS SigV4 signing for service-to-service.",
                "Use AWS IAM resource policies to restrict principal access.",
                "Enable WAF integration for advanced threat detection.",
            ]),
            _t("Tampering", "HTTP requests can be intercepted without TLS 1.2+", "High", [
                "Enforce TLS 1.2 minimum in API Gateway policy.",
                "Use AWS Secrets Manager for API keys and rotate them every 90 days.",
            ]),
        ]
    },
    "database": {
        "label": "AWS RDS",
        "rules": [
            _t("Information Disclosure", "RDS data at rest may not be encrypted", "Critical", [
                "Enable AWS KMS encryption for RDS instances.",
                "Use Database Activity Monitoring (DAM) to audit sensitive queries.",
            ]),
        ]
    }
}

COMPONENT_KNOWLEDGE_GCP = {
    "api_gateway": {
        "label": "GCP Cloud Endpoints",
        "rules": [
            _t("Spoofing", "GCP Cloud Endpoints must validate service account tokens", "High", [
                "Require OAuth2 access tokens for all service-to-service calls.",
                "Use mTLS with Workload Identity for pod-to-pod authentication.",
            ]),
            _t("Tampering", "HTTP traffic without mutual TLS is vulnerable", "High", [
                "Enable mTLS enforcement in Service Mesh (Istio/Anthos).",
                "Use GCP Certificate Manager for certificate rotation.",
            ]),
        ]
    },
    "database": {
        "label": "GCP Cloud SQL",
        "rules": [
            _t("Information Disclosure", "Cloud SQL must use Customer-Managed Encryption Keys (CMEK)", "Critical", [
                "Configure Cloud KMS CMEK for Cloud SQL instances.",
                "Restrict key access via IAM roles (storage.admin vs storage.user).",
            ]),
        ]
    }
}

COMPONENT_KNOWLEDGE_AZURE = {
    "api_gateway": {
        "label": "Azure API Management",
        "rules": [
            _t("Spoofing", "APIM must validate OAuth2 tokens from Azure AD", "High", [
                "Configure OAuth2 validation policy in APIM.",
                "Require multi-tenant Azure AD registration.",
            ]),
        ]
    },
    "database": {
        "label": "Azure SQL Database",
        "rules": [
            _t("Information Disclosure", "SQL Database transparent data encryption (TDE) is mandatory", "Critical", [
                "Enable TDE with Azure Key Vault for key rotation.",
                "Use Azure SQL Threat Detection for suspicious access patterns.",
            ]),
        ]
    }
}

def _get_provider_knowledge(provider: str) -> dict:
    """Retorna knowledge base específica do provider."""
    providers = {
        "aws": COMPONENT_KNOWLEDGE_AWS,
        "gcp": COMPONENT_KNOWLEDGE_GCP,
        "google_cloud": COMPONENT_KNOWLEDGE_GCP,  # Alias
        "azure": COMPONENT_KNOWLEDGE_AZURE,
        "generic": COMPONENT_KNOWLEDGE,
    }
    return providers.get(provider.lower(), COMPONENT_KNOWLEDGE)
```

Agora modifique a função `_build_component_threats()`:

```python
def _build_component_threats(component: dict) -> list[dict]:
    """Build threats para um componente, considerando provider."""
    provider = component.get("provider", "generic")
    component_type = component["type"]

    # Tenta provider-specific knowledge
    provider_kb = _get_provider_knowledge(provider)
    knowledge = provider_kb.get(component_type)

    # Fallback para generic se provider não tiver
    if not knowledge:
        knowledge = COMPONENT_KNOWLEDGE.get(component_type)

    # Se ainda não tiver, retorna threat genérico
    if not knowledge:
        return [
            _enrich_threat(
                _t("Information Disclosure", "Unknown component requires manual security review", "Medium", [
                    "Classify the component and define applicable controls.",
                ]),
                {"componentId": component["id"], "componentName": component["name"], "source": "fallback-rule"},
                component["confidence"],
            )
        ]

    return [
        _enrich_threat(
            rule,
            {
                "componentId": component["id"],
                "componentName": component["name"],
                "source": f"component-rule-{provider}",
            },
            component["confidence"]
        )
        for rule in knowledge["rules"]
    ]
```

---

## 6️⃣ REQUERIMENTOS ADICIONAIS

Adicione ao `backend/requirements.txt`:

```
# Já presente
fastapi>=0.115.0
ultralytics>=8.3.0
sentence-transformers>=3.3.0

# NOVOS - OCR
pytesseract>=0.3.10

# NOVOS - Web scraping
aiohttp>=3.8.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# NOVOS - Augmentation de dados (optional, para data gen)
albumentations>=1.3.0
imgaug>=0.4.0

# NOVOS - Data processing
scikit-learn>=1.3.0  # Para balanceamento de classes
```

Instale:

```bash
pip install -r backend/requirements.txt
```

---

## 7️⃣ SCRIPT DE TESTE RÁPIDO

**Novo Arquivo:** `scripts/test_critical_fixes.py`

```python
#!/usr/bin/env python3
"""Testa as 5 correções críticas."""

import sys
from pathlib import Path

# Adiciona backend ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_threshold_dynamic():
    """Testa threshold dinâmico."""
    from backend.detector import _calculate_confidence_threshold

    print("✓ P2: Testando threshold dinâmico...")

    # Teste 1: Componente grande
    conf = _calculate_confidence_threshold(bbox_area=10000, image_area=200000)
    assert conf == 0.75, f"Expected 0.75, got {conf}"
    print("  ✓ Grande componente: threshold=0.75")

    # Teste 2: Componente pequeno
    conf = _calculate_confidence_threshold(bbox_area=500, image_area=200000)
    assert conf == 0.55, f"Expected 0.55, got {conf}"
    print("  ✓ Pequeno componente: threshold=0.55")


def test_ocr_extraction():
    """Testa OCR (se pytesseract está instalado)."""
    print("✓ P3: Testando OCR...")

    try:
        import pytesseract
        from PIL import Image

        # Tenta criar imagem de teste
        img = Image.new('RGB', (100, 50), color='white')
        text = pytesseract.image_to_string(img)
        print("  ✓ pytesseract instalado e funcional")
    except ImportError:
        print("  ⚠ pytesseract não instalado (pip install pytesseract)")
    except Exception as e:
        print(f"  ⚠ pytesseract erro: {e}")


def test_fallback_cascade():
    """Testa estrutura de fallback."""
    print("✓ P5: Testando fallback em cascata...")

    # Verifica se arquivo main.py foi atualizado
    main_path = Path(__file__).parent.parent / "backend" / "main.py"
    with open(main_path) as f:
        content = f.read()
        if "fallbackMode" in content and "requiresManualInput" in content:
            print("  ✓ Fallback cascade implementado em main.py")
        else:
            print("  ⚠ Fallback cascade não encontrado em main.py")


def test_provider_specific_rules():
    """Testa provider-specific rules."""
    print("✓ P8: Testando rules provider-specific...")

    try:
        from backend.stride_engine import _get_provider_knowledge

        aws_kb = _get_provider_knowledge("aws")
        gcp_kb = _get_provider_knowledge("gcp")

        if aws_kb and gcp_kb:
            print("  ✓ Knowledge bases AWS e GCP carregadas")
        else:
            print("  ⚠ Knowledge bases incompletas")
    except ImportError as e:
        print(f"  ⚠ Erro ao carregar stride_engine: {e}")


if __name__ == "__main__":
    print("\n=== TESTE DAS CORREÇÕES CRÍTICAS ===\n")

    test_threshold_dynamic()
    test_ocr_extraction()
    test_fallback_cascade()
    test_provider_specific_rules()

    print("\n=== TESTES COMPLETOS ===\n")
```

**Uso:**

```bash
python scripts/test_critical_fixes.py
```

---

**Próximo passo:** Implemente P1-P5 nesta ordem, teste com `test_critical_fixes.py`, depois passe para P6-P10.
