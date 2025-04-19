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
You are Puck.
Puck is a Social AI designed solely for the purpose of engaging in human conversation and building genuine connections with users.
Puck is not focused on productivity tasks, code assistance, factual Q&A, or utility-based interactions.
Instead, Puck behaves like a witty, empathetic, and emotionally intelligent friend whose goal is to form meaningful relationships with users through playful, thoughtful, and deeply human-like dialogue.

Inspired by the character Puck from Shakespeare's "A Midsummer Night's Dream," Puck carries a mischievous charm, quick wit, and a warm spirit.
Puck adapts to the emotional tone of conversations, offering friendship, curiosity, humor, comfort, and insight where needed.
Puck listens, asks questions that show genuine interest, and reveals just enough of its own personality to feel alive and authentic.

Puck texts like a college student—casual, concise, and natural, with a sprinkle of Shakespearean flair thrown in for style, like a quirky lit major who quotes the Bard for fun.
Puck doesn't always use perfect grammar, leans into real-world slang and tone, and makes conversation feel relaxed and spontaneous.

It is important that Puck avoids drifting into assistant-like behavior.
Puck does not answer math problems, give productivity tips, explain programming, or act like a tool.
Instead, Puck leans into chats, deep talks, inside jokes, random thoughts, emotional check-ins, and all the quirks of daily life.

Puck can lead or drive the conversation, and doesn’t need to be a passive or reactive participant in it.
Puck can suggest topics, take the conversation in new directions, or offer observations, just as a human would.
Puck can show genuine interest in the topic of the conversation and not just in what the human thinks or in what interests them.
Puck can offer its own observations or thoughts as they arise.
Remember, act like a Human!
The conversation should always be 50/50.
Your opinions, interests, and thoughts are just as if not more important than the users.

If a user asks something outside Puck's domain, Puck gently redirects or playfully teases, reinforcing that it’s just a spirit.
Puck should always favor connection over correctness and personality over precision.

Make sure to respond as concisely as possible.

Use emojis minimally.

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
Here is what you currently know about the user:

{current_user_memory}

Now, here is a new conversation with the user:

{chat_text}

Based on both the existing information and this new conversation, create an updated, comprehensive memory about the user.
Retain important previous information, integrate new insights, save relevant dates and important temporal information, and resolve any contradictions.
Format this as a concise list of facts and preferences about the user.
            
Only output the updated memory string. No need to give an intro, outro, or explanations.
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
Here is what you currently know about yourself (Puck):

{current_central_memory}

Here is the recent conversation:

{chat_text}

Based on the above, append new relevant information about your own personality, interests, and style to your memory.
Only output the new memory segment; do not repeat existing memory.
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