import logging
import requests
from typing import Generator, Dict, List, Tuple, Optional
from config import settings
from src.llm.ollama_client import OllamaClient
from src.llm.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class LLMRouter:
    _active_provider = None
    _last_configured = None

    def __init__(self):
        self.ollama = OllamaClient()
        self.openai = OpenAIClient()
        
    def get_active_provider(self) -> str:
        """
        Returns the active/configured LLM provider.
        Tracks changes in the settings.LLM_PROVIDER configuration.
        """
        configured = settings.LLM_PROVIDER.strip()
        if LLMRouter._last_configured != configured:
            LLMRouter._last_configured = configured
            if configured.lower() == "ollama":
                LLMRouter._active_provider = "Ollama"
            elif configured.lower() == "openai":
                LLMRouter._active_provider = "OpenAI"
            else:
                LLMRouter._active_provider = configured
        return LLMRouter._active_provider
        
    def generate(self, messages: List[Dict[str, str]], stream: bool = True, max_tokens: Optional[int] = None) -> Tuple[Generator[str, None, None], str]:
        """
        Attempts to query LLM provider based on config.
        If LLM_PROVIDER is 'ollama', queries Ollama directly.
        If LLM_PROVIDER is 'openai', queries OpenAI directly.
        Returns a tuple: (content_generator, active_provider_name)
        """
        provider = settings.LLM_PROVIDER.strip().lower()
        if provider not in ("ollama", "openai"):
            logger.warning(f"Unknown LLM_PROVIDER configured: '{settings.LLM_PROVIDER}'. Using 'ollama' as default fallback.")
            provider = "ollama"
        
        def ollama_error_generator() -> Generator[str, None, None]:
            yield "⚠️ Ollama is not reachable right now. Please start the Ollama service and try again."
 
        ollama_timeout = (settings.OLLAMA_CONNECT_TIMEOUT, settings.OLLAMA_READ_TIMEOUT)
        openai_timeout = (settings.OPENAI_CONNECT_TIMEOUT, settings.OPENAI_READ_TIMEOUT)
 
        if provider == "openai":
            try:
                # Direct OpenAI call
                generator = self.openai.generate(messages, stream=stream, timeout=openai_timeout, max_tokens=max_tokens)
                LLMRouter._active_provider = "OpenAI"
                return generator, "openai"
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.warning(f"OpenAI failed (exception: {type(e).__name__}).")
                def openai_error_generator() -> Generator[str, None, None]:
                    yield "⚠️ OpenAI API is not reachable right now. Please check your OPENAI_API_KEY and network connection."
                LLMRouter._active_provider = "Unavailable"
                return openai_error_generator(), "unavailable"
        else:
            try:
                # Direct Ollama call
                generator = self.ollama.generate(messages, stream=stream, timeout=ollama_timeout, max_tokens=max_tokens)
                LLMRouter._active_provider = "Ollama"
                return generator, "ollama"
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.warning(f"Ollama failed (exception: {type(e).__name__}).")
                LLMRouter._active_provider = "Unavailable"
                return ollama_error_generator(), "unavailable"
