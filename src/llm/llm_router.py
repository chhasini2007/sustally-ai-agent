import logging
import requests
from typing import Generator, Dict, List, Tuple
from config import settings
from src.llm.omniroute_client import OmniRouteClient
from src.llm.ollama_client import OllamaClient
from src.llm.grok_client import GrokClient

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(self):
        self.omniroute = OmniRouteClient()
        self.ollama = OllamaClient()
        self.grok = GrokClient()
        
    def generate(self, messages: List[Dict[str, str]], stream: bool = True) -> Tuple[Generator[str, None, None], str]:
        """
        Attempts to query LLM provider based on config.
        If LLM_PROVIDER is 'omniroute', tries OmniRoute first, then falls back to Ollama.
        If LLM_PROVIDER is 'ollama', queries Ollama directly.
        If LLM_PROVIDER is 'grok', queries Grok directly.
        Returns a tuple: (content_generator, active_provider_name)
        """
        provider = settings.LLM_PROVIDER.strip().lower()
        if provider not in ("ollama", "omniroute", "grok"):
            logger.warning(f"Unknown LLM_PROVIDER configured: '{settings.LLM_PROVIDER}'. Using 'ollama' as default fallback.")
            provider = "ollama"
        
        def error_generator() -> Generator[str, None, None]:
            yield "⚠️ Neither OmniRoute nor Ollama is reachable right now. Please start one of the LLM services and try again."

        omni_timeout = (settings.OMNIROUTE_CONNECT_TIMEOUT, settings.OMNIROUTE_READ_TIMEOUT)
        ollama_timeout = (settings.OLLAMA_CONNECT_TIMEOUT, settings.OLLAMA_READ_TIMEOUT)
        grok_timeout = (settings.GROK_CONNECT_TIMEOUT, settings.GROK_READ_TIMEOUT)

        if provider == "omniroute":
            try:
                # Test connection / fast call
                generator = self.omniroute.generate(messages, stream=stream, timeout=omni_timeout)
                return generator, "omniroute"
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.warning(f"OmniRoute failed (exception: {type(e).__name__}). Falling back to Ollama.")
                try:
                    generator = self.ollama.generate(messages, stream=stream, timeout=ollama_timeout)
                    return generator, "ollama (fallback)"
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as fallback_err:
                    logger.warning(f"Fallback Ollama also failed (exception: {type(fallback_err).__name__}).")
                    return error_generator(), "unavailable"
        elif provider == "grok":
            try:
                # Direct Grok call
                generator = self.grok.generate(messages, stream=stream, timeout=grok_timeout)
                return generator, "grok"
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.warning(f"Grok failed (exception: {type(e).__name__}).")
                def grok_error_generator() -> Generator[str, None, None]:
                    yield "⚠️ Grok API is not reachable right now. Please check your GROK_API_KEY and network connection."
                return grok_error_generator(), "unavailable"
        else:
            try:
                # Direct Ollama call
                generator = self.ollama.generate(messages, stream=stream, timeout=ollama_timeout)
                return generator, "ollama"
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.warning(f"Ollama failed (exception: {type(e).__name__}).")
                return error_generator(), "unavailable"
