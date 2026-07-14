import re
import difflib
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
            "sib": "The South Indian Bank Limited",
            "canara": "Canara Bank",
            "can fin": "Can Fin Homes Limited",
            "can fin homes": "Can Fin Homes Limited"
        }
        self.metrics_store = MetricsStore()
        self.stopwords = {
            # Standard English stopwords (NLTK base list)
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

            # generic corporate/finance/ESG/business terms (expanded to 80+ words)
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
            "usage", "dependence", "mentioned", "increasing", "efficiency"
        }


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
        1. List of canonical company names matched exactly or via alias.
        2. List of 4-digit years matched.
        """
        analysis = self.analyze_resolution(query)
        # Return resolved companies if status is ok, otherwise empty
        if analysis["status"] == "ok":
            return analysis["companies"], analysis["years"]
        return [], analysis["years"]

    def _get_candidates(self, query_lower: str) -> List[str]:
        words = re.findall(r"\b\w+\b", query_lower)
        candidates = [w for w in words if w not in self.stopwords and not w.isdigit() and len(w) >= 3]
        return candidates

    def detect_company_from_query(self, query: str) -> List[str] | None:
        """
        Detects company names in query based on exact aliases, full company names, or token-level fuzzy matching.
        """
        query_lower = query.lower()
        
        # Clean query by removing non-alphanumeric characters (normalize spacing)
        query_clean = " ".join(re.findall(r"\b\w+\b", query_lower))
        
        matched_companies = []
        
        # 1. Check exact aliases (whole word match)
        for alias, canonical in self.aliases.items():
            pattern = rf"\b{re.escape(alias.lower())}\b"
            if re.search(pattern, query_clean):
                if canonical not in matched_companies:
                    matched_companies.append(canonical)
                    
        # 2. Check full company names and exact core names
        db_companies = self.get_known_companies()
        suffixes = ["limited", "ltd", "corporation", "corp", "company", "co", "bank", "llp", "ltd.", "co.", "of", "india", "and", "the"]
        
        for comp in db_companies:
            comp_lower = comp.lower()
            comp_words = comp_lower.split()
            core_words = [w for w in comp_words if w not in suffixes]
            core_name = " ".join(core_words)
            
            # Check entire core name (whole word phrase match)
            if len(core_name) >= 4:
                pattern = rf"\b{re.escape(core_name)}\b"
                if re.search(pattern, query_clean):
                    if comp not in matched_companies:
                        matched_companies.append(comp)
            
            # Check full name exactly as a boundary match
            pattern_full = rf"\b{re.escape(comp_lower)}\b"
            if re.search(pattern_full, query_clean):
                if comp not in matched_companies:
                    matched_companies.append(comp)
                    
        if matched_companies:
            return matched_companies
            
        # 3. Tokenize query and generate candidates (words >= 3 chars, not stopwords)
        filtered_words = self._get_candidates(query_lower)
        if not filtered_words:
            return None
            
        candidates = []
        # Single words
        for w in filtered_words:
            candidates.append((w, True))
        # 2-word contiguous phrases
        for i in range(len(filtered_words) - 1):
            phrase = f"{filtered_words[i]} {filtered_words[i+1]}"
            candidates.append((phrase, False))
        # 3-word contiguous phrases
        for i in range(len(filtered_words) - 2):
            phrase = f"{filtered_words[i]} {filtered_words[i+1]} {filtered_words[i+2]}"
            candidates.append((phrase, False))
            
        # 4. Partial/Fuzzy matches using candidates
        partial_matches = set()
        for cand, is_single in candidates:
            for comp in db_companies:
                comp_lower = comp.lower()
                comp_words = comp_lower.split()
                core_words = [w for w in comp_words if w not in suffixes]
                
                if is_single:
                    # Single word candidate: require ratio >= 0.9 and close length
                    for cw in core_words:
                        if len(cw) >= 3:
                            ratio = difflib.SequenceMatcher(None, cand, cw).ratio()
                            if ratio >= 0.92 and abs(len(cand) - len(cw)) <= 1:
                                partial_matches.add(comp)
                                break
                else:
                    # Multi-word candidate: require ratio >= 0.8 with any contiguous sub-phrase of core_words
                    cand_words = cand.split()
                    cand_word_count = len(cand_words)
                    for i in range(len(core_words) - cand_word_count + 1):
                        sub_phrase = " ".join(core_words[i : i + cand_word_count])
                        ratio = difflib.SequenceMatcher(None, cand, sub_phrase).ratio()
                        if ratio >= 0.8:
                            partial_matches.add(comp)
                            break
                            
        if partial_matches:
            return list(partial_matches)
            
        return None

    def analyze_resolution(self, query: str) -> dict:
        """
        Performs detailed analysis of the query to identify if companies mentioned
        are resolved exactly, ambiguous, unresolved, or missing.
        """
        query_lower = query.lower()
        years = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", query)
        
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
            explicit_matches = []
            for comp in matched:
                comp_lower = comp.lower()
                has_explicit = False
                for alias, canonical in self.aliases.items():
                    if canonical == comp:
                        if re.search(rf"\b{re.escape(alias.lower())}\b", query_lower):
                            has_explicit = True
                            break
                if not has_explicit:
                    comp_words = comp_lower.split()
                    suffixes = ["limited", "ltd", "corporation", "corp", "company", "co", "bank", "llp", "ltd.", "co.", "of", "india", "and", "the"]
                    core_words = [w for w in comp_words if w not in suffixes]
                    core_name = " ".join(core_words)
                    if len(core_name) >= 4 and re.search(rf"\b{re.escape(core_name)}\b", query_lower):
                        has_explicit = True
                
                if has_explicit:
                    explicit_matches.append(comp)
            
            if len(explicit_matches) >= 2:
                return {
                    "status": "ok",
                    "companies": explicit_matches,
                    "years": years,
                    "matched_term": None,
                    "matches": []
                }
            else:
                matching_candidates = []
                for cand in candidates:
                    for comp in matched:
                        comp_lower = comp.lower()
                        comp_words = comp_lower.split()
                        suffixes = ["limited", "ltd", "corporation", "corp", "company", "co", "bank", "llp", "ltd.", "co.", "of", "india", "and", "the"]
                        core_words = [w for w in comp_words if w not in suffixes]
                        
                        # Fuzzy match check for candidate in core_words
                        for cw in core_words:
                            if len(cw) >= 3:
                                ratio = difflib.SequenceMatcher(None, cand, cw).ratio()
                                if ratio >= 0.92 and abs(len(cand) - len(cw)) <= 1:
                                    matching_candidates.append(cand)
                                    break
                        if matching_candidates:
                            break
                            
                if matching_candidates:
                    matched_term = matching_candidates[0]
                    match_in_query = re.search(rf"\b{re.escape(matched_term)}\b", query, re.IGNORECASE)
                    term_display = match_in_query.group(0) if match_in_query else matched_term.title()
                else:
                    term_display = candidates[0].title() if candidates else "Multiple Companies"
                return {
                    "status": "ambiguous",
                    "companies": [],
                    "years": years,
                    "matched_term": term_display,
                    "matches": matched
                }
                
        return {
            "status": "ok",
            "companies": matched,
            "years": years,
            "matched_term": None,
            "matches": []
        }

def detect_company_from_query(query: str) -> List[str] | None:
    router = CompanyRouter()
    return router.detect_company_from_query(query)
