from __future__ import annotations
import json
import uuid
from typing import Dict
from flask import Flask, jsonify, request
from flask_cors import CORS
from chat import Chat
import user_tracking
import time
from datetime import datetime  # Added for timestamping personas

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
    session_id: str | None = data.get("sessionId")

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        # If we have an active session, get emotions with homeostasis applied
        if session_id and session_id in _chat_sessions:
            chat = _chat_sessions[session_id]
            emotions = chat.get_current_emotions()
        else:
            # No active session, get from Firebase and apply homeostasis based on last update
            from firebase_config import get_user_emotions
            emotions = get_user_emotions(user_id)
            
            # For standalone emotion requests, we don't have access to last update time
            # so we just return the stored emotions
        
        return jsonify({"emotions": emotions, "userId": user_id}), 200
    except Exception as e:
        # Log the exception for server-side debugging
        print(f"[Server] Error fetching emotions for user {user_id}: {e}")
        # Return a generic error message to the client
        return jsonify({"error": "Failed to retrieve emotional state"}), 500


@app.post("/api/reset")
def reset_user_data():
    """Reset user data by deleting emotions and memory from Firebase."""
    data = request.get_json(silent=True) or {}
    user_id: str | None = data.get("userId")

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        from firebase_config import (
            delete_user_emotions,
            delete_user_memory,
            delete_user_base_emotions,
            delete_user_sensitivity,
            delete_user_custom_instructions,
            delete_all_personas,
        )
        
        # Delete emotions from Firebase
        emotions_deleted = delete_user_emotions(user_id)
        
        # Delete memory from Firebase
        memory_deleted = delete_user_memory(user_id)
        
        # Delete base emotions from Firebase
        base_emotions_deleted = delete_user_base_emotions(user_id)
        
        # Delete sensitivity from Firebase
        sensitivity_deleted = delete_user_sensitivity(user_id)
        
        # Delete custom instructions from Firebase
        custom_instructions_deleted = delete_user_custom_instructions(user_id)
        
        # Delete all personas
        personas_deleted = delete_all_personas(user_id)
        
        # Check if all operations were successful
        success = (
            emotions_deleted and memory_deleted and base_emotions_deleted and sensitivity_deleted and custom_instructions_deleted and personas_deleted
        )
        
        return jsonify({
            "success": success,
            "message": "User data reset successfully" if success else "Failed to reset some user data",
            "emotions_deleted": emotions_deleted,
            "memory_deleted": memory_deleted,
            "base_emotions_deleted": base_emotions_deleted,
            "sensitivity_deleted": sensitivity_deleted,
            "custom_instructions_deleted": custom_instructions_deleted,
            "personas_deleted": personas_deleted,
            "userId": user_id
        }), 200 if success else 500
        
    except Exception as e:
        # Log the exception for server-side debugging
        print(f"[Server] Error resetting data for user {user_id}: {e}")
        # Return a generic error message to the client
        return jsonify({"error": "Failed to reset user data"}), 500


# ---------------------------------------------------------------------------
# Configuration API endpoints
# 
# These endpoints allow users to manually configure their AI's:
# - Memory: GET/PUT /api/config/memory?userId=<user_id>
# - Current Emotions: GET/PUT /api/config/emotions?userId=<user_id>  
# - Base Emotions (homeostasis target): GET/PUT /api/config/base-emotions?userId=<user_id>
# - Sensitivity (0-100): GET/PUT /api/config/sensitivity?userId=<user_id>
# - All Config: GET /api/config/all?userId=<user_id>
#
# All PUT requests require the userId in the request body as well.
# Emotions must be dictionaries with keys: Red, Yellow, Green, Blue, Purple
# and values that are integers summing to 100.
# Sensitivity must be an integer between 0 and 100 (affects emotion drift rates).
# ---------------------------------------------------------------------------
@app.route("/api/config/memory", methods=["GET", "PUT"])
def manage_memory():
    """Get or update user memory."""
    user_id: str | None = request.args.get("userId") if request.method == "GET" else request.get_json(silent=True, force=True).get("userId")
    
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    
    try:
        from firebase_config import get_user_memory, update_user_memory
        
        if request.method == "GET":
            memory = get_user_memory(user_id)
            return jsonify({"memory": memory, "userId": user_id}), 200
            
        elif request.method == "PUT":
            data = request.get_json(silent=True) or {}
            new_memory = data.get("memory")
            
            if new_memory is None:
                return jsonify({"error": "Memory content is required"}), 400
            
            update_user_memory(user_id, new_memory)
            return jsonify({"success": True, "message": "Memory updated successfully", "userId": user_id}), 200
            
    except Exception as e:
        print(f"[Server] Error managing memory for user {user_id}: {e}")
        return jsonify({"error": "Failed to manage memory"}), 500


@app.route("/api/config/emotions", methods=["GET", "PUT"])
def manage_current_emotions():
    """Get or update user's current emotional state."""
    user_id: str | None = request.args.get("userId") if request.method == "GET" else request.get_json(silent=True, force=True).get("userId")
    
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    
    try:
        from firebase_config import get_user_emotions, update_user_emotions
        
        if request.method == "GET":
            emotions = get_user_emotions(user_id)
            return jsonify({"emotions": emotions, "userId": user_id}), 200
            
        elif request.method == "PUT":
            data = request.get_json(silent=True) or {}
            new_emotions = data.get("emotions")
            
            if not new_emotions or not isinstance(new_emotions, dict):
                return jsonify({"error": "Valid emotions dictionary is required"}), 400
            
            # Validate emotion structure
            from config import EMOTION_KEYS
            if not all(key in new_emotions for key in EMOTION_KEYS):
                return jsonify({"error": f"All emotion keys required: {EMOTION_KEYS}"}), 400
            
            if not all(isinstance(new_emotions[key], int) for key in EMOTION_KEYS):
                return jsonify({"error": "All emotion values must be integers"}), 400
            
            # Validate that emotions sum to 100
            total = sum(new_emotions.values())
            if total != 100:
                return jsonify({"error": "Emotions must sum to 100"}), 400
            
            update_user_emotions(user_id, new_emotions)
            
            # Update active session if it exists
            for session_id, chat in _chat_sessions.items():
                if chat.user_id == user_id:
                    chat._emotions = new_emotions.copy()
                    chat._last_emotion_update = time.time()
                    break
            
            return jsonify({"success": True, "message": "Current emotions updated successfully", "userId": user_id}), 200
            
    except Exception as e:
        print(f"[Server] Error managing current emotions for user {user_id}: {e}")
        return jsonify({"error": "Failed to manage current emotions"}), 500


@app.route("/api/config/base-emotions", methods=["GET", "PUT"])
def manage_base_emotions():
    """Get or update user's base emotional state."""
    user_id: str | None = request.args.get("userId") if request.method == "GET" else request.get_json(silent=True, force=True).get("userId")
    
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    
    try:
        from firebase_config import get_user_base_emotions, update_user_base_emotions
        
        if request.method == "GET":
            base_emotions = get_user_base_emotions(user_id)
            return jsonify({"baseEmotions": base_emotions, "userId": user_id}), 200
            
        elif request.method == "PUT":
            data = request.get_json(silent=True) or {}
            new_base_emotions = data.get("baseEmotions")
            
            if not new_base_emotions or not isinstance(new_base_emotions, dict):
                return jsonify({"error": "Valid base emotions dictionary is required"}), 400
            
            # Validate emotion structure
            from config import EMOTION_KEYS
            if not all(key in new_base_emotions for key in EMOTION_KEYS):
                return jsonify({"error": f"All emotion keys required: {EMOTION_KEYS}"}), 400
            
            if not all(isinstance(new_base_emotions[key], int) for key in EMOTION_KEYS):
                return jsonify({"error": "All emotion values must be integers"}), 400
            
            # Validate that emotions sum to 100
            total = sum(new_base_emotions.values())
            if total != 100:
                return jsonify({"error": "Base emotions must sum to 100"}), 400
            
            update_user_base_emotions(user_id, new_base_emotions)
            
            # Update active session if it exists
            for session_id, chat in _chat_sessions.items():
                if chat.user_id == user_id:
                    chat._base_emotions = new_base_emotions.copy()
                    break
            
            return jsonify({"success": True, "message": "Base emotions updated successfully", "userId": user_id}), 200
            
    except Exception as e:
        print(f"[Server] Error managing base emotions for user {user_id}: {e}")
        return jsonify({"error": "Failed to manage base emotions"}), 500


@app.route("/api/config/all", methods=["GET"])
def get_all_config():
    """Get all user configuration data at once."""
    user_id: str | None = request.args.get("userId")
    
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    
    try:
        from firebase_config import get_user_memory, get_user_emotions, get_user_base_emotions, get_user_sensitivity, get_user_custom_instructions
        
        memory = get_user_memory(user_id)
        emotions = get_user_emotions(user_id)
        base_emotions = get_user_base_emotions(user_id)
        sensitivity = get_user_sensitivity(user_id)
        custom_instructions = get_user_custom_instructions(user_id)
        
        return jsonify({
            "memory": memory,
            "emotions": emotions,
            "baseEmotions": base_emotions,
            "sensitivity": sensitivity,
            "customInstructions": custom_instructions,
            "userId": user_id
        }), 200
        
    except Exception as e:
        print(f"[Server] Error getting all config for user {user_id}: {e}")
        return jsonify({"error": "Failed to get user configuration"}), 500


@app.route("/api/config/custom-instructions", methods=["GET", "PUT"])
def manage_custom_instructions():
    """Get or update user's custom instructions."""
    user_id: str | None = request.args.get("userId") if request.method == "GET" else request.get_json(silent=True, force=True).get("userId")
    
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    
    try:
        from firebase_config import get_user_custom_instructions, update_user_custom_instructions
        
        if request.method == "GET":
            custom_instructions = get_user_custom_instructions(user_id)
            return jsonify({"customInstructions": custom_instructions, "userId": user_id}), 200
            
        elif request.method == "PUT":
            data = request.get_json(silent=True) or {}
            new_instructions = data.get("customInstructions")
            
            if new_instructions is None:
                return jsonify({"error": "Custom instructions content is required"}), 400
            
            update_user_custom_instructions(user_id, new_instructions)
            return jsonify({"success": True, "message": "Custom instructions updated successfully", "userId": user_id}), 200
            
    except Exception as e:
        print(f"[Server] Error managing custom instructions for user {user_id}: {e}")
        return jsonify({"error": "Failed to manage custom instructions"}), 500


@app.route("/api/config/sensitivity", methods=["GET", "PUT"])
def manage_sensitivity():
    """Get or update user's sensitivity setting."""
    user_id: str | None = request.args.get("userId") if request.method == "GET" else request.get_json(silent=True, force=True).get("userId")
    
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    
    try:
        from firebase_config import get_user_sensitivity, update_user_sensitivity
        
        if request.method == "GET":
            sensitivity = get_user_sensitivity(user_id)
            return jsonify({"sensitivity": sensitivity, "userId": user_id}), 200
            
        elif request.method == "PUT":
            data = request.get_json(silent=True) or {}
            new_sensitivity = data.get("sensitivity")
            
            if new_sensitivity is None:
                return jsonify({"error": "Sensitivity value is required"}), 400
            
            if not isinstance(new_sensitivity, int):
                return jsonify({"error": "Sensitivity must be an integer"}), 400
            
            if not 0 <= new_sensitivity <= 100:
                return jsonify({"error": "Sensitivity must be between 0 and 100"}), 400
            
            update_user_sensitivity(user_id, new_sensitivity)
            
            # Update active session if it exists
            for session_id, chat in _chat_sessions.items():
                if chat.user_id == user_id:
                    chat._sensitivity = new_sensitivity
                    break
            
            return jsonify({"success": True, "message": "Sensitivity updated successfully", "userId": user_id}), 200
            
    except Exception as e:
        print(f"[Server] Error managing sensitivity for user {user_id}: {e}")
        return jsonify({"error": "Failed to manage sensitivity"}), 500


# ---------------------------------------------------------------------------
# Persona CRUD API
# ---------------------------------------------------------------------------

@app.route("/api/personas", methods=["GET", "POST"])
def personas_collection():
    """List or create personas scoped to a user."""
    try:
        from firebase_config import (
            get_all_personas,
            add_persona,
        )
        from config import EMOTION_KEYS

        if request.method == "GET":
            user_id: str | None = request.args.get("userId")
            if not user_id:
                return jsonify({"error": "User ID is required"}), 400
            personas = get_all_personas(user_id)
            return jsonify({"personas": personas, "userId": user_id}), 200

        # POST – create persona
        data = request.get_json(silent=True) or {}
        user_id: str | None = data.get("userId")
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        name: str | None = data.get("name")
        base_emotions: dict | None = data.get("baseEmotions")
        sensitivity: int | None = data.get("sensitivity")
        custom_instructions: str | None = data.get("customInstructions")

        # Basic validation
        if not name:
            return jsonify({"error": "Persona name is required"}), 400
        if not base_emotions or not isinstance(base_emotions, dict):
            return jsonify({"error": "baseEmotions dictionary is required"}), 400
        if not all(key in base_emotions for key in EMOTION_KEYS):
            return jsonify({"error": f"All emotion keys required: {EMOTION_KEYS}"}), 400
        if not all(isinstance(base_emotions[key], int) for key in EMOTION_KEYS):
            return jsonify({"error": "Emotion values must be integers"}), 400
        if sum(base_emotions.values()) != 100:
            return jsonify({"error": "baseEmotions must sum to 100"}), 400
        if sensitivity is None or not isinstance(sensitivity, int) or not 0 <= sensitivity <= 100:
            return jsonify({"error": "sensitivity must be an integer between 0 and 100"}), 400
        if custom_instructions is None:
            custom_instructions = ""

        persona_data = {
            "name": name,
            "baseEmotions": base_emotions,
            "sensitivity": sensitivity,
            "customInstructions": custom_instructions,
            "lastUsed": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",  # Track creation time
        }
        persona_id = add_persona(user_id, persona_data)
        persona_data["id"] = persona_id
        return jsonify({"success": True, "persona": persona_data, "userId": user_id}), 201

    except Exception as e:
        print(f"[Server] Error in personas_collection: {e}")
        return jsonify({"error": "Failed to process personas request"}), 500


@app.route("/api/personas/<persona_id>", methods=["GET", "PUT", "DELETE"])
def personas_document(persona_id: str):
    """Retrieve, update, or delete a persona for a user."""
    try:
        from firebase_config import (
            get_persona,
            update_persona,
            delete_persona,
        )
        from config import EMOTION_KEYS

        # Determine user ID (query for GET/DELETE, body for PUT)
        if request.method in ["GET", "DELETE"]:
            user_id: str | None = request.args.get("userId")
        else:  # PUT can have userId in body or query
            json_payload = request.get_json(silent=True) or {}
            user_id: str | None = json_payload.get("userId") or request.args.get("userId")

        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        if request.method == "GET":
            persona = get_persona(user_id, persona_id)
            if not persona:
                return jsonify({"error": "Persona not found"}), 404
            return jsonify({"persona": persona, "userId": user_id}), 200

        if request.method == "DELETE":
            deleted = delete_persona(user_id, persona_id)
            if not deleted:
                return jsonify({"error": "Failed to delete persona"}), 500
            return jsonify({"success": True, "personaId": persona_id, "userId": user_id}), 200

        # PUT – update persona
        data = request.get_json(silent=True) or {}
        update_payload: dict = {}

        if "name" in data:
            if not data["name"]:
                return jsonify({"error": "name cannot be empty"}), 400
            update_payload["name"] = data["name"]

        if "baseEmotions" in data:
            base_emotions = data["baseEmotions"]
            if not base_emotions or not isinstance(base_emotions, dict):
                return jsonify({"error": "baseEmotions must be a dict"}), 400
            if not all(key in base_emotions for key in EMOTION_KEYS):
                return jsonify({"error": f"All emotion keys required: {EMOTION_KEYS}"}), 400
            if not all(isinstance(base_emotions[key], int) for key in EMOTION_KEYS):
                return jsonify({"error": "Emotion values must be integers"}), 400
            if sum(base_emotions.values()) != 100:
                return jsonify({"error": "baseEmotions must sum to 100"}), 400
            update_payload["baseEmotions"] = base_emotions

        if "sensitivity" in data:
            sensitivity = data["sensitivity"]
            if not isinstance(sensitivity, int) or not 0 <= sensitivity <= 100:
                return jsonify({"error": "sensitivity must be an integer between 0 and 100"}), 400
            update_payload["sensitivity"] = sensitivity

        if "customInstructions" in data:
            update_payload["customInstructions"] = data["customInstructions"]

        if "lastUsed" in data and data["lastUsed"] is not None:
            if not isinstance(data["lastUsed"], str):
                return jsonify({"error": "lastUsed must be an ISO8601 string"}), 400
            update_payload["lastUsed"] = data["lastUsed"]

        if not update_payload:
            return jsonify({"error": "No valid fields to update"}), 400

        success = update_persona(user_id, persona_id, update_payload)
        if not success:
            return jsonify({"error": "Failed to update persona"}), 500

        persona = get_persona(user_id, persona_id)
        return jsonify({"success": True, "persona": persona, "userId": user_id}), 200

    except Exception as e:
        print(f"[Server] Error in personas_document: {e}")
        return jsonify({"error": "Failed to process persona request"}), 500


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True, port=5000)