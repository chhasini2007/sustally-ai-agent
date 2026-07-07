from typing import Dict, Any, Generator, Tuple, Optional
from src.database.metrics_store import MetricsStore
from src.retrieval.retriever import Retriever
from src.llm.llm_router import LLMRouter

class AnalysisAgent:
    def __init__(self):
        self.metrics_store = MetricsStore()
        self.retriever = Retriever()
        self.llm_router = LLMRouter()

    def summarize_report(
        self,
        company: str,
        year: Optional[str],
        stream: bool = True
    ) -> Tuple[Generator[str, None, None], str]:
        """
        Creates a high-level summary of a company's sustainability report for a specific year.
        Uses both structured metrics and strategy/targets section retrieval.
        """
        # Resolve year if not provided
        available_years = self.metrics_store.get_company_years(company)
        if not year:
            if available_years:
                year = available_years[0]
            else:
                def gen_no_data():
                    yield f"No sustainability reports or metrics found for {company}."
                return gen_no_data(), "system"
                
        # 1. Fetch structured metrics
        metrics = self.metrics_store.get_company_metrics(company, year)
        metrics_summary = ""
        if metrics:
            metrics_summary = "Extracted ESG Metrics:\n" + "\n".join([
                f"- {m['metric_key']} ({m['metric_label']}): {m['value']} {m['unit']} (Source: {m['source_file']}, Page {m['page']})"
                for m in metrics
            ])
            
        # 2. Retrieve strategy chunks
        strategy_chunks = self.retriever.retrieve_context(
            query="sustainability strategy targets vision carbon neutral net zero ESG goals",
            company=company,
            year=year,
            top_k=4
        )
        
        context_parts = []
        for r in strategy_chunks:
            meta = r["metadata"]
            context_parts.append(
                f"[File: {meta.get('source_file')}, Page: {meta.get('page')}, Type: {meta.get('section_type')}]\n{r['content']}"
            )
        strategy_text = "\n\n".join(context_parts)
        
        prompt = (
            f"You are Sustally's ESG analyst. Provide a comprehensive summary of the sustainability report for {company} in the year {year}.\n"
            f"In corporate report summaries, structure your response under the following exact headings:\n"
            f"1. Executive Summary\n"
            f"2. Climate & Environment Strategy\n"
            f"3. Social & Governance Policies\n"
            f"4. Key Metrics Summary\n\n"
            f"Structured metrics data:\n{metrics_summary}\n\n"
            f"Strategy context from report:\n{strategy_text}\n\n"
            f"Synthesize this information professionally, highlighting key targets, figures, and page numbers."
        )
        
        messages = [{"role": "user", "content": prompt}]
        return self.llm_router.generate(messages, stream=stream)
