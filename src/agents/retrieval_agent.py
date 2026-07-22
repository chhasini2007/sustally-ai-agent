"""
Retrieval Agent for Sustally ESG Intelligence Platform
Orchestrates structured database queries (SQLite) and hybrid vector search (ChromaDB)
with strict metadata pre-filtering.
"""

from typing import List, Dict, Any, Optional
import logging
from src.database.metrics_store import MetricsStore
from src.database.chroma_store import ChromaStore
from src.agents.planner_agent import QueryPlan

logger = logging.getLogger(__name__)

class RetrievalAgent:
    def __init__(self, metrics_store: Optional[MetricsStore] = None, chroma_store: Optional[ChromaStore] = None):
        self.metrics_store = metrics_store or MetricsStore()
        self.chroma_store = chroma_store or ChromaStore()

    def retrieve(self, plan: QueryPlan) -> Dict[str, Any]:
        """
        Executes retrieval according to the QueryPlan.
        Returns a payload containing structured metrics, narrative excerpts, and metadata.
        """
        structured_metrics: List[Dict[str, Any]] = []
        narrative_chunks: List[Dict[str, Any]] = []

        # 1. Structured Metrics SQL Lookup
        if plan.retrieval_strategy in ["STRUCTURED_DB_ONLY", "HYBRID_METRIC_NARRATIVE"]:
            structured_metrics = self._retrieve_structured_metrics(plan)

        # 2. Vector Narrative Search with Metadata Pre-Filtering
        if plan.retrieval_strategy in ["HYBRID_METRIC_NARRATIVE", "NARRATIVE_VECTOR_ONLY"]:
            narrative_chunks = self._retrieve_narrative_chunks(plan)

        # Fallback to vector search if structured database lookup yielded 0 metrics
        if not structured_metrics and not narrative_chunks:
            logger.info("Structured SQL search returned 0 metrics. Attempting semantic vector search fallback.")
            narrative_chunks = self._retrieve_narrative_chunks(plan)

        logger.info(
            f"Retrieval complete: resolved_companies={plan.companies}, resolved_years={plan.years}, "
            f"resolved_metrics={plan.metric_keys}. "
            f"SQL rows found={len(structured_metrics)}, Vector chunks retrieved={len(narrative_chunks)}"
        )

        return {
            "plan": plan,
            "structured_metrics": structured_metrics,
            "narrative_chunks": narrative_chunks,
            "searched_companies": plan.companies or ["All Indexed Companies"],
            "searched_years": plan.years or ["All Available Years"],
            "searched_metrics": plan.metric_keys
        }

    def _retrieve_structured_metrics(self, plan: QueryPlan) -> List[Dict[str, Any]]:
        results = []

        # Check for metadata listing requests
        if "list_companies" in plan.metric_keys:
            companies = self.metrics_store.get_all_companies()
            return [{"company": c, "metric_key": "list_companies", "metric_label": "Company Register", "value": 1.0, "unit": "entity", "source_file": "system", "page": "N/A", "year": "N/A"} for c in companies]

        if "list_xml_reports" in plan.metric_keys:
            return self.metrics_store.get_xml_metrics()

        # If specific companies and metrics requested
        if plan.companies and plan.metric_keys:
            for comp in plan.companies:
                if plan.years:
                    for yr in plan.years:
                        for key in plan.metric_keys:
                            rows = self.metrics_store.get_metric(comp, yr, key)
                            results.extend(rows)
                else:
                    rows = self.metrics_store.get_metrics_for_companies([comp], plan.metric_keys)
                    results.extend(rows)
        elif plan.companies:
            # Get all metrics for specified companies
            for comp in plan.companies:
                years = plan.years or self.metrics_store.get_company_years(comp)
                if not years:
                    years = ["2024"]
                for yr in years:
                    rows = self.metrics_store.get_company_metrics(comp, yr)
                    if plan.metric_keys:
                        rows = [r for r in rows if r["metric_key"] in plan.metric_keys]
                    results.extend(rows)
        elif plan.metric_keys:
            # Query across all companies for specified metrics
            years = plan.years or ["2024", "2023", "2025"]
            for yr in years:
                for key in plan.metric_keys:
                    rows = self.metrics_store.get_metric_for_all_companies(yr, key)
                    results.extend(rows)

        return results

    def _retrieve_narrative_chunks(self, plan: QueryPlan) -> List[Dict[str, Any]]:
        if not hasattr(self.chroma_store, "collection") or self.chroma_store.collection is None:
            return []

        try:
            from src.embeddings.embedding_manager import EmbeddingManager
            embedder = EmbeddingManager()
            if not getattr(embedder, "embedding_available", False):
                return []

            query_emb = embedder.get_embedding(plan.query)
            where_clause = {}
            if len(plan.companies) == 1:
                where_clause["company"] = plan.companies[0]
            if len(plan.years) == 1:
                where_clause["year"] = plan.years[0]

            return self.chroma_store.query_chunks(
                query_embedding=query_emb,
                filter_metadata=where_clause if where_clause else None,
                top_k=5
            )
        except Exception as e:
            logger.warning(f"Vector retrieval failed or empty: {e}")
            return []
