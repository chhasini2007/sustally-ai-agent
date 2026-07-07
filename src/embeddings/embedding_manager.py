from typing import List
from config import settings

class EmbeddingManager:
    _instance = None
    _model = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
        return cls._instance

    def _lazy_load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)

    def get_embedding(self, text: str) -> List[float]:
        self._lazy_load_model()
        return self._model.encode(text).tolist()

    def get_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        if not texts:
            return []
        self._lazy_load_model()
        # Encode with batch size
        return self._model.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()
