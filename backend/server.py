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
        
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400
        
        # Create or get existing chat session
        if not session_id or session_id not in chat_sessions:
            session_id = str(uuid.uuid4())
            chat_sessions[session_id] = {
                'history': [],
                'user_id': user_id
            }
        
        # Get the chat history for this session
        chat.api_chat_history = chat_sessions[session_id]['history']
        
        # Get response from the chat module, passing user_id
        response = chat.get_response(user_message, user_id)
        
        # Update the session's chat history
        chat_sessions[session_id]['history'] = chat.api_chat_history
        
        # Log the chat message for debugging
        print(f"Chat session {session_id}: User: '{user_message}' -> Bot: '{response[:50]}...'")
        
        return jsonify({
            "response": response,
            "sessionId": session_id
        })
    
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/end-chat', methods=['POST'])
def end_chat_endpoint():
    try:
        data = request.json
        session_id = data.get('sessionId')
        user_id = data.get('userId')  # Get user ID from request
        
        print(f"Ending chat session {session_id} for user {user_id}")
        
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400
        
        # Check if session exists
        if not session_id or session_id not in chat_sessions:
            print(f"Session {session_id} not found or already ended")
            return jsonify({"success": False, "message": "Session not found"}), 200
        
        # Get chat history from the session
        chat.api_chat_history = chat_sessions[session_id]['history']
        
        # Only summarize if there are actual messages
        if len(chat.api_chat_history) > 0:
            # Summarize the chat and update user memory
            print(f"Summarizing chat for user {user_id} with {len(chat.api_chat_history)} messages")
            success = chat.summarize_chat(user_id)
            
            # Clear the session
            del chat_sessions[session_id]
            
            return jsonify({
                "success": success,
                "message": "Chat ended and memory updated"
            })
        else:
            print(f"No messages to summarize for user {user_id}")
            # Clear the session
            del chat_sessions[session_id]
            return jsonify({
                "success": True,
                "message": "Chat ended (no messages to summarize)"
            })
    
    except Exception as e:
        print(f"Error in end_chat endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 