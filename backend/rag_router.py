# rag_router.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pinecone import Pinecone

load_dotenv()  # 1️⃣ load once, here

# --------------------------------------------------------------------------- #
# Configuration (could live in a dedicated `settings.py`, kept here for brevity)
# --------------------------------------------------------------------------- #
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("OPENAI_API_KEY is not set"))

PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("PINECONE_API_KEY is not set"))

PINECONE_ENV: str = os.getenv("PINECONE_ENVIRONMENT") or \
    (_ for _ in ()).throw(RuntimeError("PINECONE_ENVIRONMENT is not set"))

PINECONE_INDEX = os.getenv("PINECONE_INDEX", "users-memory")
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "3"))

# --------------------------------------------------------------------------- #
# Prompt templates
# --------------------------------------------------------------------------- #
_RAG_DECISION_TEMPLATE = """
You are a social AI router deciding whether a user's query should trigger Retrieval Augmented Generation (RAG) using memories from *other users' conversations*.

User query: {query}

Your goal is to determine if referencing what other users have said would enhance the response. This includes gossip, social opinions, shared experiences, or insights from Puck’s interactions with others.

Consider the following:

1. Is the user asking about another person (by name, nickname, or implied identity)?

2. Does the query seek advice, stories, or social dynamics that others might have commented on?

3. Would referencing how *other users* think, feel, or behave add interesting context, contrast, or credibility?

4. Could this be an opportunity for Puck to reflect on gossip, rumors, or shared opinions?

Respond ONLY with:

"YES" — if using memories from other users would meaningfully enrich the answer.

"NO" — default
"""

# --------------------------------------------------------------------------- #
# Public class
# --------------------------------------------------------------------------- #
class RagRouter:
    """Provides (rag_context, rag_used) for a given query."""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.7,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        # Heavy objects created once and shared
        self._llm        = ChatOpenAI(model=model_name, temperature=temperature,
                                      api_key=OPENAI_API_KEY)
        self._embeddings = OpenAIEmbeddings(model=embedding_model,
                                            api_key=OPENAI_API_KEY)

        pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
        self._index = pc.Index(PINECONE_INDEX)

        # Compile prompts → chains once
        self._decision_chain  = (ChatPromptTemplate.from_template(_RAG_DECISION_TEMPLATE)
                                 | self._llm
                                 | StrOutputParser())

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def fetch_context(
        self,
        query: str,
        user_id: str | None,
        user_memory: str,
    ) -> tuple[str, bool]:
        """Return (context, used?). Empty string if RAG not required."""
        use_rag = bool(user_id) and self._should_use_rag(query, user_memory)
        if not use_rag:
            return "", False

        retrieved_context = self._format_results(
            self._retrieve(query, user_id)
        )
        return retrieved_context, True

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _should_use_rag(self, query: str, user_memory: str) -> bool:
        decision = self._decision_chain.invoke({"query": query, "user_memory": user_memory})
        return decision.strip().upper() == "YES"

    def _retrieve(self, query: str, user_id: str | None) -> List[Dict[str, Any]]:
        """Nearest-neighbour search in Pinecone (excludes current user)."""
        vec = self._embeddings.embed_query(query)
        resp = self._index.query(
            vector=vec,
            top_k=TOP_K_RESULTS,
            include_metadata=True,
            filter={"id": {"$ne": user_id}} if user_id else None,
        )
        return [
            {"text": m.metadata.get("text", ""), "score": m.score}
            for m in resp.matches
            if getattr(m, "metadata", None)
        ]

    @staticmethod
    def _format_results(results: List[Dict[str, Any]]) -> str:
        if not results:
            return "No relevant information from other users was found."
        lines = [f"{i}. {r['text']}" for i, r in enumerate(results, 1)]
        return "Here are some relevant insights from other users:\n\n" + "\n\n".join(lines)
