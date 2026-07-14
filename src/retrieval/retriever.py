from typing import List, Dict, Any, Optional
from src.database.chroma_store import ChromaStore
from src.embeddings.embedding_manager import EmbeddingManager

class Retriever:
    def __init__(self):
        self.chroma_store = ChromaStore()
        self.embedding_manager = EmbeddingManager()

    def retrieve_context(
        self,
        query: str,
        company: Optional[str] = None,
        year: Optional[str] = None,
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        # Compute query embedding
        if not self.embedding_manager.embedding_available:
            return []
        query_embedding = self.embedding_manager.get_embedding(query)
        
        # Build filter metadata
        filter_metadata = {}
        if company:
            filter_metadata["company"] = company
        if year:
            try:
                y_int = int(year)
                filter_metadata["year"] = {"$in": [str(y_int), str(y_int + 1)]}
            except ValueError:
                filter_metadata["year"] = str(year)
            
        # Execute query
        results = self.chroma_store.query_chunks(
            query_embedding=query_embedding,
            filter_metadata=filter_metadata if filter_metadata else None,
            top_k=top_k
        )
        return results
