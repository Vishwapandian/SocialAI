# chat.py  –– Gemini‑only, Pinecone‑powered RAG via function calling
from __future__ import annotations

import os
from typing import Any, Dict, List, Protocol

import requests
from dotenv import load_dotenv
from pinecone import Pinecone                                                # NEW
from langchain_openai import OpenAIEmbeddings                                 # NEW

import firebase_config

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
load_dotenv()

# ––– Gemini ---------------------------------------------------------------- #
_API_KEY: str = os.getenv("GEMINI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("GEMINI_API_KEY not set"))
_MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
_GEMINI_URL: str = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL_NAME}:generateContent?key={_API_KEY}"
)

_DEFAULT_GEN_CFG: Dict[str, Any] = {
    "stopSequences":      [],
    "temperature":        1.2,
    "maxOutputTokens":    250,
    "topP":               0.9,
    "topK":               40,
}

# ––– Pinecone --------------------------------------------------------------- #
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("OPENAI_API_KEY is not set"))
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("PINECONE_API_KEY is not set"))
PINECONE_ENV: str = os.getenv("PINECONE_ENVIRONMENT") or \
    (_ for _ in ()).throw(RuntimeError("PINECONE_ENVIRONMENT is not set"))
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "users-memory")
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "3"))

_pc           = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
_pinecone_idx = _pc.Index(PINECONE_INDEX)
_embeddings   = OpenAIEmbeddings(model="text-embedding-3-small",
                                 api_key=OPENAI_API_KEY)

# --------------------------------------------------------------------------- #
# Gemini function declaration – passed to the model on every request
# --------------------------------------------------------------------------- #
_PINECONE_RAG_DECL = {
    "name":        "search_pinecone_memories",
    "description": (
        "Search memories that *other* users shared with Birdie and return "
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

# --------------------------------------------------------------------------- #
# Helper that the model can ask us to run
# --------------------------------------------------------------------------- #
def search_pinecone_memories(*, query: str, user_id: str | None = None) -> Dict[str, Any]:
    """Executes a vector search in Pinecone and formats the results for Gemini."""
    vec  = _embeddings.embed_query(query)
    resp = _pinecone_idx.query(
        vector=vec,
        top_k=TOP_K_RESULTS,
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

# --------------------------------------------------------------------------- #
_SYSTEM_TEMPLATE = """
You are Birdie, a Social AI.\n
Here's what you know about your conversation partner:\n
{user_memory}
"""

# --------------------------------------------------------------------------- #
# Conversation core
# --------------------------------------------------------------------------- #
class Chat:
    """
    Manages state + calls Gemini.  RAG is triggered *only* via function calling.
    """

    def __init__(
        self,
        user_id:    str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.user_id    = user_id
        self.session_id = session_id

        self._history: List[Dict[str, Any]] = []    # chron. list of Gemini‑style parts
        self._http     = requests.Session()

    # ------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------ #
    @property
    def history(self) -> List[Dict[str, Any]]:
        return self._history

    def send(self, message: str) -> str:
        """
        Send *message* to Gemini.  Gemini may respond with a function call
        (search_pinecone_memories) or with plain text.  If it calls the
        function, we execute it, feed the result back to Gemini, and return
        the model's final reply.
        """
        # ---- build user + memory‑aware system prompt ------------------ #
        system_instr = self._system_instruction()
        self._append("user", message)                            # tentatively add

        # ---- 1st request: give Gemini the option to call RAG ----------- #
        payload = {
            "system_instruction": system_instr,
            "contents":           self._history,
            "generationConfig":   _DEFAULT_GEN_CFG,
            "tools":              [{"functionDeclarations": [_PINECONE_RAG_DECL]}],
            # leave function_calling_config default = AUTO
        }
        response = self._post_raw(payload)
        first_part = response["candidates"][0]["content"]["parts"][0]

        # ---- Did Gemini ask to call our function? ---------------------- #
        if "functionCall" in first_part:
            fn_call = first_part["functionCall"]
            # execute tool
            tool_result = search_pinecone_memories(
                **fn_call.get("args", {}), user_id=self.user_id
            )

            # Gemini expects a *function response* message next
            self._history.append({
                "role": "model",
                "parts": [{"functionCall": fn_call}],
            })
            self._history.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": fn_call["name"],
                        "response": tool_result       # keep it JSON
                    }
                }],
            })

            # ---- 2nd request: get the *final* answer ------------------ #
            payload = {
                "system_instruction": system_instr,
                "contents":           self._history,
                "generationConfig":   _DEFAULT_GEN_CFG,
                # keep tools so model can chain if it really wants
                "tools":              [{"functionDeclarations": [_PINECONE_RAG_DECL]}],
            }
            response = self._post_raw(payload)
            reply_text = response["candidates"][0]["content"]["parts"][0]["text"]

            # store final reply
            self._append("model", reply_text)
            return reply_text

        # ---- No function call – simple path ---------------------------- #
        reply_text = first_part["text"]
        self._append("model", reply_text)
        return reply_text

    # ------------------------------------------------------------ #
    # Memory summarisation (unchanged)
    # ------------------------------------------------------------ #
    def summarize(self) -> bool:  # … identical to previous version …
        try:
            chat_text = self._full_chat_text()
            updated_user_mem = self._run_summary_prompt(
                current_memory=firebase_config.get_user_memory(self.user_id),
                chat_text=chat_text,
                perspective="person",
            )
            firebase_config.update_user_memory(self.user_id, updated_user_mem)
            return True
        except Exception as exc:               # noqa: BLE001
            print(f"[Chat] memory update failed: {exc}")
            return False

    # ------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------ #
    def _system_instruction(self) -> Dict[str, Any]:
        user_mem = firebase_config.get_user_memory(self.user_id) if self.user_id else ""
        return {"parts": [{"text": _SYSTEM_TEMPLATE.format(user_memory=user_mem)}]}

    def _post_raw(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._http.post(_GEMINI_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _append(self, role: str, text: str) -> None:
        self._history.append({"role": role, "parts": [{"text": text}]})

    # ---- transcript helper ------------------------------------- #
    def _full_chat_text(self) -> str:  # unchanged …
        lines: List[str] = []
        for item in self._history:
            role_tag = "User" if item["role"] == "user" else "Birdie"
            lines.append(f"{role_tag}: {item['parts'][0]['text']}")
        return "\n".join(lines)

    # ---- summary helper (unchanged) ---------------------------- #
    def _run_summary_prompt(
        self, *, current_memory: str, chat_text: str, perspective: str
    ) -> str:  # identical to previous implementation
        prompt = f"""
You've just finished another conversation with this person …
[omitted for brevity –– same as before]
        """
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature":    1.0,
                "maxOutputTokens": 5_000,
                "topP":           0.9,
                "topK":           40,
            },
        }
        resp = self._post_raw(payload)
        return resp["candidates"][0]["content"]["parts"][0]["text"]
