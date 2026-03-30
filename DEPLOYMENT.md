# Clinical Co-pilot Deployment Guide

## Project Structure

```
Clinical Co-pilot/
├── client/                    # Frontend (React + Vite + Node.js)
│   ├── package.json          # npm dependencies
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   └── ...
│   └── public/
│
├── server_rag/               # Backend (Python FastAPI + RAG)
│   ├── requirements.txt      # Python 3.11+ dependencies
│   ├── runtime.txt           # Python version pinned to 3.11.9
│   ├── api/
│   │   └── main.py          # FastAPI app
│   ├── app/
│   │   └── rag_engine.py    # RAG logic
│   └── Dockerfile           # Container config
│
└── README.md                 # Project info
```

---

## Frontend Deployment (React Client)

**Tech Stack:** Node.js, npm, React 19, Vite, Tailwind CSS

**Build & Run Locally:**
```bash
cd client
npm install --legacy-peer-deps
npm run dev        # Dev server on http://localhost:5173
npm run build      # Production build
```

**Deploy to Render (Static):**
1. Use Render's **Static Site** service
2. Build command: `cd client && npm install && npm run build`
3. Publish directory: `client/dist`

---

## Backend Deployment (FastAPI + RAG)

**Tech Stack:** Python 3.11.9, FastAPI, LangChain, Qdrant, Groq LLM

**Dependencies:**
- Pinned to **Python 3.11.9** (runtime.txt)
- Flexible version constraints for LangChain ecosystem (prevents conflicts)
- Pre-built wheels for all packages (no Rust compilation)

**Build & Run Locally:**
```bash
cd server_rag
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python api/main.py        # Runs on http://localhost:8000
```

**Deploy to Render (Web Service):**
1. Use Render's **Web Service**
2. Runtime: Python 3.11
3. Build command: `pip install -r server_rag/requirements.txt`
4. Start command: `cd server_rag && uvicorn api.main:app --host 0.0.0.0 --port $PORT`

---

## Environment Variables

Create `.env` file in both directories:

**Backend (.env in server_rag/):**
```env
GROQ_API_KEY=your_groq_api_key_here
DATABASE_URL=qdrant_url_if_needed
```

**Frontend (.env in client/):**
```env
VITE_API_URL=https://your-backend-url.onrender.com
```

---

## Key Fixes Applied

| Issue | Solution |
|---|---|
| Python 3.14 compilation errors | Pinned Python 3.11.9 → has pre-built wheels |
| LangChain version conflicts | Moved to 1.x ecosystem with flexible constraints |
| Overlapping requirements files | Removed root/client requirements; kept only backend |
| `pydantic-core` build failures | Flexible versioning lets pip resolve correctly |

---

## Testing Before Deploy

**Frontend:**
```bash
cd client && npm run build  # Verify build succeeds
```

**Backend:**
```bash
cd server_rag
python -c "from fastapi import FastAPI; from langchain_core import __version__; print('✅ All imports work!')"
```

---

## Render Deployment Checklist

- [ ] Python 3.11.9 pinned (check `server_rag/runtime.txt`)
- [ ] All env variables set in Render dashboard
- [ ] Frontend build succeeds locally (`npm run build`)
- [ ] Backend imports work locally
- [ ] `.env` files NOT committed to git
- [ ] `server_rag` folder selected for backend deployment
- [ ] Static site selected for frontend deployment

---

## Troubleshooting

**Deploy fails on Python version?**
→ Check Render dashboard uses Python 3.11 (not 3.14)

**Build fails on missing packages?**
→ Run `pip install -r server_rag/requirements.txt` locally first

**Import errors on deploy?**
→ Verify `langchain-core>=1.2.8` and `langchain-community>=0.3.24`

**API 502 errors?**
→ Check backend logs in Render dashboard; ensure all env vars are set
