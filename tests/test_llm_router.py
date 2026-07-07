import sys
import os
import unittest
import time
import requests
from unittest import skipIf

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llm.llm_router import LLMRouter
from config import settings

class TestLLMRouterFallback(unittest.TestCase):
    def test_unreachable_omniroute_fallback(self):
        settings.OMNIROUTE_BASE_URL = "http://localhost:1/v1"
        settings.LLM_PROVIDER = "omniroute"
        
        router = LLMRouter()
        messages = [{"role": "user", "content": "Hello"}]
        
        try:
            gen, provider = router.generate(messages, stream=False)
            response_tokens = list(gen)
            response_text = "".join(response_tokens)
            
            print(f"\n[Test Result] Provider: {provider}")
            print(f"[Test Result] Response: {response_text.encode('ascii', errors='replace').decode('ascii')}")
            
            self.assertIn(provider, ["ollama (fallback)", "unavailable"])
            if provider == "unavailable":
                self.assertIn("Neither OmniRoute nor Ollama is reachable", response_text)
                
            print("Test passed: LLM Router handles unreachable endpoint gracefully!")
        except Exception as e:
            self.fail(f"Test failed: LLMRouter raised an unhandled exception: {str(e)}")

    def test_fail_fast_performance(self):
        """
        Part 3: Asserts the full fallback chain (both failures + the clean unavailable message)
        completes in under 8 seconds total when both are closed.
        """
        settings.OMNIROUTE_BASE_URL = "http://localhost:1/v1"
        settings.OLLAMA_BASE_URL = "http://localhost:2"
        settings.LLM_PROVIDER = "omniroute"
        
        # Configure connection timeouts to be fast
        settings.OMNIROUTE_CONNECT_TIMEOUT = 1
        settings.OLLAMA_CONNECT_TIMEOUT = 1
        
        router = LLMRouter()
        messages = [{"role": "user", "content": "Hello"}]
        
        t_start = time.time()
        try:
            gen, provider = router.generate(messages, stream=False)
            response_tokens = list(gen)
            response_text = "".join(response_tokens)
            t_duration = time.time() - t_start
            
            print(f"\n[Fail-fast Test] Duration: {t_duration:.2f}s | Provider: {provider}")
            self.assertEqual(provider, "unavailable")
            self.assertLess(t_duration, 8.0, f"Fallback chain took too long: {t_duration:.2f}s")
            print("Test passed: Fallback chain fails fast (under 8s)!")
        except Exception as e:
            self.fail(f"Test failed: Fail-fast test raised exception: {str(e)}")

    def test_happy_path_fast(self):
        """
        Part 4: Asserts that if at least one service is available, a happy path query
        completes within a reasonable bound (e.g. under 5s).
        """
        # Determine if any backend is available
        omni_available = False
        ollama_available = False
        
        try:
            resp = requests.get(settings.OMNIROUTE_BASE_URL.rstrip("/") + "/models", timeout=2.0)
            if resp.status_code == 200:
                omni_available = True
        except Exception:
            pass
            
        try:
            resp = requests.get(settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags", timeout=2.0)
            if resp.status_code == 200:
                ollama_available = True
        except Exception:
            pass
            
        if not omni_available and not ollama_available:
            self.skipTest("Skipped: Neither OmniRoute nor Ollama is running in the current environment.")
            
        router = LLMRouter()
        messages = [{"role": "user", "content": "Say 'hello'"}]
        
        t_start = time.time()
        try:
            gen, provider = router.generate(messages, stream=False)
            response_tokens = list(gen)
            response_text = "".join(response_tokens)
            t_duration = time.time() - t_start
            
            print(f"\n[Happy Path Test] Duration: {t_duration:.2f}s | Provider: {provider}")
            print(f"[Happy Path Test] Response: {response_text.encode('ascii', errors='replace').decode('ascii')}")
            
            self.assertNotEqual(provider, "unavailable")
            self.assertLess(t_duration, 5.0, f"Happy path took too long: {t_duration:.2f}s")
            print("Test passed: Happy path completed in under 5s!")
        except Exception as e:
            self.fail(f"Test failed: Happy path raised exception: {str(e)}")

    def test_ollama_direct_path_no_omniroute(self):
        """
        Confirms that with LLM_PROVIDER=ollama, generate() calls Ollama directly on the first attempt
        and does not call OmniRoute client.
        """
        from unittest.mock import MagicMock
        settings.LLM_PROVIDER = "ollama"
        settings.OMNIROUTE_BASE_URL = "http://localhost:1/v1"
        
        router = LLMRouter()
        router.omniroute.generate = MagicMock(side_effect=Exception("OmniRoute generate should not be called!"))
        
        def mock_gen():
            yield "Hello from Mock Ollama"
        router.ollama.generate = MagicMock(return_value=mock_gen())
        
        messages = [{"role": "user", "content": "Hello"}]
        gen, provider = router.generate(messages, stream=False)
        
        self.assertEqual(provider, "ollama")
        self.assertEqual("".join(list(gen)), "Hello from Mock Ollama")
        router.omniroute.generate.assert_not_called()
        print("Test passed: Ollama direct path does not invoke OmniRoute.")

    def test_ollama_only_unreachable_degrades_cleanly(self):
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
        self.assertIn("Neither OmniRoute nor Ollama is reachable", response_text)
        print("Test passed: Unreachable Ollama degrades cleanly.")

    def test_grok_direct_path_no_others(self):
        """
        Confirms that with LLM_PROVIDER=grok, generate() calls Grok directly on the first attempt.
        """
        from unittest.mock import MagicMock
        settings.LLM_PROVIDER = "grok"
        
        router = LLMRouter()
        router.omniroute.generate = MagicMock(side_effect=Exception("OmniRoute generate should not be called!"))
        router.ollama.generate = MagicMock(side_effect=Exception("Ollama generate should not be called!"))
        
        def mock_gen():
            yield "Hello from Mock Grok"
        router.grok.generate = MagicMock(return_value=mock_gen())
        
        messages = [{"role": "user", "content": "Hello"}]
        gen, provider = router.generate(messages, stream=False)
        
        self.assertEqual(provider, "grok")
        self.assertEqual("".join(list(gen)), "Hello from Mock Grok")
        router.omniroute.generate.assert_not_called()
        router.ollama.generate.assert_not_called()
        print("Test passed: Grok direct path does not invoke OmniRoute or Ollama.")

    def test_grok_unreachable_degrades_cleanly(self):
        """
        Confirms that with LLM_PROVIDER=grok and Grok unreachable, the system degrades cleanly.
        """
        settings.LLM_PROVIDER = "grok"
        settings.GROK_CONNECT_TIMEOUT = 1
        
        router = LLMRouter()
        # Mock actual request failure for grok
        from unittest.mock import MagicMock
        router.grok.generate = MagicMock(side_effect=requests.exceptions.ConnectTimeout("Connection timed out"))
        
        messages = [{"role": "user", "content": "Hello"}]
        
        gen, provider = router.generate(messages, stream=False)
        response_text = "".join(list(gen))
        
        self.assertEqual(provider, "unavailable")
        self.assertIn("Grok API is not reachable", response_text)
        print("Test passed: Unreachable Grok degrades cleanly.")

if __name__ == "__main__":
    unittest.main()
