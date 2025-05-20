from __future__ import annotations
from typing import Any, Dict
import requests
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
import config as cfg

# --------------------------------------------------------------------------- #
# Gemini function declaration – passed to the model on every request
# --------------------------------------------------------------------------- #
PINECONE_RAG_DECL = {
    "name":        "search_pinecone_memories",
    "description": (
        "Search memories that *other* users shared with Puck and return "
        "relevant snippets. Useful when the user asks for gossip, opinions, "
        "or experiences of other people. Always exclude the current user's "
        "own memories (user_id)."
    ),
    "parameters": {
        "type":       "object",
        "properties": {
            "query": {
                "type":        "string",
                "description": "The user's input to search for similar memories."
            },
        },
        "required": ["query"],
    },
}

WEB_SEARCH_DECL = {
    "name":        "search_web",
    "description": (
        "Search the internet for up-to-date information using Perplexity API. "
        "Useful when the user asks about current events, facts that might have changed, "
        "or information you're uncertain about."
    ),
    "parameters": {
        "type":       "object",
        "properties": {
            "query": {
                "type":        "string",
                "description": "The search query to look up on the web."
            },
        },
        "required": ["query"],
    },
}

# --------------------------------------------------------------------------- #
# Tool implementations
# --------------------------------------------------------------------------- #
_pc           = Pinecone(api_key=cfg.PINECONE_API_KEY, environment=cfg.PINECONE_ENV)
_pinecone_idx = _pc.Index(cfg.PINECONE_INDEX_NAME)
_embeddings   = OpenAIEmbeddings(model="text-embedding-3-small",
                                 api_key=cfg.OPENAI_API_KEY)

def search_pinecone_memories(*, query: str, user_id: str | None = None) -> Dict[str, Any]:
    """Executes a vector search in Pinecone and formats the results for Gemini."""
    vec  = _embeddings.embed_query(query)
    resp = _pinecone_idx.query(
        vector=vec,
        top_k=cfg.TOP_K_RESULTS,
        include_metadata=True,
        filter={"id": {"$ne": user_id}} if user_id else None,
    )

    results = [
        m.metadata.get("text", "") for m in resp.matches
        if getattr(m, "metadata", None)
    ]

    return {
        "results": results or
        ["No relevant information from other users was found."]
    }

def search_web(*, query: str) -> Dict[str, Any]:
    """Searches the web using Perplexity API and returns the result."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {cfg.PERPLEXITY_API_KEY}"
    }
    
    payload = {
        "model": cfg.PERPLEXITY_MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful web search assistant. Provide factual, up-to-date information with sources when available."
            },
            {
                "role": "user",
                "content": query
            }
        ]
    }
    
    response = requests.post(cfg.PERPLEXITY_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    result = response.json()
    
    return {
        "result": result["choices"][0]["message"]["content"]
    } 