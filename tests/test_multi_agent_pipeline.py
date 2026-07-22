import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch")))

import unittest
from src.retrieval.company_router import CompanyRouter
from src.agents.planner_agent import PlannerAgent
from src.agents.retrieval_agent import RetrievalAgent
from src.agents.ranking_agent import RankingAgent
from src.agents.reasoning_agent import ReasoningAgent
from src.agents.citation_validator import CitationValidator
from src.agents.report_generator import ReportGenerator
from src.retrieval.esg_query_engine import ESGQueryEngine

class TestMultiAgentPipeline(unittest.TestCase):
    def setUp(self):
        self.router = CompanyRouter()
        self.planner = PlannerAgent()
        self.engine = ESGQueryEngine()

    def test_false_positive_company_detection(self):
        """
        Verify that common English words like 'are', 'this', 'report' are NEVER detected as company names.
        """
        query = "What are the key highlights of this report?"
        comps = self.router.detect_company_from_query(query)
        self.assertIsNone(comps, "Words like 'are' or 'this' must never be detected as companies.")

        plan = self.planner.create_plan(query)
        self.assertEqual(plan.companies, [], "Plan should have empty company list for general queries.")

    def test_query_plan_generation_intents(self):
        """
        Verify that PlannerAgent correctly assigns intents, metrics, and strategy routes.
        """
        # Ranking
        plan_rank = self.planner.create_plan("Top companies by renewable energy percentage in 2024")
        self.assertIn(plan_rank.intent, ["ranking", "RANKING"])
        self.assertEqual(plan_rank.retrieval_strategy, "STRUCTURED_DB_ONLY")

        # Trend / YoY
        plan_trend = self.planner.create_plan("Water consumption trend for Infosys between 2022 and 2024")
        self.assertIn(plan_trend.intent, ["trend_analysis", "TREND"])
        self.assertIn("Infosys Limited", plan_trend.companies)

        # Comparison
        plan_comp = self.planner.create_plan("Compare Scope 1 emissions between TCS and Infosys in 2024")
        self.assertIn(plan_comp.intent, ["comparison", "COMPARISON"])
        self.assertIn("Tata Consultancy Services Limited", plan_comp.companies)
        self.assertIn("Infosys Limited", plan_comp.companies)

    def test_full_engine_end_to_end(self):
        """
        Verify end-to-end processing returns a valid Bloomberg/MSCI standard analyst report.
        """
        res = self.engine.process_query("What is the water consumption of Infosys in 2024?")
        text = res["response_text"]

        self.assertIn("Executive Summary", text)
        self.assertIn("Evidence & Key Findings", text)
        self.assertIn("Confidence Level", text)
        self.assertIn("Sources", text)
        self.assertIn("Query Execution Log & Diagnostics", text)
        self.assertGreaterEqual(res["confidence_score"], 0.0)

    def test_yoy_delta_reasoning(self):
        """
        Verify YoY delta calculations in ReasoningAgent.
        """
        reasoner = ReasoningAgent()
        sample_metrics = [
            {"company": "Infosys Limited", "metric_key": "scope1_emissions", "metric_label": "Scope 1 Emissions", "year": "2023", "value": 1000.0, "unit": "tCO2e"},
            {"company": "Infosys Limited", "metric_key": "scope1_emissions", "metric_label": "Scope 1 Emissions", "year": "2024", "value": 1200.0, "unit": "tCO2e"}
        ]
        deltas = reasoner._compute_yoy_deltas(sample_metrics)
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0]["absolute_change"], 200.0)
        self.assertEqual(deltas[0]["percentage_change"], 20.0)
        self.assertEqual(deltas[0]["direction"], "increased")

if __name__ == "__main__":
    unittest.main()
