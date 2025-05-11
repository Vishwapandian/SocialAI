from __future__ import annotations
from typing import Any, Dict, Callable
import config as cfg
import firebase_config
import prompts as prompts

def run_summary_prompt(
    current_memory: str, 
    chat_text: str, 
    post_raw_func: Callable[..., Dict[str, Any]]
    # perspective is hardcoded to "person" in the original, so not adding as param for now
) -> str:
    prompt = prompts.MEMORY_SUMMARY_PROMPT_TEMPLATE.format( # Use imported prompt
        current_memory=current_memory,
        chat_text=chat_text
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": cfg.MEMORY_SUMMARY_GEN_CFG, # Use config from cfg
    }
    resp = post_raw_func(cfg.MEMORY_GEMINI_URL, payload)
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