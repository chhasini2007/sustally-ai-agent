import os
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Tuple, Generator, Optional
import plotly.io as pio

from config import settings
from src.database.metrics_store import MetricsStore
from src.database.history_store import HistoryStore
from src.llm.llm_router import LLMRouter
from src.processing.metric_taxonomy import METRIC_TAXONOMY
from src.visualization.charts import create_comparison_chart

def detect_requested_sector(query: str, resolved_companies: List[str] = None) -> Optional[str]:
    import re
    if not query:
        return None
    query_lower = query.lower()
    
    # Standard sectors
    sectors = {
        "banking": ["banking", "bank", "banks"],
        "pharma": ["pharma", "pharmaceutical", "pharmaceuticals"],
        "chemical": ["chemical", "chemicals"],
        "cement": ["cement"],
        "telecom": ["telecom", "telecommunication", "telecommunications"],
        "metals": ["metal", "metals", "steel", "iron"],
        "software": ["software", "technology", "it companies", "tech companies"],
        "automobile": ["automobile", "automotive", "automobiles"],
        "insurance": ["insurance"],
        "power": ["power", "energy companies"],
        "agriculture": ["agriculture", "agricultural"]
    }
    
    for sector_name, keywords in sectors.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", query_lower):
                is_part_of_resolved_company = False
                if resolved_companies:
                    for comp in resolved_companies:
                        if kw in comp.lower():
                            is_part_of_resolved_company = True
                            break
                if not is_part_of_resolved_company:
                    return sector_name
    return None

class ComparisonAgent:
    def __init__(self):
        self.metrics_store = MetricsStore()
        self.history_store = HistoryStore()
        self.llm_router = LLMRouter()

    def compare_companies(
        self,
        companies: List[str],
        years: List[str],
        metric_keys: Optional[List[str]] = None,
        stream: bool = True,
        chart_metric: Optional[str] = None,
        query: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Generator[str, None, None], str, Optional[Any], bool, Optional[str], Optional[int]]:
        """
        Pulls structured metrics for multiple companies/years, builds comparison tables,
        resolves/reuses Plotly chart cache from SQLite history_store,
        and generates commentary using the LLM.
        """
        # Resolve company list if empty
        if not companies:
            companies = self.metrics_store.get_all_companies()

        from src.processing.metric_taxonomy import ALIASED_METRICS
        if chart_metric in ALIASED_METRICS:
            chart_metric = ALIASED_METRICS[chart_metric]

        # Call ESGQueryEngine
        from src.retrieval.esg_query_engine import ESGQueryEngine
        engine = ESGQueryEngine()
        res = engine.execute_query(query or f"Compare companies on {chart_metric}")

        # Get structured data from metrics database for compatibility
        if not years:
            all_years = set()
            for company in companies:
                all_years.update(self.metrics_store.get_company_years(company))
            years = sorted(list(all_years), reverse=True)[:2]
            
        if not metric_keys:
            metric_keys = list(METRIC_TAXONOMY.keys())
            
        raw_metrics = self.metrics_store.get_metrics_for_companies(companies, metric_keys)
        
        structured_data = {}
        for company in companies:
            structured_data[company] = {}
            for year in years:
                structured_data[company][year] = {}
                
        for m in raw_metrics:
            comp_canonical = next((c for c in companies if c.lower() == m["company"].lower()), None)
            yr = m["year"]
            m_key = m["metric_key"]
            if comp_canonical and yr in years:
                structured_data[comp_canonical][yr][m_key] = {
                    "value": m["value"],
                    "unit": m["unit"],
                    "label": m["metric_label"],
                    "source": m["source_file"],
                    "page": m["page"]
                }

        requested_sector = detect_requested_sector(query, companies)
        sector_header = ""
        if requested_sector:
            sector_header = f"**Notice:** Industry/sector classification is not currently available to filter by '{requested_sector}' — showing results across all companies instead.\n\n"

        def gen_resp():
            if sector_header:
                yield sector_header
            yield res["content"]
            
        return structured_data, gen_resp(), "esg_query_engine", res["fig"], False, None, None

    def rank_companies(
        self,
        metric_key: str,
        year: Optional[str],
        query: str,
        stream: bool = True
    ) -> Tuple[Generator[str, None, None], str]:
        import re
        
        from src.processing.metric_taxonomy import ALIASED_METRICS
        if metric_key in ALIASED_METRICS:
            metric_key = ALIASED_METRICS[metric_key]

        if not year:
            import sqlite3
            conn = sqlite3.connect(self.metrics_store.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT year FROM metrics 
                    WHERE metric_key = ? AND year IS NOT NULL AND year != ''
                    ORDER BY year DESC LIMIT 1
                """, (metric_key,))
                row = cursor.fetchone()
                year = row[0] if row else "2024"
            except Exception:
                year = "2024"
            finally:
                conn.close()

        raw_metrics = self.metrics_store.get_metric_for_all_companies(year, metric_key)
        
        if not raw_metrics:
            display_metric = METRIC_TAXONOMY.get(metric_key, {}).get("label", metric_key)
            msg = f"No company data for metric '{display_metric}' was found in the database for the year {year}."
            requested_sector = detect_requested_sector(query, [])
            if requested_sector:
                msg = f"**Notice:** Industry/sector classification is not currently available to filter by '{requested_sector}' — showing results across all companies instead.\n\n" + msg
            def gen_no_data():
                yield msg
            return gen_no_data(), "ranking_engine"

        # Check threshold limits for no-matches fallback in testing
        query_lower = query.lower()
        threshold_match = re.search(r"(?:more than|greater than|less than|above|below|over|under|at least|at most|>|<)\s*(\d+(?:\.\d+)?)\s*%", query_lower)
        if not threshold_match:
            threshold_match = re.search(r"(?:more than|greater than|less than|above|below|over|under|at least|at most|>|<)\s*(\d+(?:\.\d+)?)", query_lower)
            
        threshold_val = None
        if threshold_match:
            try:
                threshold_val = float(threshold_match.group(1))
            except ValueError:
                pass

        if threshold_val is not None:
            is_greater = any(w in query_lower for w in ["more", "greater", "above", "over", ">", "at least"])
            filtered_list = []
            for m in raw_metrics:
                if is_greater and m["value"] >= threshold_val:
                    filtered_list.append(m)
                elif not is_greater and m["value"] <= threshold_val:
                    filtered_list.append(m)
            if not filtered_list:
                display_metric = METRIC_TAXONOMY.get(metric_key, {}).get("label", metric_key)
                op_word = "above" if is_greater else "below"
                unit_str = METRIC_TAXONOMY.get(metric_key, {}).get("unit", "")
                unit_display = f" {unit_str}" if unit_str else ""
                msg = f"No companies in the database currently report {display_metric} {op_word} {threshold_val}{unit_display}."
                requested_sector = detect_requested_sector(query, [])
                if requested_sector:
                    msg = f"**Notice:** Industry/sector classification is not currently available to filter by '{requested_sector}' — showing results across all companies instead.\n\n" + msg
                def gen_no_match():
                    yield msg
                return gen_no_match(), "ranking_engine"

        # Retrieve through ESGQueryEngine
        from src.retrieval.esg_query_engine import ESGQueryEngine
        engine = ESGQueryEngine()
        res = engine.execute_query(query)

        requested_sector = detect_requested_sector(query, [])
        sector_header = ""
        if requested_sector:
            sector_header = f"**Notice:** Industry/sector classification is not currently available to filter by '{requested_sector}' — showing results across all companies instead.\n\n"

        # Construct compatible ranking output format for testing
        display_metric = METRIC_TAXONOMY.get(metric_key, {}).get("label", metric_key)
        reverse = True
        if any(w in query_lower for w in ["lowest", "least", "bottom", "worst", "smallest", "minimum"]):
            reverse = False
        unique_metrics = {}
        for m in raw_metrics:
            comp = m["company"]
            if comp not in unique_metrics:
                unique_metrics[comp] = m
            else:
                existing = unique_metrics[comp]
                if existing["source_file"] == "report.xml" and m["source_file"] != "report.xml":
                    unique_metrics[comp] = m
        ranked_list = sorted(unique_metrics.values(), key=lambda x: x["value"], reverse=reverse)
        if threshold_val is not None:
            is_greater = any(w in query_lower for w in ["more", "greater", "above", "over", ">", "at least"])
            if is_greater:
                ranked_list = [m for m in ranked_list if m["value"] >= threshold_val]
            else:
                ranked_list = [m for m in ranked_list if m["value"] <= threshold_val]
        
        limit = len(ranked_list) if threshold_val is not None else 5
        num_match = re.search(r"\b(?:top|bottom|first|last)?\s*(\d+)\b", query_lower)
        if num_match:
            try:
                limit = int(num_match.group(1))
            except ValueError:
                pass
        ranked_list = ranked_list[:limit]

        table_md = f"Here is the ranking of companies by **{display_metric}** in **{year}**:\n\n"
        table_md += f"| Rank | Company | Value | Unit | Source |\n"
        table_md += f"| :--- | :--- | :--- | :--- | :--- |\n"
        for idx, m in enumerate(ranked_list):
            rank = idx + 1
            table_md += f"| {rank} | {m['company']} | **{m['value']}** | {m['unit']} | {m['source_file']}, Page {m['page']} |\n"

        def gen_resp():
            if sector_header:
                yield sector_header
            yield res["content"]
            # Append summary table for test compatibility
            yield "\n\n### Summary Table\n\n" + table_md

        return gen_resp(), "esg_query_engine"
