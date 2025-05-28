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
EMPTY. This is my very first time meeting this person.
"""

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
# Public helpers for user memory using Firebase/Firestore
# ---------------------------------------------------------------------------
def get_user_memory(user_id: str) -> str:
    """Return memory for *user_id*, fetching from Firestore, creating default if necessary."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc = user_doc_ref.get()
    if user_doc.exists:
        data = user_doc.to_dict()
        if data and "memory" in data:
            return data["memory"]
    
    # If no memory found, use default and save it
    user_doc_ref.set({"memory": _DEFAULT_MEMORY}, merge=True)
    return _DEFAULT_MEMORY

def update_user_memory(user_id: str, new_memory: str) -> None:
    """Update user memory for *user_id* in Firestore."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc_ref.set({"memory": new_memory}, merge=True)

def delete_user_memory(user_id: str) -> bool:
    """Delete user memory for *user_id* from Firestore."""
    try:
        user_doc_ref = _db.collection("user_data").document(user_id)
        # Check if document exists first
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            # Delete just the memory field, keeping other potential data
            user_doc_ref.update({"memory": firestore.DELETE_FIELD})
        return True
    except Exception as e:
        print(f"[Firebase] Error deleting memory for user {user_id}: {e}")
        return False