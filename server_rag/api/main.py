import os
import sys
from fastapi import FastAPI
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
# Resolve Vector Store Path
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
VECTOR_DIR = os.path.join(PROJECT_ROOT, "storage", "vector_store")

if not os.path.exists(VECTOR_DIR):
    raise FileNotFoundError(f"❌ Vector store not found at {VECTOR_DIR}")


# -------------------------------------------------
# Engine Factory (Creates New Instance)
# -------------------------------------------------
def create_engine():
    return ClinicalCoPilot(
        persist_dir=VECTOR_DIR,
        api_key=GROQ_API_KEY,
        debug=False
    )


# -------------------------------------------------
# Request Models
# -------------------------------------------------
class AnalyzeInput(BaseModel):
    symptoms: str


class ChatInput(BaseModel):
    user_id: str
    message: str


# -------------------------------------------------
# Stateless Endpoint
# -------------------------------------------------
@app.post("/analyze")
def analyze(data: AnalyzeInput):
    """
    Stateless clinical reasoning.
    No memory retained between requests.
    """
    engine = create_engine()
    response = engine.process(data.symptoms)

    return {
        "response": response
    }


# -------------------------------------------------
# Stateful Chat Sessions (In-Memory)
# -------------------------------------------------
class ChatSession:
    def __init__(self):
        self.engine = create_engine()


# In-memory storage (resets on restart)
sessions = {}


@app.post("/chat")
def chat(data: ChatInput):
    """
    Stateful chat endpoint.
    Maintains conversation memory per user_id.
    """

    user_id = data.user_id
    message = data.message

    if user_id not in sessions:
        sessions[user_id] = ChatSession()

    session = sessions[user_id]

    response = session.engine.process(message)

    return {
        "response": response
    }


# -------------------------------------------------
# Health Check
# -------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}
