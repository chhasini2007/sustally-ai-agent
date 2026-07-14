import sys
import os
import unittest
import time
import requests
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llm.llm_router import LLMRouter
from config import settings

class TestLLMRouter(unittest.TestCase):
    def test_ollama_unreachable_degrades_cleanly(self):
        """
        Confirms that with LLM_PROVIDER=ollama and Ollama unreachable, the system degrades cleanly.
        """
        settings.LLM_PROVIDER = "ollama"
        settings.OLLAMA_BASE_URL = "http://localhost:2"
        settings.OLLAMA_CONNECT_TIMEOUT = 1
        
        router = LLMRouter()
        messages = [{"role": "user", "content": "Hello"}]
        
        gen, provider = router.generate(messages, stream=False)
        response_text = "".join(list(gen))
        
        self.assertEqual(provider, "unavailable")
        self.assertIn("Ollama is not reachable", response_text)
        print("Test passed: Unreachable Ollama degrades cleanly.")

    def test_openai_direct_path_no_others(self):
        """
        Confirms that with LLM_PROVIDER=openai, generate() calls OpenAI directly on the first attempt.
        """
        settings.LLM_PROVIDER = "openai"
        
        router = LLMRouter()
        router.ollama.generate = MagicMock(side_effect=Exception("Ollama generate should not be called!"))
        
        def mock_gen():
            yield "Hello from Mock OpenAI"
        router.openai.generate = MagicMock(return_value=mock_gen())
        
        messages = [{"role": "user", "content": "Hello"}]
        gen, provider = router.generate(messages, stream=False)
        
        self.assertEqual(provider, "openai")
        self.assertEqual("".join(list(gen)), "Hello from Mock OpenAI")
        router.ollama.generate.assert_not_called()
        print("Test passed: OpenAI direct path does not invoke Ollama.")

    def test_openai_unreachable_degrades_cleanly(self):
        """
        Confirms that with LLM_PROVIDER=openai and OpenAI unreachable, the system degrades cleanly.
        """
        settings.LLM_PROVIDER = "openai"
        settings.OPENAI_CONNECT_TIMEOUT = 1
        
        router = LLMRouter()
        # Mock actual request failure for openai
        router.openai.generate = MagicMock(side_effect=requests.exceptions.ConnectTimeout("Connection timed out"))
        
        messages = [{"role": "user", "content": "Hello"}]
        
        gen, provider = router.generate(messages, stream=False)
        response_text = "".join(list(gen))
        
        self.assertEqual(provider, "unavailable")
        self.assertIn("OpenAI API is not reachable", response_text)
        print("Test passed: Unreachable OpenAI degrades cleanly.")

if __name__ == "__main__":
    unittest.main()
