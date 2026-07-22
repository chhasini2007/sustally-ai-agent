"""
Report Generator Agent for Sustally ESG Intelligence Platform
Standardizes analyst outputs into Bloomberg ESG Terminal / MSCI ESG Intelligence format
with complete diagnostic execution path logging.
"""

from typing import List, Dict, Any, Optional
import logging
from src.agents.planner_agent import QueryPlan

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self):
        pass

    def generate_report(
        self,
        plan: QueryPlan,
        retrieved_data: Dict[str, Any],
        reasoning_data: Dict[str, Any],
        validation_data: Dict[str, Any],
        ranking_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generates the final formatted ESG Analyst Markdown Report.
        """
        structured_metrics = retrieved_data.get("structured_metrics", [])
        narrative_chunks = retrieved_data.get("narrative_chunks", [])
        sources = validation_data.get("sources", [])
        conf_label = validation_data.get("confidence_label", "MEDIUM")
        conf_score = validation_data.get("confidence_score", 0.50)
        conf_reasons = validation_data.get("confidence_reasons", [])

        sections = []

        # Section 1: Executive Summary
        exec_summary = self._build_executive_summary(plan, structured_metrics, ranking_data, reasoning_data)
        sections.append(f"### Executive Summary\n{exec_summary}")

        # Section 2: Evidence & Key Findings
        evidence = self._build_evidence_findings(plan, structured_metrics, reasoning_data, ranking_data)
        sections.append(f"### Evidence & Key Findings\n{evidence}")

        # Section 3: Metrics Table
        metrics_table = self._build_metrics_table(structured_metrics, ranking_data)
        if metrics_table:
            sections.append(f"### Metrics Table\n{metrics_table}")

        # Section 4: Analytical Reasoning & Calculations
        analytical_reasoning = reasoning_data.get("analytical_summary", "")
        if analytical_reasoning:
            sections.append(f"### Comparison & Analytical Reasoning\n{analytical_reasoning}")

        # Section 5: Limitations & Failure Handling
        limitations = self._build_limitations(plan, structured_metrics, retrieved_data)
        sections.append(f"### Limitations & Missing Data Explanation\n{limitations}")

        # Section 6: Confidence Level
        conf_text = f"**Confidence Score:** {conf_score} / 1.0 ({conf_label})\n"
        for r in conf_reasons:
            conf_text += f"- {r}\n"
        sections.append(f"### Confidence Level\n{conf_text.strip()}")

        # Section 7: Sources & Citations
        if sources:
            sources_text = "\n".join(f"- {s}" for s in sources)
        else:
            sources_text = "- No direct verified citations available for this query."
        sections.append(f"### Sources & Evidence\n{sources_text}")

        # Section 8: Query Execution Log & Diagnostics (Requirement 11)
        exec_path_str = " -> ".join(plan.execution_path) if plan.execution_path else "PlannerAgent -> RetrievalAgent -> ReasoningAgent -> CitationValidator"
        reasoning_sources_str = ", ".join(sources) if sources else "None"
        diagnostics = (
            f"---\n### Query Execution Log & Diagnostics\n"
            f"- **Intent**: `{plan.intent}`\n"
            f"- **Execution Path**: `{exec_path_str}`\n"
            f"- **Structured Metrics Found**: {len(structured_metrics)}\n"
            f"- **Vector Chunks Retrieved**: {len(narrative_chunks)}\n"
            f"- **Reasoning Sources**: {reasoning_sources_str}\n"
            f"- **Final Confidence**: {conf_score} ({conf_label})\n"
            f"- **Target Entities**: {', '.join(plan.companies) if plan.companies else 'All Indexed Entities'}\n"
            f"- **Target Metrics**: {', '.join(plan.metric_keys) if plan.metric_keys else 'N/A'}"
        )
        sections.append(diagnostics)

        return "\n\n".join(sections)

    def _build_executive_summary(
        self,
        plan: QueryPlan,
        metrics: List[Dict[str, Any]],
        ranking_data: Optional[Dict[str, Any]],
        reasoning_data: Dict[str, Any]
    ) -> str:
        comps_str = ", ".join(plan.companies) if plan.companies else "indexed entities"
        years_str = ", ".join(plan.years) if plan.years else "all available reporting years"

        if reasoning_data.get("calculation_results"):
            calc = reasoning_data["calculation_results"][0]
            return (
                f"Mathematical unit conversion completed for **{calc['company']}** ({calc['year']}). "
                f"Reported value of **{calc['original_value']} {calc['original_unit']}** converts directly to **{calc['converted_value']:,} {calc['target_unit']}**."
            )

        if ranking_data and ranking_data.get("ranked_table"):
            top = ranking_data["top_performer"]
            sector_label = f" across the {plan.sector} sector" if plan.sector else ""
            return (
                f"This report presents an ESG ranking analysis{sector_label} for year **{ranking_data.get('year')}**. "
                f"**{top.get('company')}** leads the benchmark with **{top.get('value')} {top.get('unit')}** for **{top.get('metric_label')}**."
            )

        if metrics:
            return (
                f"This report presents verified ESG intelligence for **{comps_str}** across **{years_str}**. "
                f"All metrics are extracted strictly from corporate BRSR and sustainability disclosures."
            )

        return (
            f"An ESG intelligence audit was performed for **{comps_str}** across **{years_str}**. "
            f"No direct numerical metric entries were matched for the requested filter criteria."
        )

    def _build_evidence_findings(
        self,
        plan: QueryPlan,
        metrics: List[Dict[str, Any]],
        reasoning_data: Dict[str, Any],
        ranking_data: Optional[Dict[str, Any]]
    ) -> str:
        if reasoning_data.get("calculation_results"):
            lines = []
            for item in reasoning_data["calculation_results"]:
                lines.append(
                    f"- **{item['company']}** ({item['year']}): Original disclosure **{item['original_value']} {item['original_unit']}** = **{item['converted_value']:,} {item['target_unit']}**."
                )
            return "\n".join(lines)

        if ranking_data and ranking_data.get("ranked_table"):
            table = ranking_data["ranked_table"]
            lines = []
            for item in table[:5]:
                lines.append(
                    f"- Rank #{item['rank']}: **{item['company']}** reported **{item['metric_label']}** of **{item['value']} {item['unit']}** ({item['year']})."
                )
            return "\n".join(lines)

        if metrics:
            lines = []
            for m in metrics[:10]:
                lines.append(
                    f"- **{m.get('company')}** reported **{m.get('metric_label', m.get('metric_key'))}** of **{m.get('value')} {m.get('unit')}** in **{m.get('year')}**."
                )
            return "\n".join(lines)

        return "- No direct quantitative disclosures match the specific query parameters."

    def _build_metrics_table(
        self,
        metrics: List[Dict[str, Any]],
        ranking_data: Optional[Dict[str, Any]]
    ) -> str:
        if ranking_data and ranking_data.get("ranked_table"):
            table = ranking_data["ranked_table"]
            headers = "| Rank | Company | Year | Metric | Value | Unit | Source |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
            rows = []
            for item in table:
                rows.append(
                    f"| {item['rank']} | {item['company']} | {item['year']} | {item['metric_label']} | **{item['value']}** | {item['unit']} | {item['source_file']} |"
                )
            return headers + "\n" + "\n".join(rows)

        if metrics:
            headers = "| Company | Year | Metric | Value | Unit | Source |\n| :--- | :--- | :--- | :--- | :--- | :--- |"
            rows = []
            for m in metrics[:15]:
                rows.append(
                    f"| {m.get('company')} | {m.get('year')} | {m.get('metric_label', m.get('metric_key'))} | **{m.get('value')}** | {m.get('unit')} | {m.get('source_file')} |"
                )
            return headers + "\n" + "\n".join(rows)

        return ""

    def _build_limitations(
        self,
        plan: QueryPlan,
        metrics: List[Dict[str, Any]],
        retrieved_data: Dict[str, Any]
    ) -> str:
        limitations = []
        if not metrics:
            limitations.append("What was searched: Query filters included companies (" + (", ".join(plan.companies) if plan.companies else "All") + "), years (" + (", ".join(plan.years) if plan.years else "All") + "), and metrics (" + (", ".join(plan.metric_keys) if plan.metric_keys else "All") + ").")
            limitations.append(f"Reports checked: {', '.join(retrieved_data.get('searched_companies', []))}")
            limitations.append("Metric Status: No exact numerical match was found in the indexed database.")
            limitations.append("Possible reason: The company may not have disclosed this metric in the analyzed reporting period, or extraction requires unindexed annexures.")

        limitations.append("All reported figures reflect official company disclosures and have not been independently recalculated beyond raw report data.")
        return "\n".join(f"- {l}" for l in limitations)
