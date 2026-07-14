import re
import logging
import json
from typing import List, Dict, Any, Tuple, Optional
from src.retrieval.company_router import CompanyRouter
from src.processing.metric_taxonomy import ALIASED_METRICS, METRIC_TAXONOMY
from src.llm.llm_router import LLMRouter

logger = logging.getLogger(__name__)

def _is_genuine_follow_up(query: str, has_pronoun: bool) -> bool:
    query_lower = query.lower()
    if has_pronoun:
        return True
        
    # Direct transition starters
    starters = ["what about", "how about", "and ", "compare ", "also ", "then ", "what is the ", "what was the "]
    if any(query_lower.startswith(s) for s in starters):
        return True
        
    # Check for direct references to the company, report, or comparative years
    ref_keywords = [
        "the company", "this company", "the report", "this report", 
        "the metrics", "these metrics", "previous year", "previous reporting year", 
        "prior year", "reporting year", "compared with", "compared to", "their"
    ]
    if any(r in query_lower for r in ref_keywords):
        return True
        
    # Short direct metric lookup is generally a follow-up
    words = re.findall(r"\b\w+\b", query_lower)
    if len(words) < 6:
        return True
        
    return False

def _has_capitalized_candidate(query: str, stopwords: set) -> bool:
    # Find all words in the original query
    words = query.split()
    if not words:
        return False
        
    # Check first word only if it is not a common question starter/stopword
    first_word = words[0].strip("?,.!:;\"'")
    if first_word and first_word[0].isupper() and first_word.lower() not in stopwords:
        question_starters = {"what", "how", "why", "when", "who", "which", "where", "can", "could", "should", "would", "is", "are", "was", "were", "do", "does", "did", "show", "compare", "list", "tell", "summarize", "explain"}
        if first_word.lower() not in question_starters:
            return True
            
    # Check other words
    for w in words[1:]:
        w_clean = w.strip("?,.!:;\"'")
        if w_clean and w_clean[0].isupper():
            if w_clean.lower() not in stopwords:
                return True
                
    return False

CONVERSATIONAL_PHRASES = {
    # Greetings & Small talk
    "hi": "greeting",
    "hello": "greeting",
    "hey": "greeting",
    "greetings": "greeting",
    "good morning": "greeting",
    "good afternoon": "greeting",
    "good evening": "greeting",
    "hi there": "greeting",
    "hello there": "greeting",
    "hey there": "greeting",
    "how are you": "greeting",
    "how are you doing": "greeting",
    "how's it going": "greeting",
    "how is it going": "greeting",
    "yo": "greeting",
    
    # Thanks & Acknowledgement
    "thanks": "thanks",
    "thank you": "thanks",
    "ok": "thanks",
    "got it": "thanks",
    "okay": "thanks",
    "awesome": "thanks",
    "great": "thanks",
    "thank you very much": "thanks",
    "thank you so much": "thanks",
    "perfect": "thanks",
    "sounds good": "thanks",
    
    # Meta questions
    "what can you do": "meta",
    "how does this work": "meta",
    "what is this": "meta",
    "what are your capabilities": "meta",
    "explain your capabilities": "meta",
    "how do you work": "meta",
    "who are you": "meta",
    "what is this agent": "meta",
    "explain this agent": "meta",
    "what is the agent about": "meta",
    "how to use this": "meta",
    "help": "meta",
    "about": "meta",
    "can you help me": "meta",
}

def check_conversational_intent(query: str) -> Optional[str]:
    """
    Checks if a query is a conversational greeting, thanks, or meta question.
    Returns the conversational category ('greeting', 'thanks', 'meta') or None.
    """
    # Normalize query by lowercasing and stripping non-alphanumeric at start/end
    q = query.strip().lower()
    q_clean = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', q)
    
    if not q_clean:
        return None
        
    # Check exact match
    if q_clean in CONVERSATIONAL_PHRASES:
        return CONVERSATIONAL_PHRASES[q_clean]
        
    # Split by common punctuation to check if it consists entirely of conversational phrases
    # e.g., "hi, thank you!" -> ["hi", "thank you"]
    parts = [re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', p).strip() for p in re.split(r'[,.!?;\n]', q) if p.strip()]
    if parts and all(p in CONVERSATIONAL_PHRASES for p in parts):
        categories = [CONVERSATIONAL_PHRASES[p] for p in parts if p in CONVERSATIONAL_PHRASES]
        if "meta" in categories:
            return "meta"
        if "thanks" in categories:
            return "thanks"
        if categories:
            return categories[0]
            
    return None

def question_understanding(query: str, conversation_context: List[Dict[str, Any]] = None, active_company: str = None) -> Dict[str, Any]:
    """
    Analyzes the raw question and conversation context to return a structured understanding object.
    Uses a two-tier approach: deterministic Tier 1 first, LLM-based Tier 2 fallback only when inconclusive.
    """
    if conversation_context is None:
        conversation_context = []

    # Early check for conversational / greeting intent
    conv_category = check_conversational_intent(query)
    if conv_category is not None:
        return {
            "companies": [],
            "years": [],
            "topics": [],
            "metric_keys": [],
            "intent": "conversational",
            "is_deep_dive": False,
            "confidence": "high",
            "status": "conversational",
            "matched_term": None,
            "matches": [],
            "conversational_category": conv_category
        }

    router = CompanyRouter()
    # Prevent false partial matches on "renewable"
    router.stopwords.add("renewable")
    query_lower = query.lower()

    # --- TIER 1 extraction ---
    # 1. Company extraction
    # Resolve companies and years, checking recent conversation history first if omitted or uses pronouns.
    # Exclude demonstratives like 'this', 'that' to avoid false triggers on phrases like 'this report'.
    pronoun_pattern = re.compile(r"\b(their|its|they|them|it|he|she)\b", re.IGNORECASE)
    has_pronoun = bool(pronoun_pattern.search(query))

    # Detect companies in the current query
    analysis = router.analyze_resolution(query)
    status = analysis.get("status", "ok")
    matched_term = analysis.get("matched_term", None)
    matches = analysis.get("matches", [])

    if status == "ok":
        resolved_companies = list(analysis.get("companies", []))
    else:
        resolved_companies = []

    # Extract years from the current query
    current_years = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", query)
    resolved_years = list(current_years)

    # 2. Topics extraction
    esg_keywords = {
        "water": ["water", "kl", "aquatic", "liquid"],
        "governance": ["governance", "board", "director", "directors", "committee", "ethics", "compliance", "csr", "risk"],
        "emissions": ["emissions", "carbon", "scope 1", "scope 2", "scope 3", "ghg", "greenhouse gas"],
        "energy": ["energy", "electricity", "fuel", "power", "renewable", "solar", "wind", "hydrogen"],
        "waste": ["waste", "hazardous", "non-hazardous", "recycled", "disposed", "landfill", "tonnes"],
        "biodiversity": ["biodiversity", "habitat", "forest", "species", "conservation"],
        "diversity": ["diversity", "gender", "female", "male", "women", "men", "workforce", "employee", "employees", "worker", "workers"],
        "safety": ["safety", "injury", "injuries", "accident", "accidents", "health", "fatality", "fatalities"],
        "sustainability": ["sustainability", "esg", "brsr", "report", "reports", "target", "initiative", "policy", "strategy", "commitment", "disclosure", "supply chain", "climate", "community", "audit", "stakeholder", "environment", "social", "human rights", "net zero", "inclusion", "labor", "conservation", "ethics", "integrity", "corporate responsibility", "gri"]
    }
    matched_topics = []
    for topic, keywords in esg_keywords.items():
        if any(kw in query_lower for kw in keywords):
            matched_topics.append(topic)

    # 3. Metric keys extraction (fuzzy/alias matching)
    matched_metric_keys = []
    sorted_synonyms = sorted(ALIASED_METRICS.keys(), key=len, reverse=True)
    for synonym in sorted_synonyms:
        if synonym in query_lower:
            key = ALIASED_METRICS[synonym]
            if key not in matched_metric_keys:
                matched_metric_keys.append(key)

    has_esg_topic = len(matched_topics) > 0 or len(matched_metric_keys) > 0

    # 4. Intent and Keywords matching for context fallback checks
    # YoY / Trend Indicators
    yoy_indicators = [
        r"year\s*over\s*year",
        r"\byoy\b",
        r"percentage\s*(?:change|reduction|increase|decrease|growth|decline)",
        r"growth\b",
        r"decline\b",
        r"trend\b",
        r"\bchanged\b",
        r"\bchange\b",
        r"increase\s+from",
        r"decrease\s+from",
        r"reduction\s+from",
        r"between\s+\d{4}\s+and\s+\d{4}",
        r"from\s+\d{4}\s+to\s+\d{4}"
    ]
    is_yoy_query = any(re.search(pat, query_lower) for pat in yoy_indicators)

    # Comparison Keywords
    comparison_keywords = ["compare", "comparison", "versus", "vs", "difference", "contrasted", "higher than", "lower than", "more than", "less than"]
    is_comparison = len(resolved_companies) >= 2 or any(k in query_lower for k in comparison_keywords)

    # 5. Context awareness resolution
    has_follow_up_phrase = any(phrase in query_lower for phrase in [
        "this company", "the company", "this report", "the report", 
        "previous year", "previous reporting year", "the metrics", "these metrics",
        "their", "its", "it"
    ])
    
    question_starters = {"what", "how", "why", "when", "who", "which", "where", "can", "could", "should", "would", "is", "are", "was", "were", "do", "does", "did", "show", "compare", "list", "tell", "summarize", "explain"}
    first_word_lower = query.split()[0].lower().strip("?,.!:;\"'") if query.split() else ""
    is_question = first_word_lower in question_starters
    
    is_follow_up = (
        has_pronoun or 
        has_follow_up_phrase or 
        _is_genuine_follow_up(query, has_pronoun) or
        (is_question and has_esg_topic)
    )

    if not resolved_companies and is_follow_up:
        # Scan last 10 messages of history in reverse order
        history = list(conversation_context)
        if history and history[-1].get("content") == query and history[-1].get("role") == "user":
            history = history[:-1]
            
        context_comps = []
        context_yrs = []
        
        for msg in reversed(history[-10:]):
            msg_content = msg.get("content", "")
            msg_companies = router.detect_company_from_query(msg_content)
            if msg_companies:
                context_comps = list(msg_companies)
                break
                
        for msg in reversed(history[-10:]):
            msg_content = msg.get("content", "")
            msg_years = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", msg_content)
            if msg_years:
                context_yrs = list(msg_years)
                break
                
        if context_comps:
            resolved_companies = context_comps
            status = "ok"
            matched_term = None
            matches = []
            
            # Also carry forward the year if not specified in the current query
            if not resolved_years and context_yrs:
                resolved_years = context_yrs

    # Pull extra companies from context if this is a comparison query and we only have 1 company
    if (is_comparison) and len(resolved_companies) < 2:
        history = list(conversation_context)
        if history and history[-1].get("content") == query and history[-1].get("role") == "user":
            history = history[:-1]
        for msg in reversed(history[-10:]):
            msg_content = msg.get("content", "")
            msg_companies = router.detect_company_from_query(msg_content)
            if msg_companies:
                for c in msg_companies:
                    if c not in resolved_companies:
                        resolved_companies.append(c)
                if len(resolved_companies) >= 2:
                    break

    if not resolved_years:
        history = list(conversation_context)
        if history and history[-1].get("content") == query and history[-1].get("role") == "user":
            history = history[:-1]
        for msg in reversed(history[-10:]):
            msg_content = msg.get("content", "")
            msg_years = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", msg_content)
            if msg_years:
                resolved_years = list(msg_years)
                break

    # 6. Deep-dive phrase detection
    deep_dive_phrases = ["deep dive", "deep-dive", "detailed analysis", "delve into", "explain in detail", "comprehensive breakdown", "granular", "dive deep", "tell me everything about", "in detail", "comprehensive", "all information about"]
    is_deep_dive = any(phrase in query_lower for phrase in deep_dive_phrases)

    # 6. Intent detection logic (deterministic)
    intent = None

    # Check for help/system/out of scope
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

    # Re-evaluate comparison since resolved_companies might have changed
    is_comparison = len(resolved_companies) >= 2 or any(k in query_lower for k in comparison_keywords)

    # Ranking Keywords
    ranking_keywords = ["rank", "ranking", "highest", "lowest", "top", "bottom", "best", "worst", "order by", "sorted by"]
    ranking_esg_keywords = [
        "female", "employee", "employees", "worker", "workers", "gender", "diversity", "women", "men",
        "emissions", "carbon", "scope 1", "scope 2", "scope 3", "ghg", "greenhouse gas", "co2",
        "water", "consumption", "usage", "kl",
        "energy", "electricity", "fuel", "power", "renewable",
        "waste", "generated", "generation", "tonnes",
        "esg", "sustainability", "brsr"
    ]
    has_compan = "compan" in query_lower
    has_ranking_keyword = any(k in query_lower for k in ranking_keywords) or bool(re.search(r"\btop\s*\d*", query_lower))
    has_ranking_esg = any(re.search(rf"\b{re.escape(w)}\b", query_lower) for w in ranking_esg_keywords)

    is_ranking = (has_ranking_keyword or has_compan) and has_ranking_esg

    # Dynamic fallback mapping for ranking/cross-company queries if no synonym matched
    if not matched_metric_keys and is_ranking:
        if "female" in query_lower or "women" in query_lower or "gender" in query_lower:
            if "wage" in query_lower or "pay" in query_lower or "remuneration" in query_lower:
                matched_metric_keys = ["female_employee_wage_share_pct"]
            else:
                matched_metric_keys = ["female_employee_headcount_share_pct"]
        elif "emission" in query_lower or "carbon" in query_lower or "co2" in query_lower:
            if "scope 2" in query_lower:
                matched_metric_keys = ["scope2_emissions_tco2e"]
            elif "scope 3" in query_lower:
                matched_metric_keys = ["scope3_emissions_tco2e"]
            else:
                matched_metric_keys = ["scope1_emissions_tco2e"]
        elif "water" in query_lower:
            matched_metric_keys = ["water_consumption_kl"]
        elif "energy" in query_lower or "electricity" in query_lower or "power" in query_lower:
            matched_metric_keys = ["renewable_energy_pct"]
        elif "waste" in query_lower:
            matched_metric_keys = ["waste_generation_tonnes"]

    # Report Summary indicators
    summary_intent_phrases = [
        "report summary", "report overview", "executive summary", "key highlights", "main findings",
        "about this report", "what is this report about", "summarize this report", "summarize the report",
        "summary of this report", "summary of the report", "what are the key highlights of this report",
        "this report", "summarize it", "what are the highlights", "explain this company"
    ]
    has_summary_intent = any(phrase in query_lower for phrase in summary_intent_phrases)

    # Scope/in-scope check
    direct_esg_terms = [
        "emissions", "carbon", "scope 1", "scope 2", "scope 3", "water",
        "energy", "waste", "governance", "csr", "biodiversity", "diversity",
        "safety", "compliance", "risk", "sustainability", "esg", "brsr",
        "xbrl", "report", "annual report", "environmental", "workforce",
        "target", "initiative", "policy", "strategy", "commitment", "disclosure",
        "board", "supply chain", "climate", "community", "audit", "stakeholder",
        "environment", "social", "human rights", "net zero", "inclusion", "labor",
        "conservation", "ethics", "integrity", "corporate responsibility", "gri", "hydrogen"
    ]
    has_direct_esg = any(concept in query_lower for concept in direct_esg_terms)
    
    esg_categories = ["gender", "workforce", "emissions", "energy", "water", "waste", "employee", "employees", "worker", "workers", "female", "male", "women", "men"]
    esg_phrasings = ["ratio", "share", "percentage", "pct", "composition", "representation", "diversity", "proportion"]
    has_esg_combo = (
        any(cat in query_lower for cat in esg_categories) and
        any(phrase in query_lower for phrase in esg_phrasings)
    )
    has_esg = has_direct_esg or has_esg_combo
    
    has_system = (
        ("list" in query_lower and "xml" in query_lower and "report" in query_lower) or
        ("metric" in query_lower and "xml" in query_lower) or
        ("list" in query_lower and "compan" in query_lower)
    )
    
    has_valid_lane = any(keyword in query_lower for keyword in [
        "compare", "comparison", "versus", "vs", "difference", "contrasted",
        "higher than", "lower than", "more than", "less than", "trend", "yoy",
        "year over year", "change", "growth", "reduction", "increase",
        "decrease", "decline", "percentage", "summarize", "summary", "overview",
        "audit", "full audit", "report", "reports"
    ])

    general_opinion_phrases = ["in general", "what do you think", "your opinion", "tell me a joke", "capital of", "who are you", "joke"]
    is_general_opinion = any(phrase in query_lower for phrase in general_opinion_phrases)

    is_in_scope = bool(resolved_companies) or has_esg or has_system or has_valid_lane
    
    # Active company inheritance fallback
    if not resolved_companies and active_company and not is_general_opinion:
        if is_follow_up or is_in_scope:
            resolved_companies = [active_company]
            status = "ok"
            matched_term = None
            matches = []
            is_in_scope = True
    
    is_unmatched = (len(resolved_companies) == 0) and (
        (not matched_metric_keys and not is_comparison and not has_summary_intent and not has_esg)
        or is_general_opinion
    )

    if is_ranking:
        has_esg = True
        is_in_scope = True
        is_unmatched = False

    # Deterministic intent resolution
    if is_system_help:
        intent = "general"
    elif not is_in_scope or is_unmatched:
        intent = "general"
    elif is_yoy_query:
        intent = "trend"
    elif is_comparison:
        intent = "comparison"
    elif is_ranking:
        intent = "ranking"
    elif matched_metric_keys:
        intent = "lookup"
    else:
        intent = "narrative"

    # Specific metadata query override
    if "list" in query_lower and "xml" in query_lower and "report" in query_lower:
        matched_metric_keys = ["list_xml_reports"]
        intent = "lookup"
    elif "metric" in query_lower and "xml" in query_lower:
        matched_metric_keys = ["list_xml_metrics"]
        intent = "lookup"
    elif "list" in query_lower and "compan" in query_lower:
        matched_metric_keys = ["list_companies"]
        intent = "lookup"

    # Overrides for status and matching based on determined intent/phrases
    if intent == "general":
        status = "ok"
        matched_term = None
        matches = []
    elif has_summary_intent and not resolved_companies:
        status = "missing_company"
        matched_term = None
        matches = []
    elif (len(resolved_companies) == 0) and has_esg and intent == "narrative":
        cross_company_phrases = [
            "which company", "which companies", "what company", "what companies", 
            "any company", "any companies", "all company", "all companies", 
            "list company", "list companies", "every company", "each company", 
            "all reports", "search all", "identify every", "identify companies"
        ]
        if any(p in query_lower for p in cross_company_phrases):
            status = "ok"
        else:
            status = "missing_company"
        matched_term = None
        matches = []

    # Determine if Tier 1 is conclusive
    has_company = len(resolved_companies) > 0
    has_clear_topic = len(matched_topics) > 0 or len(matched_metric_keys) > 0
    is_help_or_metadata = is_system_help or has_system

    is_conclusive = (
        (has_company or has_clear_topic) and intent is not None
    ) or is_help_or_metadata or (not is_in_scope and not has_pronoun) or is_unmatched or has_summary_intent

    # If we have a pronoun but resolved_companies is empty, it is NOT conclusive
    if has_pronoun and not resolved_companies:
        is_conclusive = False

    if is_conclusive:
        # Tier 1 is conclusive
        return {
            "companies": resolved_companies,
            "years": resolved_years,
            "topics": matched_topics,
            "metric_keys": matched_metric_keys,
            "intent": intent,
            "is_deep_dive": is_deep_dive,
            "confidence": "high",
            "status": status,
            "matched_term": matched_term,
            "matches": matches
        }

    # --- TIER 2 (LLM Fallback) ---
    logger.info(f"Tier 2 (LLM extraction) triggered for query: {query}")
    
    # Call LLM router
    llm_router = LLMRouter()
    
    # Format messages context (last 10 messages prior to current query)
    context_str = ""
    if conversation_context:
        history = list(conversation_context)
        if history and history[-1].get("content") == query and history[-1].get("role") == "user":
            history = history[:-1]
        context_lines = []
        for msg in history[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_lines.append(f"{role}: {content}")
        context_str = "\n".join(context_lines)

    # Known companies
    known_companies = router.get_known_companies()
    
    active_company_str = f"ACTIVE SELECTED COMPANY: {active_company}\n\n" if active_company else ""
    
    system_prompt = (
        "You are an expert NLP extraction tool for a corporate sustainability (ESG) report database.\n"
        "Your task is to analyze the user's question and any recent conversation context, and extract structured metadata.\n\n"
        f"{active_company_str}"
        "TAXONOMY OF METRIC KEYS:\n"
        " - scope1_emissions_tco2e (Scope 1 Emissions)\n"
        " - scope2_emissions_tco2e (Scope 2 Emissions)\n"
        " - scope3_emissions_tco2e (Scope 3 Emissions)\n"
        " - water_consumption_kl (Water Consumption/Usage)\n"
        " - renewable_energy_pct (Renewable Energy Share/Percentage)\n"
        " - female_employee_headcount_share_pct (Female Employee Representation percentage)\n"
        " - female_employee_count (Female employee count/headcount)\n"
        " - total_employee_count (Total headcount/employee count)\n"
        " - female_employee_wage_share_pct (Wages paid to female employees share)\n"
        " - waste_generation_tonnes (Total Waste Generated)\n\n"
        f"KNOWN COMPANIES:\n{json.dumps(known_companies)}\n\n"
        f"CONVERSATION HISTORY:\n{context_str}\n\n"
        "OUTPUT FORMAT:\n"
        "You must output ONLY a valid JSON object. Do not include any markdown formatting (do not wrap in ```json), thoughts, or explanations. "
        "Strictly follow this structure:\n"
        "{\n"
        '  "companies": ["Resolved Canonical Company Name"],\n'
        '  "years": ["YYYY"],\n'
        '  "topics": ["water", "governance", "emissions", "waste", "energy", "biodiversity", "diversity", "safety", "sustainability"],\n'
        '  "metric_keys": ["metric_key_from_taxonomy"],\n'
        '  "intent": "narrative" | "lookup" | "comparison" | "trend" | "ranking" | "general",\n'
        '  "is_deep_dive": true | false\n'
        "}\n\n"
        "Rules:\n"
        "1. Resolve pronouns (like 'their', 'its') using the conversation history to map to the correct canonical company name.\n"
        "2. If no company is mentioned or can be resolved, but an ACTIVE SELECTED COMPANY is provided, and the query is about sustainability, metrics, strategy, or report content, resolve the 'companies' list to include that canonical company name.\n"
        "3. If no company is mentioned or can be resolved and no active company is selected, leave the 'companies' list empty.\n"
        "4. Choose the appropriate intent:\n"
        "   - 'lookup': requesting a specific numeric metric for a single company/year.\n"
        "   - 'narrative': general Q&A, summary, overview, strategy, policy, etc.\n"
        "   - 'comparison': comparing multiple companies.\n"
        "   - 'trend': YoY change, growth rate, trends over time.\n"
        "   - 'ranking': ranking companies by a metric (highest/lowest/top/bottom).\n"
        "   - 'general': out-of-scope, greetings, help, etc.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Analyze this question: '{query}'"}
    ]

    try:
        # Call LLM router with stream=False
        gen, provider = llm_router.generate(messages, stream=False)
        response_text = "".join(list(gen)).strip()
        
        # Clean potential markdown wrappers
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        extracted_data = json.loads(response_text)
        
        # Validate keys in extracted_data
        result = {
            "companies": extracted_data.get("companies", []),
            "years": [str(y) for y in extracted_data.get("years", [])],
            "topics": extracted_data.get("topics", []),
            "metric_keys": extracted_data.get("metric_keys", []),
            "intent": extracted_data.get("intent", "general"),
            "is_deep_dive": bool(extracted_data.get("is_deep_dive", False)),
            "confidence": "low",
            "status": status,
            "matched_term": matched_term,
            "matches": matches
        }
        
        # Ensure companies are resolved to canonical names if possible
        for i, comp in enumerate(result["companies"]):
            resolved = router.detect_company_from_query(comp)
            if resolved:
                result["companies"][i] = resolved[0]
        
        # Adjust status based on LLM output
        if result["companies"]:
            result["status"] = "ok"
            result["matched_term"] = None
            result["matches"] = []
        else:
            result["status"] = "missing_company"
            
        return result

    except Exception as e:
        logger.error(f"Tier 2 LLM extraction failed: {str(e)}")
        # Fall back to Tier 1 results
        return {
            "companies": resolved_companies,
            "years": resolved_years,
            "topics": matched_topics,
            "metric_keys": matched_metric_keys,
            "intent": intent or "general",
            "is_deep_dive": is_deep_dive,
            "confidence": "low",
            "status": status,
            "matched_term": matched_term,
            "matches": matches
        }
