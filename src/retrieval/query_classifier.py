from typing import Dict, Any, Tuple
from src.retrieval.company_router import CompanyRouter
from src.processing.metric_taxonomy import ALIASED_METRICS, METRIC_TAXONOMY

class QueryClassifier:
    def __init__(self):
        self.company_router = CompanyRouter()
        self.comparison_keywords = ["compare", "comparison", "versus", "vs", "difference", "contrasted", "higher than", "lower than"]

    def classify(self, query: str, conversation_context: list = None, active_company: str = None) -> Dict[str, Any]:
        """
        Determines the routing lane (A, B, C, D, E, G) and extracts metadata.
        Returns:
            {
                "lane": "A" | "B" | "C" | "D" | "E" | "G" | "SYSTEM_HELP",
                "companies": List[str],
                "years": List[str],
                "metric_key": Optional[str],
                "status": "ok" | "missing_company" | "general" | "unresolved" | "ambiguous",
                "matched_term": Optional[str],
                "matches": List[str],
                "question_understanding": Dict[str, Any]
            }
        """
        from src.retrieval.question_understanding import question_understanding
        qu_result = question_understanding(query, conversation_context, active_company)

        # Check for conversational status first
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

        # Check system help queries first
        query_lower = query.lower()
        query_lower_stripped = query_lower.strip("? .!")
        help_phrases = [
            "what is this agent",
            "can you explain this agent",
            "can you explain me what this agent is about",
            "what can you do",
            "help",
            "about",
            "how do you work",
            "explain your capabilities",
            "can you explain what this agent is about",
            "who are you"
        ]
        
        is_system_help = (query_lower_stripped in help_phrases) or any(
            phrase in query_lower_stripped for phrase in [
                "explain what this agent is",
                "explain what the agent is",
                "what is the agent about",
                "what is this agent about",
                "explain this agent"
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
        
        intent = qu_result.get("intent", "general")
        status = qu_result.get("status", "ok")
        matched_term = qu_result.get("matched_term", None)
        matches = qu_result.get("matches", [])

        intent_map = {
            "lookup": "A",
            "narrative": "B",
            "comparison": "C",
            "trend": "D",
            "ranking": "E",
            "general": "G"
        }
        lane = intent_map.get(intent, "G")

        # Validate Lane D (Trend/YoY)
        if lane == "D":
            trend_keywords = ["change", "changed", "growth", "decline", "trend", "yoy", "year over year", "percentage change", "increase", "decrease", "reduction"]
            has_genuine_trend = any(k in query_lower for k in trend_keywords)
            
            narrative_indicators = ["footnote", "appendix", "cross-reference", "indicate", "does the report", "methodology", "according to", "cite", "citation", "paragraph"]
            has_narrative_indicator = any(k in query_lower for k in narrative_indicators)
            
            if not has_genuine_trend or has_narrative_indicator:
                lane = "B"

        # Priority override: a named company + any ESG topic/metric should try Lane B
        # before reaching general knowledge (G) or ranking (E).
        if len(companies) > 0 and (len(qu_result.get("topics", [])) > 0 or len(metric_keys) > 0):
            if lane in ("G", "E"):
                lane = "B"

        # Handle missing_company/ambiguous/unresolved company overrides
        if status in ("missing_company", "ambiguous", "unresolved") and intent != "general":
            # Check metadata queries first
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
            
            lane = "C" if (intent == "comparison" or len(companies) >= 2) else "B"

        # Safety net: never route questions about company + ESG topic to general knowledge (G)
        ranking_esg_keywords = [
            "female", "employee", "employees", "worker", "workers", "gender", "diversity", "women", "men",
            "emissions", "carbon", "scope 1", "scope 2", "scope 3", "ghg", "greenhouse gas", "co2",
            "water", "consumption", "usage", "kl",
            "energy", "electricity", "fuel", "power", "renewable",
            "waste", "generated", "generation", "tonnes",
            "esg", "sustainability", "brsr"
        ]
        has_compan = "compan" in query_lower
        has_ranking_esg = any(w in query_lower for w in ranking_esg_keywords) or len(qu_result.get("topics", [])) > 0 or len(metric_keys) > 0
        
        if has_compan and has_ranking_esg:
            if lane == "G":
                lane = "E"

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
