import chromadb
from typing import List, Dict, Any, Optional
from config import settings

class ChromaStore:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ChromaStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, persist_dir: str = str(settings.VECTOR_DB_DIR)):
        if self._initialized:
            return
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME
        )
        self._initialized = True

    def add_chunks(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]]
    ):
        if not ids:
            return
        # Add to collection
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def query_chunks(
        self,
        query_embedding: List[float],
        filter_metadata: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        # Map filter_metadata to Chroma's filter format
        where_clause = {}
        if filter_metadata:
            filters = []
            for k, v in filter_metadata.items():
                if v is not None:
                    filters.append({k: {"$eq": v}})
            
            if len(filters) == 1:
                where_clause = filters[0]
            elif len(filters) > 1:
                where_clause = {"$and": filters}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause if where_clause else None
        )

        # Reformat results for easy consumption
        formatted = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            ids = results["ids"][0]
            distances = results.get("distances", [[]])[0]
            
            for i in range(len(docs)):
                formatted.append({
                    "id": ids[i],
                    "content": docs[i],
                    "metadata": metas[i],
                    "distance": distances[i] if i < len(distances) else None
                })
        return formatted

    def delete_company_year(self, company: str, year: str):
        self.collection.delete(
            where={"$and": [{"company": {"$eq": company}}, {"year": {"$eq": year}}]}
        )
