from __future__ import annotations
import json
import time
from typing import Dict, List, Any
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
import firebase_config

class UserTracker:
    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.start_time = time.time()
        self.messages: List[Dict[str, Any]] = []
        self.survey_data: Dict[str, Any] = {}
        self.user_memory: str = ""
        self.db = firestore.client()
    
    def add_message(self, role: str, content: str) -> None:
        """Record a message in the conversation transcript."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def record_survey(self, survey_data: Dict[str, Any]) -> None:
        """Store user experience survey data."""
        self.survey_data = survey_data
    
    def set_user_memory(self, memory: str) -> None:
        """Store the current user memory string."""
        self.user_memory = memory
    
    def get_session_duration(self) -> float:
        """Calculate session duration in seconds."""
        return time.time() - self.start_time
    
    def save_to_firestore(self) -> bool:
        """Save all collected data to Firestore."""
        try:
            # Get the current user memory if not already set
            if not self.user_memory and self.user_id:
                self.user_memory = firebase_config.get_user_memory(self.user_id)
            
            session_data = {
                "user_id": self.user_id,
                "session_id": self.session_id,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_seconds": self.get_session_duration(),
                "message_count": len(self.messages),
                "messages": self.messages,
                "survey_data": self.survey_data,
                "user_memory": self.user_memory,
                "created_at": firestore.SERVER_TIMESTAMP
            }
            
            # Add as a new document in the sessions collection
            self.db.collection("user_sessions").document().set(session_data)
            return True
        except Exception as e:
            print(f"Error saving user tracking data: {e}")
            return False

# Global tracker dictionary to store active trackers by session_id
active_trackers: Dict[str, UserTracker] = {}

def start_tracking(user_id: str, session_id: str) -> None:
    """Start tracking a new user session."""
    active_trackers[session_id] = UserTracker(user_id, session_id)
    
    # Get initial memory
    if user_id:
        memory = firebase_config.get_user_memory(user_id)
        active_trackers[session_id].set_user_memory(memory)

def add_message(session_id: str, role: str, content: str) -> None:
    """Add a message to the session transcript."""
    if session_id in active_trackers:
        active_trackers[session_id].add_message(role, content)

def record_survey(session_id: str, survey_data: Dict[str, Any]) -> None:
    """Record survey data for a session."""
    if session_id in active_trackers:
        active_trackers[session_id].record_survey(survey_data)

def update_memory(session_id: str, memory: str) -> None:
    """Update the user memory for a session."""
    if session_id in active_trackers:
        active_trackers[session_id].set_user_memory(memory)

def end_tracking(session_id: str) -> bool:
    """End tracking for a session and save data to Firestore."""
    if session_id in active_trackers:
        tracker = active_trackers.pop(session_id)
        return tracker.save_to_firestore()
    return False 