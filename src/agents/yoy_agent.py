import os
import json
import hashlib
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import plotly.io as pio

from config import settings
from src.database.metrics_store import MetricsStore
from src.database.history_store import HistoryStore
from src.processing.metric_taxonomy import METRIC_TAXONOMY
from src.visualization.charts import create_trend_chart

class YoYAgent:
    def __init__(self):
        self.metrics_store = MetricsStore()
        self.history_store = HistoryStore()

    def compare_years(
        self,
        company: str,
        metric_key: str,
        years: Optional[List[str]] = None
    ) -> Tuple[str, Optional[Any], bool, Optional[str], Optional[int]]:
        """
        Calculates YoY change for a metric and company.
        Returns:
            (response_text, fig, is_reused, refreshed_time, chart_id)
        """
        metric_info = METRIC_TAXONOMY.get(metric_key)
        if not metric_info:
            return f"Unknown metric key: {metric_key}", None, False, None, None

        # Fetch all available data for this company and metric
        conn = sqlite3.connect(settings.METRICS_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT year, value, unit, source_file, page, metric_label
            FROM metrics
            WHERE LOWER(company) = LOWER(?) AND metric_key = ?
            ORDER BY year ASC
        """, (company, metric_key))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            if metric_key == "female_employee_headcount_share_pct":
                # Check if wage share is present
                conn = sqlite3.connect(settings.METRICS_DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT year, value, unit, source_file, page
                    FROM metrics
                    WHERE LOWER(company) = LOWER(?) AND metric_key = 'female_employee_wage_share_pct'
                    ORDER BY year ASC
                """, (company,))
                wage_rows = cursor.fetchall()
                conn.close()
                if wage_rows:
                    return "headcount-based female representation was not found; only a wage-based female pay percentage was reported", None, False, None, None
            return f"No sustainability metrics found for {company}'s {metric_info['label']}.", None, False, None, None


        # Map to dict for year access
        # [{year: {value, unit, source_file, page}}]
        data_by_year = {}
        for row in rows:
            r_year, r_val, r_unit, r_src, r_page = row[:5]
            r_label = row[5] if len(row) > 5 else ""
            data_by_year[str(r_year)] = {
                "value": r_val,
                "unit": r_unit,
                "source_file": os.path.basename(r_src),
                "page": r_page,
                "label": r_label
            }

        available_years = sorted(list(data_by_year.keys()))

        # Check if we have at least 2 years of data
        if len(available_years) < 2:
            # Get the single year data
            single_yr = available_years[0]
            val_info = data_by_year[single_yr]
            return (
                f"Only one year of data ({single_yr}: {val_info['value']} {val_info['unit']}) is available for {company}'s {metric_info['label']} — "
                f"a year-over-year comparison requires at least two years of data in the uploaded reports.",
                None, False, None, None
            )

        # Determine year1 and year2
        if years and len(years) >= 2:
            # Sort requested years
            sorted_req_yrs = sorted([str(y) for y in years])
            year1 = sorted_req_yrs[0]
            year2 = sorted_req_yrs[1]
        else:
            # Default to earliest and latest
            year1 = available_years[0]
            year2 = available_years[-1]

        # Check if year1 and year2 exist in database
        if year1 not in data_by_year or year2 not in data_by_year:
            missing = []
            if year1 not in data_by_year:
                missing.append(year1)
            if year2 not in data_by_year:
                missing.append(year2)
            
            # Format nicely
            avail_str = ", ".join(available_years)
            return (
                f"Data for requested year(s) {', '.join(missing)} is not available for {company}'s {metric_info['label']}. "
                f"Available years: {avail_str}.",
                None, False, None, None
            )

        # Do the arithmetic
        d1 = data_by_year[year1]
        d2 = data_by_year[year2]
        
        val1 = d1["value"]
        val2 = d2["value"]
        unit = d1["unit"]
        
        abs_change = val2 - val1
        
        if val1 == 0:
            pct_change_str = "N/A (initial value is 0)"
            direction = "increased" if abs_change > 0 else "decreased" if abs_change < 0 else "remained unchanged"
        else:
            pct_change = ((val2 - val1) / val1) * 100
            pct_change = round(pct_change, 1)
            direction = "increased" if pct_change > 0 else "decreased" if pct_change < 0 else "remained unchanged"
            pct_change_str = f"{abs(pct_change)}%"

        # Check if headcount values are available for YoY comparison
        is_headcount = metric_key in ("female_employee_headcount_share_pct", "female_employee_count", "total_employee_count")
        
        female_count_y1 = None
        total_count_y1 = None
        female_count_y2 = None
        total_count_y2 = None
        
        if is_headcount:
            db_female_y1 = self.metrics_store.get_metric(company, year1, "female_employee_count")
            db_total_y1 = self.metrics_store.get_metric(company, year1, "total_employee_count")
            db_female_y2 = self.metrics_store.get_metric(company, year2, "female_employee_count")
            db_total_y2 = self.metrics_store.get_metric(company, year2, "total_employee_count")
            
            if db_female_y1: female_count_y1 = db_female_y1[0]["value"]
            if db_total_y1: total_count_y1 = db_total_y1[0]["value"]
            if db_female_y2: female_count_y2 = db_female_y2[0]["value"]
            if db_total_y2: total_count_y2 = db_total_y2[0]["value"]

        response_parts = []
        if is_headcount:
            # Determine values and format
            y1_str = f"{int(female_count_y1):,} female employees out of {int(total_count_y1):,} total employees ({val1:.1f}%)" if (female_count_y1 and total_count_y1) else f"{val1:.1f}% (headcount figures missing)"
            y2_str = f"{int(female_count_y2):,} female employees out of {int(total_count_y2):,} total employees ({val2:.1f}%)" if (female_count_y2 and total_count_y2) else f"{val2:.1f}% (headcount figures missing)"
            
            if direction == "remained unchanged":
                response_parts.append(
                    f"{company}'s female employee headcount representation remained unchanged from {year1} ({y1_str}) to {year2} ({y2_str})."
                )
            else:
                response_parts.append(
                    f"{company}'s female employee headcount representation {direction} by {pct_change_str} from {year1} ({y1_str}) to {year2} ({y2_str})."
                )
        else:
            if direction == "remained unchanged":
                response_parts.append(
                    f"{company}'s {metric_info['label']} remained unchanged at {val1} {unit} from {year1} to {year2}."
                )
            else:
                response_parts.append(
                    f"{company}'s {metric_info['label']} {direction} by {pct_change_str} from {year1} ({val1} {unit}) to {year2} ({val2} {unit})."
                )
            
        source1 = d1["source_file"]
        source2 = d2["source_file"]
        
        # Resolve source URLs if available
        from src.ingestion.document_manager import DocumentManager
        doc_mgr = DocumentManager()
        
        def get_source_desc(src_file, page, label):
            source_url = None
            for file_path, meta in doc_mgr.index.items():
                if meta.get("file_name") == src_file:
                    source_url = meta.get("source_url")
                    break
            
            if source_url:
                cite_link = f"[{src_file}]({source_url})"
            else:
                cite_link = src_file
                
            if src_file.lower().endswith(".xml"):
                xml_tag = f", {label}" if label and label.lower().startswith("xml tag:") else ", XML"
                return f"{cite_link}{xml_tag}"
            else:
                return f"{cite_link}, Page {page}"
            
        desc1 = get_source_desc(source1, d1["page"], d1.get("label"))
        desc2 = get_source_desc(source2, d2["page"], d2.get("label"))
        
        response_parts.append(f"Sources: {desc1}, {desc2}.")

        # If more than 2 years exist, add full series trend summary
        if len(available_years) > 2:
            series_parts = []
            for y in available_years:
                series_parts.append(f"{y} ({data_by_year[y]['value']} {unit})")
            response_parts.append(f"\nFull available series: {', '.join(series_parts)}.")

        response_text = " ".join(response_parts)

        # Generate and cache Plotly line chart if 3+ years exist
        fig = None
        is_reused = False
        refreshed_time = None
        chart_id = None

        if len(available_years) >= 3:
            # 1. Compute Cache Signature
            sig_str = f"{company.strip().lower()}||{metric_key.strip().lower()}||trend"
            topic_key = hashlib.sha256(sig_str.encode('utf-8')).hexdigest()[:16]

            # Check cache
            cached = self.history_store.get_cached_chart(topic_key)
            if cached:
                # Check for staleness
                is_stale = False
                index_path = settings.DOC_INDEX_PATH
                if os.path.exists(index_path):
                    try:
                        with open(index_path, "r") as f:
                            doc_index = json.load(f)
                        
                        chart_created_dt = datetime.fromisoformat(cached["created_at"])
                        for doc_info in doc_index.values():
                            doc_company = doc_info.get("company")
                            if doc_company and doc_company.lower() == company.lower():
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
                        fig = pio.from_json(cached["figure_json"])
                        is_reused = True
                        chart_id = cached["id"]
                        refreshed_time = datetime.fromisoformat(cached["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

            if fig is None:
                # Generate new trend chart
                years_list = available_years
                values_list = [data_by_year[y]["value"] for y in available_years]
                fig = create_trend_chart(company, metric_key, years_list, values_list)
                
                if fig:
                    fig_json = pio.to_json(fig)
                    chart_id = self.history_store.save_cached_chart(
                        topic_key,
                        companies=[company],
                        years=available_years,
                        metric_keys=[metric_key],
                        figure_json=fig_json
                    )
                    refreshed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return response_text, fig, is_reused, refreshed_time, chart_id
