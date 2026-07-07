from typing import Dict, Any, Tuple
from src.retrieval.company_router import CompanyRouter
from src.processing.metric_taxonomy import ALIASED_METRICS, METRIC_TAXONOMY

class QueryClassifier:
    def __init__(self):
        self.company_router = CompanyRouter()
        self.comparison_keywords = ["compare", "comparison", "versus", "vs", "difference", "contrasted", "higher than", "lower than"]

    def classify(self, query: str) -> Dict[str, Any]:
        """
        Determines the routing lane (A, B, or C) and extracts metadata.
        Returns:
            {
                "lane": "A" | "B" | "C",
                "companies": List[str],
                "years": List[str],
                "metric_key": Optional[str],
                "status": "ok" | "missing_company"
            }
        """
        companies, years = self.company_router.resolve_companies_and_years(query)
        
        # Check for comparison signals
        is_comparison = len(companies) >= 2 or any(k in query.lower() for k in self.comparison_keywords)
        
        # If no companies found but comparison is requested, or if no companies found at all
        if not companies:
            # Check if this query is a metadata query (e.g., "list all companies")
            if "list" in query.lower() and "compan" in query.lower():
                return {
                    "lane": "A",
                    "companies": [],
                    "years": [],
                    "metric_key": "list_companies",
                    "status": "ok"
                }
            return {
                "lane": "B",
                "companies": [],
                "years": years,
                "metric_key": None,
                "status": "missing_company"
            }

        # Check for specific metrics keywords to route to Lane A
        matched_metric_key = None
        query_lower = query.lower()
        for synonym, key in ALIASED_METRICS.items():
            if synonym in query_lower:
                matched_metric_key = key
                break

        # Decide Lane
        if is_comparison:
            lane = "C"
        elif matched_metric_key:
            lane = "A"
        else:
            lane = "B"

        return {
            "lane": lane,
            "companies": companies,
            "years": years,
            "metric_key": matched_metric_key,
            "status": "ok"
        }
