import os
import requests
import json
from typing import Dict, Any, List

class VercelAgent:
    """
    Lightweight query adapter for Vercel serverless functions.
    Avoids loading local ML databases, model files, or PyTorch, keeping the function
    footprint and uncompressed bundle size extremely small.
    """
    def __init__(self):
        self.backend_url = os.getenv("SUSTALLY_BACKEND_URL", "").strip()
        self.backend_api_key = os.getenv("SUSTALLY_BACKEND_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    def ask(self, question: str) -> Dict[str, Any]:
        # Option A: If a remote backend endpoint is configured, forward the query to it
        if self.backend_url:
            try:
                headers = {"Content-Type": "application/json"}
                if self.backend_api_key:
                    headers["Authorization"] = f"Bearer {self.backend_api_key}"

                response = requests.post(
                    f"{self.backend_url.rstrip('/')}/api/ask",
                    headers=headers,
                    json={"question": question},
                    timeout=20
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "success": False,
                        "question": question,
                        "answer": f"⚠️ Remote backend returned status code {response.status_code}.",
                        "citations": [],
                        "error": f"RemoteBackendError: {response.text}"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "question": question,
                    "answer": f"⚠️ Failed to connect to the remote backend at {self.backend_url}.",
                    "citations": [],
                    "error": f"ConnectionError: {str(e)}"
                }

        # Option B: If no remote backend, but OpenAI API key is set, run lightweight cloud reasoning
        if self.openai_api_key:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.openai_api_key}"
                }
                messages = [
                    {
                        "role": "system", 
                        "content": "You are Sustally, a production-grade AI ESG Intelligence Platform. "
                                   "You are currently running in serverless cloud mode on Vercel.\n\n"
                                   "Since local databases (metrics.db and Chroma) are excluded from the Vercel bundle, "
                                   "you do not have access to the local reports list. Answer the user's question "
                                   "using your general knowledge of sustainability disclosures. "
                                   "Clearly state that this is a serverless cloud fallback response and local reports "
                                   "were not queried."
                    },
                    {"role": "user", "content": question}
                ]
                payload = {
                    "model": self.openai_model,
                    "messages": messages,
                    "temperature": 0.3
                }
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                response.raise_for_status()
                data = response.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                return {
                    "success": True,
                    "question": question,
                    "answer": answer,
                    "citations": ["Vercel Serverless Fallback Service"],
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "question": question,
                    "answer": "⚠️ Failed to generate response via OpenAI API.",
                    "citations": [],
                    "error": f"OpenAIGenerationError: {str(e)}"
                }

        # Option C: If neither is configured, return a configuration error
        config_error = (
            "⚠️ Sustally ESG Agent is running in serverless Vercel mode, but no remote backend "
            "(`SUSTALLY_BACKEND_URL`) or OpenAI API key (`OPENAI_API_KEY`) has been configured.\n\n"
            "Please configure the environment variables in your Vercel Project Settings as detailed in the README."
        )
        return {
            "success": False,
            "question": question,
            "answer": config_error,
            "citations": [],
            "error": "ConfigurationError: Neither SUSTALLY_BACKEND_URL nor OPENAI_API_KEY is configured on Vercel."
        }
