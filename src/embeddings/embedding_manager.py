from typing import List
from config import settings

class EmbeddingManager:
    _instance = None
    _model = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
            cls._instance.embedding_available = True
        return cls._instance

    def _lazy_load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
                self.embedding_available = True
            except (ImportError, Exception) as e:
                self.embedding_available = False
                self._model = None

    def get_embedding(self, text: str) -> List[float]:
        self._lazy_load_model()
        if not self.embedding_available:
            raise ImportError("Embeddings are not available due to a local environment issue.")
        return self._model.encode(text).tolist()

    def get_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        if not texts:
            return []
        self._lazy_load_model()
        if not self.embedding_available:
            raise ImportError("Embeddings are not available due to a local environment issue.")
        # Encode with batch size
        return self._model.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()

