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
        self._emotions: Dict[str, int] = cfg.INITIAL_EMOTIONAL_STATE.copy()

        self._history: List[Dict[str, Any]] = []    # chron. list of Gemini‑style parts
        self._http     = requests.Session()

    # ------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------ #
    @property
    def history(self) -> List[Dict[str, Any]]:
        return self._history

    def send(self, message: str) -> str:
        """
        Send *message* to Gemini.  Gemini may respond with a function call
        (search_pinecone_memories) or with plain text.  If it calls the
        function, we execute it, feed the result back to Gemini, and return
        the model's final reply.
        """
        # ---- build user + memory‑aware system prompt ------------------ #
        system_instr = self._system_instruction()
        self._append("user", message)                            # tentatively add

        # ---- Update emotions based on new user message ---------------- #
        try:
            self._emotions = limbic.update_emotions_state(
                current_emotions=self._emotions,
                full_chat_text_func=self._full_chat_text,
                post_raw_func=self._post_raw
            )
        except Exception as e:
            print(f"[Chat] Emotion update failed: {e}") # Log and continue

        # ---- 1st request: give Gemini the option to call RAG ----------- #
        payload = {
            "system_instruction": system_instr,
            "contents":           self._history,
            "generationConfig":   cfg.DEFAULT_GEN_CFG,
            "tools":              [{"functionDeclarations": [tools.PINECONE_RAG_DECL, tools.WEB_SEARCH_DECL]}], # Updated to use tools
            # leave function_calling_config default = AUTO
        }
        response = self._post_raw(cfg.GEMINI_URL, payload)
        first_part = response["candidates"][0]["content"]["parts"][0]

        # ---- Did Gemini ask to call our function? ---------------------- #
        if "functionCall" in first_part:
            fn_call = first_part["functionCall"]
            fn_name = fn_call["name"]
            
            # Execute the appropriate tool based on function name
            if fn_name == "search_pinecone_memories":
                tool_result = tools.search_pinecone_memories( # Updated to use tools
                    **fn_call.get("args", {}), user_id=self.user_id
                )
            elif fn_name == "search_web":
                tool_result = tools.search_web(**fn_call.get("args", {})) # Updated to use tools
            else:
                tool_result = {"error": f"Unknown function: {fn_name}"}

            # Gemini expects a *function response* message next
            self._history.append({
                "role": "model",
                "parts": [{"functionCall": fn_call}],
            })

            # Determine the role for the function response part
            function_response_role = "user"  # Default role
            if fn_name == "search_pinecone_memories":
                function_response_role = "memory_tool"
            elif fn_name == "search_web":
                function_response_role = "internet_tool"
            # For unknown functions, tool_result is an error, and role remains "user"

            self._history.append({
                "role": function_response_role,
                "parts": [{
                    "functionResponse": {
                        "name": fn_call["name"],
                        "response": tool_result       # keep it JSON
                    }
                }],
            })

            # ---- 2nd request: get the *final* answer ------------------ #
            payload = {
                "system_instruction": system_instr,
                "contents":           self._history,
                "generationConfig":   cfg.DEFAULT_GEN_CFG,
                # keep tools so model can chain if it really wants
                "tools":              [{"functionDeclarations": [tools.PINECONE_RAG_DECL, tools.WEB_SEARCH_DECL]}], # Updated to use tools
            }
            response = self._post_raw(cfg.GEMINI_URL, payload)
            reply_text = response["candidates"][0]["content"]["parts"][0]["text"]

            # store final reply
            self._append("model", reply_text)
            return reply_text

        # ---- No function call – simple path ---------------------------- #
        reply_text = first_part["text"]
        self._append("model", reply_text)
        return reply_text

    # ------------------------------------------------------------ #
    # Memory summarisation (unchanged)
    # ------------------------------------------------------------ #
    def summarize(self) -> bool:
        if not self.user_id:
            print("[Chat] Cannot summarize memory without user_id.")
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
        emotional_state_str = "\n".join(
            [f"{emotion}: {value}" for emotion, value in self._emotions.items()]
        )
        return {"parts": [{"text": prompts.SYSTEM_TEMPLATE.format(
            user_memory=user_mem,
            emotional_state=emotional_state_str
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
                role_tag = "User" if role == "user" else "Puck"
                lines.append(f"{role_tag}: {part['text']}")
            elif "functionCall" in part:  # This will have role: "model"
                fc = part["functionCall"]
                tool_name = fc.get('name', 'unknown_tool')
                query = fc.get('args', {}).get('query', 'N/A')
                lines.append(f"Puck (system): Initiating tool call to '{tool_name}' with query: '{query}'.")
            elif "functionResponse" in part:  # Role could be "user", "memory_tool", or "internet_tool"
                if exclude_tool_outputs and role in ["memory_tool", "internet_tool"]:
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
                elif tool_name_from_response == 'search_pinecone_memories':
                    pinecone_list = response_data.get('results')
                    if isinstance(pinecone_list, list):
                        meaningful_results = [r for r in pinecone_list if isinstance(r, str) and r.strip()]
                        if meaningful_results:
                            content_summary = "; ".join(meaningful_results)
                        else:
                            content_summary = f"Memory search by '{tool_name_from_response}' found no relevant snippets or returned empty."
                    else:
                        content_summary = f"Memory search by '{tool_name_from_response}' returned unexpected data format instead of a list."
                
                # Truncate if too long
                if len(content_summary) > 250:
                    content_summary = content_summary[:247] + "..."
                
                prefix = f"Tool ({tool_name_from_response} output)" # Default fallback
                if role == "memory_tool":
                    prefix = f"Memory Tool ({tool_name_from_response} output)"
                elif role == "internet_tool":
                    prefix = f"Internet Tool ({tool_name_from_response} output)"
                elif role == "user": 
                    prefix = f"System (tool output from {tool_name_from_response})"
                
                lines.append(f"{prefix}: {content_summary}")
        return "\n".join(lines)
