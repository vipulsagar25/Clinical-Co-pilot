import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.rag_engine import ClinicalCoPilot


# -------------------------------------------------
# Load Environment Variables
# -------------------------------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY not found in .env file")


# -------------------------------------------------
# FastAPI Initialization with Lifespan
# -------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize engine on startup, cleanup on shutdown."""
    app.state.engine = ClinicalCoPilot(
        api_key=GROQ_API_KEY,
        debug=False
    )
    yield
    # Cleanup if needed

app = FastAPI(title="Clinical Co-Pilot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
# Stateless Chat Endpoint (Conversation via Client)
# -------------------------------------------------
@app.post("/chat")
def chat(request: Request, data: ChatInput):
    """
    Clinical reasoning endpoint.
    Conversation memory passed from client (stateless from server perspective).
    """
    engine = request.app.state.engine
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
