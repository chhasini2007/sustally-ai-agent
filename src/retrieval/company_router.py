import re
from typing import List, Tuple, Set
from src.database.metrics_store import MetricsStore

class CompanyRouter:
    def __init__(self):
        self.aliases = {
            "tcs": "Tata Consultancy Services Limited",
            "tata consultancy services": "Tata Consultancy Services Limited",
            "tata consultancy services limited": "Tata Consultancy Services Limited",
            "infosys": "Infosys Limited",
            "infosys limited": "Infosys Limited",
            "south indian bank": "The South Indian Bank Limited",
            "the south indian bank limited": "The South Indian Bank Limited",
            "sib": "The South Indian Bank Limited"
        }
        self.metrics_store = MetricsStore()

    def get_known_companies(self) -> List[str]:
        # Return companies from database, combined with keys in self.aliases
        db_companies = self.metrics_store.get_all_companies()
        known = set(db_companies)
        for val in self.aliases.values():
            known.add(val)
        return list(known)

    def resolve_companies_and_years(self, query: str) -> Tuple[List[str], List[str]]:
        """
        Parses query to extract:
        1. List of canonical company names matched.
        2. List of 4-digit years matched.
        """
        query_lower = query.lower()
        resolved_companies = set()
        
        # 1. Resolve via explicit alias match
        for alias, canonical in self.aliases.items():
            # Match boundary allowing underscores/hyphens/slashes
            pattern = rf"(?:^|[^a-zA-Z0-9]){re.escape(alias)}(?:$|[^a-zA-Z0-9])"
            if re.search(pattern, query_lower):
                resolved_companies.add(canonical)
                
        # 2. Resolve via database company names if not found
        if not resolved_companies:
            db_companies = self.metrics_store.get_all_companies()
            for company in db_companies:
                pattern = rf"(?:^|[^a-zA-Z0-9]){re.escape(company.lower())}(?:$|[^a-zA-Z0-9])"
                if re.search(pattern, query_lower):
                    resolved_companies.add(company)
                # Try matching parts of company names (e.g. "Tata" for "Tata Consultancy Services Limited")
                elif len(company) > 3:
                    parts = [p.lower() for p in company.split() if len(p) > 3]
                    for part in parts:
                        part_pattern = rf"(?:^|[^a-zA-Z0-9]){re.escape(part)}(?:$|[^a-zA-Z0-9])"
                        if re.search(part_pattern, query_lower):
                            resolved_companies.add(company)
                        
        # 3. Extract years (4 digit numbers starting with 20 or 19)
        years = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", query)
        
        return list(resolved_companies), years
