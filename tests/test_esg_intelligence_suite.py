import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch")))

import unittest
from src.retrieval.esg_query_engine import ESGQueryEngine
from src.agents.planner_agent import PlannerAgent
from src.database.metrics_store import MetricsStore
from src.database.company_metadata import CompanyMetadataManager

class TestESGIntelligenceSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ESGQueryEngine()
        cls.planner = PlannerAgent()
        cls.store = MetricsStore()
        cls.meta = CompanyMetadataManager()

        # Seed test data
        cls.store.clear_company_metrics("Infosys Limited", "2024")
        cls.store.clear_company_metrics("Tata Consultancy Services Limited", "2024")
        cls.store.clear_company_metrics("Cipla Limited", "2024")
        cls.store.clear_company_metrics("Sun Pharmaceutical Industries Limited", "2024")

        cls.store.save_metrics_batch([
            {
                "company": "Infosys Limited",
                "year": "2024",
                "metric_key": "water_consumption_kl",
                "metric_label": "Water Consumption",
                "value": 1000.0,
                "unit": "kl",
                "source_file": "infosys_2024.pdf",
                "page": "15"
            },
            {
                "company": "Tata Consultancy Services Limited",
                "year": "2024",
                "metric_key": "water_consumption_kl",
                "metric_label": "Water Consumption",
                "value": 1500.0,
                "unit": "kl",
                "source_file": "tcs_2024.pdf",
                "page": "20"
            },
            {
                "company": "Cipla Limited",
                "year": "2024",
                "metric_key": "water_consumption_kl",
                "metric_label": "Water Consumption",
                "value": 2500.0,
                "unit": "kl",
                "source_file": "cipla_2024.pdf",
                "page": "10"
            },
            {
                "company": "Sun Pharmaceutical Industries Limited",
                "year": "2024",
                "metric_key": "water_consumption_kl",
                "metric_label": "Water Consumption",
                "value": 3000.0,
                "unit": "kl",
                "source_file": "sun_2024.pdf",
                "page": "12"
            },
            {
                "company": "Infosys Limited",
                "year": "2024",
                "metric_key": "scope3_emissions",
                "metric_label": "Scope 3 Emissions",
                "value": 4500.0,
                "unit": "tCO2e",
                "source_file": "infosys_2024.pdf",
                "page": "18"
            }
        ])

    def test_1_key_highlights_summary_no_false_company(self):
        """Query 1: 'What are the key highlights of this report?'"""
        query = "What are the key highlights of this report?"
        plan = self.planner.create_plan(query)
        self.assertIn(plan.intent, ["summary", "reasoning", "general"])
        self.assertEqual(plan.companies, [])

    def test_2_rank_pharmaceutical_companies_water(self):
        """Query 2: 'Rank pharmaceutical companies by water consumption.'"""
        query = "Rank pharmaceutical companies by water consumption."
        plan = self.planner.create_plan(query)
        self.assertEqual(plan.intent, "ranking")
        self.assertEqual(plan.sector, "Pharmaceuticals")
        self.assertIn("water_consumption_kl", plan.metric_keys)

        res = self.engine.process_query(query)
        response_text = res["answer"]
        self.assertIn("ranking analysis", response_text.lower())
        self.assertIn("Sun Pharmaceutical Industries Limited", response_text)
        self.assertIn("Cipla Limited", response_text)

    def test_3_which_companies_have_scope3(self):
        """Query 3: 'Which companies have Scope 3 emissions?'"""
        query = "Which companies have Scope 3 emissions?"
        plan = self.planner.create_plan(query)
        self.assertIn(plan.intent, ["missing_data", "ranking", "metric_lookup"])
        self.assertIn("scope3_emissions", plan.metric_keys)

        res = self.engine.process_query(query)
        response_text = res["answer"]
        self.assertIn("Infosys Limited", response_text)

    def test_4_compare_infosys_and_tcs(self):
        """Query 4: 'Compare Infosys and TCS.'"""
        query = "Compare Infosys and TCS."
        plan = self.planner.create_plan(query)
        self.assertEqual(plan.intent, "comparison")
        self.assertIn("Infosys Limited", plan.companies)
        self.assertIn("Tata Consultancy Services Limited", plan.companies)

        res = self.engine.process_query(query)
        response_text = res["answer"]
        self.assertIn("Infosys Limited", response_text)
        self.assertIn("Tata Consultancy Services Limited", response_text)

    def test_5_convert_water_consumption_gallons(self):
        """Query 5: 'Convert Infosys water consumption into gallons.'"""
        query = "Convert Infosys water consumption into gallons."
        plan = self.planner.create_plan(query)
        self.assertEqual(plan.intent, "calculation")
        self.assertEqual(plan.target_unit, "gallons")

        res = self.engine.process_query(query)
        response_text = res["answer"]
        self.assertIn("264,172", response_text)  # 1000 kL * 264.172 = 264,172 gallons

    def test_6_most_common_esg_initiative(self):
        """Query 6: 'Across all companies, what is the most common ESG initiative?'"""
        query = "Across all companies, what is the most common ESG initiative?"
        plan = self.planner.create_plan(query)
        self.assertIn(plan.intent, ["reasoning", "summary"])

        res = self.engine.process_query(query)
        response_text = res["answer"]
        self.assertIn("Query Execution Log & Diagnostics", response_text)

if __name__ == "__main__":
    unittest.main()
