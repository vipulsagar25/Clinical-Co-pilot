import os
import sys
import time
from typing import List
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_groq import ChatGroq

# Load environment variables from .env file
load_dotenv()


class ClinicalCoPilot:
    def __init__(self, persist_dir: str, api_key: str = None, debug: bool = True):
        print(f"🧠 Loading Clinical Brain from: {persist_dir}")

        self.debug = debug

        # -----------------------------
        # Vector Store
        # -----------------------------
        try:
            self.db = Chroma(
                collection_name="imci_handbook",
                persist_directory=persist_dir,
                embedding_function=FastEmbedEmbeddings()
            )
            print("✓ Vector database loaded")
        except Exception as e:
            print(f"❌ Error loading vector database: {e}")
            raise

        # -----------------------------
        # Groq LLM
        # -----------------------------
        if api_key is None:
            api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            print("❌ GROQ_API_KEY not set.")
            sys.exit(1)

        try:
            self.llm = ChatGroq(
                api_key=api_key,
                model="llama-3.3-70b-versatile",
                temperature=0
            )
            print("✓ Groq LLM initialized (llama-3.3-70b-versatile)")
        except Exception as e:
            print(f"❌ Error initializing Groq: {e}")
            raise

        # -----------------------------
        # Conversation Memory (Limited Window)
        # -----------------------------
        self.chat_history: List[str] = []

    # ---------------------------------------------------------
    # Emergency Guardrail
    # ---------------------------------------------------------
    def check_emergency(self, text: str) -> List[str]:
        triggers = [
            "convulsion", "seizure", "unconscious",
            "unable to drink", "vomits everything",
            "lethargic", "chest indrawing",
            "stridor", "cyanosis"
        ]
        text_lower = text.lower()
        return [t for t in triggers if t in text_lower]

    # ---------------------------------------------------------
    # Main Processing
    # ---------------------------------------------------------
    def process(self, user_input: str) -> str:

        start_time = time.time()

        emergency_flags = self.check_emergency(user_input)

        # Save user message
        self.chat_history.append(f"User: {user_input}")

        # Keep only last 6 messages (3 exchanges)
        self.chat_history = self.chat_history[-6:]

        # -----------------------------
        # Retrieval
        # -----------------------------
        results = self.db.similarity_search_with_score(
            user_input,
            k=5
        )

        if not results:
            return "No relevant information found in IMCI guidelines."

        # Filter by distance threshold (lower = better)
        docs = [doc for doc, score in results if score <= 1.0]

        if not docs:
            docs = [doc for doc, score in results[:3]]

        if self.debug:
            print(f"DEBUG: Using {len(docs)} documents")
            for i, (doc, score) in enumerate(results[:3]):
                print(f"  Score {round(score,3)} | {doc.page_content[:80]}...")

        # Compress context
        context_text = "\n---\n".join([
            f"[Page {d.metadata.get('page_number', '?')}]\n"
            f"{d.page_content[:600]}"
            for d in docs
        ])

        conversation_text = "\n".join(self.chat_history)

        # -----------------------------
        # Strong Grounded Prompt
        # -----------------------------
        prompt = f"""
You are an IMCI (Integrated Management of Neonatal and Childhood Illness) clinical decision support assistant.

Use ONLY the IMCI context provided below.

STRICT RULES:
- Do NOT use outside medical knowledge.
- Do NOT assume symptoms not mentioned.
- If information is insufficient, clearly state:
  "Insufficient information according to IMCI guidelines."
- Base classification strictly on IMCI rules.

RISK LEVEL DEFINITIONS:
- High: Any IMCI danger sign present.
- Moderate: Severe classification without danger signs.
- Low: Mild classification.

IMCI CONTEXT:
{context_text}

PATIENT INFORMATION:
{conversation_text}

Provide response in this format:

Assessment:
...

Risk Level:
...

Recommended Action:
...

Key Questions to Ask:
- ...
- ...
"""

        print("🤔 Thinking...\n")

        response = self.llm.invoke(prompt)
        output = response.content.strip()

        # Emergency override
        if emergency_flags:
            output = (
                f"⚠️ DANGER SIGNS DETECTED: {', '.join(emergency_flags)}\n"
                f"Immediate referral to hospital is required.\n\n"
                + output
            )

        # Save assistant response
        self.chat_history.append(f"Assistant: {output}")

        end_time = time.time()

        if self.debug:
            print(f"⏱ Response time: {round(end_time - start_time, 2)} sec")

        return output

    # ---------------------------------------------------------
    # Reset conversation
    # ---------------------------------------------------------
    def reset(self):
        self.chat_history = []
        print("🔄 Conversation reset.\n")


# =========================================================
# Interactive CLI Chat
# =========================================================
if __name__ == "__main__":

    script_dir = os.path.dirname(os.path.abspath(__file__))
    persist_dir = os.path.join(script_dir, "..", "storage", "vector_store")
    persist_dir = os.path.abspath(persist_dir)

    if not os.path.exists(persist_dir):
        print(f"❌ Vector store not found at {persist_dir}")
        print("Run: python ../builders/build_vector_db.py")
        sys.exit(1)

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("❌ Set your Groq API key:")
        print("$env:GROQ_API_KEY='your-key'")
        sys.exit(1)

    bot = ClinicalCoPilot(persist_dir, api_key=groq_api_key, debug=True)

    print("\n💬 Clinical Co-Pilot (Groq Powered)")
    print("Type '/reset' to clear memory.")
    print("Type '/exit' to quit.\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() == "/exit":
            print("Exiting...")
            break

        if user_input.lower() == "/reset":
            bot.reset()
            continue

        response = bot.process(user_input)
        print(f"\nAssistant:\n{response}\n")
