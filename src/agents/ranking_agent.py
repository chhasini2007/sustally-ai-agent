"""
Ranking Agent for Sustally ESG Intelligence Platform
Executes pure SQL query sorting, ranking, sector filtering, and threshold evaluations.
NEVER uses vector embeddings for numerical ordering.
"""

import re
from typing import List, Dict, Any, Optional
import logging
from src.database.metrics_store import MetricsStore
from src.database.company_metadata import CompanyMetadataManager
from src.agents.planner_agent import QueryPlan

logger = logging.getLogger(__name__)

class RankingAgent:
    def __init__(self, metrics_store: Optional[MetricsStore] = None):
        self.metrics_store = metrics_store or MetricsStore()
        self.metadata_mgr = CompanyMetadataManager()

    def rank(self, plan: QueryPlan, retrieved_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ranks structured metrics data based on query plan and optional sector filter.
        """
        metric_key = plan.metric_keys[0] if plan.metric_keys else "scope1_emissions"
        year = plan.years[0] if plan.years else "2024"

        # 1. Resolve Sector Companies
        target_companies = plan.companies
        if plan.sector and not target_companies:
            sector_companies = self.metadata_mgr.get_companies_by_sector(plan.sector)
            if sector_companies:
                target_companies = sector_companies

        # 2. Fetch metrics using the new aliasing/filtering query in MetricsStore
        rows = self.metrics_store.get_filtered_ranking_metrics(
            metric_key=metric_key,
            companies=target_companies,
            year=year,
            threshold_filter=plan.threshold_filter
        )
        
        # If no metrics were found for target year, try other years as fallback
        if not rows and not plan.years:
            for ry in ["2024", "2023", "2025", "2022"]:
                if ry != year:
                    rows = self.metrics_store.get_filtered_ranking_metrics(
                        metric_key=metric_key,
                        companies=target_companies,
                        year=ry,
                        threshold_filter=plan.threshold_filter
                    )
                    if rows:
                        year = ry
                        break
                        
        valid_rows = [r for r in rows if r.get("value") is not None]

        # 3. Fallback to vector database if structured metrics is empty (Task 4)
        used_vector_fallback = False
        if not valid_rows:
            logger.info("Structured SQLite ranking returned 0 metrics. Performing semantic vector retrieval fallback.")
            try:
                from src.database.chroma_store import ChromaStore
                from src.embeddings.embedding_manager import EmbeddingManager
                
                chroma_store = ChromaStore()
                embedding_manager = EmbeddingManager()
                
                query_emb = embedding_manager.get_embedding(plan.query)
                chunks = chroma_store.query_chunks(query_emb, top_k=20)
                
                fallback_rows = []
                for chunk in chunks:
                    content = chunk.get("content", "")
                    meta = chunk.get("metadata", {})
                    company = meta.get("company", "Unknown")
                    yr = meta.get("year", "Unknown")
                    source_file = meta.get("source_file", meta.get("source", "Unknown"))
                    page = meta.get("page", "N/A")
                    
                    val = self._extract_numeric_value(content, plan.query)
                    if val is not None:
                        fallback_rows.append({
                            "company": company,
                            "year": yr,
                            "metric_key": metric_key,
                            "metric_label": f"Semantic Extract: \"{content[:60]}...\"",
                            "value": val,
                            "unit": "%" if ("%" in plan.query or "percent" in plan.query) else "units",
                            "source_file": source_file,
                            "page": page
                        })
                
                # Keep the best/first entry per company
                unique_companies = {}
                for row in fallback_rows:
                    comp = row["company"]
                    if comp not in unique_companies:
                        unique_companies[comp] = row
                
                # Apply threshold filter if any
                valid_rows = list(unique_companies.values())
                if plan.threshold_filter:
                    op = plan.threshold_filter.get("operator")
                    val = plan.threshold_filter.get("value")
                    if op == ">":
                        valid_rows = [r for r in valid_rows if r["value"] > val]
                    elif op == "<":
                        valid_rows = [r for r in valid_rows if r["value"] < val]
                        
                used_vector_fallback = True
            except Exception as e:
                logger.warning(f"Vector fallback for ranking failed: {e}")

        # 4. Determine Sort Order
        ascending = False
        query_lower = plan.query.lower()
        if any(w in query_lower for w in ["lowest", "bottom", "least", "minimum"]):
            ascending = True
        elif any(w in query_lower for w in ["highest", "top", "most", "maximum", "best"]):
            ascending = False
        elif "emissions" in metric_key or "waste" in metric_key or "ltifr" in metric_key:
            ascending = True

        sorted_rows = sorted(valid_rows, key=lambda r: r.get("value", 0.0), reverse=not ascending)

        # 5. Support Top N / Bottom N slicing (Task 6)
        n_match = re.search(r"\b(?:top|bottom)\s*(\d+)\b", query_lower)
        if n_match:
            n_val = int(n_match.group(1))
            sorted_rows = sorted_rows[:n_val]

        ranked_table = []
        for idx, row in enumerate(sorted_rows, start=1):
            ranked_table.append({
                "rank": idx,
                "company": row.get("company"),
                "year": row.get("year"),
                "metric_key": row.get("metric_key") or row.get("metric"),
                "metric_label": row.get("metric_label"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "source_file": row.get("source_file"),
                "page": row.get("page")
            })

        # Debug logging (Task 5)
        from src.database.metrics_store import get_all_aliases
        aliases = get_all_aliases(metric_key)
        logger.info("=== Ranking Agent Diagnostics ===")
        logger.info(f"- Resolved Metric Aliases: {aliases}")
        logger.info(f"- Applied Filters: Sector={plan.sector}, Threshold={plan.threshold_filter}, Year={plan.years or [year]}")
        logger.info(f"- Rows Retrieved: {len(valid_rows)}")
        logger.info(f"- Ranking Count: {len(sorted_rows)}")
        logger.info(f"- Returned Companies: {[r.get('company') for r in sorted_rows]}")
        logger.info(f"- Used Vector Fallback: {used_vector_fallback}")

        return {
            "metric_key": metric_key,
            "year": year,
            "sector": plan.sector,
            "sort_order": "asc" if ascending else "desc",
            "threshold_applied": plan.threshold_filter,
            "ranked_table": ranked_table,
            "top_performer": ranked_table[0] if ranked_table else None,
            "bottom_performer": ranked_table[-1] if ranked_table else None
        }

    def _extract_numeric_value(self, text: str, query: str) -> Optional[float]:
        import re
        query_lower = query.lower()
        text_clean = text.replace(",", "")
        
        if "%" in query_lower or "percent" in query_lower:
            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text_clean)
            if pct_match:
                return float(pct_match.group(1))
                
        patterns = [
            r"(?:scope\s*1|scope1)[^\d]*(\d+(?:\.\d+)?)",
            r"(?:scope\s*2|scope2)[^\d]*(\d+(?:\.\d+)?)",
            r"(?:scope\s*3|scope3)[^\d]*(\d+(?:\.\d+)?)",
            r"(?:emissions|emission)[^\d]*(\d+(?:\.\d+)?)",
            r"(?:water|waste)[^\d]*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*(?:kl|tco2e|tonnes|percentage|%)"
        ]
        for pattern in patterns:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass
                    
        match = re.search(r"\b\d+(?:\.\d+)?\b", text_clean)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                pass
                
        return None

