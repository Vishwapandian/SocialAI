from __future__ import annotations
import os

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# ––– Gemini ---------------------------------------------------------------- #
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("GEMINI_API_KEY not set"))
GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL: str = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
)

# ––– Memory Model ---------------------------------------------------------- #
MEMORY_MODEL_NAME: str = "gemini-2.0-flash-lite"
MEMORY_GEMINI_URL: str = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MEMORY_MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
)

# ––– Limbic (Emotion) Model ----------------------------------------- #
LIMBIC_MODEL_NAME: str = "gemini-2.0-flash-lite"
LIMBIC_GEMINI_URL: str = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{LIMBIC_MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
)
INITIAL_EMOTIONAL_STATE: Dict[str, int] = {
    "Happiness": 50,
    "Sadness":   10,
    "Fear":      10,
    "Anger":     5,
    "Disgust":   5,
    "Surprise":  20,
}
EMOTION_KEYS: List[str] = ["Happiness", "Sadness", "Fear", "Anger", "Disgust", "Surprise"]

# ––– Default Generation Configuration -------------------------------------- #
DEFAULT_GEN_CFG: Dict[str, Any] = {
    "stopSequences":      [],
    "temperature":        1.2,
    "maxOutputTokens":    250,
    "topP":               0.9,
    "topK":               40,
}

# ––– Limbic System Generation Configuration -------------------------------- #
LIMBIC_GENERATION_CONFIG: Dict[str, Any] = {
    "temperature":    1.0,
    "maxOutputTokens": 20,
    "topP":           0.9,
    "topK":           40,
}

# ––– Memory Summary Generation Configuration ------------------------------- #
MEMORY_SUMMARY_GEN_CFG: Dict[str, Any] = {
    "temperature":    1.0,
    "maxOutputTokens": 5_000,
    "topP":           0.9,
    "topK":           40,
}

# ––– Pinecone --------------------------------------------------------------- #
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("OPENAI_API_KEY is not set"))
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("PINECONE_API_KEY is not set"))
PINECONE_ENV: str = os.getenv("PINECONE_ENVIRONMENT") or \
    (_ for _ in ()).throw(RuntimeError("PINECONE_ENVIRONMENT is not set"))
PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX", "users-memory") # Renamed from PINECONE_INDEX to avoid conflict with pinecone.Index
TOP_K_RESULTS: int = int(os.getenv("TOP_K_RESULTS", "3"))

# ––– Perplexity Web Search -------------------------------------------------- #
PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("PERPLEXITY_API_KEY is not set"))
PERPLEXITY_MODEL_NAME: str = os.getenv("PERPLEXITY_MODEL", "sonar") # Renamed from PERPLEXITY_MODEL
PERPLEXITY_URL: str = "https://api.perplexity.ai/chat/completions"

# For type hinting if needed elsewhere
from typing import Any, Dict, List # Added this import 