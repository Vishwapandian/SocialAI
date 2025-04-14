from __future__ import annotations
import json
import uuid
from typing import Dict
from flask import Flask, jsonify, request
from flask_cors import CORS
from chat import GeminiChat

# ---------------------------------------------------------------------------
# Flask setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "neko_chat_secret_key"  # noqa: S105 (demo‑only)
CORS(app, supports_credentials=True)

# ---------------------------------------------------------------------------
# In‑memory session store (for demo / single‑instance deployments)
# ---------------------------------------------------------------------------
_chat_sessions: Dict[str, GeminiChat] = {}

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
        _chat_sessions[session_id] = GeminiChat(user_id=user_id)

    chat = _chat_sessions[session_id]
    reply = chat.send(user_message)

    return jsonify({"response": reply, "sessionId": session_id})


@app.post("/api/end-chat")
def end_chat_endpoint():
    # Handle fetch/beacon JSON or raw‑body
    payload = request.get_json(silent=True) or json.loads(request.data or "{}")
    session_id: str | None = payload.get("sessionId")
    user_id: str | None = payload.get("userId")

    if not session_id or session_id not in _chat_sessions:
        return jsonify({"error": "Invalid session ID"}), 400
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    chat = _chat_sessions.pop(session_id)
    success = chat.summarize()

    return jsonify({"success": success, "message": "Chat ended successfully"})


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=True, port=5000)