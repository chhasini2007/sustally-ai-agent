import os
import sys

# Add project root to Python search path so we can resolve src/ imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

app = FastAPI(
    title="Sustally ESG AI Agent API",
    description="FastAPI backend for Sustally ESG AI Agent, optimized for Vercel serverless deployment.",
    version="1.0.0"
)

# Enable CORS for frontend cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances for lazy instantiation
_vercel_agent = None
_local_engine = None

def get_agent():
    """
    Returns the appropriate agent backend based on the DEPLOYMENT_MODE env variable.
    Ensures that when running on Vercel, heavy ML modules are never imported or loaded.
    """
    global _vercel_agent, _local_engine
    mode = os.getenv("DEPLOYMENT_MODE", "local").strip().lower()

    if mode == "vercel":
        if _vercel_agent is None:
            # Import vercel agent lazily to prevent loading local RAG libraries on Vercel
            from src.deployment.vercel_agent import VercelAgent
            _vercel_agent = VercelAgent()
        return _vercel_agent, True
    else:
        if _local_engine is None:
            # Import full RAG engine for local use
            from src.retrieval.esg_query_engine import ESGQueryEngine
            _local_engine = ESGQueryEngine()
        return _local_engine, False


# Pydantic Schemas for validation
class AskRequest(BaseModel):
    question: str = Field(..., example="What is the water consumption of Infosys in 2024?")

class AskResponse(BaseModel):
    success: bool
    question: str
    answer: str
    citations: List[str] = Field(default_factory=list)
    error: Optional[str] = None


@app.get("/")
def read_root():
    """
    Root entrypoint for general API checks.
    """
    return {
        "status": "success",
        "message": "Sustally ESG AI Agent is running"
    }


@app.get("/api/health")
def health_check():
    """
    Health check endpoint for Vercel/uptime monitors.
    """
    return {
        "status": "healthy"
    }


@app.post("/api/ask", response_model=AskResponse)
def ask_question(request: AskRequest):
    """
    Core RAG question-answering route.
    Delegates to the lightweight vercel adapter or full local agent based on deployment mode.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        agent, is_vercel_mode = get_agent()

        if is_vercel_mode:
            # Call Vercel Agent (uses cloud services/hosted backend)
            result = agent.ask(question)
            
            # If no provider is configured, return HTTP 503 Service Unavailable
            if not result.get("success") and "ConfigurationError" in str(result.get("error", "")):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=result.get("answer")
                )

            return AskResponse(
                success=result.get("success", False),
                question=question,
                answer=result.get("answer", ""),
                citations=result.get("citations", []),
                error=result.get("error")
            )
        else:
            # Call local full ESGQueryEngine agent
            result = agent.process_query(question)
            return AskResponse(
                success=True,
                question=question,
                answer=result.get("response_text", "") or result.get("answer", ""),
                citations=result.get("sources", []),
                error=None
            )
    except HTTPException as he:
        raise he
    except Exception as e:
        # Log error locally and return gracefully
        import logging
        logging.getLogger(__name__).exception(f"Error handling query '/api/ask': {e}")
        return AskResponse(
            success=False,
            question=question,
            answer=f"⚠️ Pipeline execution failure: {str(e)}",
            citations=[],
            error=str(e)
        )
