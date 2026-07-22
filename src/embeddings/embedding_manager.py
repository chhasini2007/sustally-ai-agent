import os
import logging
from typing import List
import requests
from config import settings

logger = logging.getLogger(__name__)

class EmbeddingManager:
    _instance = None
    _model = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
            cls._instance.embedding_available = True
            cls._instance.use_openai_fallback = False
        return cls._instance

    def _lazy_load_model(self):
        if self._model is None and not self.use_openai_fallback:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
                self.embedding_available = True
                self.use_openai_fallback = False
            except (ImportError, Exception) as e:
                logger.warning(
                    f"Local embedding model '{settings.EMBEDDING_MODEL}' failed to load "
                    f"(Exception: {type(e).__name__}: {e}). "
                    f"Checking for OpenAI API Key as a fallback..."
                )
                if os.getenv("OPENAI_API_KEY"):
                    logger.info("OPENAI_API_KEY is available. Activating OpenAI Embeddings fallback.")
                    self.embedding_available = True
                    self.use_openai_fallback = True
                    self._model = None
                else:
                    logger.error("No OPENAI_API_KEY found. Embeddings are completely disabled.")
                    self.embedding_available = False
                    self.use_openai_fallback = False
                    self._model = None

    def _get_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
            
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": "text-embedding-3-small",
            "input": texts
        }
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        # Sort embeddings by their index to ensure they match input order
        embeddings_data = data.get("data", [])
        embeddings_data_sorted = sorted(embeddings_data, key=lambda x: x.get("index", 0))
        return [item.get("embedding") for item in embeddings_data_sorted]

    def get_embedding(self, text: str) -> List[float]:
        self._lazy_load_model()
        if not self.embedding_available:
            raise ImportError("Embeddings are not available due to a local environment issue.")
        if self.use_openai_fallback:
            res = self._get_openai_embeddings([text])
            return res[0] if res else []
        return self._model.encode(text).tolist()

    def get_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        if not texts:
            return []
        self._lazy_load_model()
        if not self.embedding_available:
            raise ImportError("Embeddings are not available due to a local environment issue.")
        if self.use_openai_fallback:
            return self._get_openai_embeddings(texts)
        # Encode with batch size
        return self._model.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()


