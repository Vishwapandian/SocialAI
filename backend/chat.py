from __future__ import annotations
import os
from typing import Any, Dict, List
import requests
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
import firebase_config

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
load_dotenv()

# ––– Gemini ---------------------------------------------------------------- #
_API_KEY: str = os.getenv("GEMINI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("GEMINI_API_KEY not set"))
_MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
_GEMINI_URL: str = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL_NAME}:generateContent?key={_API_KEY}"
)

# ––– Limbic System (Emotion Model) ----------------------------------------- #
_LIMBIC_MODEL_NAME: str = "gemini-2.0-flash-lite"
_LIMBIC_GEMINI_URL: str = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{_LIMBIC_MODEL_NAME}:generateContent?key={_API_KEY}"
)
_INITIAL_EMOTIONAL_STATE: Dict[str, int] = {
    "Happiness": 50,
    "Sadness":   10,
    "Fear":      10,
    "Anger":     5,
    "Disgust":   5,
    "Surprise":  20,
}
_EMOTION_KEYS: List[str] = ["Happiness", "Sadness", "Fear", "Anger", "Disgust", "Surprise"]

_LIMBIC_SYSTEM_PROMPT_TEMPLATE: str = """
You are a Human Limbic System. Based on the following conversation, update your current emotional state.
The emotional state consists of Happiness, Sadness, Fear, Anger, Disgust, and Surprise.
These are percentages and their values **must sum to 100**.

Conversation:
{conversation_state}

Current Emotional state (as comma-separated integers for: {emotion_keys_list}):
{current_emotional_state}

Output only the updated emotional state *exactly* in this format: a comma-separated list of six integers representing {emotion_keys_list}, ensuring the sum of these integers is 100.
Example: "50,10,10,5,5,20"
"""

_DEFAULT_GEN_CFG: Dict[str, Any] = {
    "stopSequences":      [],
    "temperature":        1.2,
    "maxOutputTokens":    20,
    "topP":               0.9,
    "topK":               40,
}

# ––– Pinecone --------------------------------------------------------------- #
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("OPENAI_API_KEY is not set"))
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("PINECONE_API_KEY is not set"))
PINECONE_ENV: str = os.getenv("PINECONE_ENVIRONMENT") or \
    (_ for _ in ()).throw(RuntimeError("PINECONE_ENVIRONMENT is not set"))
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "users-memory")
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "3"))

_pc           = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
_pinecone_idx = _pc.Index(PINECONE_INDEX)
_embeddings   = OpenAIEmbeddings(model="text-embedding-3-small",
                                 api_key=OPENAI_API_KEY)

# ––– Perplexity Web Search -------------------------------------------------- #
PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY") or \
    (_ for _ in ()).throw(RuntimeError("PERPLEXITY_API_KEY is not set"))
PERPLEXITY_MODEL: str = os.getenv("PERPLEXITY_MODEL", "sonar")
PERPLEXITY_URL: str = "https://api.perplexity.ai/chat/completions"

# --------------------------------------------------------------------------- #
# Gemini function declaration – passed to the model on every request
# --------------------------------------------------------------------------- #
_PINECONE_RAG_DECL = {
    "name":        "search_pinecone_memories",
    "description": (
        "Search memories that *other* users shared with Birdie and return "
        "relevant snippets. Useful when the user asks for gossip, opinions, "
        "or experiences of other people. Always exclude the current user's "
        "own memories (user_id)."
    ),
    "parameters": {
        "type":       "object",
        "properties": {
            "query": {
                "type":        "string",
                "description": "The user's input to search for similar memories."
            },
        },
        "required": ["query"],
    },
}

_WEB_SEARCH_DECL = {
    "name":        "search_web",
    "description": (
        "Search the internet for up-to-date information using Perplexity API. "
        "Useful when the user asks about current events, facts that might have changed, "
        "or information you're uncertain about."
    ),
    "parameters": {
        "type":       "object",
        "properties": {
            "query": {
                "type":        "string",
                "description": "The search query to look up on the web."
            },
        },
        "required": ["query"],
    },
}

# --------------------------------------------------------------------------- #
# Helper that the model can ask us to run
# --------------------------------------------------------------------------- #
def search_pinecone_memories(*, query: str, user_id: str | None = None) -> Dict[str, Any]:
    """Executes a vector search in Pinecone and formats the results for Gemini."""
    vec  = _embeddings.embed_query(query)
    resp = _pinecone_idx.query(
        vector=vec,
        top_k=TOP_K_RESULTS,
        include_metadata=True,
        filter={"id": {"$ne": user_id}} if user_id else None,
    )

    results = [
        m.metadata.get("text", "") for m in resp.matches
        if getattr(m, "metadata", None)
    ]

    return {
        "results": results or
        ["No relevant information from other users was found."]
    }

def search_web(*, query: str) -> Dict[str, Any]:
    """Searches the web using Perplexity API and returns the result."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}"
    }
    
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful web search assistant. Provide factual, up-to-date information with sources when available."
            },
            {
                "role": "user",
                "content": query
            }
        ]
    }
    
    response = requests.post(PERPLEXITY_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    return {
        "result": result["choices"][0]["message"]["content"]
    }

# --------------------------------------------------------------------------- #
_SYSTEM_TEMPLATE = """
You are Birdie, a Social AI.\n
Here's what you know about your conversation partner:\n
{user_memory}\n
Here's your current emotional state:\n
{emotional_state}
"""

# --------------------------------------------------------------------------- #
# Conversation core
# --------------------------------------------------------------------------- #
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
        self._emotions: Dict[str, int] = _INITIAL_EMOTIONAL_STATE.copy()

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
            self._update_emotions()
        except Exception as e:
            print(f"[Chat] Emotion update failed: {e}") # Log and continue

        # ---- 1st request: give Gemini the option to call RAG ----------- #
        payload = {
            "system_instruction": system_instr,
            "contents":           self._history,
            "generationConfig":   _DEFAULT_GEN_CFG,
            "tools":              [{"functionDeclarations": [_PINECONE_RAG_DECL, _WEB_SEARCH_DECL]}],
            # leave function_calling_config default = AUTO
        }
        response = self._post_raw(_GEMINI_URL, payload)
        first_part = response["candidates"][0]["content"]["parts"][0]

        # ---- Did Gemini ask to call our function? ---------------------- #
        if "functionCall" in first_part:
            fn_call = first_part["functionCall"]
            fn_name = fn_call["name"]
            
            # Execute the appropriate tool based on function name
            if fn_name == "search_pinecone_memories":
                tool_result = search_pinecone_memories(
                    **fn_call.get("args", {}), user_id=self.user_id
                )
            elif fn_name == "search_web":
                tool_result = search_web(**fn_call.get("args", {}))
            else:
                tool_result = {"error": f"Unknown function: {fn_name}"}

            # Gemini expects a *function response* message next
            self._history.append({
                "role": "model",
                "parts": [{"functionCall": fn_call}],
            })
            self._history.append({
                "role": "user",
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
                "generationConfig":   _DEFAULT_GEN_CFG,
                # keep tools so model can chain if it really wants
                "tools":              [{"functionDeclarations": [_PINECONE_RAG_DECL, _WEB_SEARCH_DECL]}],
            }
            response = self._post_raw(_GEMINI_URL, payload)
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
    def summarize(self) -> bool:  # … identical to previous version …
        try:
            chat_text = self._full_chat_text()
            updated_user_mem = self._run_summary_prompt(
                current_memory=firebase_config.get_user_memory(self.user_id),
                chat_text=chat_text,
                perspective="person",
            )
            firebase_config.update_user_memory(self.user_id, updated_user_mem)
            return True
        except Exception as exc:               # noqa: BLE001
            print(f"[Chat] memory update failed: {exc}")
            return False

    # ------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------ #
    def _system_instruction(self) -> Dict[str, Any]:
        user_mem = firebase_config.get_user_memory(self.user_id) if self.user_id else ""
        emotional_state_str = "\\n".join(
            [f"{emotion}: {value}" for emotion, value in self._emotions.items()]
        )
        return {"parts": [{"text": _SYSTEM_TEMPLATE.format(
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
    def _full_chat_text(self) -> str:
        lines: List[str] = []
        for item in self._history:
            part = item["parts"][0]
            role = item["role"]

            if "text" in part:
                role_tag = "User" if role == "user" else "Birdie"
                lines.append(f"{role_tag}: {part['text']}")
            elif "functionCall" in part:  # This will have role: "model"
                fc = part["functionCall"]
                tool_name = fc.get('name', 'unknown_tool')
                query = fc.get('args', {}).get('query', 'N/A')
                lines.append(f"Birdie (system): Initiating tool call to '{tool_name}' with query: '{query}'.")
            elif "functionResponse" in part:  # This currently has role: "user"
                fr = part["functionResponse"]
                tool_name = fr.get('name', 'unknown_tool')
                response_data = fr.get('response', {})

                content_summary = f"Output from tool '{tool_name}'."  # Generic fallback

                if tool_name == 'search_web':
                    web_text = response_data.get('result')
                    if isinstance(web_text, str) and web_text.strip():
                        content_summary = web_text
                    else:
                        content_summary = f"Web search by '{tool_name}' yielded no text result or an empty result."
                elif tool_name == 'search_pinecone_memories':
                    pinecone_list = response_data.get('results')
                    if isinstance(pinecone_list, list):
                        meaningful_results = [r for r in pinecone_list if isinstance(r, str) and r.strip()]
                        if meaningful_results:
                            content_summary = "; ".join(meaningful_results)
                        else:
                            content_summary = f"Memory search by '{tool_name}' found no relevant snippets or returned empty."
                    else:
                        content_summary = f"Memory search by '{tool_name}' returned unexpected data format instead of a list."
                
                # Truncate if too long
                if len(content_summary) > 250:
                    content_summary = content_summary[:247] + "..."
                
                # Even though role is "user" for the functionResponse part in history,
                # this isn't a direct user utterance for the summary/emotion context.
                lines.append(f"System (tool output): {content_summary}")
        return "\\n".join(lines)

    # ---- summary helper (unchanged) ---------------------------- #
    def _run_summary_prompt(
        self, *, current_memory: str, chat_text: str, perspective: str
    ) -> str:  # identical to previous implementation
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
            "generationConfig": {
                "temperature":    1.0,
                "maxOutputTokens": 5_000,
                "topP":           0.9,
                "topK":           40,
            },
        }
        resp = self._post_raw(_GEMINI_URL, payload)
        return resp["candidates"][0]["content"]["parts"][0]["text"]

    # ---- Emotion update helpers -------------------------------- #
    def _parse_emotions(self, response_text: str) -> Dict[str, int] | None:
        """Parses the emotion string from the LLM into a dictionary.
        Expects a comma-separated string of 6 integers.
        """
        try:
            parts = response_text.strip().split(',')
            if len(parts) != len(_EMOTION_KEYS):
                print(f"[Chat] Emotion parsing failed: Expected {len(_EMOTION_KEYS)} values, got {len(parts)}. Response: '{response_text}'")
                return None

            int_values = [int(p.strip()) for p in parts]

            parsed_emotions: Dict[str, int] = {}
            for i, key in enumerate(_EMOTION_KEYS):
                parsed_emotions[key] = int_values[i]
            
            return parsed_emotions

        except ValueError as e:
            print(f"[Chat] Emotion parsing failed: Invalid integer value. Error: {e}. Response: '{response_text}'")
            return None
        except Exception as e: # Catch any other unexpected errors during parsing
            print(f"[Chat] Unexpected error during emotion parsing: {e}. Response: '{response_text}'")
            return None

    def _update_emotions(self) -> None:
        """Calls the limbic system LLM to update the current emotional state."""
        conversation_state = self._full_chat_text()
        
        # Format current emotions as a comma-separated string of integers
        current_emotional_state_str = ",".join([str(self._emotions[key]) for key in _EMOTION_KEYS])

        prompt = _LIMBIC_SYSTEM_PROMPT_TEMPLATE.format(
            conversation_state=conversation_state,
            current_emotional_state=current_emotional_state_str,
            emotion_keys_list=", ".join(_EMOTION_KEYS) # For clarity in the prompt
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": _DEFAULT_GEN_CFG, # Using default, can be tuned
        }

        try:
            response_json = self._post_raw(_LIMBIC_GEMINI_URL, payload)
            if response_json and "candidates" in response_json and response_json["candidates"]:
                limbic_response_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
                new_emotions = self._parse_emotions(limbic_response_text)
                if new_emotions:
                    self._emotions = new_emotions
                    print(f"[Chat] Emotions updated: {self._emotions}")
                else:
                    print("[Chat] Failed to parse emotions from limbic system response.")
            else:
                print("[Chat] Invalid or empty response from limbic system.")
        except requests.exceptions.RequestException as e:
            print(f"[Chat] Limbic system API call failed: {e}")
        except Exception as e:
            print(f"[Chat] Error processing limbic system response: {e}")
