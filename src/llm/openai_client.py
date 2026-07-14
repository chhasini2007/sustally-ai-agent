import requests
import json
from typing import Generator, Dict, List, Any, Optional
from config import settings

class OpenAIClient:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://api.openai.com/v1"
        self.model = settings.OPENAI_MODEL
        self.api_key = settings.OPENAI_API_KEY

    def generate(self, messages: List[Dict[str, str]], stream: bool = True, timeout: Any = None, max_tokens: Optional[int] = None) -> Generator[str, None, None]:
        if timeout is None:
            timeout = (settings.OPENAI_CONNECT_TIMEOUT, settings.OPENAI_READ_TIMEOUT)
            
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
            
        response = self.session.post(url, headers=headers, json=payload, stream=stream, timeout=timeout)
        response.raise_for_status()
        
        def _generator() -> Generator[str, None, None]:
            if stream:
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode("utf-8").strip()
                        if decoded.startswith("data: "):
                            data_str = decoded[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data_json = json.loads(data_str)
                                choice = data_json.get("choices", [{}])[0]
                                delta = choice.get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
            else:
                result = response.json()
                yield result.get("choices", [{}])[0].get("message", {}).get("content", "")

        return _generator()
