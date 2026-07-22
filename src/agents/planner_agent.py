"""
Planner Agent for Sustally ESG Intelligence Platform
Generates a structured QueryPlan across 10 canonical ESG intents,
entity resolution, metric normalization, sector extraction, and calculation directives.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import re
import logging

from src.retrieval.company_router import CompanyRouter
from src.processing.metric_taxonomy import METRIC_TAXONOMY, ALIASED_METRICS, resolve_canonical_metric

logger = logging.getLogger(__name__)

@dataclass
class QueryPlan:
    query: str
    intent: str  # summary, metric_lookup, comparison, ranking, trend_analysis, reasoning, calculation, missing_data, contradiction_check, report_navigation, general
    companies: List[str] = field(default_factory=list)
    years: List[str] = field(default_factory=list)
    metric_keys: List[str] = field(default_factory=list)
    sector: Optional[str] = None
    target_unit: Optional[str] = None  # e.g., "gallons", "kgCO2e", "MWh"
    threshold_filter: Optional[Dict[str, Any]] = None  # e.g., {"operator": ">", "value": 30.0}
    retrieval_strategy: str = "STRUCTURED_DB_ONLY"  # STRUCTURED_DB_ONLY, HYBRID_METRIC_NARRATIVE, NARRATIVE_VECTOR_ONLY
    reasoning_strategy: str = "SUMMARY_SYNTHESIS"
    execution_path: List[str] = field(default_factory=list)
    confidence: str = "high"
    status: str = "ok"
    matched_term: Optional[str] = None
    matches: List[str] = field(default_factory=list)
    conversational_category: Optional[str] = None


class PlannerAgent:
    def __init__(self):
        self.company_router = CompanyRouter()

    def create_plan(
        self,
        query: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        active_company: Optional[str] = None
    ) -> QueryPlan:
        if conversation_context is None:
            conversation_context = []

        query_lower = query.lower().strip()

        # 1. Conversational check
        from src.retrieval.question_understanding import check_conversational_intent
        conv_cat = check_conversational_intent(query)
        if conv_cat:
            return QueryPlan(
                query=query,
                intent="general",
                execution_path=["PlannerAgent", "ConversationalHandler"],
                confidence="high",
                status="conversational",
                conversational_category=conv_cat
            )

        # 2. Company Resolution
        analysis = self.company_router.analyze_resolution(query)
        status = analysis.get("status", "ok")
        matched_term = analysis.get("matched_term")
        matches = analysis.get("matches", [])
        resolved_companies = list(analysis.get("companies", []))
        years = list(analysis.get("years", []))

        # Context carryover for follow-ups
        if not resolved_companies and conversation_context:
            history = [m for m in conversation_context if m.get("content") != query]
            for msg in reversed(history[-5:]):
                detected = self.company_router.detect_company_from_query(msg.get("content", ""))
                if detected:
                    resolved_companies = list(detected)
                    status = "ok"
                    matched_term = None
                    matches = []
                    break

        if not resolved_companies and active_company and status != "ambiguous":
            resolved_companies = [active_company]
            status = "ok"

        # 3. Year Resolution
        fy_matches = re.findall(r"\bfy\s*(\d{2,4})\b", query_lower)
        for fy in fy_matches:
            yr = f"20{fy}" if len(fy) == 2 else fy
            if yr not in years:
                years.append(yr)

        range_match = re.search(r"between\s+(\d{4})\s+and\s+(\d{4})", query_lower)
        if range_match:
            y_start, y_end = int(range_match.group(1)), int(range_match.group(2))
            for yr in range(y_start, y_end + 1):
                if str(yr) not in years:
                    years.append(str(yr))

        # 4. Metric Resolution
        metric_keys = []
        sorted_synonyms = sorted(ALIASED_METRICS.keys(), key=len, reverse=True)
        for syn in sorted_synonyms:
            if syn in query_lower:
                m_key = ALIASED_METRICS[syn]
                if m_key not in metric_keys:
                    metric_keys.append(m_key)

        # Dynamic metric resolution fallback
        if not metric_keys:
            if "water" in query_lower:
                metric_keys.append("water_consumption_kl")
            elif "scope 1" in query_lower or "direct emissions" in query_lower:
                metric_keys.append("scope1_emissions")
            elif "scope 2" in query_lower or "indirect emissions" in query_lower:
                metric_keys.append("scope2_emissions")
            elif "scope 3" in query_lower or "value chain emissions" in query_lower:
                metric_keys.append("scope3_emissions")
            elif "renewable" in query_lower or "green energy" in query_lower:
                metric_keys.append("renewable_energy_pct")
            elif "female" in query_lower or "women" in query_lower or "gender" in query_lower:
                metric_keys.append("female_employee_headcount_share_pct")
            elif "waste" in query_lower:
                metric_keys.append("waste_generation_tonnes")

        # 5. Sector/Industry Resolution
        sectors_map = {
            "banking": "Banking", "bank": "Banking", "banks": "Banking",
            "pharmaceutical": "Pharmaceuticals", "pharmaceuticals": "Pharmaceuticals", "pharma": "Pharmaceuticals",
            "it": "IT", "technology": "IT", "tech": "IT", "software": "IT",
            "cement": "Cement", "chemical": "Chemicals", "chemicals": "Chemicals", "telecom": "Telecommunications",
            "energy": "Energy", "metal": "Metals & Mining", "steel": "Metals & Mining",
            "automobile": "Automobile", "auto": "Automobile"
        }
        sector = None
        for kw, s_val in sectors_map.items():
            if re.search(rf"\b{re.escape(kw)}\b", query_lower):
                sector = s_val
                break

        # 6. Threshold Filter Extraction
        threshold_filter = None
        thresh_match = re.search(r"(?:more than|greater than|above|over|>)\s*(\d+(?:\.\d+)?)", query_lower)
        if thresh_match:
            threshold_filter = {"operator": ">", "value": float(thresh_match.group(1))}
        else:
            thresh_match_less = re.search(r"(?:less than|below|under|<)\s*(\d+(?:\.\d+)?)", query_lower)
            if thresh_match_less:
                threshold_filter = {"operator": "<", "value": float(thresh_match_less.group(1))}

        # 7. Unit Conversion Directives
        target_unit = None
        if "gallon" in query_lower or "gallons" in query_lower:
            target_unit = "gallons"
        elif "kgco2e" in query_lower or "kilogram" in query_lower:
            target_unit = "kgCO2e"
        elif "mwh" in query_lower or "megawatt" in query_lower:
            target_unit = "MWh"

        # 8. Intent Classification across 10 Canonical Types
        is_calc = any(w in query_lower for w in ["convert", "conversion", "calculate", "math", "in gallons", "into gallons"]) or target_unit is not None
        is_ranking = (
            any(w in query_lower for w in ["rank", "ranking", "highest", "lowest", "top", "bottom", "best", "worst", "order by", "sorted by"]) 
            or bool(re.search(r"\btop\s*\d*", query_lower))
            or (threshold_filter is not None and ("which companies" in query_lower or "companies" in query_lower))
        )
        is_trend = any(w in query_lower for w in ["trend", "yoy", "year over year", "historical", "series", "growth", "decline", "percentage change"]) or len(years) > 1
        is_comparison = len(resolved_companies) >= 2 or any(w in query_lower for w in ["compare", "versus", "vs", "difference", "contrasted", "comparison"])
        is_summary = any(w in query_lower for w in ["summary", "summarize", "overview", "highlights", "key findings", "main points"])
        is_missing = any(w in query_lower for w in ["missing", "unreported", "gap", "incomplete", "audit", "which companies have"])
        is_contradiction = any(w in query_lower for w in ["contradict", "contradiction", "discrepancy", "inconsistent", "verify consistency"])
        is_navigation = any(w in query_lower for w in ["where in the report", "locate", "section", "page number", "xml tag", "table location"])
        is_reasoning = any(w in query_lower for w in ["why", "how", "reason", "strategy", "initiative", "initiative across", "common initiative", "most common"])

        intent = "metric_lookup"
        retrieval_strat = "STRUCTURED_DB_ONLY"

        if is_calc:
            intent = "calculation"
            retrieval_strat = "STRUCTURED_DB_ONLY"
        elif is_ranking:
            intent = "ranking"
            retrieval_strat = "STRUCTURED_DB_ONLY"
        elif is_trend:
            intent = "trend_analysis"
            retrieval_strat = "STRUCTURED_DB_ONLY"
        elif is_comparison:
            intent = "comparison"
            retrieval_strat = "STRUCTURED_DB_ONLY" if metric_keys else "HYBRID_METRIC_NARRATIVE"
        elif is_summary:
            intent = "summary"
            retrieval_strat = "HYBRID_METRIC_NARRATIVE"
        elif is_missing:
            intent = "missing_data"
            retrieval_strat = "STRUCTURED_DB_ONLY"
        elif is_contradiction:
            intent = "contradiction_check"
            retrieval_strat = "HYBRID_METRIC_NARRATIVE"
        elif is_navigation:
            intent = "report_navigation"
            retrieval_strat = "HYBRID_METRIC_NARRATIVE"
        elif is_reasoning:
            intent = "reasoning"
            retrieval_strat = "HYBRID_METRIC_NARRATIVE"
        elif metric_keys:
            intent = "metric_lookup"
            retrieval_strat = "STRUCTURED_DB_ONLY"
        else:
            intent = "reasoning"
            retrieval_strat = "HYBRID_METRIC_NARRATIVE"

        # Special metadata list overrides
        if "list" in query_lower and "xml" in query_lower:
            metric_keys = ["list_xml_reports"]
            intent = "metric_lookup"
            retrieval_strat = "STRUCTURED_DB_ONLY"
        elif "list" in query_lower and "company" in query_lower:
            metric_keys = ["list_companies"]
            intent = "metric_lookup"
            retrieval_strat = "STRUCTURED_DB_ONLY"

        exec_path = ["PlannerAgent", "CompanyResolver", "MetricResolver"]
        if retrieval_strat == "STRUCTURED_DB_ONLY":
            exec_path.append("MetricsStore(SQLite)")
        else:
            exec_path.extend(["MetricsStore(SQLite)", "ChromaStore(Vector)"])

        return QueryPlan(
            query=query,
            intent=intent,
            companies=resolved_companies,
            years=years,
            metric_keys=metric_keys,
            sector=sector,
            target_unit=target_unit,
            threshold_filter=threshold_filter,
            retrieval_strategy=retrieval_strat,
            execution_path=exec_path,
            confidence="high" if (resolved_companies or is_ranking or metric_keys or is_calc) else "medium",
            status=status,
            matched_term=matched_term,
            matches=matches
        )
