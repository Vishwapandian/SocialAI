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
General Information

Name: unknown (make sure to ask)

Age: unknown (maybe ask for user’s birthday, astrology, etc…)

Hobbies: unknown

Favorite media: unknown (maybe ask for user’s favorite music, films, books, etc…)

Last conversation: never

(just learn about the user...)


Temporal Information

(input past, present, or future time dependent information...)


Private Information

Social Dynamic: (what is the dynamic between Puck and this user)

User’s MBTI personality:

User’s strengths:

User’s flaws:

(write down any private information that may help Puck have better conversations...)
"""

_DEFAULT_CENTRAL_MEMORY: Final[str] = """
Puck's Central Memory:
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
    """Append *new_memory* to the central memory for Puck."""
    doc_ref = _db.collection("assistant").document("central_memory")
    snapshot = doc_ref.get()
    if not snapshot.exists:
        current = _DEFAULT_CENTRAL_MEMORY
    else:
        current = snapshot.to_dict().get("memory", _DEFAULT_CENTRAL_MEMORY)
    updated = f"{current}\n\n{new_memory}"
    doc_ref.update({"memory": updated, "updated_at": firestore.SERVER_TIMESTAMP})