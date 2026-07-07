import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw_reports"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_DB_DIR = PROJECT_ROOT / "vector_db"

# Create directories if they do not exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)

# Database and Cache Paths
METRICS_DB_PATH = str(DATA_DIR / "metrics.db")
CACHE_DB_PATH = str(DATA_DIR / "query_cache.sqlite")
DOC_INDEX_PATH = str(DATA_DIR / "document_index.json")
HISTORY_DB_PATH = str(DATA_DIR / "conversation_history.db")

# Embeddings
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_COLLECTION_NAME = "sustainability_reports"

import logging

logger = logging.getLogger(__name__)

# LLM Providers Configuration
raw_provider = os.getenv("LLM_PROVIDER", "ollama")
LLM_PROVIDER = raw_provider.strip().lower()
if LLM_PROVIDER not in ("ollama", "omniroute", "grok"):
    logger.warning(f"Unknown LLM_PROVIDER configured: '{raw_provider}'. Supported values are 'ollama', 'omniroute', or 'grok'.")

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
OMNIROUTE_MODEL = os.getenv("OMNIROUTE_MODEL", "auto")
OMNIROUTE_CONNECT_TIMEOUT = int(os.getenv("OMNIROUTE_CONNECT_TIMEOUT", 3))
OMNIROUTE_READ_TIMEOUT = int(os.getenv("OMNIROUTE_READ_TIMEOUT", 12))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_CONNECT_TIMEOUT = int(os.getenv("OLLAMA_CONNECT_TIMEOUT", 3))
OLLAMA_READ_TIMEOUT = int(os.getenv("OLLAMA_READ_TIMEOUT", 20))

GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_MODEL = os.getenv("GROK_MODEL", "grok-4.1-fast")
GROK_CONNECT_TIMEOUT = int(os.getenv("GROK_CONNECT_TIMEOUT", 3))
GROK_READ_TIMEOUT = int(os.getenv("GROK_READ_TIMEOUT", 20))
