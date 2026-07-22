"""
Reasoning Agent for Sustally ESG Intelligence Platform
Performs time-series YoY delta calculations, sector benchmarking, mathematical unit conversions,
and analytical synthesis.
"""

from typing import List, Dict, Any, Optional
import logging
from src.agents.planner_agent import QueryPlan

logger = logging.getLogger(__name__)

UNIT_CONVERSION_RATES = {
    ("kl", "gallons"): 264.172052,
    ("kl", "gallon"): 264.172052,
    ("tco2e", "kgco2e"): 1000.0,
    ("gj", "mwh"): 0.277778,
}

class ReasoningAgent:
    def __init__(self):
        pass

    def reason(
        self,
        plan: QueryPlan,
        retrieved_data: Dict[str, Any],
        ranking_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes analytical reasoning over retrieved metric data, narrative context, and unit conversions.
        """
        structured_metrics = retrieved_data.get("structured_metrics", [])
        
        yoy_analysis = []
        if plan.intent == "trend_analysis" or len(plan.years) > 1:
            yoy_analysis = self._compute_yoy_deltas(structured_metrics)

        benchmark_analysis = {}
        if plan.intent == "comparison" or len(plan.companies) > 1:
            benchmark_analysis = self._compute_cross_company_benchmarks(structured_metrics)

        calculation_results = []
        if plan.intent == "calculation" or plan.target_unit:
            calculation_results = self._compute_unit_conversions(plan, structured_metrics)

        analytical_summary = self._generate_analytical_summary(
            plan, 
            structured_metrics, 
            yoy_analysis, 
            ranking_data, 
            calculation_results,
            retrieved_data=retrieved_data
        )

        return {
            "yoy_analysis": yoy_analysis,
            "benchmark_analysis": benchmark_analysis,
            "calculation_results": calculation_results,
            "analytical_summary": analytical_summary,
            "has_numeric_evidence": len(structured_metrics) > 0,
            "metrics_count": len(structured_metrics)
        }

    def _compute_unit_conversions(self, plan: QueryPlan, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        target_unit = (plan.target_unit or "gallons").lower().strip()
        results = []

        for m in metrics:
            val = m.get("value")
            orig_unit = (m.get("unit") or "kl").lower().strip()
            if val is not None:
                rate_key = (orig_unit, target_unit)
                if rate_key in UNIT_CONVERSION_RATES:
                    conv_factor = UNIT_CONVERSION_RATES[rate_key]
                    converted_val = round(val * conv_factor, 2)
                    results.append({
                        "company": m.get("company"),
                        "year": m.get("year"),
                        "original_value": val,
                        "original_unit": m.get("unit"),
                        "converted_value": converted_val,
                        "target_unit": target_unit,
                        "formula": f"{val} {m.get('unit')} × {conv_factor} = {converted_val} {target_unit}"
                    })
                elif orig_unit == "kl" and ("gallon" in target_unit or target_unit == "gallons"):
                    conv_factor = 264.172052
                    converted_val = round(val * conv_factor, 2)
                    results.append({
                        "company": m.get("company"),
                        "year": m.get("year"),
                        "original_value": val,
                        "original_unit": m.get("unit"),
                        "converted_value": converted_val,
                        "target_unit": "gallons",
                        "formula": f"{val} kL × 264.172 = {converted_val} gallons"
                    })
        return results

    def _compute_yoy_deltas(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[tuple, List[Dict[str, Any]]] = {}
        for m in metrics:
            comp = m.get("company")
            key = m.get("metric_key")
            val = m.get("value")
            yr = m.get("year")
            if comp and key and val is not None and yr:
                k = (comp, key)
                if k not in grouped:
                    grouped[k] = []
                grouped[k].append(m)

        yoy_results = []
        for (comp, key), rows in grouped.items():
            sorted_rows = sorted(rows, key=lambda r: str(r.get("year")))
            if len(sorted_rows) >= 2:
                for i in range(len(sorted_rows) - 1):
                    prev = sorted_rows[i]
                    curr = sorted_rows[i + 1]
                    val_prev = prev["value"]
                    val_curr = curr["value"]
                    abs_change = val_curr - val_prev
                    pct_change = ((val_curr - val_prev) / val_prev * 100.0) if val_prev != 0 else 0.0

                    yoy_results.append({
                        "company": comp,
                        "metric_key": key,
                        "metric_label": curr.get("metric_label", key),
                        "base_year": prev.get("year"),
                        "base_value": val_prev,
                        "target_year": curr.get("year"),
                        "target_value": val_curr,
                        "unit": curr.get("unit"),
                        "absolute_change": round(abs_change, 2),
                        "percentage_change": round(pct_change, 2),
                        "direction": "increased" if abs_change > 0 else ("decreased" if abs_change < 0 else "remained unchanged")
                    })
        return yoy_results

    def _compute_cross_company_benchmarks(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_key: Dict[str, List[float]] = {}
        for m in metrics:
            k = m.get("metric_key")
            v = m.get("value")
            if k and v is not None:
                if k not in by_key:
                    by_key[k] = []
                by_key[k].append(float(v))

        benchmarks = {}
        for k, vals in by_key.items():
            if vals:
                benchmarks[k] = {
                    "count": len(vals),
                    "mean": round(sum(vals) / len(vals), 2),
                    "min": min(vals),
                    "max": max(vals),
                    "spread": round(max(vals) - min(vals), 2)
                }
        return benchmarks

    def _generate_analytical_summary(
        self,
        plan: QueryPlan,
        metrics: List[Dict[str, Any]],
        yoy: List[Dict[str, Any]],
        ranking: Optional[Dict[str, Any]],
        calc: List[Dict[str, Any]],
        retrieved_data: Optional[Dict[str, Any]] = None
    ) -> str:
        if calc:
            lines = []
            for item in calc:
                lines.append(
                    f"**{item['company']}** water consumption of **{item['original_value']} {item['original_unit']}** ({item['year']}) "
                    f"equals **{item['converted_value']:,} {item['target_unit']}** ({item['formula']})."
                )
            return " ".join(lines)

        if not metrics and not ranking:
            narrative_chunks = retrieved_data.get("narrative_chunks", []) if retrieved_data else []
            if narrative_chunks:
                try:
                    from src.llm.llm_router import LLMRouter
                    llm_router = LLMRouter()

                    context_parts = []
                    for idx, chunk in enumerate(narrative_chunks):
                        meta = chunk.get("metadata", {})
                        src_file = meta.get("source_file", meta.get("source", "Unknown"))
                        page = meta.get("page", "N/A")
                        context_parts.append(
                            f"[Excerpt #{idx+1} - File: {src_file}, Page: {page}]\n{chunk.get('content', '')}"
                        )
                    context_text = "\n\n".join(context_parts)

                    prompt = (
                        f"You are Sustally, a professional AI sustainability analyst dashboard. "
                        f"Answer the user's ESG question using ONLY the retrieved report excerpts provided below. "
                        f"If the context does not contain enough information, explain that clearly instead of guessing.\n\n"
                        f"Retrieved Report Context:\n{context_text}\n\n"
                        f"User Question: {plan.query}\n\n"
                        f"Answer (be structured, detailed, and cite [File: filename, Page: page_no] where applicable):"
                    )

                    messages = [{"role": "user", "content": prompt}]
                    generator, provider = llm_router.generate(messages, stream=False)
                    full_answer = "".join(generator).strip()
                    if full_answer:
                        return full_answer
                except Exception as e:
                    logger.warning(f"Failed to run LLM reasoning synthesis: {e}")

            return "No verified structured metrics or narrative disclosures were found in the database for the specified company, year, or topic filters."

        summary_parts = []
        if ranking and ranking.get("ranked_table"):
            top = ranking["top_performer"]
            bot = ranking["bottom_performer"]
            m_lbl = top.get("metric_label", "Metric")
            summary_parts.append(
                f"In the ranking analysis for **{m_lbl}** ({ranking.get('year')}), "
                f"**{top.get('company')}** ranked #1 with **{top.get('value')} {top.get('unit')}**, while "
                f"**{bot.get('company')}** recorded **{bot.get('value')} {bot.get('unit')}**."
            )

        if yoy:
            for item in yoy:
                summary_parts.append(
                    f"**{item['company']}** ({item['metric_label']}) changed by **{item['percentage_change']}%** "
                    f"from **{item['base_value']} {item['unit']}** ({item['base_year']}) to **{item['target_value']} {item['unit']}** ({item['target_year']})."
                )

        if not summary_parts and metrics:
            for m in metrics[:5]:
                summary_parts.append(
                    f"**{m.get('company')}** reported **{m.get('metric_label', m.get('metric_key'))}** of **{m.get('value')} {m.get('unit')}** in **{m.get('year')}**."
                )

        return " ".join(summary_parts)
