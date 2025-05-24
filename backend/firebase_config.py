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
EMPTY. This is my very first time meeting this person.
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
# Public helpers for user emotions using Firestore
# ---------------------------------------------------------------------------
def get_user_emotions(user_id: str) -> dict[str, int]:
    """Return emotional state for *user_id*, fetching from Firestore, creating default if necessary."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc = user_doc_ref.get()
    if user_doc.exists:
        data = user_doc.to_dict()
        if data and "emotions" in data:
            return data["emotions"]
    
    # If no emotions found, use initial default and save it
    from config import INITIAL_EMOTIONAL_STATE # Import here to avoid circular dependency
    default_emotions = INITIAL_EMOTIONAL_STATE.copy()
    # Ensure the collection/document exists before trying to set (though set with merge=True often handles this)
    # For clarity, ensuring user_doc_ref exists or creating it if using .set without merge=True initially.
    # With merge=True, it will create if not exist or update if exists.
    user_doc_ref.set({"emotions": default_emotions}, merge=True)
    return default_emotions

def update_user_emotions(user_id: str, emotions: dict[str, int]) -> None:
    """Update user emotions for *user_id* in Firestore."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc_ref.set({"emotions": emotions}, merge=True)

def delete_user_emotions(user_id: str) -> bool:
    """Delete user emotions for *user_id* from Firestore."""
    try:
        user_doc_ref = _db.collection("user_data").document(user_id)
        # Check if document exists first
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            # Delete just the emotions field, keeping other potential data
            user_doc_ref.update({"emotions": firestore.DELETE_FIELD})
        return True
    except Exception as e:
        print(f"[Firebase] Error deleting emotions for user {user_id}: {e}")
        return False

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

def delete_user_memory(user_id: str) -> bool:
    """Delete user memory for *user_id* from Pinecone."""
    try:
        _index.delete(ids=[user_id])
        return True
    except Exception as e:
        print(f"[Pinecone] Error deleting memory for user {user_id}: {e}")
        return False