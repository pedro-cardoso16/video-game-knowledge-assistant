"""
api.py - FastAPI Service Layer with Latency & Observability Middleware.
"""
import time
import os
from typing import Optional, Any, cast
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from opensearchpy import OpenSearch

from llm import RAGClient
from graph import create_rag_graph
from tasks import async_ingest_game_task

app = FastAPI(
    title="Video Game Knowledge Assistant API",
    version="2.0.0",
    description="Asynchronous Backend API powered by FastAPI, LangGraph, and Celery."
)

# Granular Latency Tracking Middleware
@app.middleware("http")
async def latency_monitoring_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    return response

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"

class IngestRequest(BaseModel):
    game_id: str
    source: Optional[str] = "igdb"

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag-backend"}

@app.post("/v1/query")
async def query_endpoint(payload: QueryRequest):
    """Executes stateful LangGraph workflow with hybrid search and fallback."""
    try:
        client = OpenSearch(
            hosts=[{"host": os.getenv("OPENSEARCH_HOST", "localhost"), "port": int(os.getenv("OPENSEARCH_PORT", 9200))}],
            http_auth=(os.getenv("OPENSEARCH_USER", "admin"), os.getenv("OPENSEARCH_PASSWORD", "Opensearch16admin#")),
            use_ssl=False, verify_certs=False, ssl_show_warn=False
        )
        rag_client = RAGClient(client)
        rag_graph = create_rag_graph(rag_client)
        
        initial_state = {
            "query": payload.query,
            "context": [],
            "confidence_score": 0.0,
            "response": ""
        }
        final_state = await rag_graph.ainvoke(initial_state)
        return {
            "query": payload.query,
            "response": final_state["response"],
            "retrieved_chunks": len(final_state["context"]),
            "confidence": final_state["confidence_score"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/ingest/async")
async def trigger_ingestion(payload: IngestRequest):
    """Enqueues background task into Celery + Redis with idempotency guards."""
    # cast para Any cala a reclamação do linter sobre o método dinâmico .delay() do Celery
    task = cast(Any, async_ingest_game_task).delay(payload.game_id, payload.source)
    return {"task_id": getattr(task, "id", "queued"), "status": "QUEUED"}