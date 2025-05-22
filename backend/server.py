from __future__ import annotations
import json
import uuid
from typing import Dict
from flask import Flask, jsonify, request
from flask_cors import CORS
from chat import Chat
import user_tracking

# ---------------------------------------------------------------------------
# Flask setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "puck_chat_secret_key"  # noqa: S105 (demo‑only)
CORS(
    app,
    resources={r"/api/*": {"origins": ["https://heypuck.com"]}},
    supports_credentials=True
)

# ---------------------------------------------------------------------------
# In‑memory session store (for demo / single‑instance deployments)
# ---------------------------------------------------------------------------
_chat_sessions: Dict[str, Chat] = {}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/api/chat")
def chat_endpoint():
    data = request.get_json(silent=True) or {}
    user_message: str = data.get("message", "").strip()
    session_id: str | None = data.get("sessionId")
    user_id: str | None = data.get("userId")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Bootstrap session
    if not session_id or session_id not in _chat_sessions:
        session_id = str(uuid.uuid4())
        _chat_sessions[session_id] = Chat(user_id=user_id)
        # Start tracking when a new session begins
        if user_id:
            user_tracking.start_tracking(user_id, session_id)

    chat = _chat_sessions[session_id]
    # Track user message
    if user_id:
        user_tracking.add_message(session_id, "user", user_message)
    
    result = chat.send(user_message)
    reply = result["reply"]
    emotions = result["emotions"]
    
    # Track model reply
    if user_id:
        user_tracking.add_message(session_id, "model", reply)

    return jsonify({"response": reply, "emotions": emotions, "sessionId": session_id})


@app.post("/api/end-chat")
def end_chat_endpoint():
    # Handle fetch/beacon JSON or raw‑body
    payload = request.get_json(silent=True) or json.loads(request.data or "{}")
    session_id: str | None = payload.get("sessionId")
    user_id: str | None = payload.get("userId")
    survey_data: Dict = payload.get("surveyData", {})

    if not session_id or session_id not in _chat_sessions:
        return jsonify({"error": "Invalid session ID"}), 400
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    # Save survey data if provided
    if survey_data:
        user_tracking.record_survey(session_id, survey_data)
    
    chat = _chat_sessions.pop(session_id)
    
    # First summarize the chat to update the user memory
    memory_saved = chat.summarize()

    # Save final emotional state
    emotions_saved = False
    if user_id: # Ensure user_id is present before attempting to save emotions
        from firebase_config import update_user_emotions # Import here to avoid potential circular imports at module level
        try:
            update_user_emotions(user_id, chat._emotions) # Accessing _emotions directly, consider a getter if preferred
            emotions_saved = True
        except Exception as e:
            print(f"[Server] Failed to save emotions for user {user_id}: {e}") # Log error
            # Decide if this failure should affect the overall success response
    
    # Get the updated memory and update it in the tracker
    updated_memory = None
    if memory_saved and user_id:
        from firebase_config import get_user_memory
        updated_memory = get_user_memory(user_id)
        user_tracking.update_memory(session_id, updated_memory)
    
    # Now end tracking and save all data
    tracking_saved = user_tracking.end_tracking(session_id)

    return jsonify({
        "success": memory_saved and tracking_saved and emotions_saved, 
        "message": "Chat ended successfully",
        "tracking_saved": tracking_saved,
        "memory_saved": memory_saved,
        "emotions_saved": emotions_saved, # Add emotion save status to response
        "updated_memory": updated_memory,  # Optional: for debugging
    })


@app.post("/api/survey")
def save_survey():
    data = request.get_json(silent=True) or {}
    session_id: str | None = data.get("sessionId")
    user_id: str | None = data.get("userId")
    survey_data: Dict = data.get("surveyData", {})
    
    if not session_id:
        return jsonify({"error": "Session ID is required"}), 400
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    if not survey_data:
        return jsonify({"error": "Survey data is required"}), 400
        
    # Record survey data
    user_tracking.record_survey(session_id, survey_data)
    
    return jsonify({"success": True, "message": "Survey data saved"})


@app.post("/api/emotions")
def get_emotions_endpoint():
    data = request.get_json(silent=True) or {}
    user_id: str | None = data.get("userId")

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        from firebase_config import get_user_emotions # Import here
        emotions = get_user_emotions(user_id)
        return jsonify({"emotions": emotions, "userId": user_id}), 200
    except Exception as e:
        # Log the exception for server-side debugging
        print(f"[Server] Error fetching emotions for user {user_id}: {e}")
        # Return a generic error message to the client
        return jsonify({"error": "Failed to retrieve emotional state"}), 500


@app.post("/api/reset")
def reset_user_data():
    """Reset user data by deleting emotions from Firebase and memory from Pinecone."""
    data = request.get_json(silent=True) or {}
    user_id: str | None = data.get("userId")

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        from firebase_config import delete_user_emotions, delete_user_memory
        
        # Delete emotions from Firebase
        emotions_deleted = delete_user_emotions(user_id)
        
        # Delete memory from Pinecone
        memory_deleted = delete_user_memory(user_id)
        
        # Check if both operations were successful
        success = emotions_deleted and memory_deleted
        
        return jsonify({
            "success": success,
            "message": "User data reset successfully" if success else "Failed to reset some user data",
            "emotions_deleted": emotions_deleted,
            "memory_deleted": memory_deleted,
            "userId": user_id
        }), 200 if success else 500
        
    except Exception as e:
        # Log the exception for server-side debugging
        print(f"[Server] Error resetting data for user {user_id}: {e}")
        # Return a generic error message to the client
        return jsonify({"error": "Failed to reset user data"}), 500


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True, port=5000)