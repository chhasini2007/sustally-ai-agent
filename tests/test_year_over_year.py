import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.retrieval.query_classifier import QueryClassifier
from src.agents.yoy_agent import YoYAgent

class TestYearOverYear(unittest.TestCase):
    def setUp(self):
        self.classifier = QueryClassifier()
        self.yoy_agent = YoYAgent()

    def test_query_classification_lane_d(self):
        """
        Verify that YoY comparative queries are correctly routed to Lane D.
        """
        queries = [
            "What is the percentage change in Scope 1 emissions for Infosys from 2024 to 2025?",
            "how have scope 2 emissions changed year over year for TCS?",
            "growth in water consumption for Infosys between 2023 and 2025",
            "trend in waste generation for TCS over the years"
        ]
        for q in queries:
            c = self.classifier.classify(q)
            self.assertEqual(c["lane"], "D", f"Query '{q}' should be classified as Lane D")

    def test_non_yoy_queries_unaffected(self):
        """
        Verify that existing Lane A, B, and C classification are unaffected.
        """
        # Lane A: single year lookup
        c1 = self.classifier.classify("What is the water consumption of Infosys in 2024?")
        self.assertEqual(c1["lane"], "A")

        # Lane B: summary
        c2 = self.classifier.classify("Summarize the sustainability report of Infosys 2024")
        self.assertEqual(c2["lane"], "B")

        # Lane C: compare across companies
        c3 = self.classifier.classify("Compare the water consumption between TCS and Infosys in 2024")
        self.assertEqual(c3["lane"], "C")

    @patch("sqlite3.connect")
    def test_yoy_calculation_insufficient_data(self, mock_connect):
        """
        Verify that YoY agent returns the correct message when only 1 year of data is available.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock database output: only 1 year
        mock_cursor.fetchall.return_value = [
            ("2024", 100.0, "tCO2e", "report_2024.xml", "12")
        ]

        msg, fig, is_reused, refreshed_time, chart_id = self.yoy_agent.compare_years(
            "Infosys Limited", "scope1_emissions_tco2e"
        )
        self.assertIn("Only one year of data", msg)
        self.assertIn("2024: 100.0 tCO2e", msg)
        self.assertIsNone(fig)

    @patch("sqlite3.connect")
    def test_yoy_calculation_success(self, mock_connect):
        """
        Verify correct percentage change calculation for 2 years.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock database output: 2 years (100 -> 120, +20%)
        mock_cursor.fetchall.return_value = [
            ("2023", 100.0, "tCO2e", "report_2023.xml", "10"),
            ("2024", 120.0, "tCO2e", "report_2024.xml", "12")
        ]

        msg, fig, is_reused, refreshed_time, chart_id = self.yoy_agent.compare_years(
            "Infosys Limited", "scope1_emissions_tco2e", years=["2023", "2024"]
        )
        self.assertIn("increased by 20.0%", msg)
        self.assertIn("from 2023 (100.0 tCO2e) to 2024 (120.0 tCO2e)", msg)
        self.assertIn("report_2023.xml, XML, report_2024.xml, XML", msg)
        self.assertIsNone(fig) # No chart for exactly 2 years

    @patch("sqlite3.connect")
    def test_yoy_calculation_with_chart(self, mock_connect):
        """
        Verify correct calculation and trend series for 3+ years.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock database output: 3 years (100 -> 80, -20% from earliest to latest)
        mock_cursor.fetchall.return_value = [
            ("2022", 100.0, "tCO2e", "report_2022.xml", "8"),
            ("2023", 90.0, "tCO2e", "report_2023.xml", "10"),
            ("2024", 80.0, "tCO2e", "report_2024.xml", "12")
        ]

        # Patch save_cached_chart to prevent DB insertion errors during tests
        self.yoy_agent.history_store.save_cached_chart = MagicMock(return_value=42)
        self.yoy_agent.history_store.get_cached_chart = MagicMock(return_value=None)

        msg, fig, is_reused, refreshed_time, chart_id = self.yoy_agent.compare_years(
            "Infosys Limited", "scope1_emissions_tco2e"
        )
        self.assertIn("decreased by 20.0%", msg)
        self.assertIn("from 2022 (100.0 tCO2e) to 2024 (80.0 tCO2e)", msg)
        self.assertIn("Full available series: 2022 (100.0 tCO2e), 2023 (90.0 tCO2e), 2024 (80.0 tCO2e)", msg)
        self.assertIsNotNone(fig)

if __name__ == "__main__":
    unittest.main()
