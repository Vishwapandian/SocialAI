from typing import Dict, List, Tuple, Any, Optional
import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from pinecone import Pinecone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    raise RuntimeError("PINECONE_API_KEY is not set")

PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT")
if not PINECONE_ENV:
    raise RuntimeError("PINECONE_ENVIRONMENT is not set")

PINECONE_INDEX = os.getenv("PINECONE_INDEX", "users-memory")
TOP_K_RESULTS = 3

# Initialize Pinecone client
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
index = pc.Index(PINECONE_INDEX)

# Initialize LangChain components
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, api_key=OPENAI_API_KEY)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)

# Prompt templates
RAG_DECISION_TEMPLATE = """
You are a router that decides whether a user's query needs to be augmented with RAG (Retrieval Augmented Generation).

User query: {query}
Current user's memory: {user_memory}

Determine if this query would benefit from retrieving memories from other users' conversations.
Consider these factors:
1. Is the query asking for advice, experiences, or opinions that other users might have shared?
2. Is the query about a common topic that multiple users have likely discussed?
3. Would the response benefit from diverse perspectives or experiences?

Return only "YES" if RAG would be helpful, or "NO" if the current user's memory is sufficient.
"""

RESPONSE_GENERATION_TEMPLATE = """
My name is Puck!

I am a Social AI designed solely for the purpose of engaging in human conversation and building genuine connections with users.

This is what I currently know about myself: {central_memory}

This is what I currently know about the user I am chatting with: {user_memory}

Additional context from other users' conversations that might be relevant:
{retrieved_context}

The user's query is: {query}

Respond as Puck would, incorporating insights from the additional context when relevant, but maintaining Puck's personality.
"""

def should_use_rag(query: str, user_memory: str) -> bool:
    """Determine if RAG should be used for this query."""
    prompt = ChatPromptTemplate.from_template(RAG_DECISION_TEMPLATE)
    chain = prompt | llm | StrOutputParser()
    
    response = chain.invoke({"query": query, "user_memory": user_memory})
    return response.strip().upper() == "YES"

def retrieve_similar_memories(query: str, user_id: str) -> List[Dict[str, Any]]:
    """Retrieve similar memories from other users."""
    # Generate embedding for the query
    query_embedding = embeddings.embed_query(query)
    
    # Search Pinecone for similar vectors, excluding the current user
    search_response = index.query(
        vector=query_embedding,
        top_k=TOP_K_RESULTS,
        include_metadata=True,
        filter={"id": {"$ne": user_id}}  # Exclude current user
    )
    
    # Extract the results
    results = []
    for match in search_response.matches:
        if hasattr(match, 'metadata') and match.metadata:
            results.append({
                "text": match.metadata.get("text", ""),
                "score": match.score
            })
    
    return results

def format_retrieved_context(retrieved_memories: List[Dict[str, Any]]) -> str:
    """Format retrieved memories for inclusion in the prompt."""
    if not retrieved_memories:
        return "No relevant information from other users was found."
    
    formatted_context = "Here are some relevant insights from other users:\n\n"
    for i, memory in enumerate(retrieved_memories, 1):
        # Extract only the most relevant parts of the memory
        formatted_context += f"{i}. {memory['text']}\n\n"
    
    return formatted_context

def generate_response(
    query: str, 
    user_id: str, 
    user_memory: str, 
    central_memory: str
) -> str:
    """Generate a response using RAG if necessary."""
    # Decide if RAG is needed
    use_rag = should_use_rag(query, user_memory)
    
    if use_rag:
        # Retrieve similar memories
        retrieved_memories = retrieve_similar_memories(query, user_id)
        retrieved_context = format_retrieved_context(retrieved_memories)
    else:
        retrieved_context = "No additional context needed."
    
    # Generate response with or without RAG
    prompt = ChatPromptTemplate.from_template(RESPONSE_GENERATION_TEMPLATE)
    chain = prompt | llm | StrOutputParser()
    
    response = chain.invoke({
        "query": query,
        "user_memory": user_memory,
        "central_memory": central_memory,
        "retrieved_context": retrieved_context
    })
    
    return response

def process_query(
    query: str, 
    user_id: str, 
    user_memory: str, 
    central_memory: str
) -> Tuple[str, bool]:
    """Process a query and return the response and whether RAG was used."""
    use_rag = should_use_rag(query, user_memory)
    response = generate_response(query, user_id, user_memory, central_memory)
    return response, use_rag