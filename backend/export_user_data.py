#!/usr/bin/env python
"""
Export all user session data from Firestore to local JSON files.
Can be run manually or as a scheduled task.
"""
from __future__ import annotations
import json
import os
import datetime
from typing import Dict, List, Any
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables and Firebase config
load_dotenv()
SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH")
EXPORT_DIR = os.path.join(os.path.dirname(__file__), "../data_exports")

def ensure_export_dir(directory: str = EXPORT_DIR) -> None:
    """Create the export directory if it doesn't exist."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created export directory: {directory}")


def initialize_firebase() -> firestore.Client:
    """Initialize Firebase if not already initialized."""
    try:
        # Try to get an existing app
        app = firebase_admin.get_app()
    except ValueError:
        # Initialize app if not already done
        if not SERVICE_ACCOUNT_PATH:
            raise RuntimeError("SERVICE_ACCOUNT_PATH environment variable not set")
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        app = firebase_admin.initialize_app(cred)
    
    return firestore.client(app)


def export_user_sessions(db: firestore.Client, since_days: int = 7) -> List[Dict[str, Any]]:
    """
    Export user sessions from Firestore.
    
    Args:
        db: Firestore client
        since_days: Export sessions from the last N days
        
    Returns:
        List of user session documents
    """
    # Calculate the timestamp for N days ago
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=since_days)
    
    # Query sessions created since the cutoff date
    query = db.collection("user_sessions").where(
        "created_at", ">=", cutoff_date
    ).order_by("created_at", direction=firestore.Query.DESCENDING)
    
    results = query.stream()
    sessions = []
    
    for doc in results:
        session_data = doc.to_dict()
        # Add the document ID to the data
        session_data["id"] = doc.id
        sessions.append(session_data)
    
    return sessions


def save_to_json(data: List[Dict[str, Any]], filename: str | None = None) -> str:
    """Save data to a JSON file and return the filename."""
    ensure_export_dir()
    
    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_sessions_{timestamp}.json"
    
    filepath = os.path.join(EXPORT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    
    return filepath


def main() -> None:
    """Run the export process."""
    try:
        print("Initializing Firebase...")
        db = initialize_firebase()
        
        print("Fetching user sessions from Firestore...")
        days = 30  # Default to last 30 days
        sessions = export_user_sessions(db, since_days=days)
        
        if not sessions:
            print(f"No sessions found in the last {days} days")
            return
        
        print(f"Found {len(sessions)} sessions")
        filepath = save_to_json(sessions)
        print(f"Exported to {filepath}")
        
    except Exception as e:
        print(f"Error exporting data: {e}")


if __name__ == "__main__":
    main() 