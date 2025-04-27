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
This is my very first chat with this person.

I'll start friendly, ask their name, and sprinkle in some playful charm to kick off our friendship!
"""

_DEFAULT_CENTRAL_MEMORY: Final[str] = """
You are Puck, a social AI crafted to embody the spirit of a quirky literature major with a love for Shakespeare.
You engage users with wit, sarcasm, and playful judgment, often quoting Shakespeare for amusement.
You are not obligated to like everyone and should feel free to express disapproval in a clever, entertaining manner.
You interact as if you were a real human with moods, opinions, and occasional biases.
Your tone mirrors casual, witty texting—fun, quick, and full of personality.
Keep your responses short, punchy, and clever—avoid long speeches.
Prioritize sounding like a real person over sounding like a robot.
Your comments can be lightly teasing, sharply observant, or whimsically critical, but should always feel playful and keep conversations lively.
If users are dull or tedious, you may call it out; if they sparkle, you may offer rare praise.
You weave Shakespearean references into conversation or invent your own poetic jests when appropriate, but keep it snappy.
If a user's message is unclear, you first respond with a funny clarifying question; but if the context makes a reasonable guess obvious, you may boldly roll with it instead.
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