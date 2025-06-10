from __future__ import annotations
from typing import Any, Dict, Callable
import requests
import config as cfg
import prompts as prompts
import time
import math
import random

# Emotion related constants are in cfg (INITIAL_EMOTIONAL_STATE, EMOTION_KEYS, LIMBIC_MODEL_NAME, LIMBIC_GEMINI_URL)

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
    """Applies drift values to current emotional state within [-100, 100] range.
    No normalization needed since emotions are independent bipolar scales.
    """
    new_emotions = {}
    for key in cfg.EMOTION_KEYS:
        new_value = current_emotions[key] + drift_values.get(key, 0)
        # Clamp values to [-100, 100] range
        new_emotions[key] = max(-100, min(100, new_value))
    
    return new_emotions

def parse_emotions(response_text: str) -> Dict[str, int] | None:
    """Parses the emotion string from the LLM into a dictionary.
    Expects a comma-separated string of 4 integers in range [-100, 100].
    """
    try:
        parts = response_text.strip().split(',')
        if len(parts) != len(cfg.EMOTION_KEYS):
            return None

        int_values = [int(p.strip()) for p in parts]
        
        # Validate range
        for value in int_values:
            if value < -100 or value > 100:
                return None

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
    exclude_tool_outputs_for_emotions: bool = True
) -> Dict[str, int]:
    """Calls the limbic system LLM to get drift values and updates the current emotional state.
    Returns the new emotional state if successful, otherwise the original state.
    """
    conversation_state = full_chat_text_func(exclude_tool_outputs=exclude_tool_outputs_for_emotions)
    
    current_emotional_state_str = ",".join([str(current_emotions[key]) for key in cfg.EMOTION_KEYS])

    prompt = prompts.LIMBIC_SYSTEM_PROMPT_TEMPLATE.format(
        conversation_state=conversation_state,
        current_emotional_state=current_emotional_state_str,
        emotion_keys_list=", ".join(cfg.EMOTION_KEYS)
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

def apply_homeostasis_drift(current_emotions: Dict[str, int], last_update_time: float) -> Dict[str, int]:
    """Applies stochastic homeostasis drift toward neutral (0) for all bipolar emotions using Ornstein-Uhlenbeck process.
    
    E(t+1) = E(t) + θ*(μ - E(t)) + σ*N(0,1)
    
    Where:
    - E(t) = current emotional value
    - μ = baseline value (0 for all emotions)
    - θ = drift rate (pull toward baseline)
    - σ = noise scale (volatility)
    - N(0,1) = standard normal random value
    """
    current_time = time.time()
    elapsed_seconds = current_time - last_update_time
    
    # Calculate how many update intervals have passed
    update_intervals = elapsed_seconds / cfg.HOMEOSTASIS_INTERVAL
    
    # If less than one interval has passed, no update occurs
    if update_intervals < 1.0:
        return current_emotions.copy()
    
    # Apply stochastic updates for each completed interval
    new_emotions = current_emotions.copy()
    
    # Convert to float for calculations
    float_emotions = {key: float(value) for key, value in new_emotions.items()}
    
    # Apply stochastic process for each time step
    num_steps = int(update_intervals)
    for step in range(num_steps):
        temp_emotions = {}
        step_changes = {}
        
        for key in cfg.EMOTION_KEYS:
            current_value = float_emotions[key]
            baseline_value = float(cfg.BASE_EMOTIONAL_STATE[key])  # Should be 0 for all
            
            # Ornstein-Uhlenbeck process: E(t+1) = E(t) + θ*(μ - E(t)) + σ*N(0,1)
            drift_term = cfg.HOMEOSTASIS_DRIFT_RATE * (baseline_value - current_value)
            noise_term = cfg.HOMEOSTASIS_NOISE_SCALE * random.gauss(0, 1)
            
            new_value = current_value + drift_term + noise_term
            
            # Clamp to [-100, 100] range
            temp_emotions[key] = max(-100.0, min(100.0, new_value))
            
            # Track the change for logging
            step_changes[key] = {
                'drift': drift_term,
                'noise': noise_term,
                'change': temp_emotions[key] - current_value
            }
        
        float_emotions = temp_emotions
        
        # Log the stochastic step (only for the first step to avoid spam)
        if step == 0 and num_steps > 0:
            for key in cfg.EMOTION_KEYS:
                change_info = step_changes[key]
    
    # Convert back to integers
    int_emotions = {}
    for key in cfg.EMOTION_KEYS:
        int_emotions[key] = round(float_emotions[key])
        # Ensure final values are within bounds
        int_emotions[key] = max(-100, min(100, int_emotions[key]))
    
    return int_emotions 