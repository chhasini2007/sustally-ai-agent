import os
import sys

# Add project root to Python search path so we can resolve src/ imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
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

# Global engine container for lazy instantiation
_engine = None

def get_engine():
    """
    Lazy initializer for the ESG query engine.
    Ensures expensive modules and classes are loaded only when the first query arrives,
    rather than during server initialization (which speeds up serverless warm starts).
    """
    global _engine
    if _engine is None:
        from src.retrieval.esg_query_engine import ESGQueryEngine
        _engine = ESGQueryEngine()
    return _engine


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
    Delegates parsing, planning, routing, delta reasoning, and report generation
    to the active ESGQueryEngine agent pipeline.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        engine = get_engine()
        result = engine.process_query(question)

        # Extract answer and metadata citations
        answer = result.get("response_text", "") or result.get("answer", "")
        citations = result.get("sources", [])

        return AskResponse(
            success=True,
            question=question,
            answer=answer,
            citations=citations,
            error=None
        )
    except Exception as e:
        # Log error locally and return gracefully to avoid API crashes
        import logging
        logging.getLogger(__name__).exception(f"Error handling query '/api/ask': {e}")
        
        # If the local database is missing (untracked on GitHub), fall back to explanation
        error_msg = str(e)
        user_friendly_answer = (
            "⚠️ The ESG Intelligence Platform encountered a deployment limitations error.\n\n"
            f"**Error Details:** `{error_msg}`\n\n"
            "**Possible Cause:** The local SQLite database (`metrics.db`) or Chroma vector database is "
            "not present in the cloud bundle (they are excluded from GitHub for repo hygiene).\n\n"
            "**Action Required:** Connect the platform to a hosted cloud database or object store for serverless "
            "deployments as detailed in `docs/Deployment.md`."
        )
        
        return AskResponse(
            success=False,
            question=question,
            answer=user_friendly_answer,
            citations=[],
            error=error_msg
        )
