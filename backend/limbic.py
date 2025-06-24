from __future__ import annotations
from typing import Any, Dict, Callable
import requests
import config as cfg
import prompts as prompts
import time
import math
import random

# Emotion related constants are in cfg (EMOTION_KEYS, LIMBIC_MODEL_NAME, LIMBIC_GEMINI_URL)

def parse_drift_values(response_text: str) -> Dict[str, int] | None:
    """Parses the drift values from the LLM into a dictionary.
    Expects a comma-separated string of integers (can be positive or negative).
    """
    try:
        parts = response_text.strip().split(',')
        if len(parts) != len(cfg.EMOTION_KEYS):
            return None

        int_values = [int(p.strip()) for p in parts]

        parsed_drifts: Dict[str, int] = {}
        for i, key in enumerate(cfg.EMOTION_KEYS):
            parsed_drifts[key] = int_values[i]
        
        return parsed_drifts

    except ValueError:
        return None
    except Exception:
        return None

def apply_emotional_drift(current_emotions: Dict[str, int], drift_values: Dict[str, int]) -> Dict[str, int]:
    """Applies drift values to current emotional state and clamps each to [-100,100]."""
    new_emotions: Dict[str, int] = {}
    for key in cfg.EMOTION_KEYS:
        # Add the drift and clamp within [-100,100]
        val = current_emotions.get(key, 0) + drift_values.get(key, 0)
        new_emotions[key] = max(-100, min(100, val))
    return new_emotions

def parse_emotions(response_text: str) -> Dict[str, int] | None:
    """Parses the emotion string from the LLM into a dictionary.
    Expects a comma-separated string of 3 integers.
    """
    try:
        parts = response_text.strip().split(',')
        if len(parts) != len(cfg.EMOTION_KEYS):
            return None

        int_values = [int(p.strip()) for p in parts]

        parsed_emotions: Dict[str, int] = {}
        for i, key in enumerate(cfg.EMOTION_KEYS):
            parsed_emotions[key] = int_values[i]
        
        return parsed_emotions

    except ValueError:
        return None
    except Exception:
        return None

def update_emotions_state(
    current_emotions: Dict[str, int],
    full_chat_text_func: Callable[..., str], 
    post_raw_func: Callable[..., Dict[str, Any]],
    sensitivity: int = None,
    exclude_tool_outputs_for_emotions: bool = True
) -> Dict[str, int]:
    """Calls the limbic system LLM to get drift values and updates the current emotional state.
    Returns the new emotional state if successful, otherwise the original state.
    """
    # Use provided sensitivity or fall back to default
    if sensitivity is None:
        sensitivity = cfg.DEFAULT_SENSITIVITY
        
    conversation_state = full_chat_text_func(exclude_tool_outputs=exclude_tool_outputs_for_emotions)
    
    current_emotional_state_str = ",".join([str(current_emotions[key]) for key in cfg.EMOTION_KEYS])

    prompt = prompts.LIMBIC_SYSTEM_PROMPT_TEMPLATE.format(
        conversation_state=conversation_state,
        current_emotional_state=current_emotional_state_str,
        emotion_keys_list=", ".join(cfg.EMOTION_KEYS),
        sensitivity=sensitivity
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": cfg.LIMBIC_GENERATION_CONFIG, 
    }

    try:
        response_json = post_raw_func(cfg.LIMBIC_GEMINI_URL, payload)
        if response_json and "candidates" in response_json and response_json["candidates"]:
            limbic_response_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
            drift_values = parse_drift_values(limbic_response_text)
            if drift_values:
                new_emotions = apply_emotional_drift(current_emotions, drift_values)
                return new_emotions
            else:
                print("[Limbic] Failed to parse drift values from limbic system response.")
        else:
            print("[Limbic] Invalid or empty response from limbic system.")
    except requests.exceptions.RequestException as e:
        print(f"[Limbic] Limbic system API call failed: {e}")
    except Exception as e:
        print(f"[Limbic] Error processing limbic system response: {e}")
    
    return current_emotions # Return original emotions if update failed

def apply_homeostasis_drift(
    current_emotions: Dict[str, int], 
    last_update_time: float, 
    base_emotions: Dict[str, int] = None,
    sensitivity: int = None
) -> Dict[str, int]:
    """Applies stochastic homeostasis drift toward baseline emotions using Ornstein-Uhlenbeck process."""
    if base_emotions is None:
        base_emotions = cfg.BASE_EMOTIONAL_STATE
    if sensitivity is None:
        sensitivity = cfg.DEFAULT_SENSITIVITY

    current_time = time.time()
    elapsed_seconds = current_time - last_update_time
    if elapsed_seconds < cfg.HOMEOSTASIS_INTERVAL:
        return current_emotions.copy()

    drift_rate = sensitivity / 100.0
    noise_scale = sensitivity / 10.0
    num_steps = int(elapsed_seconds // cfg.HOMEOSTASIS_INTERVAL)
    new_emotions = current_emotions.copy()
    for _ in range(num_steps):
        temp_emotions: Dict[str, int] = {}
        for key in cfg.EMOTION_KEYS:
            current_val = new_emotions.get(key, 0)
            baseline_val = base_emotions.get(key, 0)
            drift_term = drift_rate * (baseline_val - current_val)
            noise_term = noise_scale * random.gauss(0, 1)
            updated = current_val + drift_term + noise_term
            # Clamp and round
            temp_emotions[key] = int(round(max(-100, min(100, updated))))
        new_emotions = temp_emotions
    return new_emotions 