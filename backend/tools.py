from __future__ import annotations
from typing import Any, Dict
import requests
import config as cfg

# --------------------------------------------------------------------------- #
# Gemini function declaration – passed to the model on every request
# --------------------------------------------------------------------------- #
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