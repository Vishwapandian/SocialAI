from __future__ import annotations
import os
from typing import Any, Dict, List
import requests
from dotenv import load_dotenv
import firebase_config
import config as cfg
import prompts as prompts
import tools as tools
import limbic as limbic
import memory as memory
import time

load_dotenv()

class Chat:
    """
    Manages state + calls Gemini.  RAG is triggered *only* via function calling.
    """

    def __init__(
        self,
        user_id:    str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.user_id    = user_id
        self.session_id = session_id
        if user_id:
            self._emotions = firebase_config.get_user_emotions(user_id)
            self._base_emotions = firebase_config.get_user_base_emotions(user_id)
            self._sensitivity = firebase_config.get_user_sensitivity(user_id)
        else:
            self._emotions = cfg.BASE_EMOTIONAL_STATE.copy()
            self._base_emotions = cfg.BASE_EMOTIONAL_STATE.copy()
            self._sensitivity = cfg.DEFAULT_SENSITIVITY

        # Track when emotions were last updated for homeostasis
        self._last_emotion_update = time.time()
        
        self._history: List[Dict[str, Any]] = []    # chron. list of Gemini‑style parts
        self._http     = requests.Session()

    # ------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------ #
    @property
    def history(self) -> List[Dict[str, Any]]:
        return self._history

    def get_current_emotions(self) -> Dict[str, int]:
        """Get current emotions with homeostasis drift applied."""
        # Apply homeostasis drift based on time elapsed
        current_emotions = limbic.apply_homeostasis_drift(
            self._emotions, 
            self._last_emotion_update, 
            self._base_emotions,
            self._sensitivity
        )
        
        # Update stored emotions and timestamp if drift occurred
        if current_emotions != self._emotions:
            self._emotions = current_emotions
            self._last_emotion_update = time.time()
            
            # Save updated emotions to Firebase if user_id exists
            if self.user_id:
                try:
                    firebase_config.update_user_emotions(self.user_id, self._emotions)
                except Exception as e:
                    print(f"[Chat] Emotion update failed: {e}")
        
        return self._emotions.copy()

    def send(self, message: str) -> Dict[str, Any]:
        """
        Send *message* to Gemini. Gemini must respond with a function call
        to either send a message or use a tool. If it does not, it is
        interpreted as the AI choosing to remain silent.
        """
        # ---- Apply homeostasis drift before processing message ---- #
        self._emotions = self.get_current_emotions()
        
        # ---- build user + memory‑aware system prompt ------------------ #
        system_instr = self._system_instruction()
        self._append("user", message)

        # ---- Update emotions based on new user message ---------------- #
        try:
            self._emotions = limbic.update_emotions_state(
                current_emotions=self._emotions,
                full_chat_text_func=self._full_chat_text,
                post_raw_func=self._post_raw,
                sensitivity=self._sensitivity
            )
            # Update timestamp after LLM emotion update
            self._last_emotion_update = time.time()
        except Exception as e:
            print(f"[Chat] Emotion update failed: {e}") # Log and continue

        # ---- Interaction loop: allow for chained tool calls ----------- #
        available_tools = [
            {"functionDeclarations": [tools.SEND_CHAT_MESSAGE_DECL, tools.WEB_SEARCH_DECL]}
        ]
        
        for _ in range(5): # Max 5 tool calls
            payload = {
                "system_instruction": system_instr,
                "contents":           self._history,
                "generationConfig":   cfg.GEMINI_GEN_CFG,
                "tools":              available_tools,
            }
            response = self._post_raw(cfg.GEMINI_URL, payload)

            if not response.get("candidates"):
                print("[Chat] Gemini response had no candidates. Interpreting as silence.")
                return {"reply": "", "emotions": self._emotions.copy()}
            
            content = response["candidates"][0]["content"]
            all_parts = content.get("parts", [])

            # --- Filter for only parts that are valid function calls ---
            all_tool_calls = [p for p in all_parts if "functionCall" in p]

            if not all_tool_calls:
                # Model returned text or nothing, which we treat as silence.
                return {"reply": "", "emotions": self._emotions.copy()}

            # --- Separate chat messages from other tools ---
            chat_message_parts = [p for p in all_tool_calls if p["functionCall"].get("name") == "send_chat_message"]
            other_tool_parts = [p for p in all_tool_calls if p["functionCall"].get("name") != "send_chat_message"]

            # --- Handle chat messages: format and combine them ---
            if chat_message_parts:
                full_reply = []
                for part in chat_message_parts:
                    fn_call = part["functionCall"]
                    # Log the original model-generated part
                    self._history.append({"role": "model", "parts": [part]})
                    
                    message = fn_call.get("args", {}).get("message", "")
                    full_reply.append(message)

                formatted_reply = self._format_response_for_messaging("\n".join(full_reply))
                self._append("model", formatted_reply)
                return {"reply": formatted_reply, "emotions": self._emotions.copy()}
            
            # --- Handle other tool calls (e.g., web search) ---
            if not other_tool_parts:
                 # No other tools to call, and no chat messages means silence.
                return {"reply": "", "emotions": self._emotions.copy()}

            # For this implementation, we'll process one non-chat tool call per turn.
            part = other_tool_parts[0]
            fn_call = part["functionCall"]
            fn_name = fn_call["name"]
            
            self._history.append({
                "role": "model",
                "parts": [part],
            })
            
            if fn_name == "search_web":
                tool_result = tools.search_web(**fn_call.get("args", {}))
                self._history.append({
                    "role": "internet_tool",
                    "parts": [{
                        "functionResponse": {
                            "name": fn_call["name"],
                            "response": tool_result
                        }
                    }],
                })
                continue # continue loop to get final answer
            else:
                # Handle unknown function calls gracefully
                tool_result = {"error": f"Unknown function call: {fn_name}"}
                self._history.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": fn_name,
                            "response": tool_result,
                        }
                    }],
                })
                continue # allow model to recover

        # If we exit the loop, it's a silent failure.
        return {"reply": "", "emotions": self._emotions.copy()}

    def _format_response_for_messaging(self, response: str) -> str:
        """
        Format the AI response to be more suitable for M:N messaging.
        This can include breaking up long responses, adding natural breaks, etc.
        """
        # Remove excessive whitespace and normalize line breaks
        response = response.strip()
        
        # Replace multiple consecutive newlines with single newlines
        import re
        response = re.sub(r'\n{3,}', '\n\n', response)
        response = re.sub(r'\n{2,}', '\n', response)
        
        # If response is very long (> 200 chars) and has no line breaks, try to add some
        if len(response) > 200 and '\n' not in response:
            # Look for natural break points like sentences ending with punctuation
            sentences = re.split(r'(?<=[.!?])\s+', response)
            if len(sentences) > 1:
                # Group sentences into chunks of reasonable length
                chunks = []
                current_chunk = ""
                for sentence in sentences:
                    if len(current_chunk + sentence) < 150:
                        current_chunk += sentence + " "
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + " "
                if current_chunk:
                    chunks.append(current_chunk.strip())
                response = "\n".join(chunks)
        
        return response

    # ------------------------------------------------------------ #
    # Memory summarisation (unchanged)
    # ------------------------------------------------------------ #
    def summarize(self) -> bool:
        if not self.user_id:
            return False
        return memory.summarize_memory( # Updated to call the function from memory.py
            user_id=self.user_id,
            full_chat_text_func=self._full_chat_text,
            post_raw_func=self._post_raw
        )

    # ------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------ #
    def _system_instruction(self) -> Dict[str, Any]:
        user_mem = firebase_config.get_user_memory(self.user_id) if self.user_id else ""
        custom_instructions = firebase_config.get_user_custom_instructions(self.user_id) if self.user_id else "N/A"
        emotional_state_str = "\n".join(
            [f"{emotion}: {value}" for emotion, value in self._emotions.items()]
        )
        return {"parts": [{"text": prompts.SYSTEM_TEMPLATE.format(
            user_memory=user_mem,
            emotional_state=emotional_state_str,
            custom_instructions=custom_instructions
        )}]}

    def _post_raw(self, url:str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._http.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _append(self, role: str, text: str) -> None:
        self._history.append({"role": role, "parts": [{"text": text}]})

    # ---- transcript helper ------------------------------------- #
    def _full_chat_text(self, exclude_tool_outputs: bool = False) -> str:
        lines: List[str] = []
        for item in self._history:
            part = item["parts"][0]
            role = item["role"]

            if "text" in part:
                role_tag = "User" if role == "user" else "Self"
                lines.append(f"{role_tag}: {part['text']}")
            elif "functionCall" in part:  # This will have role: "model"
                fc = part["functionCall"]
                tool_name = fc.get('name', 'unknown_tool')
                query = fc.get('args', {}).get('query', 'N/A')
                lines.append(f"Self (system): Initiating tool call to '{tool_name}' with query: '{query}'.")
            elif "functionResponse" in part:  # Role could be "user", "memory_tool", or "internet_tool"
                if exclude_tool_outputs and role in ["internet_tool"]:
                    continue # Skip these tool outputs if requested

                fr = part["functionResponse"]
                tool_name_from_response = fr.get('name', 'unknown_tool')
                response_data = fr.get('response', {})

                content_summary = f"Output from tool '{tool_name_from_response}'."  # Generic fallback

                if tool_name_from_response == 'search_web':
                    web_text = response_data.get('result')
                    if isinstance(web_text, str) and web_text.strip():
                        content_summary = web_text
                    else:
                        content_summary = f"Web search by '{tool_name_from_response}' yielded no text result or an empty result."
                
                # Truncate if too long
                if len(content_summary) > 250:
                    content_summary = content_summary[:247] + "..."
                
                prefix = f"Tool ({tool_name_from_response} output)" # Default fallback
                if role == "internet_tool":
                    prefix = f"Internet Tool ({tool_name_from_response} output)"
                elif role == "user": 
                    prefix = f"System (tool output from {tool_name_from_response})"
                
                lines.append(f"{prefix}: {content_summary}")
        return "\n".join(lines)
