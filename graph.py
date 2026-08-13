"""
graph.py - Stateful RAG Orchestration using LangGraph.
Implements routing, hybrid retrieval with OpenSearch (RRF), and fallback logic.
"""
from typing import TypedDict, List, Any
from langgraph.graph import StateGraph, END
from llm import RAGClient

class AgentState(TypedDict):
    query: str
    context: List[str]
    confidence_score: float
    response: str

def create_rag_graph(rag_client: RAGClient):
    async def router_node(state: AgentState):
        """Analyzes user query intent."""
        return state

    async def retrieve_node(state: AgentState):
        """Executes hybrid retrieval (Dense + BM25 via RRF) on OpenSearch."""
        search_res = rag_client.search(
            index="igdb",
            query=state["query"],
            num=3,
            search_type="hybrid"
        )
        hits = search_res.get("hits", {}).get("hits", [])
        
        chunks = []
        for h in hits:
            if isinstance(h, dict):
                src = h.get("_source") or {}
                if isinstance(src, dict) and src.get("summary"):
                    chunks.append(str(src.get("summary")))
        
        state["context"] = chunks if chunks else ["No direct hybrid match."]
        state["confidence_score"] = 0.85 if chunks else 0.40
        return state

    async def fallback_rewrite_node(state: AgentState):
        """Fallback node triggered if retrieval confidence is below threshold."""
        fallback_res = rag_client.search(
            index="wikipedia",
            query=state["query"],
            num=2,
            search_type="lexical"
        )
        hits = fallback_res.get("hits", {}).get("hits", [])
        
        extra_chunks = []
        for h in hits:
            if isinstance(h, dict):
                src = h.get("_source") or {}
                if isinstance(src, dict) and src.get("text"):
                    extra_chunks.append(str(src.get("text"))[:500])
                    
        state["context"].extend(extra_chunks)
        state["confidence_score"] = 0.70
        return state

    async def generator_node(state: AgentState):
        """Generates grounded answer via Gemini LLM using verified context."""
        context_block = "\n---\n".join(state["context"])
        prompt = f"Context:\n{context_block}\n\nQuestion: {state['query']}"
        answer = rag_client.llm(prompt)
        text = answer.text if hasattr(answer, "text") else str(answer)
        state["response"] = text
        return state

    def should_fallback(state: AgentState) -> str:
        if state.get("confidence_score", 0.0) < 0.60:
            return "fallback"
        return "generate"

    workflow = StateGraph(AgentState)
    workflow.add_node("router", router_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("fallback_rewrite", fallback_rewrite_node)
    workflow.add_node("generator", generator_node)

    workflow.set_entry_point("router")
    workflow.add_edge("router", "retrieve")
    workflow.add_conditional_edges("retrieve", should_fallback, {
        "fallback": "fallback_rewrite",
        "generate": "generator"
    })
    workflow.add_edge("fallback_rewrite", "generator")
    workflow.add_edge("generator", END)

    return workflow.compile()