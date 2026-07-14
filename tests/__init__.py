import os
import shutil
from config import settings

# Override base directories first to use a unique process-specific test directory
# to guarantee no lock contention or compactor errors from previous runs.
settings.VECTOR_DB_DIR = settings.PROJECT_ROOT / f"test_vector_db_{os.getpid()}"

# Override all database and index paths to test-specific files
# to prevent tests from contaminating the production database.
settings.METRICS_DB_PATH = os.path.join(os.path.dirname(settings.METRICS_DB_PATH), "test_metrics.db")
settings.CACHE_DB_PATH = os.path.join(os.path.dirname(settings.CACHE_DB_PATH), "test_query_cache.sqlite")
settings.DOC_INDEX_PATH = os.path.join(os.path.dirname(settings.DOC_INDEX_PATH), "test_document_index.json")
settings.HISTORY_DB_PATH = os.path.join(os.path.dirname(settings.HISTORY_DB_PATH), "test_conversation_history.db")

# Setup and seed the test environment
if True:
    # Clean test directories and files
    for p in [settings.METRICS_DB_PATH, settings.DOC_INDEX_PATH, settings.CACHE_DB_PATH, settings.HISTORY_DB_PATH]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except:
                pass

    # Create the unique clean directory
    settings.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)

    # Seed the test database using MetricsStore
    from src.database.metrics_store import MetricsStore
    store = MetricsStore()
    store.save_metrics_batch([
        {
            "company": "Infosys Limited",
            "year": "2024",
            "metric_key": "dummy_key",
            "metric_label": "Dummy",
            "value": 0.0,
            "unit": "",
            "source_file": "dummy.pdf",
            "page": "1"
        },
        {
            "company": "Tata Consultancy Services Limited",
            "year": "2024",
            "metric_key": "dummy_key",
            "metric_label": "Dummy",
            "value": 0.0,
            "unit": "",
            "source_file": "dummy.pdf",
            "page": "1"
        },
        {
            "company": "Tata Chemicals Limited",
            "year": "2024",
            "metric_key": "dummy_key",
            "metric_label": "Dummy",
            "value": 0.0,
            "unit": "",
            "source_file": "dummy.pdf",
            "page": "1"
        }
    ])
