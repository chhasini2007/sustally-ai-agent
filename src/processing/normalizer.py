import re
from typing import Dict, Any

class Normalizer:
    def __init__(self):
        # Section classification rules
        self.classification_keywords = {
            "environment": ["environment", "carbon", "emission", "energy", "water", "waste", "climate", "biodiversity", "ecological"],
            "social": ["social", "employee", "diversity", "csr", "community", "human rights", "safety", "workforce", "women", "gender"],
            "governance": ["governance", "board", "ethics", "compliance", "policy", "audit", "committee", "anti-corruption", "stakeholder"],
            "strategy": ["strategy", "vision", "materiality", "framework", "ceo letter", "chairman message", "business model"],
            "metrics": ["metric", "target", "indicator", "kpi", "performance data", "esg table", "assurance statement"],
            "risk": ["risk", "mitigation", "hazard", "threat", "uncertainty", "tcfd", "scenario analysis"],
            "targets": ["target", "goal", "commitment", "net zero", "pathway", "milestone", "ambition"],
            "company_info": ["profile", "corporate information", "about us", "subsidiaries", "operation", "locations"]
        }

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        # Remove consecutive duplicate whitespace/newlines
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    def classify_section(self, text: str) -> str:
        text_lower = text.lower()
        scores = {category: 0 for category in self.classification_keywords}
        
        for category, keywords in self.classification_keywords.items():
            for word in keywords:
                # Count occurrences of the keyword
                scores[category] += text_lower.count(word)
                
        # Find the category with maximum score, default to 'strategy' if all scores are 0
        best_cat = max(scores, key=scores.get)
        if scores[best_cat] == 0:
            return "strategy"
        return best_cat
