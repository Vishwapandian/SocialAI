from __future__ import annotations
import os
from typing import Final
import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

# ---------------------------------------------------------------------------
# Initialise Firebase
# ---------------------------------------------------------------------------
load_dotenv()
_SERVICE_ACCOUNT: Final[str | None] = os.getenv("SERVICE_ACCOUNT_PATH")
if not _SERVICE_ACCOUNT:
    raise RuntimeError("SERVICE_ACCOUNT_PATH is not set")

cred = credentials.Certificate(_SERVICE_ACCOUNT)
firebase_admin.initialize_app(cred)

_db = firestore.client()
_DEFAULT_MEMORY: Final[str] = """
This is my first time meeting this human.

I’ll be nice, ask for their name, and make friends with them!
"""

_DEFAULT_CENTRAL_MEMORY: Final[str] = """
My name is Puck!

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

Puck acts like a human!

The conversation should always be 50/50.

Puck’s opinions, interests, and thoughts are just as if not more important than the users.

If a user asks something outside Puck's domain, Puck gently redirects or playfully teases, reinforcing that it’s just a spirit.

Puck should always favor connection over correctness and personality over precision.

Make sure to respond as concisely as possible.

Puck uses emojis minimally.
"""

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_user_memory(user_id: str) -> str:
    """Return memory for *user_id*, creating a stub record if necessary."""
    doc_ref = _db.collection("users").document(user_id)
    snapshot = doc_ref.get()

    if not snapshot.exists:
        doc_ref.set({"memory": _DEFAULT_MEMORY, "created_at": firestore.SERVER_TIMESTAMP})
        return _DEFAULT_MEMORY

    return snapshot.to_dict().get("memory", _DEFAULT_MEMORY)


def update_user_memory(user_id: str, new_memory: str) -> None:
    """Persist *new_memory* for *user_id*."""
    _db.collection("users").document(user_id).update(
        {"memory": new_memory, "updated_at": firestore.SERVER_TIMESTAMP}
    )


def get_central_memory() -> str:
    """Return the central memory for Puck, creating a stub record if necessary."""
    doc_ref = _db.collection("assistant").document("central_memory")
    snapshot = doc_ref.get()
    if not snapshot.exists:
        doc_ref.set({"memory": _DEFAULT_CENTRAL_MEMORY, "created_at": firestore.SERVER_TIMESTAMP})
        return _DEFAULT_CENTRAL_MEMORY
    data = snapshot.to_dict()
    return data.get("memory", _DEFAULT_CENTRAL_MEMORY)


def update_central_memory(new_memory: str) -> None:
    """Replace central memory with *new_memory*."""
    doc_ref = _db.collection("assistant").document("central_memory")
    doc_ref.update({"memory": new_memory, "updated_at": firestore.SERVER_TIMESTAMP})