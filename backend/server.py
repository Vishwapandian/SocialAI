from flask import Flask, request, jsonify, session
from flask_cors import CORS
import chat
import uuid
import json

app = Flask(__name__)
app.secret_key = "neko_chat_secret_key"  # Secret key for sessions
CORS(app, supports_credentials=True)  # Enable CORS with credentials

# Store chat sessions
chat_sessions = {}

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    try:
        data = request.json
        user_message = data.get('message', '')
        session_id = data.get('sessionId')
        user_id = data.get('userId')  # Get user ID from request
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Create or get existing chat session
        if not session_id or session_id not in chat_sessions:
            session_id = str(uuid.uuid4())
            chat_sessions[session_id] = []
        
        # Get the chat history for this session
        chat.api_chat_history = chat_sessions[session_id]
        
        # Get response from the chat module, passing user_id if available
        response = chat.get_response(user_message, user_id)
        
        # Update the session's chat history
        chat_sessions[session_id] = chat.api_chat_history
        
        return jsonify({
            "response": response,
            "sessionId": session_id
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/end-chat', methods=['POST'])
def end_chat_endpoint():
    try:
        # Handle both JSON and beacon requests
        if request.is_json:
            data = request.json
        else:
            # For beacon requests, the data is in the request body as a string
            data = json.loads(request.data.decode('utf-8'))
            
        session_id = data.get('sessionId')
        user_id = data.get('userId')  # Get user ID from request
        
        if not session_id or session_id not in chat_sessions:
            return jsonify({"error": "Invalid session ID"}), 400
        
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400
        
        # Summarize the chat and update user memory
        success = chat.summarize_chat(user_id)
        
        # Clear the session
        del chat_sessions[session_id]
        
        return jsonify({
            "success": success,
            "message": "Chat ended successfully"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 