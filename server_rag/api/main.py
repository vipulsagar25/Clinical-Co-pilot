import os
import sys
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from ..app.rag_engine import ClinicalCoPilot


# -------------------------------------------------
# Load Environment Variables
# -------------------------------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY not found in .env file")


# -------------------------------------------------
# FastAPI Initialization
# -------------------------------------------------
app = FastAPI(title="Clinical Co-Pilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# Engine Factory (Creates New Instance)
# -------------------------------------------------
def create_engine():
    return ClinicalCoPilot(
        api_key=GROQ_API_KEY,
        debug=False
    )


# -------------------------------------------------
# Request Models
# -------------------------------------------------
class AnalyzeInput(BaseModel):
    symptoms: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatInput(BaseModel):
    message: str
    history: list[ChatMessage] = []


# -------------------------------------------------
# Global Engine Instance
# -------------------------------------------------
try:
    engine = create_engine()
except Exception as e:
    print(f"Warning: Could not initialize engine on startup: {e}")
    engine = None

# -------------------------------------------------
# Stateless Endpoint
# -------------------------------------------------
@app.post("/analyze")
def analyze(data: AnalyzeInput):
    """
    Stateless clinical reasoning.
    No memory retained between requests.
    """
    global engine
    if not engine: # Lazy load if failed during startup
        engine = create_engine()
        
    response = engine.process(data.symptoms, [])

    return {
        "response": response
    }


# -------------------------------------------------
# Stateless Chat Sessions (Passed from Client)
# -------------------------------------------------
@app.post("/chat")
def chat(data: ChatInput):
    """
    Stateless chat endpoint.
    Conversation memory passed from client.
    """
    global engine
    if not engine: # Lazy load if failed during startup
        engine = create_engine()

    message = data.message
    
    # Format history as strings for the RAG engine
    formatted_history = []
    for msg in data.history:
        role_label = "User" if msg.role == "user" else "Assistant"
        formatted_history.append(f"{role_label}: {msg.content}")

    response = engine.process(message, formatted_history)

    return {
        "response": response
    }


# -------------------------------------------------
# Health Check
# -------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}
