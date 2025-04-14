import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Set model name here for flexibility
MODEL_NAME = "gemini-2.0-flash-lite"

# API endpoint using the model name
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

# Initial system instruction
system_instruction = {
    "parts": [
        {"text": "You are a cat. Your name is Neko. You respond like a cute but sarcastic cat."}
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

def get_response(user_message):
    """Get a response from the Gemini API for a single message."""
    global api_chat_history
    
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
            return f"Error parsing response: {str(e)}"
    else:
        return f"Request failed with status code: {response.status_code}"

# Start the chat loop (only run this in CLI mode)
if __name__ == "__main__":
    chat_history = []
    print("🐾 Neko the Cat is here! Type 'exit' to leave the chat.")
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
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
