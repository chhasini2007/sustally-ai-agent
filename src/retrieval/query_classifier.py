from typing import Dict, Any, Tuple
import re
from src.retrieval.company_router import CompanyRouter
from src.processing.metric_taxonomy import ALIASED_METRICS, METRIC_TAXONOMY

class QueryClassifier:
    def __init__(self):
        self.company_router = CompanyRouter()
        self.comparison_keywords = ["compare", "comparison", "versus", "vs", "difference", "contrasted", "higher than", "lower than"]

    def classify(self, query: str, conversation_context: list = None, active_company: str = None) -> Dict[str, Any]:
        """
        Determines the routing lane (A, B, C, D, E, G) and extracts metadata.
        """
        from src.retrieval.question_understanding import question_understanding
        qu_result = question_understanding(query, conversation_context, active_company)

        if qu_result.get("status") == "conversational":
            return {
                "lane": "CONVERSATIONAL",
                "companies": [],
                "years": [],
                "metric_key": None,
                "status": "conversational",
                "matched_term": None,
                "matches": [],
                "question_understanding": qu_result
            }

        query_lower = query.lower().strip()
        query_lower_stripped = query_lower.strip("? .!")
        help_phrases = [
            "what is this agent", "can you explain this agent", "can you explain me what this agent is about",
            "what can you do", "help", "about", "how do you work", "explain your capabilities",
            "can you explain what this agent is about", "who are you"
        ]
        
        is_system_help = (query_lower_stripped in help_phrases) or any(
            phrase in query_lower_stripped for phrase in [
                "explain what this agent is", "explain what the agent is", "what is the agent about",
                "what is this agent about", "explain this agent"
            ]
        )
        
        if is_system_help:
            return {
                "lane": "SYSTEM_HELP",
                "companies": [],
                "years": [],
                "metric_key": None,
                "status": "system_help",
                "matched_term": None,
                "matches": [],
                "question_understanding": qu_result
            }

        companies = qu_result.get("companies", [])
        years = qu_result.get("years", [])
        metric_keys = qu_result.get("metric_keys", [])
        matched_metric_key = metric_keys[0] if metric_keys else None
        
        from src.retrieval.esg_query_engine import ESGQueryEngine
        engine = ESGQueryEngine()
        parsed = engine.parse_query(query, conversation_context, active_company)
        new_intent = parsed["intent"]

        intent_map = {
            "METRIC_LOOKUP": "A",
            "Metric Search": "A",
            "SUMMARY": "B",
            "Summary": "B",
            "Company Search": "B",
            "COMPARISON": "C",
            "Multi-company Comparison": "C",
            "Cross-company Analytics": "C",
            "ESG Benchmarking": "C",
            "Visualization": "C",
            "TREND": "D",
            "Trend Analysis": "D",
            "Year Comparison": "D",
            "RANKING": "E",
            "Ranking": "E",
            "REASONING": "B",
            "RISK_ASSESSMENT": "B",
            "MISSING_DATA_ANALYSIS": "B",
            "GENERAL": "G",
            "Source Verification": "A",
            "Data Quality Audit": "B"
        }
        
        qu_intent = qu_result.get("intent", "general")
        if qu_intent == "general":
            lane = "G"
        else:
            lane = intent_map.get(new_intent, "B")

        if lane == "D":
            trend_keywords = ["change", "changed", "growth", "decline", "trend", "yoy", "year over year", "percentage change", "increase", "decrease", "reduction"]
            has_genuine_trend = any(k in query_lower for k in trend_keywords) or len(years) > 1
            narrative_indicators = ["footnote", "appendix", "cross-reference", "indicate", "does the report", "methodology", "according to", "cite", "citation", "paragraph"]
            has_narrative_indicator = any(k in query_lower for k in narrative_indicators)
            
            if not has_genuine_trend or has_narrative_indicator:
                lane = "B"

        if len(companies) > 0 and (len(qu_result.get("topics", [])) > 0 or len(metric_keys) > 0):
            if lane in ("G", "E"):
                lane = "B"

        status = qu_result.get("status", "ok")
        matched_term = qu_result.get("matched_term", None)
        matches = qu_result.get("matches", [])

        if status in ("missing_company", "ambiguous", "unresolved") and new_intent not in ("GENERAL", "general", "Data Quality Audit"):
            if "list" in query.lower() and "compan" in query.lower():
                return {
                    "lane": "A",
                    "companies": [],
                    "years": [],
                    "metric_key": "list_companies",
                    "status": "ok",
                    "matched_term": None,
                    "matches": [],
                    "question_understanding": qu_result
                }
            
            is_comp_or_rank = new_intent in ("COMPARISON", "RANKING", "Multi-company Comparison", "Ranking", "Cross-company Analytics", "ESG Benchmarking") or len(companies) >= 2
            lane = "C" if is_comp_or_rank else "B"

        ranking_esg_keywords = [
            "female", "employee", "employees", "worker", "workers", "gender", "diversity", "women", "men",
            "emissions", "carbon", "scope 1", "scope 2", "scope 3", "ghg", "greenhouse gas", "co2",
            "water", "consumption", "usage", "kl",
            "energy", "electricity", "fuel", "power", "renewable",
            "waste", "generated", "generation", "tonnes",
            "esg", "sustainability", "brsr"
        ]
        has_compan = bool(re.search(r"\bcompan", query_lower)) or "pharmaceutical" in query_lower or "banking" in query_lower or "it company" in query_lower or "it companies" in query_lower
        has_threshold = bool(re.search(r"(?:more than|greater than|less than|above|below|over|under|at least|at most|>|<)\s*\d+", query_lower))
        has_ranking_esg = any(w in query_lower for w in ranking_esg_keywords) or len(qu_result.get("topics", [])) > 0 or len(metric_keys) > 0
        
        if (has_compan or has_threshold) and has_ranking_esg:
            if lane == "G":
                lane = "E"

        if not companies and (new_intent in ("RANKING", "Ranking", "Cross-company Analytics") or "which company" in query_lower or "which companies" in query_lower):
            status = "ok"

        return {
            "lane": lane,
            "companies": companies,
            "years": years,
            "metric_key": matched_metric_key,
            "status": status,
            "matched_term": matched_term,
            "matches": matches,
            "question_understanding": qu_result
        }
