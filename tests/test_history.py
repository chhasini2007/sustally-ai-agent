import sys
import os
import time
import json
import unittest
import sqlite3
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
# Use a separate temporary database path for testing to avoid cluttering production database
TEST_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "test_conversation_history.db"))
settings.HISTORY_DB_PATH = TEST_DB_PATH

from src.database.history_store import HistoryStore
from src.agents.comparison_agent import ComparisonAgent
from src.retrieval.query_classifier import QueryClassifier

class TestHistoryAndCache(unittest.TestCase):
    def setUp(self):
        self.store = HistoryStore(db_path=TEST_DB_PATH)
        
        # Seed mock metrics for comparison tests
        from src.database.metrics_store import MetricsStore
        m_store = MetricsStore()
        m_store.clear_company_metrics("Tata Consultancy Services Limited", "2024")
        m_store.clear_company_metrics("Infosys Limited", "2024")
        m_store.save_metrics_batch([
            {
                "company": "Tata Consultancy Services Limited",
                "year": "2024",
                "metric_key": "water_consumption_kl",
                "metric_label": "Water consumption",
                "value": 15000.0,
                "unit": "kl",
                "source_file": "tcs_report.xml",
                "page": "1"
            },
            {
                "company": "Infosys Limited",
                "year": "2024",
                "metric_key": "water_consumption_kl",
                "metric_label": "Water consumption",
                "value": 12000.0,
                "unit": "kl",
                "source_file": "infosys_report.xml",
                "page": "1"
            },
            {
                "company": "Infosys Limited",
                "year": "2024",
                "metric_key": "scope1_emissions_tco2e",
                "metric_label": "Scope 1 emissions",
                "value": 12450.5,
                "unit": "tCO2e",
                "source_file": "infosys_report.xml",
                "page": "1"
            }
        ])
        
        # Clean tables to ensure fresh state for every test case
        conn = sqlite3.connect(TEST_DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM conversations")
            cursor.execute("DELETE FROM charts")
            conn.commit()
        finally:
            conn.close()
            
        # Mock LLMRouter.generate to make tests run instantly without querying local Ollama
        def mock_gen(*args, **kwargs):
            def gen_response():
                yield "Mock comparison analysis."
            return gen_response(), "ollama"
            
        self.generate_patcher = patch("src.agents.comparison_agent.LLMRouter.generate", side_effect=mock_gen)
        self.mock_generate = self.generate_patcher.start()
        
        self.agent = ComparisonAgent()
        self.classifier = QueryClassifier()

    def tearDown(self):
        self.generate_patcher.stop()

    def test_same_comparison_twice_hits_cache(self):
        """
        1. Ask the same comparison question twice (exact same wording)
        Assert the second call hits the chart cache (checked via mock of create_comparison_chart)
        and runs the chart portion in under 200ms specifically.
        """
        query = "Compare water consumption for Infosys and TCS in 2024"
        classification = self.classifier.classify(query)
        comps = classification["companies"]
        years = classification["years"]
        metric_key = classification["metric_key"]
        
        # Call 1: cold cache
        structured_data, gen, provider, fig1, is_reused1, ref_time1, cid1 = self.agent.compare_companies(
            companies=comps,
            years=years,
            stream=False,
            chart_metric=metric_key
        )
        self.assertFalse(is_reused1)
        self.assertIsNotNone(fig1)
        self.assertIsNotNone(cid1)
        
        # Call 2: hot cache
        t_start = time.time()
        # Mock create_comparison_chart to ensure it is NOT called during cache hit
        with patch("src.agents.comparison_agent.create_comparison_chart") as mock_create_chart:
            structured_data2, gen2, provider2, fig2, is_reused2, ref_time2, cid2 = self.agent.compare_companies(
                companies=comps,
                years=years,
                stream=False,
                chart_metric=metric_key
            )
            t_duration = (time.time() - t_start) * 1000.0  # in ms
            
            # Assert create_comparison_chart was not called
            mock_create_chart.assert_not_called()
            
        self.assertTrue(is_reused2)
        self.assertEqual(cid1, cid2)
        self.assertIsNotNone(fig2)
        self.assertLess(t_duration, 200.0, f"Cache retrieval took too long: {t_duration:.2f}ms")
        print(f"Test 1 Passed: Hot cache retrieved in {t_duration:.2f}ms without rebuilding chart.")

    def test_differently_worded_queries_reuse_chart(self):
        """
        2. Ask two DIFFERENTLY WORDED questions that resolve to the same entities
        Assert both produce the same topic_key and reuse the cached chart.
        """
        q1 = "Compare Infosys and TCS water usage"
        q2 = "TCS vs Infosys water usage"
        
        c1 = self.classifier.classify(q1)
        c2 = self.classifier.classify(q2)
        
        # Check entities resolved are the same
        self.assertEqual(sorted(c1["companies"]), sorted(c2["companies"]))
        self.assertEqual(sorted(c1["years"]), sorted(c2["years"]))
        self.assertEqual(c1["metric_key"], c2["metric_key"])
        
        # Execute query 1
        sd1, g1, p1, fig1, is_reused1, rf1, cid1 = self.agent.compare_companies(
            companies=c1["companies"],
            years=c1["years"],
            stream=False,
            chart_metric=c1["metric_key"]
        )
        self.assertFalse(is_reused1)
        
        # Execute query 2
        sd2, g2, p2, fig2, is_reused2, rf2, cid2 = self.agent.compare_companies(
            companies=c2["companies"],
            years=c2["years"],
            stream=False,
            chart_metric=c2["metric_key"]
        )
        
        # Should hit cache
        self.assertTrue(is_reused2)
        self.assertEqual(cid1, cid2)
        print("Test 2 Passed: Differently worded queries successfully resolved to the same cached chart.")

    def test_ingestion_updates_cause_staleness_regeneration(self):
        """
        3. Simulate a new file being ingested for one of the companies involved,
        then re-ask the same comparison — assert the chart is regenerated (not stale),
        by checking that the charts row's created_at timestamp updates.
        """
        query = "Compare water consumption for Infosys and TCS in 2024"
        classification = self.classifier.classify(query)
        comps = classification["companies"]
        years = classification["years"]
        metric_key = classification["metric_key"]
        
        # Execute query 1 (saves to cache)
        _, _, _, _, is_reused1, rf1, cid1 = self.agent.compare_companies(
            companies=comps,
            years=years,
            stream=False,
            chart_metric=metric_key
        )
        self.assertFalse(is_reused1)
        
        # Get initial creation time and age it to simulate elapsed time
        conn = sqlite3.connect(TEST_DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE charts SET created_at = datetime('now', '-1 hour') WHERE id = ?", (cid1,))
            conn.commit()
            cursor.execute("SELECT created_at FROM charts WHERE id = ?", (cid1,))
            original_created_at = cursor.fetchone()[0]
        finally:
            conn.close()
            
        # Simulate a new file being ingested by modifying settings.DOC_INDEX_PATH
        # We will write a dummy document_index.json with a processed_date set to NOW
        temp_index_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "test_document_index.json"))
        original_doc_index = settings.DOC_INDEX_PATH
        settings.DOC_INDEX_PATH = temp_index_path
        
        now_str = datetime.now().isoformat()
        dummy_index = {
            "dummy_path": {
                "company": comps[0],
                "year": years[0] if years else "2024",
                "processed_date": now_str
            }
        }
        with open(temp_index_path, "w") as f:
            json.dump(dummy_index, f)
            
        try:
            # Re-execute query. It should notice the new processed_date > chart's created_at
            # and regenerate the chart.
            _, _, _, _, is_reused2, rf2, cid2 = self.agent.compare_companies(
                companies=comps,
                years=years,
                stream=False,
                chart_metric=metric_key
            )
            self.assertFalse(is_reused2) # Should NOT be reused because it is stale
            
            # Check database for updated created_at
            conn = sqlite3.connect(TEST_DB_PATH)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT created_at FROM charts WHERE id = ?", (cid2,))
                new_created_at = cursor.fetchone()[0]
            finally:
                conn.close()
                
            self.assertNotEqual(original_created_at, new_created_at)
            print("Test 3 Passed: Stale cache detected and regenerated successfully after new ingestion simulation.")
        finally:
            # Clean up
            if os.path.exists(temp_index_path):
                os.remove(temp_index_path)
            settings.DOC_INDEX_PATH = original_doc_index

    def test_conversation_history_persistence_across_restarts(self):
        """
        4. Confirm conversation history persists across simulated app restarts
        (i.e. read from SQLite database directly, not just in-memory state).
        """
        session_id = "test-session-xyz"
        conv_title = "Water Comparison"
        
        # 1. Start application "session": save conversation & messages
        conv_id = self.store.create_conversation(session_id, conv_title)
        self.store.add_message(conv_id, "user", "How much water did Infosys use?")
        self.store.add_message(conv_id, "assistant", "Infosys used 450,000 kl in 2024.", lane="A")
        
        # 2. Simulate "app restart" by creating a fresh HistoryStore pointing to the same DB
        new_store_instance = HistoryStore(db_path=TEST_DB_PATH)
        
        # Read from the SQLite database file directly
        conversations = new_store_instance.get_conversations_list()
        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0]["session_id"], session_id)
        self.assertEqual(conversations[0]["title"], conv_title)
        
        messages = new_store_instance.get_conversation_messages(conv_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "How much water did Infosys use?")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "Infosys used 450,000 kl in 2024.")
        self.assertEqual(messages[1]["lane"], "A")
        print("Test 4 Passed: Conversation history verified persistent across simulated app restart.")

if __name__ == "__main__":
    unittest.main()
