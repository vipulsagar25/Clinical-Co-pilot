from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.rag_engine import ClinicalCoPilot

# ---------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------

app = FastAPI(title="Clinical Co-Pilot API")

# Allow frontend (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------
# Initialize Clinical Engine
# ---------------------------------------------

copilot = ClinicalCoPilot(
    persist_dir="../storage/vector_store"
)

# ---------------------------------------------
# Request Models
# ---------------------------------------------

class AnalyzeInput(BaseModel):
    symptoms: str


class ChatInput(BaseModel):
    user_id: str
    message: str


# ---------------------------------------------
# Stateless Clinical Query Endpoint
# ---------------------------------------------

@app.post("/analyze")
def analyze(data: AnalyzeInput):
    """
    Stateless endpoint.
    Each request is processed independently.
    Best for structured clinical input.
    """
    return copilot.process(data.symptoms)


# ---------------------------------------------
# Simple In-Memory Chat Session (UI Memory Only)
# ---------------------------------------------

class ChatSession:
    def __init__(self):
        self.history = []

    def add(self, role: str, content):
        self.history.append({
            "role": role,
            "content": content
        })

    def get_recent(self, n: int = 4):
        return self.history[-n:]


# In-memory session store (resets on server restart)
sessions = {}


@app.post("/chat")
def chat(data: ChatInput):
    """
    Chat endpoint.
    Maintains UI conversation history per user_id.
    Clinical reasoning remains stateless for safety.
    """

    user_id = data.user_id
    message = data.message

    if user_id not in sessions:
        sessions[user_id] = ChatSession()

    session = sessions[user_id]

    # Store user message
    session.add("user", message)

    # Clinical processing (stateless reasoning)
    response = copilot.process(message)

    # Store assistant response
    session.add("assistant", response)

    return response
