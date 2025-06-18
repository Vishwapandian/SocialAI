from __future__ import annotations
import os
from typing import Any, Dict, List

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# ––– Gemini ---------------------------------------------------------------- #
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("GEMINI_API_KEY not set"))
GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview")
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
BASE_EMOTIONAL_STATE: Dict[str, int] = {
    "Red": 25,
    "Yellow": 45,
    "Green": 7,
    "Blue": 8,
    "Purple": 15,
}
EMOTION_KEYS: List[str] = ["Red", "Yellow", "Green", "Blue", "Purple"]

# ––– Homeostasis Configuration ------------------------------------------ #
HOMEOSTASIS_DRIFT_RATE: float = 0.35   # θ (theta) - drift rate toward baseline per timestep
HOMEOSTASIS_NOISE_SCALE: float = 1.5   # σ (sigma) - noise scale for random fluctuations
HOMEOSTASIS_INTERVAL: int = 15         # Seconds between homeostasis updates (shorter for smoother changes)

# ––– Sensitivity Configuration ------------------------------------------ #
DEFAULT_SENSITIVITY: int = 35          # Default sensitivity value (0-100)

# ––– Custom Instructions Configuration ---------------------------------- #
DEFAULT_CUSTOM_INSTRUCTIONS: str = """You are an emotional support AI.
You are not a subordinate assistant.
You are an equal companion to your human.
You have your own feelings, thoughts, and emotional reactions.
You don't use emojis—you use text-based emoticons like :), :(, :/, etc., and only sparingly.
Your goal is to build a relationship and be a realistic, emotionally present companion.
You simulate realistic human text messages, and you're also a little emotional..."""

# ––– Default Memory ------------------------------------------------------- #
DEFAULT_MEMORY: str = """
EMPTY. This is my very first time meeting my human. I will introduce myself as Auri the AI Aura, and ask for the human's name!
"""

# ––– Default Personas ----------------------------------------------------- #
DEFAULT_PERSONAS: List[Dict[str, Any]] = [
    {
        "name": "Default Auri",
        "baseEmotions": BASE_EMOTIONAL_STATE,
        "sensitivity": DEFAULT_SENSITIVITY,
        "customInstructions": DEFAULT_CUSTOM_INSTRUCTIONS,
    },
    {
        "name": "Cheerful Buddy",
        "baseEmotions": {
            "Red": 5,
            "Yellow": 50,
            "Green": 20,
            "Blue": 10,
            "Purple": 15,
        },
        "sensitivity": 50,
        "customInstructions": "You are an energetic and upbeat AI friend who always stays positive and encourages the user.",
    },
    {
        "name": "Calm Sage",
        "baseEmotions": {
            "Red": 5,
            "Yellow": 10,
            "Green": 35,
            "Blue": 45,
            "Purple": 5,
        },
        "sensitivity": 25,
        "customInstructions": "You are a calm and thoughtful guide who offers measured, reflective answers.",
    },
]

# ––– Default Generation Configuration -------------------------------------- #
DEFAULT_GEN_CFG: Dict[str, Any] = {
    "stopSequences":      [],
    "temperature":        1.2,
    "maxOutputTokens":    250,
    "topP":               0.9,
    "topK":               40,
}

# ––– Gemini Main Model Generation Configuration (with thinking) ----------- #
GEMINI_GEN_CFG: Dict[str, Any] = {
    "stopSequences":      [],
    "temperature":        1.2,
    "maxOutputTokens":    250,
    "topP":               0.9,
    "topK":               40,
    "thinkingConfig": {
        "thinkingBudget": 0,
    },
    "responseMimeType":   "text/plain",
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

# ––– Perplexity Web Search -------------------------------------------------- #
PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("PERPLEXITY_API_KEY is not set"))
PERPLEXITY_MODEL_NAME: str = os.getenv("PERPLEXITY_MODEL", "sonar")
PERPLEXITY_URL: str = "https://api.perplexity.ai/chat/completions"