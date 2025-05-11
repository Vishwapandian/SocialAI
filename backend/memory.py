from __future__ import annotations
from typing import Any, Dict, Callable
import config as cfg
import firebase_config # Assuming firebase_config is accessible like this

def run_summary_prompt(
    current_memory: str, 
    chat_text: str, 
    post_raw_func: Callable[..., Dict[str, Any]]
    # perspective is hardcoded to "person" in the original, so not adding as param for now
) -> str:
    prompt = f"""
You've just finished another conversation with this person. Each interaction reveals more about who they are.

Here is your current understanding of this user:

{current_memory}

Here is the full conversation you just had:

{chat_text}

Reflect on what you've learned about them from this exchange. Did they share new facts, feelings, or preferences? Did they contradict or deepen something you already knew? Are there shifts in mood, identity, goals, or relationships worth noting?

Update your internal model of this person: facts about them, their personality, interests, habits, and life—based on this experience.

Respond with only your **fully updated understanding of this person**, rewritten from scratch to include any new insights or corrections.
    """
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": { # This config is specific and not from DEFAULT_GEN_CFG
            "temperature":    1.0,
            "maxOutputTokens": 5_000,
            "topP":           0.9,
            "topK":           40,
        },
    }
    resp = post_raw_func(cfg.GEMINI_URL, payload)
    return resp["candidates"][0]["content"]["parts"][0]["text"]

def summarize_memory(
    user_id: str, 
    full_chat_text_func: Callable[..., str],
    post_raw_func: Callable[..., Dict[str, Any]],
    exclude_tool_outputs_for_summary: bool = True 
) -> bool:
    try:
        chat_text = full_chat_text_func(exclude_tool_outputs=exclude_tool_outputs_for_summary)
        current_user_memory = firebase_config.get_user_memory(user_id)
        
        updated_user_mem = run_summary_prompt(
            current_memory=current_user_memory,
            chat_text=chat_text,
            post_raw_func=post_raw_func
        )
        firebase_config.update_user_memory(user_id, updated_user_mem)
        print(f"[Memory] Memory updated for user {user_id}")
        return True
    except Exception as exc:               # noqa: BLE001
        print(f"[Memory] Memory update failed for user {user_id}: {exc}")
        return False 