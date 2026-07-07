from typing import Dict, Any, Tuple, Generator, Optional
from src.database.metrics_store import MetricsStore
from src.retrieval.retriever import Retriever
from src.llm.llm_router import LLMRouter
from src.processing.metric_taxonomy import METRIC_TAXONOMY

class QAAgent:
    def __init__(self):
        self.metrics_store = MetricsStore()
        self.retriever = Retriever()
        self.llm_router = LLMRouter()

    def run_lane_a(
        self,
        company: str,
        year: Optional[str],
        metric_key: str,
        query: str,
        stream: bool = True
    ) -> Tuple[Generator[str, None, None], str, str]:
        """
        Lane A: Structured SQL lookup
        Returns: (output_generator, provider_name, lane)
        """
        # Resolve year if not provided
        available_years = self.metrics_store.get_company_years(company)
        if not year:
            if available_years:
                year = available_years[0]
            else:
                def gen_no_data():
                    yield f"This information was not found in the uploaded reports for {company}."
                return gen_no_data(), "direct_lookup", "A"
                
        metrics = self.metrics_store.get_metric(company, year, metric_key)
        
        if not metrics:
            def gen_not_found():
                yield f"This information was not found in the uploaded reports."
            return gen_not_found(), "direct_lookup", "A"
            
        metric_data = metrics[0]
        val = metric_data["value"]
        unit = metric_data["unit"]
        label = metric_data["metric_label"]
        source = metric_data["source_file"]
        page = metric_data["page"]
        
        # Format metric
        display_name = METRIC_TAXONOMY[metric_key]["label"]
        
        prompt = (
            f"You are Sustally's ESG analyst. Answer this query: '{query}' based on this exact data point:\n"
            f"Company: {company}\n"
            f"Year: {year}\n"
            f"Metric Name: {display_name} (Reported as '{label}')\n"
            f"Value: {val} {unit}\n"
            f"Source: {source} (Page {page})\n\n"
            f"Formulate a very short, direct, and professional answer stating the exact figure and source. Do not add narrative filler."
        )
        
        messages = [{"role": "user", "content": prompt}]
        try:
            gen, provider = self.llm_router.generate(messages, stream=stream)
            return gen, provider, "A"
        except Exception:
            # Direct fallback if LLM is down
            def gen_static():
                yield (
                    f"**Sustally Analysis**\n\n"
                    f"**{display_name}** for **{company}** in **{year}** is **{val} {unit}**.\n\n"
                    f"**Sources:**\n"
                    f"- {source} (Page {page})"
                )
            return gen_static(), "static_formatter", "A"

    def run_lane_b(
        self,
        company: str,
        year: Optional[str],
        query: str,
        stream: bool = True
    ) -> Tuple[Generator[str, None, None], str, str]:
        """
        Lane B: Narrative RAG
        """
        # Resolve year if not provided
        available_years = self.metrics_store.get_company_years(company)
        if not year and available_years:
            year = available_years[0]
            
        # Retrieve chunks
        results = self.retriever.retrieve_context(query, company, year, top_k=6)
        
        if not results:
            def gen_no_context():
                yield "This information was not found in the uploaded reports."
            return gen_no_context(), "retriever", "B"
            
        # Format context
        context_parts = []
        sources = []
        for r in results:
            meta = r["metadata"]
            src_str = f"File: {meta.get('source_file')}, Page: {meta.get('page')}"
            sources.append(src_str)
            context_parts.append(
                f"[{src_str}]\n{r['content']}"
            )
            
        context_text = "\n\n".join(context_parts)
        
        prompt = (
            f"You are Sustally's ESG analyst. Answer the user question based on the following report context.\n"
            f"If the information is not in the context, state that it was not found in the reports. Do not guess.\n"
            f"Provide sources matching the bracketed headings [File: ..., Page: ...] in your response.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )
        
        messages = [{"role": "user", "content": prompt}]
        gen, provider = self.llm_router.generate(messages, stream=stream)
        return gen, provider, "B"
