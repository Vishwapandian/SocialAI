from __future__ import annotations
import os

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# ––– Gemini ---------------------------------------------------------------- #
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("GEMINI_API_KEY not set"))
GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
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
    "Red": 25,
    "Yellow":   45,
    "Green":      10,
    "Blue":     10,
    "Purple":   10,
}
BASE_EMOTIONAL_STATE: Dict[str, int] = {
    "Red": 5,
    "Yellow": 20,
    "Green": 30,
    "Blue": 40,
    "Purple": 5,
}
EMOTION_KEYS: List[str] = ["Red", "Yellow", "Green", "Blue", "Purple"]

# ––– Homeostasis Configuration ------------------------------------------ #
HOMEOSTASIS_DRIFT_RATE: float = 0.35   # θ (theta) - drift rate toward baseline per timestep
HOMEOSTASIS_NOISE_SCALE: float = 1.5   # σ (sigma) - noise scale for random fluctuations
HOMEOSTASIS_INTERVAL: int = 15         # Seconds between homeostasis updates (shorter for smoother changes)

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
PERPLEXITY_MODEL_NAME: str = os.getenv("PERPLEXITY_MODEL", "sonar") # Renamed from PERPLEXITY_MODEL
PERPLEXITY_URL: str = "https://api.perplexity.ai/chat/completions"

# For type hinting if needed elsewhere
from typing import Any, Dict, List # Added this import 