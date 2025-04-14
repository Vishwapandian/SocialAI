import requests
import os
from dotenv import load_dotenv
import firebase_config

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Set model name here for flexibility
MODEL_NAME = "gemini-2.0-flash-lite"

# API endpoint using the model name
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

# Initial system instruction template
SYSTEM_INSTRUCTION_TEMPLATE = {
    "parts": [
        {"text": ""}
    ]
}

# Generation configuration (tweak these as needed)
generation_config = {
    "stopSequences": [],
    "temperature": 1.0,
    "maxOutputTokens": 100,
    "topP": 0.95,
    "topK": 10
}

# Chat history for the API function
api_chat_history = []

def get_response(user_message, user_id=None):
    """Get a response from the Gemini API for a single message."""
    global api_chat_history
    
    # Get user memory if user_id is provided
    user_memory = ""
    if user_id:
        user_memory = firebase_config.get_user_memory(user_id)
        print(f"Retrieved memory for user {user_id}: {user_memory[:100]}...")
    
    # Create system instruction with user memory
    system_instruction = SYSTEM_INSTRUCTION_TEMPLATE.copy()
    system_instruction_text = "You are a cat. Your name is Neko. You respond like a cute but sarcastic cat."
    
    # Add user memory to the system instruction if it exists and isn't the default
    if user_memory and user_memory != firebase_config.DEFAULT_MEMORY:
        system_instruction_text += f" Here is what you know about the user: {user_memory}"
    elif user_memory == firebase_config.DEFAULT_MEMORY:
        system_instruction_text += " You don't know the user yet. Try to ask for their name and learn about them."
    
    system_instruction["parts"][0]["text"] = system_instruction_text
    
    # Append user message to chat history
    api_chat_history.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    # Build the payload with generation config
    payload = {
        "system_instruction": system_instruction,
        "contents": api_chat_history,
        "generationConfig": generation_config
    }

    response = requests.post(URL, json=payload)

    if response.status_code == 200:
        try:
            res_json = response.json()
            ai_response = res_json["candidates"][0]["content"]["parts"][0]["text"]
            
            # Append model reply to chat history
            api_chat_history.append({
                "role": "model",
                "parts": [{"text": ai_response}]
            })
            
            return ai_response

        except Exception as e:
            print(f"Error parsing response: {str(e)}")
            return f"Error parsing response: {str(e)}"
    else:
        print(f"Request failed with status code: {response.status_code}")
        return f"Request failed with status code: {response.status_code}"

def summarize_chat(user_id):
    """Summarize the chat history and update user memory."""
    global api_chat_history
    if not api_chat_history or not user_id or len(api_chat_history) < 2:
        print("Not enough messages to summarize or missing user ID")
        return False
    
    # Create a prompt for summarization
    summary_prompt = """Please extract and summarize important information from this conversation that should be remembered for future interactions with this user. Format the summary concisely, as if creating notes about the user for future reference."""
    
    # Format the chat history for summarization
    chat_text = ""
    for message in api_chat_history:
        role = "User" if message["role"] == "user" else "ai"
        text = message["parts"][0]["text"]
        chat_text += f"{role}: {text}\n"
    
    # Get the current memory
    current_memory = firebase_config.get_user_memory(user_id)
    
    # Create the payload for summarization
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{summary_prompt}\n\n{chat_text}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 200,
            "topP": 0.8,
            "topK": 40
        }
    }
    
    # Get summary from Gemini
    response = requests.post(URL, json=payload)
    
    if response.status_code == 200:
        try:
            res_json = response.json()
            summary = res_json["candidates"][0]["content"]["parts"][0]["text"]
            
            print(f"Generated memory summary: {summary[:100]}...")
            
            # Check if this is the first real conversation (if memory is still the default)
            if current_memory == firebase_config.DEFAULT_MEMORY:
                new_memory = summary
            else:
                # Look for duplicate information before combining
                new_memory = f"{current_memory}\n\n{summary}"
            
            # Update user memory in Firestore
            firebase_config.update_user_memory(user_id, new_memory)
            
            # Clear api_chat_history after summarizing to keep it clean for next session
            api_chat_history = []
            
            return True
        except Exception as e:
            print(f"Error summarizing chat: {str(e)}")
            return False
    else:
        print(f"Failed to get summary: {response.status_code}")
        return False

# Start the chat loop (only run this in CLI mode)
if __name__ == "__main__":
    chat_history = []
    print("🐾 Neko the Cat is here! Type 'exit' to leave the chat.")
    
    # For CLI testing, use a default user ID
    test_user_id = "test_user"
    
    # Get user memory
    user_memory = firebase_config.get_user_memory(test_user_id)
    
    # Create system instruction with user memory
    system_instruction = SYSTEM_INSTRUCTION_TEMPLATE.copy()
    system_instruction["parts"][0]["text"] = system_instruction["parts"][0]["text"].format(user_memory=user_memory)
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            # Summarize chat before exiting
            summarize_chat(test_user_id)
            break

        # Append user message to chat history
        chat_history.append({
            "role": "user",
            "parts": [{"text": user_input}]
        })

        # Build the payload with generation config
        payload = {
            "system_instruction": system_instruction,
            "contents": chat_history,
            "generationConfig": generation_config
        }

        response = requests.post(URL, json=payload)

        if response.status_code == 200:
            try:
                res_json = response.json()
                ai_response = res_json["candidates"][0]["content"]["parts"][0]["text"]
                print(f"Neko: {ai_response}")

                # Append model reply to chat history
                chat_history.append({
                    "role": "model",
                    "parts": [{"text": ai_response}]
                })

            except Exception as e:
                print("⚠️ Error parsing response:", e)
        else:
            print("❌ Request failed with status code:", response.status_code)
            print(response.text)
