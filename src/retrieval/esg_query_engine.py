"""
ESG Query Engine for Sustally ESG Intelligence Platform
Orchestrates the Multi-Agent Architecture:
PlannerAgent -> RetrievalAgent / RankingAgent -> ReasoningAgent -> CitationValidator -> ReportGenerator & VisualizationAgent
"""

from typing import List, Dict, Any, Optional, Generator
import logging

from src.agents.planner_agent import PlannerAgent, QueryPlan
from src.agents.retrieval_agent import RetrievalAgent
from src.agents.ranking_agent import RankingAgent
from src.agents.reasoning_agent import ReasoningAgent
from src.agents.citation_validator import CitationValidator
from src.agents.report_generator import ReportGenerator
from src.agents.visualization_agent import VisualizationAgent

logger = logging.getLogger(__name__)

class ESGQueryEngine:
    def __init__(self):
        self.planner = PlannerAgent()
        self.retriever = RetrievalAgent()
        self.ranker = RankingAgent()
        self.reasoner = ReasoningAgent()
        self.validator = CitationValidator()
        self.report_gen = ReportGenerator()
        self.visualizer = VisualizationAgent()

    def parse_query(
        self,
        query: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        active_company: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses raw query into structured query plan dictionary for backward compatibility.
        """
        plan = self.planner.create_plan(query, conversation_context, active_company)
        return {
            "intent": plan.intent,
            "companies": plan.companies,
            "years": plan.years,
            "metrics": plan.metric_keys,
            "sector": plan.sector,
            "threshold_filter": plan.threshold_filter,
            "retrieval_strategy": plan.retrieval_strategy,
            "confidence": plan.confidence,
            "status": plan.status,
            "matched_term": plan.matched_term,
            "matches": plan.matches
        }

    def execute_query(
        self,
        query: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        active_company: Optional[str] = None
    ) -> Dict[str, Any]:
        res = self.process_query(query, conversation_context, active_company)
        res["content"] = res["response_text"]
        return res

    def process_query(
        self,
        query: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        active_company: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Redesigned Production-Grade Multi-Agent Query Processing Pipeline.
        """
        # Step 1: Planner Agent
        plan = self.planner.create_plan(query, conversation_context, active_company)

        # Handle Conversational / Greetings directly
        if plan.status == "conversational":
            conv_cat = plan.conversational_category
            if conv_cat == "greeting":
                text = "Hello! I am Sustally, your production-grade AI ESG Intelligence Platform. How can I assist you with corporate sustainability disclosures, rankings, or multi-year analysis today?"
            elif conv_cat == "thanks":
                text = "You're welcome! Let me know if you need further ESG reports, cross-company benchmarks, or data audits."
            else:
                text = "I am Sustally, a Bloomberg-style ESG Intelligence Platform capable of analyzing 1,000+ corporate BRSR and sustainability reports, ranking entities, computing YoY trends, and auditing disclosures with full source citations."

            return {
                "answer": text,
                "response_text": text,
                "query_plan": plan,
                "chart": None,
                "confidence_score": 1.0,
                "confidence_level": "HIGH",
                "sources": [],
                "status": "conversational"
            }

        # Handle Ambiguous / Unresolved Company Status
        if plan.status == "ambiguous":
            matched_term = plan.matched_term or "your query"
            options_str = ", ".join(f"**{m}**" for m in plan.matches)
            text = f"The term '{matched_term}' matches multiple entities in the sustainability index: {options_str}.\n\nPlease specify which entity you would like to analyze."
            return {
                "answer": text,
                "response_text": text,
                "query_plan": plan,
                "chart": None,
                "confidence_score": 0.0,
                "confidence_level": "LOW",
                "sources": [],
                "status": "ambiguous"
            }

        # Step 2: Retrieval Agent
        retrieved_data = self.retriever.retrieve(plan)

        # Step 3: Ranking Agent (if applicable)
        ranking_data = None
        if plan.intent in ["ranking", "RANKING"] or getattr(plan, "reasoning_strategy", "") == "RANKING_SORT":
            ranking_data = self.ranker.rank(plan, retrieved_data.get("structured_metrics", []))

        # Step 4: Reasoning Agent
        reasoning_data = self.reasoner.reason(plan, retrieved_data, ranking_data)

        # Step 5: Citation & Fact Validator
        validation_data = self.validator.validate_and_score(plan, retrieved_data, reasoning_data, ranking_data)

        # Step 6: Report Generator
        report_text = self.report_gen.generate_report(plan, retrieved_data, reasoning_data, validation_data, ranking_data)

        # Step 7: Visualization Agent
        chart_fig = self.visualizer.create_visualization(plan, retrieved_data, ranking_data)

        return {
            "answer": report_text,
            "response_text": report_text,
            "query_plan": plan,
            "chart": chart_fig,
            "confidence_score": validation_data.get("confidence_score", 0.50),
            "confidence_level": validation_data.get("confidence_label", "MEDIUM"),
            "sources": validation_data.get("sources", []),
            "status": plan.status,
            "retrieved_data": retrieved_data,
            "reasoning_data": reasoning_data,
            "ranking_data": ranking_data
        }

    def process_query_stream(
        self,
        query: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        active_company: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Yields chunked response text for streaming Streamlit output.
        """
        result = self.process_query(query, conversation_context, active_company)
        full_text = result["response_text"]
        # Yield in chunks for smooth streaming UI
        words = full_text.split(" ")
        for i in range(0, len(words), 5):
            yield " ".join(words[i:i+5]) + " "
