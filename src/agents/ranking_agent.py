"""
Ranking Agent for Sustally ESG Intelligence Platform
Executes pure SQL query sorting, ranking, sector filtering, and threshold evaluations.
NEVER uses vector embeddings for numerical ordering.
"""

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

        # Sector Filtering
        target_companies = plan.companies
        if plan.sector and not target_companies:
            sector_companies = self.metadata_mgr.get_companies_by_sector(plan.sector)
            if sector_companies:
                target_companies = sector_companies

        # Fetch metrics across target companies or all companies
        if target_companies:
            rows = self.metrics_store.get_metrics_for_companies(target_companies, [metric_key])
            if plan.years:
                rows = [r for r in rows if str(r.get("year")) in plan.years]
            retrieved_metrics = rows
        elif not retrieved_metrics or len(set(m.get("company") for m in retrieved_metrics)) < 2:
            all_rows = self.metrics_store.get_metric_for_all_companies(year, metric_key)
            if all_rows:
                retrieved_metrics = all_rows
            else:
                for ry in ["2024", "2023", "2025", "2022"]:
                    if ry != year:
                        all_rows = self.metrics_store.get_metric_for_all_companies(ry, metric_key)
                        if all_rows:
                            retrieved_metrics = all_rows
                            year = ry
                            break

        valid_rows = [r for r in retrieved_metrics if r.get("value") is not None]

        # Apply Threshold Filters
        if plan.threshold_filter:
            op = plan.threshold_filter.get("operator")
            val = plan.threshold_filter.get("value")
            if op == ">":
                valid_rows = [r for r in valid_rows if r["value"] > val]
            elif op == "<":
                valid_rows = [r for r in valid_rows if r["value"] < val]

        # Determine Sort Order
        ascending = False
        query_lower = plan.query.lower()
        if any(w in query_lower for w in ["lowest", "bottom", "least", "minimum"]):
            ascending = True
        elif any(w in query_lower for w in ["highest", "top", "most", "maximum", "best"]):
            ascending = False
        elif "emissions" in metric_key or "waste" in metric_key or "ltifr" in metric_key:
            ascending = True

        sorted_rows = sorted(valid_rows, key=lambda r: r.get("value", 0.0), reverse=not ascending)

        ranked_table = []
        for idx, row in enumerate(sorted_rows, start=1):
            ranked_table.append({
                "rank": idx,
                "company": row.get("company"),
                "year": row.get("year"),
                "metric_key": row.get("metric_key"),
                "metric_label": row.get("metric_label"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "source_file": row.get("source_file"),
                "page": row.get("page")
            })

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
