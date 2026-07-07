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
        chart_metric: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Generator[str, None, None], str, Optional[Any], bool, Optional[str], Optional[int]]:
        """
        Pulls structured metrics for multiple companies/years, builds comparison tables,
        resolves/reuses Plotly chart cache from SQLite history_store,
        and generates commentary using the LLM.
        
        Returns:
            (structured_data, gen, provider, figure, is_reused, refreshed_time, chart_id)
        """
        # If no specific years are requested, fetch all available years for these companies
        if not years:
            all_years = set()
            for company in companies:
                all_years.update(self.metrics_store.get_company_years(company))
            years = sorted(list(all_years), reverse=True)[:2] # default to top 2 years
            
        # If no specific metrics are requested, use a default list of common taxonomy keys
        if not metric_keys:
            metric_keys = list(METRIC_TAXONOMY.keys())
            
        # Determine active chart metric
        active_chart_metric = chart_metric if chart_metric else (metric_keys[0] if (metric_keys and len(metric_keys) == 1) else "scope1_emissions_tco2e")
        
        # 1. Compute Topic Key (signature of resolved entities)
        sorted_comps = sorted([c.strip() for c in companies])
        sorted_yrs = sorted([str(y).strip() for y in years])
        sorted_mkeys = sorted([str(k).strip() for k in (metric_keys or [active_chart_metric])])
        
        sig_str = "|".join(sorted_comps) + "||" + "|".join(sorted_yrs) + "||" + "|".join(sorted_mkeys)
        topic_key = hashlib.sha256(sig_str.encode('utf-8')).hexdigest()[:16]
        
        # 2. Check Cache
        cached_chart = self.history_store.get_cached_chart(topic_key)
        is_reused = False
        fig = None
        refreshed_time = None
        chart_id = None
        
        if cached_chart:
            # Check for staleness
            is_stale = False
            index_path = settings.DOC_INDEX_PATH
            if os.path.exists(index_path):
                try:
                    with open(index_path, "r") as f:
                        doc_index = json.load(f)
                    
                    chart_created_dt = datetime.fromisoformat(cached_chart["created_at"])
                    
                    # If any document relevant to this comparison has been processed
                    # after the cached chart's creation date, mark it as stale.
                    for doc_info in doc_index.values():
                        doc_company = doc_info.get("company")
                        doc_year = doc_info.get("year")
                        
                        comp_match = any(c.lower() == doc_company.lower() for c in companies)
                        year_match = any(str(y) == str(doc_year) for y in years)
                        
                        if comp_match and year_match:
                            proc_date_str = doc_info.get("processed_date")
                            if proc_date_str:
                                file_processed_dt = datetime.fromisoformat(proc_date_str)
                                if file_processed_dt > chart_created_dt:
                                    is_stale = True
                                    break
                except Exception:
                    pass
            
            if not is_stale:
                try:
                    fig = pio.from_json(cached_chart["figure_json"])
                    is_reused = True
                    chart_id = cached_chart["id"]
                    self.history_store.update_chart_used_time(chart_id)
                    dt = datetime.fromisoformat(cached_chart["created_at"])
                    refreshed_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    fig = None
                    
        # Pull raw metrics
        raw_metrics = self.metrics_store.get_metrics_for_companies(companies, metric_keys)
        
        # Organize data by company -> year -> metric_key
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
                
        # If not reused, construct a fresh chart
        if not is_reused:
            fig = create_comparison_chart(structured_data, active_chart_metric)
            if fig:
                fig_json = pio.to_json(fig)
                chart_id = self.history_store.save_cached_chart(
                    topic_key=topic_key,
                    companies=companies,
                    years=years,
                    metric_keys=sorted_mkeys,
                    figure_json=fig_json
                )
                refreshed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
        # Build text description of data for LLM prompt
        comparison_text = []
        for key in metric_keys:
            label = METRIC_TAXONOMY[key]["label"]
            comparison_text.append(f"Metric: {label}")
            for company in companies:
                for year in years:
                    data = structured_data[company][year].get(key)
                    if data:
                        comparison_text.append(f"  - {company} ({year}): {data['value']} {data['unit']} [Source: {data['source']} p. {data['page']}]")
                    else:
                        comparison_text.append(f"  - {company} ({year}): Not Reported")
                        
        data_summary = "\n".join(comparison_text)
        
        prompt = (
            f"You are Sustally's ESG analyst. Provide a brief comparative analysis based on this data:\n\n"
            f"{data_summary}\n\n"
            f"Write a concise analysis comparing the performance, efficiency, and progress between these entities. "
            f"Cite the sources and page numbers provided. Keep the commentary short and strictly grounded in these numbers."
        )
        
        messages = [{"role": "user", "content": prompt}]
        gen, provider = self.llm_router.generate(messages, stream=stream)
        
        return structured_data, gen, provider, fig, is_reused, refreshed_time, chart_id
