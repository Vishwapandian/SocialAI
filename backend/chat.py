from __future__ import annotations
import os
from typing import Any, Dict, List
import requests
from dotenv import load_dotenv
import firebase_config

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
Here is what you know about yourself: {central_memory}

Here is what you know about this person: {user_memory}
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

        payload = {
            "system_instruction": self._system_instruction(),
            "contents": self._history,
            "generationConfig": DEFAULT_GENERATION_CFG,
        }

        reply = self._post(payload)
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
First summarize this text in half:{current_user_memory}

Then summarize this text in half: {chat_text}

Then concatante these two together and output the new string.
            
Only output the new string. No need to give an intro, outro, or explanations.
        """

        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_memory_update_prompt}]}],
            "generationConfig": {
                "temperature": 1.0,
                "maxOutputTokens": 1000,
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
                    "maxOutputTokens": 1000,
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
First, summarize the existing central memory in half: {current_central_memory}

Then, summarize the recent conversation in half: {chat_text}

Finally, concatenate these two summaries and output ONLY the combined result as the new central memory.
"""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _system_instruction(self) -> Dict[str, Any]:
        user_memory = firebase_config.get_user_memory(self.user_id) if self.user_id else ""
        central_memory = firebase_config.get_central_memory()
        return {"parts": [{"text": _SYSTEM_TEMPLATE.format(central_memory=central_memory, user_memory=user_memory)}]}

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
        print(f"Puck: {chat.send(user_input)}")


if __name__ == "__main__":  # pragma: no cover
    _cli()