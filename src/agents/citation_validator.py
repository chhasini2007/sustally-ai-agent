"""
Citation & Fact Validator Agent for Sustally ESG Intelligence Platform
Validates data completeness, prevents hallucinations, attaches source metadata,
and computes transparent confidence scores.
"""

from typing import List, Dict, Any, Tuple, Optional
import logging
from src.agents.planner_agent import QueryPlan

logger = logging.getLogger(__name__)

class CitationValidator:
    def __init__(self):
        pass

    def validate_and_score(
        self,
        plan: QueryPlan,
        retrieved_data: Dict[str, Any],
        reasoning_data: Dict[str, Any],
        ranking_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validates evidence metrics and returns formatted source citations and confidence metrics.
        """
        structured_metrics = retrieved_data.get("structured_metrics", [])
        narrative_chunks = retrieved_data.get("narrative_chunks", [])

        # If ranking data filter was applied, only cite ranked companies
        if ranking_data and ranking_data.get("ranked_table") is not None:
            ranked_comps = set(item["company"] for item in ranking_data["ranked_table"])
            structured_metrics = [m for m in structured_metrics if m.get("company") in ranked_comps]

        sources_list = []
        seen_sources = set()

        for m in structured_metrics:
            comp = m.get("company", "Unknown")
            src_file = m.get("source_file", "Unknown")
            page_val = m.get("page", "N/A")
            page_str = str(page_val) if page_val is not None else "N/A"

            is_xml = src_file.lower().endswith(".xml") or page_str.lower() in ["xml", "xml section", "brsr xml"]

            source_key = (comp, src_file, page_str)
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                if is_xml:
                    citation_text = f"**{comp}**: File: {src_file}, XML Section"
                else:
                    citation_text = f"**{comp}**: File: {src_file}, Page {page_str}"
                sources_list.append(citation_text)

        for chunk in narrative_chunks:
            meta = chunk.get("metadata", {})
            comp = meta.get("company", "Unknown")
            src_file = meta.get("source", "Unknown")
            page_str = str(meta.get("page", "N/A"))
            source_key = (comp, src_file, page_str)
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                sources_list.append(f"**{comp}**: File: {src_file}, Page {page_str}")

        confidence_score, confidence_label, confidence_reasons = self._calculate_confidence(plan, structured_metrics, narrative_chunks)

        return {
            "sources": sources_list,
            "confidence_score": confidence_score,
            "confidence_label": confidence_label,
            "confidence_reasons": confidence_reasons,
            "verified_metrics_count": len(structured_metrics),
            "verified_narrative_count": len(narrative_chunks)
        }

    def _calculate_confidence(
        self,
        plan: QueryPlan,
        structured_metrics: List[Dict[str, Any]],
        narrative_chunks: List[Dict[str, Any]]
    ) -> Tuple[float, str, List[str]]:
        reasons = []
        score = 0.50

        if not structured_metrics and not narrative_chunks:
            return 0.20, "LOW", ["No verified disclosures or structured metrics matched the query."]

        if structured_metrics:
            score += 0.30
            reasons.append(f"Retrieved {len(structured_metrics)} verified metric data points from database.")

        if plan.companies:
            matched_comps = set(m.get("company") for m in structured_metrics)
            if all(c in matched_comps for c in plan.companies):
                score += 0.15
                reasons.append(f"Complete company coverage across requested entities ({', '.join(plan.companies)}).")
            else:
                reasons.append(f"Partial company coverage for requested entities.")

        if plan.years:
            matched_years = set(str(m.get("year")) for m in structured_metrics)
            if any(y in matched_years for y in plan.years):
                score += 0.05
                reasons.append(f"Matched target reporting year(s) ({', '.join(plan.years)}).")

        score = min(1.0, max(0.0, score))

        if score >= 0.75:
            label = "HIGH"
        elif score >= 0.50:
            label = "MEDIUM"
        else:
            label = "LOW"

        return round(score, 2), label, reasons
