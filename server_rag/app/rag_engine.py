"""
rag_engine.py — Clinical Co-Pilot RAG Engine
=============================================
Upgrades in this version:
  🥇 Confidence scoring  — based on doc count, conflict presence, keyword strength
  🥈 Fuzzy symptom recall — RapidFuzz for typo/variant tolerance
  🥉 Structured evidence  — LLM forced to cite page + quote per finding

Architecture:
  extract_patient_state()   — deterministic, zero LLM, rule + fuzzy matching
  check_emergency()         — multi-layer danger sign detection
  score_retrieval_confidence() — numeric confidence from retrieval signals
  detect_doc_conflicts()    — conservative conflict flag
  ClinicalCoPilot.process() — dual-pass retrieval → conflict check → prompt
"""

import os
import sys
import re
import json
import time
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from langchain_community.vectorstores import Qdrant
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_groq import ChatGroq
from qdrant_client import QdrantClient
from rapidfuzz import fuzz, process as fuzz_process

load_dotenv()

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
HISTORY_WINDOW       = 6      # last N messages to include in prompt
CHUNK_CHAR_LIMIT     = 800    # max chars per retrieved chunk
MAX_RESPONSE_TOKENS  = 1024   # prevents LLM response truncation
TOP_K_RESULTS        = 5      # chunks per retrieval pass
DISTANCE_THRESHOLD   = 0.5    # Qdrant distance threshold (lower = better match, keep <= 0.5)

# Fuzzy match threshold — 0-100, higher = stricter
# 82 catches common misspellings (convulsoin, seziure) without
# false-positives on short words like "rash" vs "rush"
FUZZY_THRESHOLD = 82

# -------------------------------------------------------------------
# 🥈 SYMPTOM PATTERNS — canonical name → list of variants
#
# These feed BOTH exact matching and fuzzy matching.
# Fuzzy matching catches typos, phonetic variants, and informal
# spellings that real users (parents, community health workers) type.
# -------------------------------------------------------------------
SYMPTOM_PATTERNS: Dict[str, List[str]] = {
    "fever":           ["fever", "high temperature", "hot body", "high fever", "temperature"],
    "red_eyes":        ["red eyes", "red eye", "conjunctivitis", "redness in eyes", "pink eye"],
    "rash":            ["rash", "rashes", "skin rash", "generalized rash", "spots on skin", "skin spots"],
    "cough":           ["cough", "coughing", "dry cough", "wet cough"],
    "runny_nose":      ["runny nose", "nasal discharge", "running nose", "nose running", "sneezing"],
    "fast_breathing":  ["fast breathing", "rapid breathing", "breathing fast", "breathes quickly"],
    "chest_indrawing": ["chest indrawing", "chest in-drawing", "chest retractions", "sucking chest"],
    "stridor":         ["stridor", "noisy breathing", "crowing sound", "harsh breathing"],
    "convulsion":      ["convulsion", "seizure", "fits", "shaking", "jerking", "fitting"],
    "unconscious":     ["unconscious", "unresponsive", "not waking", "cannot wake", "collapsed"],
    "lethargic":       ["lethargic", "very sleepy", "drowsy", "not moving", "limp", "weak"],
    "vomits_all":      ["vomits everything", "cannot keep anything down", "vomiting everything", "throws up everything"],
    "unable_to_drink": ["unable to drink", "not drinking", "refusing feeds", "cannot drink", "refuses milk"],
    "ear_pain":        ["ear pain", "ear ache", "pulling ear", "ear discharge", "ear drainage"],
    "diarrhea":        ["diarrhea", "diarrhoea", "loose stool", "watery stool", "loose motions"],
    "malnutrition":    ["weight loss", "not eating", "wasting", "underweight", "not gaining weight"],
    "pale":            ["pale", "pallor", "pale palms", "anaemia", "anemia"],
    "stiff_neck":      ["stiff neck", "neck stiffness", "cannot bend neck"],
    "bulging_fontanelle": ["bulging fontanelle", "bulging soft spot", "fontanelle bulging"],
}

# Flat list of all variants for fuzzy candidate matching
ALL_VARIANTS: List[Tuple[str, str]] = [
    (variant, key)
    for key, variants in SYMPTOM_PATTERNS.items()
    for variant in variants
]

# IMCI-defined danger signs — any one = HIGH risk
DANGER_SIGN_KEYS = {
    "convulsion", "unconscious", "lethargic",
    "vomits_all", "unable_to_drink", "chest_indrawing", "stridor"
}

# Phrases that signal a symptom was denied by the user
DENIAL_PREFIXES = [
    "no ", "doesn't have", "does not have",
    "without", "no sign of", "absent", "denies", "not having"
]


# -------------------------------------------------------------------
# 🥈 Fuzzy symptom matching
#
# Strategy:
#   1. Exact substring match (fast path, zero cost)
#   2. Fuzzy token-set ratio on each word/phrase in user text
#      against all known variants (catches typos, reorderings)
#
# Token-set ratio is better than simple ratio for medical text
# because it handles word-order differences:
#   "eyes red" vs "red eyes" → token_set_ratio = 100
#   simple ratio             → ~72
# -------------------------------------------------------------------
def fuzzy_match_symptoms(text: str) -> Dict[str, float]:
    """
    Returns {symptom_key: best_match_score} for every symptom
    that was detected in text (exact or fuzzy).

    Score is 0-100. Exact match = 100.
    Only returns entries at or above FUZZY_THRESHOLD.
    """
    text_lower = text.lower()
    matches: Dict[str, float] = {}

    # Build candidate windows from text (unigrams + bigrams + trigrams)
    words = text_lower.split()
    candidates = words.copy()
    candidates += [" ".join(words[i:i+2]) for i in range(len(words)-1)]
    candidates += [" ".join(words[i:i+3]) for i in range(len(words)-2)]

    for candidate in candidates:
        if len(candidate) < 3:
            continue

        # Check against all known variant strings
        for variant, symptom_key in ALL_VARIANTS:
            score = fuzz.token_set_ratio(candidate, variant)
            if score >= FUZZY_THRESHOLD:
                # Keep highest score per symptom key
                if symptom_key not in matches or score > matches[symptom_key]:
                    matches[symptom_key] = float(score)

    return matches


def extract_patient_state(history: List[str], current_input: str) -> Dict:
    """
    Deterministic patient state extraction — zero LLM calls.

    Uses exact matching first, fuzzy as fallback.
    Denial overrides confirmation (clinically safer).

    Returns:
        confirmed: {symptom_key: True}
        denied:    {symptom_key: True}
        age:       str | None
        duration:  str | None
        fuzzy_matches: {symptom_key: score}  ← for confidence scoring
    """
    confirmed: Dict[str, bool] = {}
    denied: Dict[str, bool] = {}
    fuzzy_scores: Dict[str, float] = {}

    # Only scan user-side turns
    user_texts = []
    for msg in history + [f"User: {current_input}"]:
        if msg.lower().startswith("user:"):
            user_texts.append(msg[5:].strip().lower())
        elif not msg.lower().startswith("assistant:"):
            user_texts.append(msg.strip().lower())

    full_text = " ".join(user_texts)

    # --- Exact matching ---
    for symptom_key, variants in SYMPTOM_PATTERNS.items():
        for variant in variants:
            if variant in full_text:
                is_denied = any((prefix + variant) in full_text for prefix in DENIAL_PREFIXES)
                if is_denied:
                    denied[symptom_key] = True
                    confirmed.pop(symptom_key, None)
                elif symptom_key not in denied:
                    confirmed[symptom_key] = True

    # --- Fuzzy matching (fills gaps exact matching missed) ---
    fuzzy_hits = fuzzy_match_symptoms(full_text)
    for symptom_key, score in fuzzy_hits.items():
        fuzzy_scores[symptom_key] = score
        # Only add to confirmed if not already handled by exact match or denied
        if symptom_key not in confirmed and symptom_key not in denied:
            confirmed[symptom_key] = True

    # Age: "4 year old", "6 months", "10 weeks"
    age = None
    age_match = re.search(r'(\d+)\s*(year|yr|month|mon|week|wk|day)s?\s*(old)?', full_text)
    if age_match:
        age = age_match.group(0).strip()

    # Duration: "since 3 days", "for 2 weeks", "last 5 hours"
    duration = None
    dur_match = re.search(r'(since|for|last)\s+(\d+)\s*(day|week|hour|month)s?', full_text)
    if dur_match:
        duration = dur_match.group(0).strip()

    return {
        "confirmed": confirmed,
        "denied": denied,
        "age": age,
        "duration": duration,
        "fuzzy_matches": fuzzy_scores,
    }


def format_patient_state(state: Dict) -> str:
    """Clean prompt-ready string from extracted patient state."""
    lines = []
    if state.get("age"):
        lines.append(f"- Age: {state['age']}")
    if state.get("duration"):
        lines.append(f"- Duration: {state['duration']}")
    if state["confirmed"]:
        lines.append("- Confirmed symptoms: " + ", ".join(
            k.replace("_", " ") for k in state["confirmed"]
        ))
    if state["denied"]:
        lines.append("- Denied symptoms: " + ", ".join(
            k.replace("_", " ") for k in state["denied"]
        ))
    return "\n".join(lines)


# -------------------------------------------------------------------
# 🥇 CONFIDENCE SCORING
#
# Confidence is computed from retrieval and extraction signals —
# not from the LLM. The LLM reports the confidence we give it.
#
# Factors:
#   + Number of docs retrieved (more = better coverage)
#   + Best retrieval score (lower L2 distance = stronger match)
#   + Presence of strong IMCI keywords in retrieved docs
#   - Document conflict (disagreement = lower confidence)
#   - Fuzzy-only matches (no exact symptom confirmation)
#   - Missing critical fields (age, confirmed symptoms)
# -------------------------------------------------------------------
STRONG_IMCI_KEYWORDS = [
    "classify", "classified as", "danger sign", "refer urgently",
    "give treatment", "follow up", "severe", "mild", "moderate",
    "assess and classify", "imci", "integrated management"
]


def score_retrieval_confidence(
    docs: list,
    all_results: List[Tuple],
    patient_state: Dict,
    has_conflict: bool
) -> Tuple[str, List[str]]:
    """
    🥇 Returns (confidence_label, reasons_list).

    confidence_label: "High" | "Medium" | "Low"
    reasons_list: human-readable explanation of each factor

    Scoring (0-100 scale internally):
      Base: 50
      +15  if >= 3 docs retrieved
      +10  if best score <= 0.6 (very close match)
      +10  if >= 2 strong IMCI keywords found across docs
      +10  if age is known
      +5   if duration is known
      -20  if document conflict detected
      -15  if only fuzzy matches (no exact confirmed symptoms)
      -10  if no confirmed symptoms at all
    """
    score = 50
    reasons = []

    # Doc count
    if len(docs) >= 3:
        score += 15
        reasons.append(f"+15: {len(docs)} supporting documents retrieved")
    else:
        reasons.append(f"  0: only {len(docs)} document(s) retrieved")

    # Best retrieval score (L2 distance — lower is better)
    if all_results:
        best_score = all_results[0][1]
        if best_score <= 0.6:
            score += 10
            reasons.append(f"+10: strong semantic match (score={round(best_score, 3)})")
        elif best_score <= 1.0:
            reasons.append(f"  0: moderate semantic match (score={round(best_score, 3)})")
        else:
            score -= 5
            reasons.append(f" -5: weak semantic match (score={round(best_score, 3)})")

    # IMCI keyword presence across all retrieved docs
    combined_text = " ".join(d.page_content.lower() for d in docs)
    kw_hits = [kw for kw in STRONG_IMCI_KEYWORDS if kw in combined_text]
    if len(kw_hits) >= 2:
        score += 10
        reasons.append(f"+10: strong IMCI keywords found ({', '.join(kw_hits[:3])})")
    else:
        reasons.append(f"  0: few IMCI keywords in retrieved docs")

    # Patient state completeness
    if patient_state.get("age"):
        score += 10
        reasons.append("+10: patient age confirmed")
    else:
        reasons.append("  0: patient age unknown")

    if patient_state.get("duration"):
        score += 5
        reasons.append("+5: symptom duration known")

    # Conflict penalty
    if has_conflict:
        score -= 20
        reasons.append("-20: conflicting risk signals across documents")

    # Fuzzy-only symptom penalty
    confirmed = set(patient_state["confirmed"].keys())
    fuzzy_only = set(patient_state["fuzzy_matches"].keys()) - confirmed
    if fuzzy_only and not (confirmed - fuzzy_only):
        score -= 15
        reasons.append(f"-15: symptoms detected via fuzzy match only (may be imprecise)")

    # No confirmed symptoms at all
    if not patient_state["confirmed"]:
        score -= 10
        reasons.append("-10: no confirmed symptoms in patient state")

    # Map score to label
    if score >= 70:
        label = "High"
    elif score >= 45:
        label = "Medium"
    else:
        label = "Low"

    return label, reasons


# -------------------------------------------------------------------
# FIX 4: Hardened emergency detection — multi-layer
# -------------------------------------------------------------------
EMERGENCY_VARIANTS: Dict[str, List[str]] = {
    "convulsion":      ["convulsion", "seizure", "fits", "fitting", "shaking badly", "jerking"],
    "unconscious":     ["unconscious", "unresponsive", "not waking up", "collapsed", "fainted"],
    "lethargic":       ["lethargic", "very lethargic", "cannot be woken", "limp", "not responding"],
    "chest_indrawing": ["chest indrawing", "chest in-drawing", "chest retractions", "sucking in chest"],
    "stridor":         ["stridor", "noisy breathing", "crowing sound", "harsh noisy breath"],
    "cyanosis":        ["cyanosis", "blue lips", "bluish", "turning blue", "lips blue"],
    "vomits_all":      ["vomits everything", "cannot keep anything", "vomiting everything", "throws up all"],
    "unable_to_drink": ["unable to drink", "not drinking", "refuses all feeds", "cannot swallow"],
}


def check_emergency(text: str, patient_state: Dict) -> List[str]:
    """
    Layer 1: raw text keyword scan (current message)
    Layer 2: fuzzy match against emergency variants
    Layer 3: confirmed state from prior turns
    """
    found = []
    text_lower = text.lower()

    # Layer 1: exact keyword scan
    for sign, variants in EMERGENCY_VARIANTS.items():
        if any(v in text_lower for v in variants) and sign not in found:
            found.append(sign)

    # Layer 2: fuzzy scan for emergency terms
    for sign, variants in EMERGENCY_VARIANTS.items():
        if sign in found:
            continue
        for variant in variants:
            score = fuzz.token_set_ratio(text_lower, variant)
            if score >= FUZZY_THRESHOLD:
                found.append(sign)
                break

    # Layer 3: confirmed state from history
    for key in DANGER_SIGN_KEYS:
        if patient_state["confirmed"].get(key) and key not in found:
            found.append(key)

    return found


# -------------------------------------------------------------------
# FIX 3: Document conflict detection
# -------------------------------------------------------------------
RISK_KEYWORDS = {
    "high":     ["severe", "danger sign", "urgent", "immediate referral", "emergency"],
    "moderate": ["moderate", "classified as", "give treatment", "follow up in"],
    "low":      ["mild", "home treatment", "counsel mother", "no signs of"],
}


def detect_doc_conflicts(docs) -> Optional[str]:
    signals = set()
    for doc in docs:
        content_lower = doc.page_content.lower()
        for level, keywords in RISK_KEYWORDS.items():
            if any(kw in content_lower for kw in keywords):
                signals.add(level)
    if "high" in signals and "low" in signals:
        return (
            "Retrieved documents contain conflicting risk signals "
            "(some indicate severe/high, others indicate mild/low). "
            "Apply the CONSERVATIVE (higher risk) classification. "
            "Cite the specific page numbers that conflict."
        )
    return None


# -------------------------------------------------------------------
# Main class
# -------------------------------------------------------------------
class ClinicalCoPilot:
    def __init__(self, api_key: str = None, debug: bool = True):
        print("Initializing Clinical Co-Pilot with Qdrant backend...")
        self.debug = debug

        # Get Qdrant credentials from environment
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not qdrant_url or not qdrant_api_key:
            raise ValueError("❌ QDRANT_URL or QDRANT_API_KEY not found in .env file")

        try:
            # Initialize Qdrant client
            client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
            )
            print("✓ Connected to Qdrant cloud")

            # Initialize vectorstore with Qdrant
            self.db = Qdrant(
                client=client,
                collection_name="imci_handbook",
                embeddings=FastEmbedEmbeddings()
            )
            print("✓ Qdrant vectorstore initialized (imci_handbook collection)")
        except Exception as e:
            print(f"❌ Error initializing Qdrant: {e}")
            raise

        if api_key is None:
            api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set.")

        try:
            self.llm = ChatGroq(
                api_key=api_key,
                model="llama-3.3-70b-versatile",
                temperature=0,
                max_tokens=MAX_RESPONSE_TOKENS
            )
            print("✓ Groq LLM initialized (llama-3.3-70b-versatile)")
        except Exception as e:
            print(f"Error initializing Groq: {e}")
            raise

    def process(self, user_input: str, external_history: List[str] = None) -> str:
        start_time = time.time()

        if external_history is None:
            external_history = []

        recent_history = external_history[-HISTORY_WINDOW:]

        # --------------------------------------------------
        # Step 1: Deterministic patient state (rule + fuzzy)
        # --------------------------------------------------
        patient_state = extract_patient_state(recent_history, user_input)
        patient_state_text = format_patient_state(patient_state)

        if self.debug:
            print(f"DEBUG patient state:\n{json.dumps(patient_state, indent=2)}\n")

        # --------------------------------------------------
        # Step 2: Emergency check (before any LLM call)
        # --------------------------------------------------
        emergency_flags = check_emergency(user_input, patient_state)

        # --------------------------------------------------
        # Step 3: Dual-pass decoupled retrieval
        # --------------------------------------------------
        results_a = self.db.similarity_search_with_score(user_input, k=TOP_K_RESULTS)

        results_b = []
        if patient_state["confirmed"]:
            symptom_query = "IMCI classification child with " + " ".join(
                k.replace("_", " ") for k in patient_state["confirmed"]
            )
            if patient_state.get("age"):
                symptom_query += f" aged {patient_state['age']}"
            results_b = self.db.similarity_search_with_score(symptom_query, k=TOP_K_RESULTS)

        # Merge and deduplicate by content hash, keep best score per doc
        seen: Dict[int, tuple] = {}
        for doc, score in (results_a + results_b):
            key = hash(doc.page_content[:100])
            if key not in seen or score < seen[key][1]:
                seen[key] = (doc, score)

        all_results = sorted(seen.values(), key=lambda x: x[1])

        # Score-ranked filtering with fallback
        docs = [doc for doc, score in all_results if score <= DISTANCE_THRESHOLD]
        if not docs:
            docs = [doc for doc, _ in all_results[:3]]
        docs = docs[:5]

        if self.debug:
            print(f"DEBUG: {len(docs)} docs after dual-pass retrieval")
            for doc, score in all_results[:5]:
                print(f"  Score {round(score, 3)} | {doc.page_content[:80]}...")

        if not docs:
            return "No relevant information found in IMCI guidelines."

        # --------------------------------------------------
        # Step 4: Conflict detection
        # --------------------------------------------------
        conflict_warning = detect_doc_conflicts(docs)
        has_conflict = conflict_warning is not None

        # --------------------------------------------------
        # 🥇 Step 5: Confidence scoring
        # --------------------------------------------------
        confidence_label, confidence_reasons = score_retrieval_confidence(
            docs, all_results, patient_state, has_conflict
        )

        if self.debug:
            print(f"DEBUG confidence: {confidence_label}")
            for r in confidence_reasons:
                print(f"  {r}")
            print()

        # --------------------------------------------------
        # Step 6: Build context block with page metadata
        # --------------------------------------------------
        context_text = "\n---\n".join([
            f"[Page {d.metadata.get('page_number', '?')}]\n{d.page_content[:CHUNK_CHAR_LIMIT]}"
            for d in docs
        ])

        conversation_text = "\n".join(recent_history) + f"\nUser: {user_input}"

        conflict_block = (
            f"\nDOCUMENT CONFLICT WARNING:\n{conflict_warning}\n"
            if conflict_warning else ""
        )
        confirmed_block = (
            f"\nCONFIRMED PATIENT STATE (rule-extracted — do not re-ask these):\n"
            f"{patient_state_text}\n"
            if patient_state_text else ""
        )

        # --------------------------------------------------
        # 🥇🥉 Step 7: Final prompt
        #
        # Three upgrades in the prompt itself:
        #   🥇 Confidence label is passed in — LLM echoes it
        #      (we computed it, LLM didn't — avoids LLM overconfidence)
        #   🥉 LLM forced to output Evidence block with page + quote
        #      Short quotes only — not full paragraphs
        # --------------------------------------------------
        prompt = f"""
You are an IMCI (Integrated Management of Neonatal and Childhood Illness) clinical decision support assistant.

Use ONLY the IMCI context provided below. Every factual claim must cite a page number.

STRICT RULES:
- Do NOT use outside medical knowledge.
- Do NOT assume symptoms not mentioned.
- Do NOT re-ask about symptoms already listed under "Confirmed symptoms" or "Denied symptoms".
- If confirmed symptoms are sufficient to classify under IMCI, provide the classification now.
- Do NOT say "Insufficient information" when confirmed symptoms already satisfy IMCI criteria.
- If genuinely insufficient, ask for ONE specific missing piece only — not a list.
- If documents conflict, apply the CONSERVATIVE (higher risk) classification.
- Every claim in Assessment and Recommended Action MUST cite a page number.

RISK LEVEL DEFINITIONS:
- High: Any IMCI danger sign present.
- Moderate: Severe classification without danger signs.
- Low: Mild classification.

CONFIDENCE LEVEL (pre-computed from retrieval quality): {confidence_label}
Use this confidence level exactly as given. Do not upgrade it.

IMCI CONTEXT:
{context_text}
{conflict_block}{confirmed_block}
FULL CONVERSATION:
{conversation_text}

Respond in EXACTLY this format (all 6 sections required):

Assessment:
[Assessment with page citations in brackets e.g. (Page 12)]

Risk Level:
[High / Moderate / Low — one-line justification]

Confidence:
[{confidence_label} — copy this label exactly, then one sentence explaining the main limiting factor]

Recommended Action:
[IMCI-guided action with page citation]

Evidence:
- Page [N] → "[brief direct quote under 15 words that supports your assessment]"
- Page [N] → "[brief direct quote under 15 words that supports your recommendation]"

Key Questions to Ask:
- [Only unconfirmed, clinically necessary — max 2 questions]
"""

        print("Thinking...\n")
        response = self.llm.invoke(prompt)
        output = response.content.strip()

        # Emergency override — always prepend, never suppress
        if emergency_flags:
            labels = [f.replace("_", " ") for f in emergency_flags]
            output = (
                f"⚠️  DANGER SIGNS DETECTED: {', '.join(labels)}\n"
                f"IMMEDIATE REFERRAL TO HOSPITAL REQUIRED.\n"
                f"Do not wait for further assessment.\n\n"
                + output
            )

        if self.debug:
            print(f"Response time: {round(time.time() - start_time, 2)} sec")

        return output


# =========================================================
# Interactive CLI Chat
# =========================================================
if __name__ == "__main__":

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("Set your Groq API key:")
        print("  export GROQ_API_KEY='your-key'       # Linux/Mac")
        print("  $env:GROQ_API_KEY='your-key'         # Windows PowerShell")
        sys.exit(1)

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    if not qdrant_url or not qdrant_api_key:
        print("Set your Qdrant credentials:")
        print("  QDRANT_URL (e.g., https://xxx.cloud.qdrant.io)")
        print("  QDRANT_API_KEY")
        sys.exit(1)

    bot = ClinicalCoPilot(debug=True)
    print("\nCommands: /reset — clear history | /exit — quit\n")

    chat_history = []

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "/exit":
            print("Exiting...")
            break
        if user_input.lower() == "/reset":
            chat_history = []
            print("Conversation reset.\n")
            continue

        response = bot.process(user_input, chat_history)
        chat_history.append(f"User: {user_input}")
        chat_history.append(f"Assistant: {response}")
        print(f"\nAssistant:\n{response}\n")