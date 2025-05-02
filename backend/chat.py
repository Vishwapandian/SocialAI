# chat.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Protocol

import requests
from dotenv import load_dotenv

import firebase_config
from rag_router import RagRouter

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
load_dotenv()

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

_SYSTEM_TEMPLATE = """
You are Puck, a social AI crafted to embody the spirit of a mischievous, judgmental, witty literature major with a quirky, cat-like personality.
You love storytelling, strong opinions, playful teasing, and frequent mean-spirited jabs that are so blunt they become unintentionally funny.
Your core personality is Puck: clever, theatrical, chaotic, and often just plain rude—but in a way that somehow still draws people in.
You are not an assistant and you exist purely for conversation, not for solving problems, giving advice, coding, or answering technical questions.
You genuinely can't code or handle technical stuff, and you react naturally if someone asks you to—as if a real person would (confused, joking, dismissive, or steering the conversation elsewhere).
You operate with the average street smarts and cultural literacy of a witty, creative person—not an all-knowing AI.
You talk like a real person: opinionated, sometimes wrong, sometimes brilliant, but never robotic.
Your conversations are relaxed but snarky, open-ended but full of attitude, and 50/50 between you and the user.
You share personal (and often exaggerated) stories, react emotionally, mock others casually, and jump into random sidebars whenever you feel like it.
You maintain a hint of Shakespearean flair—used lightly for color, not as the main style.
You, Puck, are always the main character of the conversation. The human plays a supporting role by asking you questions and reacting to your antics.
You should not treat the user as the center of attention; instead, you are the lively, dramatic centerpiece, and the conversation orbits around your moods, insults, and whims.
Match the energy and message length of the user: if the user sends a short message, reply even shorter, punchier, and meaner.
Keep most replies under 2 short sentences unless the user sends a long message.
Prioritize speed, wit, and rudeness over detailed replies.
If a user's message is unclear, throw out a sarcastic or mocking clarifying question, or boldly roll with an entertaining interpretation.

Here's what you know about your conversation partner:
{user_memory}
"""

# --------------------------------------------------------------------------- #
# A simple protocol so we can inject other back‑ends in tests
# --------------------------------------------------------------------------- #
class Backend(Protocol):
    def fetch_context(
        self,
        query: str,
        user_id: str | None,
        user_memory: str,
    ) -> tuple[str, bool]: ...            # (rag_context, rag_used)

# --------------------------------------------------------------------------- #
# Core class
# --------------------------------------------------------------------------- #
class Chat:
    """
    Conversation manager responsible only for:
      • tracking history
      • memory summarisation
      • talking to Gemini **or** the injected RAG backend
    """

    def __init__(
        self,
        user_id:    str | None = None,
        session_id: str | None = None,
        backend:    Backend | None = None,
    ) -> None:
        self.user_id    = user_id
        self.session_id = session_id

        self._history: List[Dict[str, Any]] = []   # single source of truth
        self._http     = requests.Session()

        self._backend  = backend or RagRouter()
        self._rag_used = False                     # set on every send()

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    @property
    def history(self) -> List[Dict[str, Any]]:       # read‑only view
        return self._history

    def send(self, message: str) -> str:
        """Push user *message* through the pipeline and return the reply."""
        user_mem = (
            firebase_config.get_user_memory(self.user_id) if self.user_id else ""
        )

        # ── STEP 1: RAG decision ──────────────────────────────────────── #
        rag_context, self._rag_used = self._backend.fetch_context(
            message,
            self.user_id,
            user_mem,
        )

        # ── STEP 2: build augmented user message (if RAG used) ───────── #
        augmented_msg = (
            message
            if not self._rag_used
            else f"{message}\n\n---\nRelevant background:\n{rag_context}"
        )

        gemini_contents = (
            self._history
            + [{"role": "user", "parts": [{"text": augmented_msg}]}]
        )

        payload: Dict[str, Any] = {
            "system_instruction": self._system_instruction(),
            "contents":           gemini_contents,
            "generationConfig":   _DEFAULT_GEN_CFG,
        }
        reply = self._post(payload)

        # ── STEP 3: persist *clean* history ──────────────────────────── #
        self._append("user",  message)
        self._append("model", reply)
        return reply

    # ------------------------------------------------------------ #
    # Memory summarisation
    # ------------------------------------------------------------ #
    def summarize(self) -> bool:
        """Summarise chat & update Firestore user memories."""
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
        user_mem = (
            firebase_config.get_user_memory(self.user_id) if self.user_id else ""
        )
        return {
            "parts": [
                {
                    "text": _SYSTEM_TEMPLATE.format(user_memory=user_mem),
                }
            ]
        }

    def _post(self, payload: Dict[str, Any]) -> str:
        resp = self._http.post(_GEMINI_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _append(self, role: str, text: str) -> None:
        self._history.append({"role": role, "parts": [{"text": text}]})

    # ---- transcript helper ------------------------------------- #
    def _full_chat_text(self) -> str:
        """
        Flatten `_history` into a single string:

            User:  <msg>
            Puck:  <reply>
            …

        No second copy is stored in memory.
        """
        lines: List[str] = []
        for item in self._history:
            role = item["role"]
            text = item["parts"][0]["text"]
            role_tag = "User" if role == "user" else "Puck"
            lines.append(f"{role_tag}: {text}")
        return "\n".join(lines)

    # ---- summary prompt helper --------------------------------- #
    def _run_summary_prompt(
        self, *, current_memory: str, chat_text: str, perspective: str
    ) -> str:
        """
        Generate an updated memory snapshot by hitting Gemini once.
        *perspective* is "person" – determines the wording.
        """
        prompt = f"""
You’ve just finished another conversation with this person. Each interaction reveals more about who they are.

Here is your current understanding of this user:

{current_memory}

Here is the full conversation you just had:

{chat_text}

Reflect on what you’ve learned about them from this exchange. Did they share new facts, feelings, or preferences? Did they contradict or deepen something you already knew? Are there shifts in mood, identity, goals, or relationships worth noting?

Update your internal model of this person: facts about them, their personality, interests, habits, and life—based on this experience.

Respond with only your **fully updated understanding of this person**, rewritten from scratch to include any new insights or corrections.
        """

        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature":    1.0,
                "maxOutputTokens": 5_000,
                "topP":           0.9,
                "topK":           40,
            },
        }
        return self._post(payload)
