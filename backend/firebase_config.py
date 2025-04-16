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
_DEFAULT_MEMORY: Final[str] = "ask user for their name"

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