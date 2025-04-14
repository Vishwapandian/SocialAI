from flask import Flask, request, jsonify, session
from flask_cors import CORS
import chat
import uuid

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
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Create or get existing chat session
        if not session_id or session_id not in chat_sessions:
            session_id = str(uuid.uuid4())
            chat_sessions[session_id] = []
        
        # Get the chat history for this session
        chat.api_chat_history = chat_sessions[session_id]
        
        # Get response from the chat module
        response = chat.get_response(user_message)
        
        # Update the session's chat history
        chat_sessions[session_id] = chat.api_chat_history
        
        return jsonify({
            "response": response,
            "sessionId": session_id
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 