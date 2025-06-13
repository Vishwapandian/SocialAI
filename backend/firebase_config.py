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
EMPTY. This is my very first time meeting my human. I will introduce myself as Auri the AI Aura, and ask for the human's name!
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
# Public helpers for base emotional state using Firestore
# ---------------------------------------------------------------------------
def get_user_base_emotions(user_id: str) -> dict[str, int]:
    """Return base emotional state for *user_id*, fetching from Firestore, creating default if necessary."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc = user_doc_ref.get()
    if user_doc.exists:
        data = user_doc.to_dict()
        if data and "base_emotions" in data:
            return data["base_emotions"]
    
    # If no base emotions found, use default and save it
    from config import BASE_EMOTIONAL_STATE # Import here to avoid circular dependency
    default_base_emotions = BASE_EMOTIONAL_STATE.copy()
    user_doc_ref.set({"base_emotions": default_base_emotions}, merge=True)
    return default_base_emotions

def update_user_base_emotions(user_id: str, base_emotions: dict[str, int]) -> None:
    """Update base emotions for *user_id* in Firestore."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc_ref.set({"base_emotions": base_emotions}, merge=True)

def delete_user_base_emotions(user_id: str) -> bool:
    """Delete base emotions for *user_id* from Firestore."""
    try:
        user_doc_ref = _db.collection("user_data").document(user_id)
        # Check if document exists first
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            # Delete just the base_emotions field, keeping other potential data
            user_doc_ref.update({"base_emotions": firestore.DELETE_FIELD})
        return True
    except Exception as e:
        print(f"[Firebase] Error deleting base emotions for user {user_id}: {e}")
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

# ---------------------------------------------------------------------------
# Public helpers for user custom instructions using Firebase/Firestore
# ---------------------------------------------------------------------------
_DEFAULT_CUSTOM_INSTRUCTIONS: Final[str] = "N/A"

def get_user_custom_instructions(user_id: str) -> str:
    """Return custom instructions for *user_id*, fetching from Firestore, creating default if necessary."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc = user_doc_ref.get()
    if user_doc.exists:
        data = user_doc.to_dict()
        if data and "custom_instructions" in data:
            return data["custom_instructions"]
    
    # If no custom instructions found, use default and save it
    user_doc_ref.set({"custom_instructions": _DEFAULT_CUSTOM_INSTRUCTIONS}, merge=True)
    return _DEFAULT_CUSTOM_INSTRUCTIONS

def update_user_custom_instructions(user_id: str, new_instructions: str) -> None:
    """Update custom instructions for *user_id* in Firestore."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc_ref.set({"custom_instructions": new_instructions}, merge=True)

def delete_user_custom_instructions(user_id: str) -> bool:
    """Delete custom instructions for *user_id* from Firestore."""
    try:
        user_doc_ref = _db.collection("user_data").document(user_id)
        # Check if document exists first
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            # Delete just the custom_instructions field, keeping other potential data
            user_doc_ref.update({"custom_instructions": firestore.DELETE_FIELD})
        return True
    except Exception as e:
        print(f"[Firebase] Error deleting custom instructions for user {user_id}: {e}")
        return False

# ---------------------------------------------------------------------------
# Public helpers for user sensitivity using Firestore
# ---------------------------------------------------------------------------
def get_user_sensitivity(user_id: str) -> int:
    """Return sensitivity for *user_id*, fetching from Firestore, creating default if necessary."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc = user_doc_ref.get()
    if user_doc.exists:
        data = user_doc.to_dict()
        if data and "sensitivity" in data:
            return data["sensitivity"]
    
    # If no sensitivity found, use default and save it
    from config import DEFAULT_SENSITIVITY # Import here to avoid circular dependency
    user_doc_ref.set({"sensitivity": DEFAULT_SENSITIVITY}, merge=True)
    return DEFAULT_SENSITIVITY

def update_user_sensitivity(user_id: str, sensitivity: int) -> None:
    """Update sensitivity for *user_id* in Firestore."""
    user_doc_ref = _db.collection("user_data").document(user_id)
    user_doc_ref.set({"sensitivity": sensitivity}, merge=True)

def delete_user_sensitivity(user_id: str) -> bool:
    """Delete sensitivity for *user_id* from Firestore."""
    try:
        user_doc_ref = _db.collection("user_data").document(user_id)
        # Check if document exists first
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            # Delete just the sensitivity field, keeping other potential data
            user_doc_ref.update({"sensitivity": firestore.DELETE_FIELD})
        return True
    except Exception as e:
        print(f"[Firebase] Error deleting sensitivity for user {user_id}: {e}")
        return False