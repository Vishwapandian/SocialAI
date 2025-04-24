from __future__ import annotations
import os
from typing import Final
import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

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
# Initialize Pinecone for user memory
# ---------------------------------------------------------------------------
_PINECONE_API_KEY: Final[str | None] = os.getenv("PINECONE_API_KEY")
if not _PINECONE_API_KEY:
    raise RuntimeError("PINECONE_API_KEY is not set")
_PINECONE_ENV: Final[str | None] = os.getenv("PINECONE_ENVIRONMENT")
if not _PINECONE_ENV:
    raise RuntimeError("PINECONE_ENVIRONMENT is not set")
_OPENAI_API_KEY: Final[str | None] = os.getenv("OPENAI_API_KEY")
if not _OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")
_OPENAI_EMBEDDING_MODEL: Final[str] = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
_PINECONE_INDEX: Final[str] = os.getenv("PINECONE_USER_INDEX", "users-memory")

_openai_client = OpenAI(api_key=_OPENAI_API_KEY)
_pc = Pinecone(api_key=_PINECONE_API_KEY, environment=_PINECONE_ENV)
_existing_indexes = [idx["name"] for idx in _pc.list_indexes()]
if _PINECONE_INDEX not in _existing_indexes:
    _pc.create_index(name=_PINECONE_INDEX, dimension=1536, metric="cosine",
                     spec=ServerlessSpec(cloud="aws", region="us-east-1"))
_index = _pc.Index(_PINECONE_INDEX)

# ---------------------------------------------------------------------------
# Public helpers for user memory using Pinecone
# ---------------------------------------------------------------------------
def get_user_memory(user_id: str) -> str:
    """Return memory for *user_id*, fetching from Pinecone, creating stub record if necessary."""
    fetch_response = _index.fetch(ids=[user_id])
    # Pinecone FetchResponse has a .vectors attribute (dict)
    vectors = fetch_response.vectors if hasattr(fetch_response, 'vectors') else {}
    if user_id not in vectors:
        text = _DEFAULT_MEMORY
        # Generate embedding
        embedding = _openai_client.embeddings.create(
            input=text.replace("\n", " "), model=_OPENAI_EMBEDDING_MODEL
        ).data[0].embedding
        metadata = {"text": text}
        _index.upsert(vectors=[(user_id, embedding, metadata)])
        return text
    vector = vectors[user_id]
    metadata = getattr(vector, "metadata", {}) or {}
    return metadata.get("text", _DEFAULT_MEMORY)

def update_user_memory(user_id: str, new_memory: str) -> None:
    """Update user memory for *user_id* in Pinecone."""
    text = new_memory
    embedding = _openai_client.embeddings.create(
        input=text.replace("\n", " "), model=_OPENAI_EMBEDDING_MODEL
    ).data[0].embedding
    metadata = {"text": text}
    _index.upsert(vectors=[(user_id, embedding, metadata)])

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
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