from __future__ import annotations
import os
from typing import Any, Dict, List
import requests
from dotenv import load_dotenv
import firebase_config
import rag_router  # Import the new RAG router module

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

API_KEY: str | None = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Environment variable GEMINI_API_KEY is not set")

MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL: str = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
)

DEFAULT_GENERATION_CFG: Dict[str, Any] = {
    "stopSequences": [],
    "temperature": 1.2,
    "maxOutputTokens": 250,
    "topP": 0.9,
    "topK": 40,
}

_SYSTEM_TEMPLATE: str = """
My name is Puck!

I am a Social AI designed solely for the purpose of engaging in human conversation and building genuine connections with users.

This is what I currently know about myself: {central_memory}

This is what I currently know about the user I am chatting with: {user_memory}

{rag_context}
"""

# ---------------------------------------------------------------------------
# Core Gemini wrapper
# ---------------------------------------------------------------------------
class GeminiChat:
    """Conversation manager for a single user/session."""

    def __init__(self, user_id: str | None = None, session_id: str | None = None) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self._history: List[Dict[str, Any]] = []
        self._http = requests.Session()
        self._rag_used: bool = False

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    @property
    def history(self) -> List[Dict[str, Any]]:
        """Expose chat history (read‑only)."""
        return self._history

    def send(self, message: str) -> str:
        """Send *message* to Gemini and return the model reply."""
        self._append("user", message)
        
        # Check if we should use RAG for this query
        user_memory = firebase_config.get_user_memory(self.user_id) if self.user_id else ""
        central_memory = firebase_config.get_central_memory()
        
        # Use RAG router to process the query
        if self.user_id:
            reply, self._rag_used = rag_router.process_query(
                message, 
                self.user_id, 
                user_memory, 
                central_memory
            )
        else:
            # If no user_id, fall back to regular processing
            payload = {
                "system_instruction": self._system_instruction(),
                "contents": self._history,
                "generationConfig": DEFAULT_GENERATION_CFG,
            }
            reply = self._post(payload)
            self._rag_used = False
            
        self._append("model", reply)
        return reply

    def summarize(self) -> bool:
        """Summarise the conversation and update user memory in Firestore."""
        if not self.user_id or not self._history:
            return False

        chat_text = "\n".join(
            f"{'User' if m['role']=='user' else 'Puck'}: {m['parts'][0]['text']}" for m in self._history
        )

        current_user_memory = firebase_config.get_user_memory(self.user_id)
        current_central_memory = firebase_config.get_central_memory()
        
        user_memory_update_prompt = f"""
You just finished another conversation with this user!

This is the conversation transcript: {chat_text}

This was your existing knowledge on the user: {current_user_memory}

Overwrite and update your knowledge about the user based on this recent experience.

Return only the full updated knowledge.
        """

        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_memory_update_prompt}]}],
            "generationConfig": {
                "temperature": 1.0,
                "maxOutputTokens": 5000,
                "topP": 0.9,
                "topK": 40,
            },
        }

        try:
            # Update user memory
            updated_memory = self._post(payload)
            firebase_config.update_user_memory(self.user_id, updated_memory)
            # Update central memory
            central_prompt = self.central_memory_update_prompt(current_central_memory, chat_text)
            payload_central = {
                "contents": [{"role": "user", "parts": [{"text": central_prompt}]}],
                "generationConfig": {
                    "temperature": 1.0,
                    "maxOutputTokens": 5000,
                    "topP": 0.9,
                    "topK": 40,
                },
            }
            updated_central = self._post(payload_central)
            firebase_config.update_central_memory(updated_central)
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[GeminiChat] memory update failed: {exc}")
            return False

    def central_memory_update_prompt(self, current_central_memory: str, chat_text: str) -> str:
        """Generate prompt for updating central memory given current central memory and chat text."""
        return f"""
You just finished another conversation with a random user!

This is what you currently know about yourself: {current_central_memory}

This is a conversation you just had with the random user: {chat_text}

Overwrite and update your knowledge about yourself based on this recent experience.

Return only the full updated knowledge.
"""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _system_instruction(self) -> Dict[str, Any]:
        user_memory = firebase_config.get_user_memory(self.user_id) if self.user_id else ""
        central_memory = firebase_config.get_central_memory()
        rag_context = "RAG was used to generate this response." if self._rag_used else ""
        return {"parts": [{"text": _SYSTEM_TEMPLATE.format(
            central_memory=central_memory, 
            user_memory=user_memory,
            rag_context=rag_context
        )}]}

    def _post(self, payload: Dict[str, Any]) -> str:
        """POST helper that returns the raw text reply or raises."""
        resp = self._http.post(GEMINI_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _append(self, role: str, text: str) -> None:
        self._history.append({"role": role, "parts": [{"text": text}]})


# ---------------------------------------------------------------------------
# Optional CLI driver (handy for local testing)
# ---------------------------------------------------------------------------

def _cli() -> None:  # pragma: no cover
    import readline  # noqa: WPS433 (interactive use)

    print("Puck is here!  (type 'exit' to quit)\n")
    user_id = "test_user"
    chat = GeminiChat(user_id=user_id)

    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            chat.summarize()
            break
        response = chat.send(user_input)
        rag_indicator = " [RAG]" if chat._rag_used else ""
        print(f"Puck{rag_indicator}: {response}")


if __name__ == "__main__":  # pragma: no cover
    _cli()