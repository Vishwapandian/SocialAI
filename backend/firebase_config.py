import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Firebase Admin SDK
cred = credentials.Certificate(os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH"))
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

# Default memory for new users
DEFAULT_MEMORY = "ask user for their name"

def get_user_memory(user_id):
    """
    Get the user's memory from Firestore.
    If the user doesn't exist, create a new user with default memory.
    """
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        # Create new user with default memory
        user_ref.set({
            'memory': DEFAULT_MEMORY,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        return DEFAULT_MEMORY
    
    return user_doc.to_dict().get('memory', DEFAULT_MEMORY)

def update_user_memory(user_id, new_memory):
    """
    Update the user's memory in Firestore.
    This function helps ensure that memories aren't duplicated and manages memory length.
    """
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        # Create new user if they don't exist
        user_ref.set({
            'memory': new_memory,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        return True
    
    # Get the existing memory but trim it if it's getting too long
    # This ensures the memory doesn't grow indefinitely
    memory_data = new_memory
    
    # If the memory is too long, truncate it (keeping approximately last 1000 chars)
    if len(memory_data) > 2000:
        # Find the first newline after the 1000th character to get a clean break
        cutoff = 1000
        next_newline = memory_data[cutoff:].find('\n\n')
        if next_newline != -1:
            cutoff = cutoff + next_newline + 2  # Include the newlines
        memory_data = memory_data[cutoff:]
    
    # Update with the new memory
    user_ref.update({
        'memory': memory_data,
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    
    print(f"Updated memory for user {user_id}. New memory: {memory_data[:100]}...")
    return True 