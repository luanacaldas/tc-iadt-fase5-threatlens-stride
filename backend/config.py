import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSION_PATH = PROJECT_ROOT / "VERSION"

# Carrega .env da raiz do projeto (um nível acima de /backend)
load_dotenv(PROJECT_ROOT / ".env")


def _read_app_version() -> str:
    if not VERSION_PATH.is_file():
        raise RuntimeError("Required VERSION file is missing")
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    if not version:
        raise RuntimeError("VERSION file is empty")
    return version


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
APP_VERSION: str = _read_app_version()
ENABLE_GENERATIVE_REPORTS: bool = _env_flag("ENABLE_GENERATIVE_REPORTS")
ENABLE_REMOTE_VALIDATION: bool = _env_flag("ENABLE_REMOTE_VALIDATION")
ENABLE_VISION_FALLBACK: bool = _env_flag("ENABLE_VISION_FALLBACK")
FLOW_STRATEGY: str = os.getenv("FLOW_STRATEGY", "legacy").strip().lower()
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
YOLO_MODEL_PATH: str = os.getenv(
    "YOLO_MODEL_PATH",
    "models/threatlens-hybrid-v2/weights/best.pt",
)
YOLO_CONFIDENCE_THRESHOLD: float = float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.70"))
YOLO_MIN_DETECTION_CONFIDENCE: float = float(os.getenv("YOLO_MIN_DETECTION_CONFIDENCE", "0.35"))
YOLO_CALIBRATION_PATH: str = os.getenv(
    "YOLO_CALIBRATION_PATH",
    "models/component-confidence-calibration.json",
)
TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "")
CORS_ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://127.0.0.1:4173,http://localhost:4173",
    ).split(",")
    if origin.strip()
]
MAX_IMAGE_SIZE: int = int(os.getenv("MAX_IMAGE_SIZE_MB", "25")) * 1024 * 1024
MAX_IMAGE_PIXELS: int = int(os.getenv("MAX_IMAGE_PIXELS", "40000000"))
MAX_JSON_SIZE: int = int(os.getenv("MAX_JSON_SIZE_MB", "2")) * 1024 * 1024
MAX_COMPONENTS: int = int(os.getenv("MAX_COMPONENTS", "200"))
MAX_FLOWS: int = int(os.getenv("MAX_FLOWS", "1000"))
MAX_TRUST_BOUNDARIES: int = int(os.getenv("MAX_TRUST_BOUNDARIES", "100"))
MAX_FIELD_LENGTH: int = int(os.getenv("MAX_FIELD_LENGTH", "300"))
MAX_REPORT_THREATS: int = int(os.getenv("MAX_REPORT_THREATS", "500"))

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"

KNOWLEDGE_DIR: Path = Path(__file__).parent / "knowledge"
CHROMA_DB_DIR: Path = Path(__file__).parent / "chroma_db"

RAG_COLLECTION_NAME = "threatlens_knowledge"
RAG_TOP_K = 6
RAG_EMBEDDING_MODEL: str = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
