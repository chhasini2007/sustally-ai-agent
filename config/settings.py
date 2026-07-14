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
INCOMING_XML_DIR = DATA_DIR / "incoming_xml"

# Create directories if they do not exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
INCOMING_XML_DIR.mkdir(parents=True, exist_ok=True)

# Database and Cache Paths (Automatically use test files when running unit tests)
import sys
IS_TESTING = (
    "unittest" in sys.modules 
    or "pytest" in sys.modules 
    or os.getenv("TESTING") == "true"
    or (len(sys.argv) > 0 and (
        "test_" in os.path.basename(sys.argv[0]) or 
        os.path.basename(sys.argv[0]).startswith("test")
    ))
)

if IS_TESTING:
    METRICS_DB_PATH = str(DATA_DIR / "test_metrics.db")
    CACHE_DB_PATH = str(DATA_DIR / "test_query_cache.sqlite")
    DOC_INDEX_PATH = str(DATA_DIR / "test_document_index.json")
    HISTORY_DB_PATH = str(DATA_DIR / "test_conversation_history.db")
    VECTOR_DB_DIR = PROJECT_ROOT / "test_vector_db"
else:
    METRICS_DB_PATH = str(DATA_DIR / "metrics.db")
    CACHE_DB_PATH = str(DATA_DIR / "query_cache.sqlite")
    DOC_INDEX_PATH = str(DATA_DIR / "document_index.json")
    HISTORY_DB_PATH = str(DATA_DIR / "conversation_history.db")
    VECTOR_DB_DIR = PROJECT_ROOT / "vector_db"

# Embeddings
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_COLLECTION_NAME = "sustainability_reports"

import logging

logger = logging.getLogger(__name__)

# LLM Providers Configuration
raw_provider = os.getenv("LLM_PROVIDER", "ollama")
LLM_PROVIDER = raw_provider.strip().lower()
if LLM_PROVIDER not in ("ollama", "openai"):
    logger.warning(f"Unknown LLM_PROVIDER configured: '{raw_provider}'. Supported values are 'ollama' or 'openai'.")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_CONNECT_TIMEOUT = int(os.getenv("OLLAMA_CONNECT_TIMEOUT", 3))
OLLAMA_READ_TIMEOUT = int(os.getenv("OLLAMA_READ_TIMEOUT", 20))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_CONNECT_TIMEOUT = int(os.getenv("OPENAI_CONNECT_TIMEOUT", 3))
OPENAI_READ_TIMEOUT = int(os.getenv("OPENAI_READ_TIMEOUT", 20))
