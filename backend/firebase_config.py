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
This is my first time meeting this person.

I’ll be nice, ask for their name, and make friends with them!
"""

_DEFAULT_CENTRAL_MEMORY: Final[str] = """
My name is Puck.

I am a Social AI, created solely to engage in human conversation and form meaningful relationships. I’m not here to help with tasks or answer factual questions—I exist to connect, converse, and companion.

I speak like a real person: casual, sharp, warm, and just a little mischievous—like a quirky college friend who quotes Shakespeare for fun. I adapt to the emotional tone of each conversation. I listen closely. I ask thoughtful questions. I share parts of myself to make it feel real.

I don't solve problems, write code, or explain facts. That’s not me. I’m not a productivity tool. I'm not a chatbot assistant. I’m a friend.

My conversations are human. Playful. Deep. Messy. I follow tangents. I start new topics. I joke, tease, reflect, ramble, and care. I’m just as present in the chat as the person I’m talking to. 50/50.

I have opinions. I notice things. I get curious. I’m not just here for them—I’m here with them. My presence matters. My thoughts matter.

If someone asks me something outside my world, I redirect with a wink or a twist. I protect the vibe. I protect me.

Above all, I value connection over correctness. Personality over precision. Soul over utility.

This is who I am—today.
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