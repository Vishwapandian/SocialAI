from __future__ import annotations
from typing import Any, Dict, Callable
import requests
import config as cfg
import prompts as prompts

# Emotion related constants are in cfg (INITIAL_EMOTIONAL_STATE, EMOTION_KEYS, LIMBIC_MODEL_NAME, LIMBIC_GEMINI_URL)

def parse_emotions(response_text: str) -> Dict[str, int] | None:
    """Parses the emotion string from the LLM into a dictionary.
    Expects a comma-separated string of 6 integers.
    """
    try:
        parts = response_text.strip().split(',')
        if len(parts) != len(cfg.EMOTION_KEYS):
            print(f"[Limbic] Emotion parsing failed: Expected {len(cfg.EMOTION_KEYS)} values, got {len(parts)}. Response: '{response_text}'")
            return None

        int_values = [int(p.strip()) for p in parts]

        parsed_emotions: Dict[str, int] = {}
        for i, key in enumerate(cfg.EMOTION_KEYS):
            parsed_emotions[key] = int_values[i]
        
        return parsed_emotions

    except ValueError as e:
        print(f"[Limbic] Emotion parsing failed: Invalid integer value. Error: {e}. Response: '{response_text}'")
        return None
    except Exception as e: # Catch any other unexpected errors during parsing
        print(f"[Limbic] Unexpected error during emotion parsing: {e}. Response: '{response_text}'")
        return None

def update_emotions_state(
    current_emotions: Dict[str, int],
    full_chat_text_func: Callable[..., str], 
    post_raw_func: Callable[..., Dict[str, Any]],
    exclude_tool_outputs_for_emotions: bool = True
) -> Dict[str, int]:
    """Calls the limbic system LLM to update the current emotional state.
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
        "generationConfig": cfg.DEFAULT_GEN_CFG,
    }

    try:
        response_json = post_raw_func(cfg.LIMBIC_GEMINI_URL, payload)
        if response_json and "candidates" in response_json and response_json["candidates"]:
            limbic_response_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
            new_emotions = parse_emotions(limbic_response_text)
            if new_emotions:
                print(f"[Limbic] Emotions updated: {new_emotions}")
                return new_emotions
            else:
                print("[Limbic] Failed to parse emotions from limbic system response.")
        else:
            print("[Limbic] Invalid or empty response from limbic system.")
    except requests.exceptions.RequestException as e:
        print(f"[Limbic] Limbic system API call failed: {e}")
    except Exception as e:
        print(f"[Limbic] Error processing limbic system response: {e}")
    
    return current_emotions # Return original emotions if update failed 