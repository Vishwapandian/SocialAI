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
    """Applies drift values to current emotional state and normalizes to sum to 100.
    Ensures no emotion goes below 0.
    """
    # Apply drift values
    new_emotions = {}
    for key in cfg.EMOTION_KEYS:
        new_value = current_emotions[key] + drift_values.get(key, 0)
        # Ensure no emotion goes below 0
        new_emotions[key] = max(0, new_value)
    
    # Normalize to sum to 100
    total = sum(new_emotions.values())
    if total > 0:
        # Scale proportionally to sum to 100
        for key in cfg.EMOTION_KEYS:
            new_emotions[key] = round((new_emotions[key] / total) * 100)
        
        # Handle rounding errors - ensure sum is exactly 100
        current_sum = sum(new_emotions.values())
        if current_sum != 100:
            # Add/subtract the difference to the largest emotion
            largest_emotion = max(cfg.EMOTION_KEYS, key=lambda k: new_emotions[k])
            new_emotions[largest_emotion] += (100 - current_sum)
    else:
        # If all emotions would be 0, reset to initial state
        new_emotions = cfg.INITIAL_EMOTIONAL_STATE.copy()
    
    return new_emotions

def parse_emotions(response_text: str) -> Dict[str, int] | None:
    """Parses the emotion string from the LLM into a dictionary.
    Expects a comma-separated string of 6 integers.
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
    """Applies stochastic homeostasis drift toward baseline emotions using Ornstein-Uhlenbeck process.
    
    E(t+1) = E(t) + θ*(μ - E(t)) + σ*N(0,1)
    
    Where:
    - E(t) = current emotional value
    - μ = baseline value (center it drifts toward) 
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
    # For multiple intervals, we apply the process iteratively
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
            baseline_value = float(cfg.INITIAL_EMOTIONAL_STATE[key])
            
            # Ornstein-Uhlenbeck process: E(t+1) = E(t) + θ*(μ - E(t)) + σ*N(0,1)
            drift_term = cfg.HOMEOSTASIS_DRIFT_RATE * (baseline_value - current_value)
            noise_term = cfg.HOMEOSTASIS_NOISE_SCALE * random.gauss(0, 1)
            
            new_value = current_value + drift_term + noise_term
            
            # Ensure no negative values (emotions can't be negative)
            temp_emotions[key] = max(0.1, new_value)
            
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
        
        # Log the final normalized result
        total = sum(float_emotions.values())
        if total > 0:
            # Scale proportionally to sum to 100
            normalized_emotions = {}
            for key in cfg.EMOTION_KEYS:
                normalized_emotions[key] = (float_emotions[key] / total) * 100
            
            # Convert back to integers and handle rounding
            int_emotions = {}
            for key in cfg.EMOTION_KEYS:
                int_emotions[key] = round(normalized_emotions[key])
            
            # Handle rounding errors - ensure sum is exactly 100
            current_sum = sum(int_emotions.values())
            if current_sum != 100:
                # Add/subtract the difference to the emotion closest to its float value
                differences = {}
                for key in cfg.EMOTION_KEYS:
                    differences[key] = abs(normalized_emotions[key] - int_emotions[key])
                
                # Find the emotion with the smallest rounding error to adjust
                adjustment_key = min(differences.keys(), key=lambda k: differences[k])
                int_emotions[adjustment_key] += (100 - current_sum)
                
                # Ensure the adjustment doesn't make the emotion negative
                if int_emotions[adjustment_key] < 0:
                    int_emotions[adjustment_key] = 0
                    # Redistribute the deficit across other emotions
                    deficit = 100 - sum(int_emotions.values())
                    if deficit > 0:
                        # Add to the largest emotion
                        largest_key = max(cfg.EMOTION_KEYS, key=lambda k: int_emotions[k])
                        int_emotions[largest_key] += deficit
            
            return int_emotions
        else:
            # If all emotions would be 0 (shouldn't happen with minimum), reset to initial state
            return cfg.INITIAL_EMOTIONAL_STATE.copy() 