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
        company: str,
        year: Optional[str] = None,
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        # Compute query embedding
        query_embedding = self.embedding_manager.get_embedding(query)
        
        # Build filter metadata
        filter_metadata = {"company": company}
        if year:
            filter_metadata["year"] = str(year)
            
        # Execute pre-filtered query
        results = self.chroma_store.query_chunks(
            query_embedding=query_embedding,
            filter_metadata=filter_metadata,
            top_k=top_k
        )
        return results
