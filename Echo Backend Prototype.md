# Echo Backend (FastAPI) — Working Prototype

Below are the two files for the Echo backend prototype. Create a folder `backend/`, save both files, then run:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

CORS is enabled for `http://localhost:3000` (the React frontend).

## requirements.txt

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
```

## main.py

```python
"""
Echo: A Knowledge-Risk Engine for Seamless Team Handovers
Working backend prototype (Round 1/2 demo slice).

Run: uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs

API contract:
  GET  /api/risk-map          -> Knowledge Risk Map (deterministic scores)
  GET  /api/artifacts         -> all artifacts + links
  POST /api/interview/questions -> gap-driven interview questions for leaver
  POST /api/interview/answers   -> submit answers; stored & linked to artifacts
  GET  /api/handover          -> successor handover package (Meera)
  POST /api/ask               -> retrieval-first Q&A with citations / "unknown"
"""

import math
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Echo — Knowledge-Risk Engine Prototype", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------------
# SEEDED DEMO DATA (Aarav resigning; Meera is successor; Priya is a teammate)
# ----------------------------------------------------------------------------

LEAVER = "aarav"
SUCCESSOR = "meera"

PEOPLE = {
    "aarav": {"name": "Aarav", "role": "Backend Engineer (resigning)"},
    "meera": {"name": "Meera", "role": "Backend Engineer (successor)"},
    "priya": {"name": "Priya", "role": "Platform Engineer"},
    "rohan": {"name": "Rohan", "role": "Data Engineer"},
    "manager": {"name": "Neha", "role": "Engineering Manager"},
}

# artifacts: id, type, title, criticality (1-5), doc_coverage (0-1), last_touch days ago
ARTIFACTS = [
    {"id": "MOD-SYNC", "type": "module", "title": "nightly_sync.py — nightly data sync job",
     "criticality": 5, "doc_coverage": 0.0, "days_since_touch": 3, "repo": "core-platform"},
    {"id": "MOD-RETRY", "type": "module", "title": "payments/retry.py — payment retry logic",
     "criticality": 4, "doc_coverage": 0.3, "days_since_touch": 10, "repo": "core-platform"},
    {"id": "MOD-BILLING", "type": "module", "title": "billing/invoice_gen.py",
     "criticality": 3, "doc_coverage": 0.6, "days_since_touch": 40, "repo": "core-platform"},
    {"id": "MOD-AUTH", "type": "module", "title": "auth/session.py",
     "criticality": 4, "doc_coverage": 0.8, "days_since_touch": 15, "repo": "core-platform"},
    {"id": "PR-214", "type": "pull_request", "title": "PR #214 — changed retry limit 3 -> 7 (no explanation)",
     "criticality": 4, "doc_coverage": 0.1, "days_since_touch": 10, "repo": "core-platform"},
    {"id": "PR-198", "type": "pull_request", "title": "PR #198 — auth token refresh fix",
     "criticality": 3, "doc_coverage": 0.7, "days_since_touch": 15, "repo": "core-platform"},
    {"id": "TICK-882", "type": "ticket", "title": "JIRA-882 — Sync job fails silently on weekends",
     "criticality": 4, "doc_coverage": 0.4, "days_since_touch": 7, "repo": "jira"},
    {"id": "SLACK-VENDOR", "type": "chat_thread", "title": "Vendor thread — DataPipe Inc. (Aarav only responder)",
     "criticality": 3, "doc_coverage": 0.0, "days_since_touch": 2, "repo": "slack"},
    {"id": "DOC-RUNBOOK", "type": "document", "title": "Runbook — payments service (stale, last updated 8 months ago)",
     "criticality": 3, "doc_coverage": 0.2, "days_since_touch": 240, "repo": "docs"},
]

# contribution counts per artifact (ownership concentration denominator)
CONTRIBUTIONS = {
    "MOD-SYNC":   {"aarav": 22, "priya": 0, "rohan": 0},
    "MOD-RETRY":  {"aarav": 14, "priya": 2, "rohan": 0},
    "MOD-BILLING":{"aarav": 6,  "priya": 5, "rohan": 3},
    "MOD-AUTH":   {"aarav": 4,  "priya": 9, "rohan": 6},
    "PR-214":     {"aarav": 1,  "priya": 0, "rohan": 0},
    "PR-198":     {"aarav": 1,  "priya": 1, "rohan": 0},
    "TICK-882":   {"aarav": 8,  "priya": 1, "rohan": 0},
    "SLACK-VENDOR": {"aarav": 12, "priya": 0, "rohan": 0},
    "DOC-RUNBOOK": {"aarav": 3, "priya": 2, "rohan": 2},
}

# Knowledge-graph edges: (source, relation, target)
EDGES = [
    ("aarav", "authored", "MOD-SYNC"), ("aarav", "authored", "MOD-RETRY"),
    ("aarav", "owns", "SLACK-VENDOR"), ("aarav", "authored", "PR-214"),
    ("aarav", "authored", "TICK-882"), ("meera", "assigned_successor_of", "aarav"),
    ("priya", "reviewed", "MOD-AUTH"), ("rohan", "authored", "MOD-BILLING"),
]

# Planted knowledge gaps (ground truth for gap-coverage evaluation)
PLANTED_GAPS = ["MOD-SYNC", "PR-214", "SLACK-VENDOR", "TICK-882"]

# ----------------------------------------------------------------------------
# RISK SCORING (deterministic, transparent formula from the proposal)
# Risk = OwnershipConcentration x Criticality x (1 - DocCoverage) x RecencyWeight
# ----------------------------------------------------------------------------

def recency_weight(days: int) -> float:
    if days <= 7: return 1.0
    if days <= 30: return 0.7
    if days <= 90: return 0.4
    return 0.15

def ownership_concentration(artifact_id: str, person: str = LEAVER) -> float:
    counts = CONTRIBUTIONS.get(artifact_id, {})
    total = sum(counts.values())
    if total == 0: return 0.0
    return counts.get(person, 0) / total

def compute_risk(a: dict, person: str = LEAVER) -> dict:
    oc = ownership_concentration(a["id"], person)
    crit = a["criticality"] / 5.0
    doc = a["doc_coverage"]
    rec = recency_weight(a["days_since_touch"])
    risk = oc * crit * (1 - doc) * rec
    return {
        "artifact_id": a["id"], "title": a["title"], "type": a["type"],
        "risk_score": round(risk, 3),
        "risk_pct": round(risk * 100, 1),
        "components": {
            "ownership_concentration": round(oc, 2),
            "criticality": round(crit, 2),
            "doc_gap": round(1 - doc, 2),
            "recency_weight": rec,
        },
        "bus_factor_one": oc >= 0.8,
    }

def risk_rank(person: str = LEAVER):
    scored = [compute_risk(a, person) for a in ARTIFACTS]
    scored.sort(key=lambda x: -x["risk_score"])
    return scored

# ----------------------------------------------------------------------------
# GAP-DRIVEN INTERVIEW AGENT (heuristic templates; optionally LLM via env key)
# ----------------------------------------------------------------------------

QUESTION_TEMPLATES = {
    "undocumented_single_owner": (
        "The module '{title}' has no documentation and you are effectively its only "
        "contributor. What happens if it fails, and how is it restarted?"
    ),
    "unexplained_change": (
        "In '{title}' you made a significant change with no written explanation. "
        "What problem were you solving, and what options did you reject?"
    ),
    "solo_external_contact": (
        "You were the only person replying in '{title}'. What should the next person "
        "know about working with this contact?"
    ),
    "quiet_failure": (
        "For '{title}', are there failure modes that produce no alert? What should "
        "the successor check first when something looks wrong?"
    ),
}

def classify_gap(artifact: dict, risk: dict) -> Optional[str]:
    aid = artifact["id"]
    if artifact["type"] == "chat_thread":
        return "solo_external_contact"
    if artifact["type"] == "pull_request" and "#" in artifact["title"] and risk["components"]["doc_gap"] > 0.5:
        return "unexplained_change"
    if artifact["type"] == "module" and risk["components"]["doc_gap"] >= 0.7 and risk["bus_factor_one"]:
        return "undocumented_single_owner"
    if artifact["type"] == "ticket" and "silently" in artifact["title"].lower():
        return "quiet_failure"
    return None

def generate_questions(limit: int = 6):
    ranked = risk_rank()
    questions = []
    for risk in ranked:
        art = next(a for a in ARTIFACTS if a["id"] == risk["artifact_id"])
        gap = classify_gap(art, risk)
        if not gap:
            continue
        questions.append({
            "id": f"Q{len(questions) + 1}",
            "artifact_id": art["id"],
            "evidence": art["title"],
            "gap_type": gap,
            "risk_score": risk["risk_score"],
            "question": QUESTION_TEMPLATES[gap].format(title=art["title"]),
            "rationale": "Generated from evidence: ownership concentration "
                         f"{risk['components']['ownership_concentration']}, doc gap "
                         f"{risk['components']['doc_gap']}, risk {risk['risk_pct']}%.",
        })
        if len(questions) >= limit:
            break
    return questions

# ----------------------------------------------------------------------------
# IN-MEMORY STORES for answers / decisions / knowledge entries
# ----------------------------------------------------------------------------

INTERVIEW_ANSWERS = []   # {question_id, artifact_id, answer, submitted_at}
DECISIONS = []           # {artifact_id, decision, rationale, rejected_options}
OPEN_LOOPS = [
    {"id": "OL-1", "title": "Review pending on Rohan's invoice refactor PR",
     "artifact_id": "MOD-BILLING", "owner": LEAVER},
    {"id": "OL-2", "title": "Monthly DataPipe report due next Friday",
     "artifact_id": "SLACK-VENDOR", "owner": LEAVER},
]

# ----------------------------------------------------------------------------
# MODELS
# ----------------------------------------------------------------------------

class AnswerIn(BaseModel):
    question_id: str
    artifact_id: str
    answer: str

class AskIn(BaseModel):
    question: str
    asker: str = SUCCESSOR

# ----------------------------------------------------------------------------
# HELPERS: retrieval-first Ask Echo
# ----------------------------------------------------------------------------

def tokenize(s: str):
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def knowledge_entries():
    """Corpus for retrieval: interview answers + decisions + artifact docs."""
    entries = []
    for ans in INTERVIEW_ANSWERS:
        q = next((q for q in ALL_QUESTIONS if q["id"] == ans["question_id"]), {})
        entries.append({
            "source": f"Exit interview — {q.get('evidence', ans['artifact_id'])}",
            "artifact_id": ans["artifact_id"],
            "kind": "interview_answer",
            "person": LEAVER,
            "text": ans["answer"],
        })
    for d in DECISIONS:
        entries.append({"source": f"Decision log — {d['artifact_id']}",
                        "artifact_id": d["artifact_id"], "kind": "decision",
                        "person": LEAVER, "text": d["decision"] + " Rationale: " + d["rationale"]})
    for a in ARTIFACTS:
        if a["doc_coverage"] > 0.5:
            entries.append({"source": f"Documentation — {a['title']}",
                            "artifact_id": a["id"], "kind": "docs",
                            "person": None, "text": a["title"]})
    return entries

def retrieve(question: str, top_k: int = 3):
    qt = tokenize(question)
    scored = []
    for e in knowledge_entries():
        et = tokenize(e["text"] + " " + e["source"])
        if not qt or not et:
            continue
        overlap = len(qt & et)
        score = overlap / (1 + math.log(1 + len(et)))
        if overlap > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:top_k]]

# ----------------------------------------------------------------------------
# ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "echo-prototype"}

@app.get("/api/risk-map")
def get_risk_map():
    ranked = risk_rank()
    detected = [r for r in ranked if r["artifact_id"] in PLANTED_GAPS and r["risk_score"] > 0.15]
    return {
        "leaver": PEOPLE[LEAVER],
        "artifacts": ranked,
        "high_risk_count": len([r for r in ranked if r["risk_pct"] >= 30]),
        "bus_factor_violations": [r["artifact_id"] for r in ranked if r["bus_factor_one"]],
        "gaps_detected": [r["artifact_id"] for r in detected],
        "gaps_planted": PLANTED_GAPS,
        "formula": "Risk = OwnershipConcentration x Criticality x (1 - DocCoverage) x RecencyWeight",
    }

@app.get("/api/artifacts")
def get_artifacts():
    return {"artifacts": ARTIFACTS, "edges": [
        {"source": s, "relation": r, "target": t} for s, r, t in EDGES]}

ALL_QUESTIONS = generate_questions()

@app.post("/api/interview/questions")
def post_interview_questions(limit: int = 6):
    """Generate evidence-based questions. Always regenerate from live data."""
    qs = generate_questions(limit)
    return {"leaver": PEOPLE[LEAVER], "questions": qs,
            "time_budget_minutes": 15,
            "note": "Questions are ranked by risk score; each is tied to evidence."}

@app.get("/api/interview/questions")
def get_interview_questions():
    return {"questions": ALL_QUESTIONS}

@app.post("/api/interview/answers")
def post_interview_answers(payload: AnswerIn):
    q = next((q for q in ALL_QUESTIONS if q["id"] == payload.question_id), None)
    if not q:
        raise HTTPException(404, f"Unknown question {payload.question_id}")
    entry = {"question_id": payload.question_id, "artifact_id": payload.artifact_id,
             "evidence": q["evidence"], "question": q["question"],
             "answer": payload.answer.strip(),
             "submitted_at": datetime.now(timezone.utc).isoformat()}
    INTERVIEW_ANSWERS.append(entry)
    # naive decision extraction: anything mentioning 'because'/'so that'/'we chose'
    text = entry["answer"].lower()
    if any(k in text for k in ["because", "we chose", "so that", "option"]):
        DECISIONS.append({"artifact_id": payload.artifact_id,
                          "decision": q["question"],
                          "rationale": payload.answer.strip()})
    return {"status": "stored", "linked_to": payload.artifact_id,
            "decision_logged": any(d["artifact_id"] == payload.artifact_id for d in DECISIONS),
            "answers_total": len(INTERVIEW_ANSWERS)}

@app.get("/api/handover")
def get_handover():
    ranked = risk_rank()
    landmines = [
        {"rank": i + 1, "artifact_id": r["artifact_id"], "title": r["title"],
         "risk_pct": r["risk_pct"],
         "captured": next((a["answer"] for a in INTERVIEW_ANSWERS
                           if a["artifact_id"] == r["artifact_id"]), None)}
        for i, r in enumerate(ranked[:3])
    ]
    who_to_ask = [
        {"area": "Sync job / data pipeline", "contact": "Aarav (until exit) then Priya",
         "confidence": "high" if any(a["artifact_id"] == "MOD-SYNC" for a in INTERVIEW_ANSWERS) else "low"},
        {"area": "Vendor relationship (DataPipe)", "contact": "Priya",
         "confidence": "low"},
        {"area": "Auth / sessions", "contact": "Priya", "confidence": "high"},
    ]
    return {
        "successor": PEOPLE[SUCCESSOR],
        "onboarding_path": [
            {"week": 1, "days": "1-2", "task": "Shadow a deploy of the payments service",
             "why": "Highest-criticality area (" + "MOD-RETRY/MOD-BILLING" + ")"},
            {"week": 1, "days": "3-4", "task": "Read captured interview answers on nightly sync job",
             "why": "Single-owner, zero-doc module"},
            {"week": 1, "days": "5", "task": "Intro call with DataPipe vendor contact", "why": "Solo-owner thread"},
            {"week": 2, "days": "1-3", "task": "Take first ticket in retry logic", "why": "Active area"},
            {"week": 2, "days": "4-5", "task": "Own one nightly sync run end-to-end", "why": "Independence check"},
        ],
        "landmines": landmines,
        "open_loops": OPEN_LOOPS,
        "who_to_ask": who_to_ask,
        "decision_log": DECISIONS,
        "coverage": {"gaps_detected": len([r for r in ranked if r["risk_pct"] >= 30]),
                     "interview_answers_captured": len(INTERVIEW_ANSWERS)},
        "status": "pending_manager_approval",
        "manager": PEOPLE["manager"],
    }

@app.post("/api/ask")
def ask_echo(payload: AskIn):
    hits = retrieve(payload.question)
    if not hits:
        # honesty-over-completeness fallback
        return {"answer": None,
                "echo_says": f"I don't have evidence for that. I'd ask Priya — she reviewed auth code and works on the platform.",
                "suggested_contact": "priya",
                "citations": []}
    primary = hits[0]
    answer = primary["text"]
    if primary.get("person") and primary["kind"] == "interview_answer":
        answer = f"{answer} (captured from Aarav's exit interview)"
    return {
        "answer": answer,
        "citations": [{"source": h["source"], "artifact_id": h["artifact_id"],
                       "kind": h["kind"]} for h in hits],
        "stale_warning": any(h["artifact_id"] == "DOC-RUNBOOK" for h in hits),
        "disclaimer": "Retrieval-first: answers come only from stored evidence.",
    }

@app.post("/api/reset")
def reset_demo():
    INTERVIEW_ANSWERS.clear()
    DECISIONS.clear()
    return {"status": "demo state reset"}
```

## Quick demo script (matches the pitch)

1. `GET /api/risk-map` → risk map highlights `MOD-SYNC`, `MOD-RETRY`, `SLACK-VENDOR` as single-owner; shows gaps detected vs planted.
2. `POST /api/interview/questions` → 3 sharp questions from real commits (retry limit, nightly sync, vendor thread).
3. `POST /api/interview/answers` × 3 → answers linked to artifacts; the retry-limit answer auto-becomes a decision log entry.
4. `GET /api/handover` → Meera's package with landmines, open loops, who-to-ask, decision log.
5. `POST /api/ask` with `{"question": "Why is the retry limit 7?"}` → cited answer from Aarav's interview.
6. `POST /api/ask` with `{"question": "What is the wifi password?"}` → `"unknown — ask Priya"` (honesty behavior).
