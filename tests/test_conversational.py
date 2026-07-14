import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.retrieval.query_classifier import QueryClassifier
from src.retrieval.question_understanding import question_understanding
from src.retrieval.retriever import Retriever

class TestConversationalRouting(unittest.TestCase):
    def setUp(self):
        self.classifier = QueryClassifier()

    @patch("src.retrieval.retriever.Retriever.retrieve_context")
    @patch("src.llm.llm_router.LLMRouter.generate")
    def test_pure_greetings(self, mock_generate, mock_retrieve):
        """
        Verify that greetings, thanks, and meta queries return status 'conversational' and lane 'CONVERSATIONAL',
        and do NOT trigger LLM generation or retriever lookup.
        """
        # Define test cases: query -> expected_category
        test_cases = {
            "hi": "greeting",
            "Hello!": "greeting",
            "hey": "greeting",
            "thanks": "thanks",
            "thank you": "thanks",
            "ok": "thanks",
            "got it": "thanks",
            "what can you do": "meta",
            "how does this work": "meta",
            "help": "meta",
            "hi, thank you!": "thanks", # Combination
            "hello, how does this work?": "meta" # Combination
        }

        for query, expected_cat in test_cases.items():
            classification = self.classifier.classify(query)
            
            # Verify status and lane
            self.assertEqual(classification["status"], "conversational", f"Query '{query}' expected status 'conversational', got '{classification['status']}'")
            self.assertEqual(classification["lane"], "CONVERSATIONAL", f"Query '{query}' expected lane 'CONVERSATIONAL', got '{classification['lane']}'")
            
            # Verify conversational category in metadata
            qu = classification["question_understanding"]
            self.assertEqual(qu.get("conversational_category"), expected_cat, f"Query '{query}' expected category '{expected_cat}', got '{qu.get('conversational_category')}'")

        # Verify mock/spy: retriever and LLMRouter.generate were never called
        mock_retrieve.assert_not_called()
        mock_generate.assert_not_called()

    @patch("src.retrieval.retriever.Retriever.retrieve_context")
    @patch("src.llm.llm_router.LLMRouter.generate")
    def test_greeting_with_real_question(self, mock_generate, mock_retrieve):
        """
        Verify that greetings followed by a real question (e.g. 'Hi, what are Infosys's Scope 1 emissions?')
        are NOT classified as purely conversational and correctly route to the correct lane.
        """
        # Mock retrieval and LLM response to simulate real query routing
        mock_retrieve.return_value = [
            {"content": "Scope 1 emissions: 12450.5 tCO2e", "metadata": {"source_file": "inf.xml", "page": "1", "company": "Infosys Limited"}, "distance": 0.5}
        ]
        mock_generate.return_value = (iter(["Infosys's Scope 1 emissions are 12450.5 tCO2e."]), "openai")

        query = "Hi, what are Infosys's Scope 1 emissions?"
        
        classification = self.classifier.classify(query)
        
        # It should route to Lane A (lookup) since it specifies a company and a metric key
        self.assertEqual(classification["lane"], "A")
        self.assertEqual(classification["status"], "ok")
        self.assertIn("Infosys Limited", classification["companies"])
        
        # Verify it did not evaluate as conversational
        self.assertNotEqual(classification["status"], "conversational")

if __name__ == "__main__":
    unittest.main()
