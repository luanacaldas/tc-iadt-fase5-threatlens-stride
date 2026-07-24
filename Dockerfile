FROM node:20-bookworm-slim

LABEL org.opencontainers.image.title="ThreatLens AI" \
      org.opencontainers.image.description="Offline STRIDE threat modeling from architecture diagrams" \
      org.opencontainers.image.version="1.0.0-mvp"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHON_EXECUTABLE=/usr/bin/python3 \
    BACKEND_HOST=127.0.0.1 \
    FLOW_STRATEGY=legacy \
    HF_HOME=/opt/huggingface \
    ENABLE_GENERATIVE_REPORTS=false \
    ENABLE_REMOTE_VALIDATION=false \
    ENABLE_VISION_FALLBACK=false

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements-lock.txt /app/backend/requirements-lock.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir -r backend/requirements-lock.txt

COPY . /app

# Build the vector index and cache the embedding model while network is available.
RUN HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python3 -c \
    "from backend import rag; rag.initialize_rag(); assert rag._get_collection().count() > 0"

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

EXPOSE 4173
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:4173/api/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["npm", "run", "dev"]
