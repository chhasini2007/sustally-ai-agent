import requests
import json
from typing import Generator, Dict, List, Any
from config import settings

class OllamaClient:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL

    def generate(self, messages: List[Dict[str, str]], stream: bool = True, timeout: Any = None) -> Generator[str, None, None]:
        if timeout is None:
            timeout = (settings.OLLAMA_CONNECT_TIMEOUT, settings.OLLAMA_READ_TIMEOUT)
            
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream
        }
        
        response = self.session.post(url, json=payload, stream=stream, timeout=timeout)
        response.raise_for_status()
        
        def _generator() -> Generator[str, None, None]:
            if stream:
                for line in response.iter_lines():
                    if line:
                        try:
                            data_json = json.loads(line.decode("utf-8"))
                            content = data_json.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
            else:
                result = response.json()
                yield result.get("message", {}).get("content", "")

        return _generator()
