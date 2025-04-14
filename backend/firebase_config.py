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
    """
    user_ref = db.collection('users').document(user_id)
    user_ref.update({
        'memory': new_memory,
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    return True 