# Echo — Knowledge-Risk Engine for Seamless Team Handovers

> **We Code Coders · Hackathon Submission**  
> Companion to the Backend + Frontend prototypes and Presentation Guide.

---

## 🚀 Quickstart

You can start both backend and frontend with a single command:

```bash
./run.sh
```

Or run them individually in two separate terminals:

### 1. Backend (FastAPI)
```bash
cd echo/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
- **API Docs / Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 2. Frontend (React 19 + Vite + Tailwind CSS + Lucide)
```bash
cd echo/frontend
npm install
npm run dev
```
- **Frontend UI:** [http://localhost:3000](http://localhost:3000)  
  *(Note: You can also build via `npm run build` or open [http://localhost:8000](http://localhost:8000) directly as the backend serves the built frontend).*

---

## 📁 Project Structure

```
wecode/
├── echo/
│   ├── backend/
│   │   ├── main.py            # FastAPI backend with deterministic risk scoring & retrieval
│   │   ├── requirements.txt   # FastAPI, Uvicorn, Pydantic
│   │   └── .venv/             # Python virtual environment
│   └── frontend/
│       └── index.html         # Single-page React 18 + Tailwind UI
├── run.sh                     # Automated startup script for both services
├── README.md                  # This file
├── Echo Backend Prototype.md  # Backend specification & code
├── Echo Frontend Prototype.md # Frontend specification & code
└── Echo Demo & Presentation Guide.md # 2-minute judge pitch & rubric guide
```

---

## 🎯 2-Minute Demo Script (Rubric-Mapped)

| Time | Tab | Action | What to say |
|---|---|---|---|
| **0:00–0:20** | **Risk Map** | Open tab; show stats & formula | *"When Aarav resigns, most teams summarize what he wrote down. Echo instead finds what only he knows. This map runs continuously — scores use a transparent, deterministic formula, not a black box."* |
| **0:20–0:50** | **Risk Map** | Point at top 3 artifacts + bus-factor badges | *"nightly_sync.py: one owner, zero docs, high criticality, touched 3 days ago. That's a landmine waiting to go off. We detected 4/4 planted gaps."* |
| **0:50–1:20** | **Exit Interview** | Show evidence-based questions; answer retry question | *"The questions aren't a generic HR form — each is generated from evidence in Aarav's own commits."* Type: `we chose 7 because the vendor API rate-limited us` → auto-logs decision. |
| **1:20–1:40** | **Handover** | Click Handover tab | *"Meera gets a personalized package, not a static PDF: a 2-week onboarding path, landmines with captured answers attached, open loops, and who-to-ask."* |
| **1:40–2:00** | **Ask Echo** | Ask retry limit, then wifi password | Ask: `Why is the retry limit 7?` → Cited answer.<br>Ask: `What is the wifi password?` → *Unknown — suggested contact: Priya*.<br>*"Every answer is cited. When we don't know, Echo says so — that's the trust layer."* |

---

## 🔌 API Endpoints

- `GET /api/risk-map`: Deterministic risk scores per artifact, bus-factor violations, and planted gap detection.
- `GET /api/artifacts`: Full artifact catalog with knowledge graph edges.
- `GET|POST /api/interview/questions`: Evidence-based questions generated for the leaver.
- `GET|POST /api/interview/answers`: Submit and retrieve answers; automatically extracts decision logs.
- `GET /api/handover`: Personalized successor package for Meera (onboarding path, landmines, open loops, who-to-ask).
- `POST /api/ask`: Retrieval-first Q&A with citations and honesty fallback ("Unknown" + suggested contact).
- `POST /api/reset`: Reset interview answers and decision logs for a clean demo run.

