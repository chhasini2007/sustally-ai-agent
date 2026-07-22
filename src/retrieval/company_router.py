import re
import os
import csv
import difflib
import logging
from typing import List, Tuple, Set, Dict, Optional, Any
from src.database.metrics_store import MetricsStore

logger = logging.getLogger(__name__)

ENGLISH_STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "you're", "you've", "you'll", "you'd", 
    "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "she's", "her", "hers", 
    "herself", "it", "it's", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", "which", 
    "who", "whom", "this", "that", "that'll", "these", "those", "am", "is", "are", "was", "were", "be", "been", 
    "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", 
    "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", "about", "against", 
    "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
    "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", 
    "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", 
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", 
    "don", "don't", "should", "should've", "now", "d", "ll", "m", "o", "re", "ve", "y", "ain", "aren", 
    "aren't", "couldn", "couldn't", "didn", "didn't", "doesn", "doesn't", "hadn", "hadn't", "hasn", "hasn't", 
    "haven", "haven't", "isn", "isn't", "ma", "mightn", "mightn't", "mustn", "mustn't", "needn", "needn't", 
    "shan", "shan't", "shouldn", "shouldn't", "wasn", "wasn't", "weren", "weren't", "won", "won't", "wouldn", 
    "wouldn't",
    # ESG and domain stopwords
    "data", "table", "page", "report", "reports", "document", "documents", "footnote", "footnotes", "section", 
    "sections", "figure", "figures", "value", "values", "total", "totals", "market", "markets", "location", 
    "locations", "based", "share", "shares", "ratio", "ratios", "percentage", "percentages", "compare", 
    "compares", "compared", "comparing", "count", "counts", "emissions", "emission", "year", "years", "scope", 
    "greenhouse", "carbon", "sustainability", "environmental", "water", "consumption", "gas", "electricity", 
    "waste", "energy", "net", "zero", "social", "governance", "esg", "brsr", "annual", "audit", "compliance", 
    "policy", "strategy", "strategies", "target", "targets", "initiative", "initiatives", "disclosure", 
    "disclosures", "board", "stakeholder", "stakeholders", "performance", "progress", "metric", "metrics", 
    "wages", "wage", "salary", "salaries", "remuneration", "average", "averages", "number", "numbers", 
    "amount", "amounts", "reported", "reporting", "many", "much", "show", "shows", "give", "gives", "list", 
    "lists", "get", "gets", "view", "views", "find", "finds", "select", "selects", "choose", "chooses", 
    "analyze", "analyzes", "analysis", "corporation", "corp", "company", "companies", "limited", "ltd", "llp", 
    "bank", "banks", "insurance", "industries", "industry", "steel", "cement", "housing", "finance", "global", 
    "national", "securities", "holding", "holdings", "infrastructure", "development", "investments", 
    "investment", "capital", "mutual", "fund", "funds", "technologies", "technology", "software", "solutions", 
    "digital", "systems", "enterprises", "enterprise", "specific", "good", "general", "look", "looks", 
    "information", "details", "detail", "chart", "charts", "graph", "graphs", "plot", "plots", "use", "uses", 
    "using", "used", "tell", "tells", "performs", "perform", "performed", "performing", "employee", 
    "employees", "invested", "invest", "investing", "create", "creates", "created", "creating", "climate", 
    "reduction", "reductions", "increase", "increases", "decrease", "decreases", "change", "changes", 
    "growth", "grow", "grown", "decline", "declines", "declined", "difference", "differences", "versus", "vs", 
    "higher", "lower", "more", "less", "trend", "trends", "yoy", "year-over-year", "approach", "management",
    "corporate", "business", "material", "materials", "materiality", "issue", "issues", "major", "significant", "visible",
    "usage", "dependence", "mentioned", "increasing", "efficiency", "renewable", "france", "paris",
    "pharmaceutical", "pharmaceuticals", "pharma", "banking", "banks", "chemical", "chemicals", "telecom", "energy", "cement", "automobile", "auto"
}

IGNORE_WORDS = {
    "what", "which", "are", "is", "the", "this", "that", "report", "summary", 
    "show", "compare", "find", "about", "analysis", "key", "highlights", 
    "give", "me", "it", "its", "their"
}

CORPORATE_SUFFIXES = [
    "limited", "ltd", "corporation", "corp", "company", "co", "bank", "llp", "ltd.", "co.",
    "of", "india", "and", "the", "inc", "incorporated", "holdings", "industries", "enterprise",
    "enterprises", "capital", "finance", "services", "securities", "solutions", "systems",
    "technologies", "technology", "materials", "markets", "financial", "global", "international", "group"
]


class CompanyRouter:
    def __init__(self, csv_path: Optional[str] = None):
        self.metrics_store = MetricsStore()
        self.stopwords = set(ENGLISH_STOPWORDS)
        self.ignore_words = set(IGNORE_WORDS)
        
        self.aliases = {
            "tcs": "Tata Consultancy Services Limited",
            "tata consultancy services": "Tata Consultancy Services Limited",
            "tata consultancy services limited": "Tata Consultancy Services Limited",
            "tata chemicals": "Tata Chemicals Limited",
            "tata chemicals limited": "Tata Chemicals Limited",
            "infosys": "Infosys Limited",
            "infosys limited": "Infosys Limited",
            "south indian bank": "The South Indian Bank Limited",
            "the south indian bank limited": "The South Indian Bank Limited",
            "sib": "The South Indian Bank Limited",
            "canara": "Canara Bank",
            "canara bank": "Canara Bank",
            "can fin": "Can Fin Homes Limited",
            "can fin homes": "Can Fin Homes Limited",
            "reliance": "Reliance Industries Limited",
            "reliance industries": "Reliance Industries Limited",
            "reliance industries limited": "Reliance Industries Limited",
            "lupin": "Lupin Limited",
            "persistent": "Persistent Systems Limited",
            "pricol": "Pricol Limited",
            "blue star": "Blue Star Limited"
        }
        
        self.csv_path = csv_path or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "CF-BRSR-equities-14-Jul-2026.csv")
        self.equities_companies = self._load_csv_companies()

    def _load_csv_companies(self) -> List[str]:
        companies = []
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row and row[0].strip():
                            comp_name = row[0].strip().strip('"')
                            companies.append(comp_name)
            except Exception as e:
                logger.warning(f"Could not load CSV equities file: {e}")
        return companies

    def get_known_companies(self) -> List[str]:
        db_companies = self.metrics_store.get_all_companies()
        known = set(db_companies)
        known.update(self.equities_companies)
        known.update(self.aliases.values())
        return sorted(list(known))

    def detect_company_from_query(self, query: str) -> Optional[List[str]]:
        query_lower = query.lower()
        query_clean = " ".join(re.findall(r"\b\w+\b", query_lower))
        if not query_clean.strip():
            return None

        matched_companies: List[str] = []

        # Stage 1: Exact aliases
        sorted_aliases = sorted(self.aliases.keys(), key=len, reverse=True)
        for alias in sorted_aliases:
            pattern = rf"\b{re.escape(alias.lower())}\b"
            if re.search(pattern, query_clean):
                canonical = self.aliases[alias]
                if canonical not in matched_companies:
                    matched_companies.append(canonical)

        if matched_companies:
            return matched_companies

        # Stage 2: Full company names and core names
        known_companies = self.get_known_companies()
        
        for comp in known_companies:
            comp_lower = comp.lower()
            comp_words = comp_lower.split()
            core_words = [w for w in comp_words if w not in CORPORATE_SUFFIXES]
            core_name = " ".join(core_words)

            if len(core_name) >= 3 and core_name not in self.stopwords and core_name not in self.ignore_words:
                pattern = rf"\b{re.escape(core_name)}\b"
                if re.search(pattern, query_clean):
                    if comp not in matched_companies:
                        matched_companies.append(comp)

            pattern_full = rf"\b{re.escape(comp_lower)}\b"
            if re.search(pattern_full, query_clean):
                if comp not in matched_companies:
                    matched_companies.append(comp)

        if matched_companies:
            return matched_companies

        # Stage 3: Strict fuzzy matching for company core names
        candidate_words = self._get_candidates(query_lower)

        if not candidate_words:
            return None

        fuzzy_matches = set()
        candidate_phrases = [(w, True) for w in candidate_words]
        for i in range(len(candidate_words) - 1):
            candidate_phrases.append((f"{candidate_words[i]} {candidate_words[i+1]}", False))

        for cand, is_single in candidate_phrases:
            for comp in known_companies:
                comp_lower = comp.lower()
                comp_words = comp_lower.split()
                core_words = [w for w in comp_words if w not in CORPORATE_SUFFIXES]

                if is_single:
                    for cw in core_words:
                        if len(cw) >= 4 and cw not in self.stopwords and cw not in self.ignore_words:
                            ratio = difflib.SequenceMatcher(None, cand, cw).ratio()
                            if ratio >= 0.90 and abs(len(cand) - len(cw)) <= 1:
                                fuzzy_matches.add(comp)
                                break
                else:
                    cand_words = cand.split()
                    cand_len = len(cand_words)
                    for i in range(len(core_words) - cand_len + 1):
                        sub_phrase = " ".join(core_words[i : i + cand_len])
                        ratio = difflib.SequenceMatcher(None, cand, sub_phrase).ratio()
                        if ratio >= 0.88:
                            fuzzy_matches.add(comp)
                            break

        if fuzzy_matches:
            return list(fuzzy_matches)

        return None

    def _get_candidates(self, query_lower: str) -> List[str]:
        words = re.findall(r"\b\w+\b", query_lower)
        candidates = [
            w for w in words 
            if w not in self.stopwords and w not in self.ignore_words and not w.isdigit() and len(w) >= 3
        ]
        return candidates

    def analyze_resolution(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        years = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", query)

        # Ambiguity check for "tata"
        if re.search(r"\btata\b", query_lower) and not re.search(r"\btata\s+(consultancy|chemicals)\b", query_lower):
            return {
                "status": "ambiguous",
                "companies": [],
                "years": years,
                "matched_term": "tata",
                "matches": ["Tata Consultancy Services Limited", "Tata Chemicals Limited"]
            }

        matched = self.detect_company_from_query(query)
        candidates = self._get_candidates(query_lower)

        if matched is None:
            if not candidates:
                return {
                    "status": "missing_company",
                    "companies": [],
                    "years": years,
                    "matched_term": None,
                    "matches": []
                }
            else:
                first_unresolved = candidates[0]
                match_in_query = re.search(rf"\b{re.escape(first_unresolved)}\b", query, re.IGNORECASE)
                term_display = match_in_query.group(0) if match_in_query else first_unresolved.title()
                return {
                    "status": "unresolved",
                    "companies": [],
                    "years": years,
                    "matched_term": term_display,
                    "matches": []
                }

        if len(matched) > 1:
            return {
                "status": "ok",
                "companies": matched,
                "years": years,
                "matched_term": None,
                "matches": []
            }

        return {
            "status": "ok",
            "companies": matched,
            "years": years,
            "matched_term": None,
            "matches": []
        }

    def resolve_companies_and_years(self, query: str) -> Tuple[List[str], List[str]]:
        analysis = self.analyze_resolution(query)
        if analysis["status"] == "ok":
            return analysis["companies"], analysis["years"]
        return [], analysis["years"]


def detect_company_from_query(query: str) -> Optional[List[str]]:
    router = CompanyRouter()
    return router.detect_company_from_query(query)
