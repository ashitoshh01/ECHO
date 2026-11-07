"""
Echo: A Knowledge-Risk Engine for Seamless Team Handovers
Backend API powered by SQLite persistent storage, real Git scanner,
and deterministic knowledge-risk engine.
"""

import os
import math
import re
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import init_db, get_db, get_active_project
from fixtures.demo_seed import seed_demo_data, DEMO_PROJECT_ID
from services.risk_engine import calculate_project_risk
from services.interview_engine import (
    sync_project_questions,
    retrieve_answers,
    get_knowledge_entries,
)
from services.connectors import get_connectors_status
from services.git_scanner import scan_git_repository

app = FastAPI(title="Echo — Knowledge-Risk Engine", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------------
# STARTUP INITIALIZATION
# ----------------------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    init_db()
    seed_demo_data(reset=False)
    # Automatically scan the live local workspace repository and set it active
    try:
        scan_git_repository(repo_path=None, project_id="proj-live")
        sync_project_questions("proj-live")
    except Exception as e:
        print("Live git scan notice:", e)

    try:
        sync_project_questions(DEMO_PROJECT_ID)
    except Exception as e:
        print("Initial questions sync notice:", e)

# ----------------------------------------------------------------------------
# REQUEST MODELS
# ----------------------------------------------------------------------------
class ProjectSelectIn(BaseModel):
    project_id: str

class GitScanIn(BaseModel):
    repo_path: Optional[str] = None
    leaver_name: Optional[str] = None

class AnswerIn(BaseModel):
    question_id: str
    artifact_id: str
    answer: str
    submitted_by: Optional[str] = None

class AskIn(BaseModel):
    question: str
    asker: Optional[str] = None
    project_id: Optional[str] = None

class ApproveHandoverIn(BaseModel):
    approved_by: Optional[str] = "Neha (Engineering Manager)"
    project_id: Optional[str] = None

# ----------------------------------------------------------------------------
# CORE / HEALTH & PROJECTS
# ----------------------------------------------------------------------------
@app.get("/api/health")
def health():
    active = get_active_project()
    return {
        "status": "ok",
        "service": "echo-knowledge-risk-engine",
        "version": "0.2.0",
        "database": "sqlite_connected",
        "active_project": active,
        "mode": active.get("mode") if active else "demo",
    }

@app.get("/api/projects")
def list_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY created_at ASC").fetchall()
    conn.close()
    return {"projects": [dict(r) for r in rows]}

@app.post("/api/projects/select")
def select_project(payload: ProjectSelectIn):
    conn = get_db()
    with conn:
        conn.execute("UPDATE projects SET is_active = 0")
        res = conn.execute("UPDATE projects SET is_active = 1 WHERE id = ?", (payload.project_id,))
        if res.rowcount == 0:
            raise HTTPException(404, f"Project {payload.project_id} not found")
    conn.close()
    sync_project_questions(payload.project_id)
    return {"status": "selected", "active_project": get_active_project()}

@app.post("/api/projects/scan-git")
def scan_git(payload: GitScanIn):
    try:
        res = scan_git_repository(
            repo_path=payload.repo_path,
            project_id="proj-live",
            leaver_name=payload.leaver_name
        )
        sync_project_questions("proj-live")
        return res
    except Exception as e:
        raise HTTPException(400, f"Git scan failed: {str(e)}")

@app.get("/api/projects/{project_id}/repositories")
def get_project_repositories(project_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM repositories WHERE project_id = ?", (project_id,)).fetchall()
    conn.close()
    return {"repositories": [dict(r) for r in rows]}

@app.get("/api/team-members")
def get_team_members(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    conn = get_db()
    rows = conn.execute("SELECT * FROM team_members WHERE project_id = ?", (p_id,)).fetchall()
    conn.close()
    return {"team_members": [dict(r) for r in rows]}

# ----------------------------------------------------------------------------
# RISK MAP & ARTIFACTS
# ----------------------------------------------------------------------------
@app.get("/api/risk-map")
def get_risk_map(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    return calculate_project_risk(p_id)

@app.get("/api/artifacts")
def get_artifacts(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    conn = get_db()
    art_rows = conn.execute("SELECT * FROM artifacts WHERE project_id = ?", (p_id,)).fetchall()
    edge_rows = conn.execute("SELECT source, relation, target FROM graph_edges WHERE project_id = ?", (p_id,)).fetchall()
    conn.close()
    return {
        "artifacts": [dict(r) for r in art_rows],
        "edges": [dict(r) for r in edge_rows]
    }

@app.get("/api/artifacts/{artifact_id}")
def get_artifact_details(artifact_id: str, project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    conn = get_db()
    art_row = conn.execute("SELECT * FROM artifacts WHERE id = ? AND project_id = ?", (artifact_id, p_id)).fetchone()
    if not art_row:
        conn.close()
        raise HTTPException(404, f"Artifact {artifact_id} not found")
    
    contrib_rows = conn.execute("""
        SELECT t.name, t.id as person_id, c.count
        FROM contributions c
        JOIN team_members t ON c.person_id = t.id
        WHERE c.artifact_id = ?
    """, (artifact_id,)).fetchall()

    edges_rows = conn.execute("""
        SELECT source, relation, target FROM graph_edges
        WHERE project_id = ? AND (source = ? OR target = ?)
    """, (p_id, artifact_id, artifact_id)).fetchall()

    conn.close()
    return {
        "artifact": dict(art_row),
        "contributions": [dict(r) for r in contrib_rows],
        "edges": [dict(r) for r in edges_rows]
    }

# ----------------------------------------------------------------------------
# EXIT INTERVIEW
# ----------------------------------------------------------------------------
@app.get("/api/interview/questions")
def get_interview_questions(limit: int = 6, project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    sync_project_questions(p_id, limit=limit)
    conn = get_db()
    leaver_row = conn.execute("SELECT * FROM team_members WHERE project_id = ? AND is_leaver = 1", (p_id,)).fetchone()
    leaver = dict(leaver_row) if leaver_row else {"name": "Team Member", "role": "Engineer"}
    q_rows = conn.execute(
        "SELECT * FROM interview_questions WHERE project_id = ? ORDER BY order_index ASC LIMIT ?",
        (p_id, limit)
    ).fetchall()
    conn.close()
    return {
        "leaver": leaver,
        "questions": [dict(r) for r in q_rows],
        "time_budget_minutes": 15,
        "note": "Ranked by deterministic risk score; grounded in evidence."
    }

@app.post("/api/interview/questions/generate")
def generate_questions_endpoint(limit: int = 6, project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    conn = get_db()
    conn.execute("DELETE FROM interview_questions WHERE project_id = ?", (p_id,))
    conn.commit()
    conn.close()
    sync_project_questions(p_id, limit=limit)
    return get_interview_questions(limit=limit, project_id=p_id)

@app.post("/api/interview/answers")
def submit_interview_answer(payload: AnswerIn):
    conn = get_db()
    q_row = conn.execute("SELECT * FROM interview_questions WHERE id = ?", (payload.question_id,)).fetchone()
    if not q_row:
        conn.close()
        raise HTTPException(404, f"Question {payload.question_id} not found")

    now = datetime.now(timezone.utc).isoformat()
    project_id = q_row["project_id"]

    # Check leaver name
    leaver_name = payload.submitted_by
    if not leaver_name:
        l_row = conn.execute("SELECT name FROM team_members WHERE project_id = ? AND is_leaver = 1", (project_id,)).fetchone()
        leaver_name = l_row["name"] if l_row else "Leaver"

    with conn:
        # Check existing answer
        existing = conn.execute("SELECT id FROM interview_answers WHERE question_id = ?", (payload.question_id,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE interview_answers
                SET answer = ?, submitted_at = ?, submitted_by = ?
                WHERE id = ?
            """, (payload.answer.strip(), now, leaver_name, existing["id"]))
            answer_id = existing["id"]
        else:
            cur = conn.execute("""
                INSERT INTO interview_answers (question_id, artifact_id, evidence, question, answer, submitted_by, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (payload.question_id, payload.artifact_id, q_row["evidence"], q_row["question"], payload.answer.strip(), leaver_name, now))
            answer_id = cur.lastrowid

        # Real decision extraction
        text = payload.answer.lower()
        decision_logged = False
        if any(marker in text for marker in ["because", "we chose", "so that", "option", "instead of", "tradeoff"]):
            conn.execute("""
                INSERT OR REPLACE INTO decisions (project_id, artifact_id, decision, rationale, extracted_from_answer_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (project_id, payload.artifact_id, q_row["question"], payload.answer.strip(), answer_id, now))
            decision_logged = True

        total_ans = conn.execute("SELECT COUNT(*) as c FROM interview_answers a JOIN interview_questions q ON a.question_id = q.id WHERE q.project_id = ?", (project_id,)).fetchone()["c"]

    conn.close()
    return {
        "status": "stored",
        "linked_to": payload.artifact_id,
        "decision_logged": decision_logged,
        "answers_total": total_ans
    }

@app.get("/api/interview/answers")
def get_interview_answers(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, q.gap_type, q.risk_score
        FROM interview_answers a
        JOIN interview_questions q ON a.question_id = q.id
        WHERE q.project_id = ?
        ORDER BY a.submitted_at DESC
    """, (p_id,)).fetchall()
    conn.close()
    return {"answers": [dict(r) for r in rows], "total": len(rows)}

# ----------------------------------------------------------------------------
# HANDOVER PACKAGE
# ----------------------------------------------------------------------------
@app.get("/api/handover")
def get_handover_package(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    conn = get_db()

    pkg_row = conn.execute("SELECT * FROM handover_packages WHERE project_id = ?", (p_id,)).fetchone()
    if not pkg_row:
        # Default package if not yet created
        l_row = conn.execute("SELECT id FROM team_members WHERE project_id = ? AND is_leaver = 1", (p_id,)).fetchone()
        s_row = conn.execute("SELECT id FROM team_members WHERE project_id = ? AND is_successor = 1", (p_id,)).fetchone()
        l_id = l_row["id"] if l_row else "leaver"
        s_id = s_row["id"] if s_row else "successor"
        conn.execute("""
            INSERT INTO handover_packages (id, project_id, leaver_id, successor_id, manager_id, status)
            VALUES (?, ?, ?, ?, 'manager', 'pending_manager_approval')
        """, (f"pkg-{p_id}", p_id, l_id, s_id))
        conn.commit()
        pkg_row = conn.execute("SELECT * FROM handover_packages WHERE project_id = ?", (p_id,)).fetchone()

    pkg_id = pkg_row["id"]

    # Successor & Manager
    succ_row = conn.execute("SELECT * FROM team_members WHERE id = ? AND project_id = ?", (pkg_row["successor_id"], p_id)).fetchone()
    if not succ_row:
        succ_row = conn.execute("SELECT * FROM team_members WHERE project_id = ? AND is_successor = 1", (p_id,)).fetchone()
    successor = dict(succ_row) if succ_row else {"name": "Meera", "role": "Backend Engineer (successor)"}

    mgr_row = conn.execute("SELECT * FROM team_members WHERE project_id = ? AND is_manager = 1", (p_id,)).fetchone()
    manager = dict(mgr_row) if mgr_row else {"name": "Neha", "role": "Engineering Manager"}

    # Onboarding Tasks
    tasks_rows = conn.execute("SELECT * FROM onboarding_tasks WHERE package_id = ? ORDER BY order_index ASC", (pkg_id,)).fetchall()

    # Open Loops
    loops_rows = conn.execute("SELECT * FROM open_loops WHERE package_id = ?", (pkg_id,)).fetchall()

    # Who to Ask
    ask_rows = conn.execute("SELECT * FROM who_to_ask WHERE package_id = ?", (pkg_id,)).fetchall()

    # Decisions
    dec_rows = conn.execute("SELECT * FROM decisions WHERE project_id = ? ORDER BY created_at DESC", (p_id,)).fetchall()

    # Answers map for landmines
    ans_rows = conn.execute("""
        SELECT a.artifact_id, a.answer
        FROM interview_answers a
        JOIN interview_questions q ON a.question_id = q.id
        WHERE q.project_id = ?
    """, (p_id,)).fetchall()
    answers_map = {r["artifact_id"]: r["answer"] for r in ans_rows}

    conn.close()

    # Risk ranking for Landmines
    risk_data = calculate_project_risk(p_id)
    top_risks = risk_data["artifacts"][:3]

    landmines = [
        {
            "rank": i + 1,
            "artifact_id": r["artifact_id"],
            "title": r["title"],
            "risk_pct": r["risk_pct"],
            "captured": answers_map.get(r["artifact_id"])
        }
        for i, r in enumerate(top_risks)
    ]

    return {
        "package_id": pkg_id,
        "successor": successor,
        "manager": manager,
        "status": pkg_row["status"],
        "approved_at": pkg_row["approved_at"],
        "approved_by": pkg_row["approved_by"],
        "onboarding_path": [dict(t) for t in tasks_rows],
        "landmines": landmines,
        "open_loops": [dict(l) for l in loops_rows],
        "who_to_ask": [dict(w) for w in ask_rows],
        "decision_log": [dict(d) for d in dec_rows],
        "coverage": {
            "gaps_detected": risk_data["high_risk_count"],
            "interview_answers_captured": len(answers_map)
        }
    }

@app.post("/api/handover/approve")
def approve_handover(payload: ApproveHandoverIn):
    p_id = payload.project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            UPDATE handover_packages
            SET status = 'approved', approved_at = ?, approved_by = ?
            WHERE project_id = ?
        """, (now, payload.approved_by, p_id))
    conn.close()
    return {"status": "approved", "approved_at": now, "approved_by": payload.approved_by}

@app.post("/api/handover/task/{task_id}/toggle")
def toggle_onboarding_task(task_id: int):
    conn = get_db()
    with conn:
        row = conn.execute("SELECT is_completed FROM onboarding_tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, f"Task {task_id} not found")
        new_state = 0 if row["is_completed"] == 1 else 1
        conn.execute("UPDATE onboarding_tasks SET is_completed = ? WHERE id = ?", (new_state, task_id))
    conn.close()
    return {"task_id": task_id, "is_completed": bool(new_state)}

# ----------------------------------------------------------------------------
# ASK ECHO (CONVERSATIONS & RETRIEVAL)
# ----------------------------------------------------------------------------
@app.get("/api/conversations")
def get_conversations(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE project_id = ? ORDER BY created_at ASC",
        (p_id,)
    ).fetchall()
    conn.close()
    messages = []
    for r in rows:
        import json
        cit = []
        if r["citations_json"]:
            try: cit = json.loads(r["citations_json"])
            except: pass
        messages.append({
            "id": r["id"],
            "role": r["role"],
            "text": r["text"],
            "answer": r["answer"],
            "echo_says": r["echo_says"],
            "suggested_contact": r["suggested_contact"],
            "stale_warning": bool(r["stale_warning"]),
            "citations": cit,
            "created_at": r["created_at"],
        })
    return {"messages": messages}

@app.post("/api/ask")
def ask_echo_endpoint(payload: AskIn):
    p_id = payload.project_id or (get_active_project() or {}).get("id") or DEMO_PROJECT_ID
    hits = retrieve_answers(payload.question, p_id)
    now = datetime.now(timezone.utc).isoformat()
    import json

    conn = get_db()

    # Save user message
    with conn:
        conn.execute("""
            INSERT INTO chat_messages (project_id, role, text, created_at)
            VALUES (?, 'user', ?, ?)
        """, (p_id, payload.question.strip(), now))

    if not hits:
        # Dynamic honesty fallback
        w_row = conn.execute("SELECT contact FROM who_to_ask WHERE package_id = (SELECT id FROM handover_packages WHERE project_id = ?) LIMIT 1", (p_id,)).fetchone()
        suggested = w_row["contact"] if w_row else "Priya"
        fallback_msg = f"I don't have verified evidence for that. I'd ask {suggested} — platform engineer familiar with this subsystem."

        with conn:
            conn.execute("""
                INSERT INTO chat_messages (project_id, role, text, answer, echo_says, suggested_contact, stale_warning, citations_json, created_at)
                VALUES (?, 'echo', ?, NULL, ?, ?, 0, '[]', ?)
            """, (p_id, fallback_msg, fallback_msg, suggested.lower().split()[0], now))

        conn.close()
        return {
            "answer": None,
            "echo_says": fallback_msg,
            "suggested_contact": suggested.lower().split()[0],
            "citations": []
        }

    primary = hits[0]
    answer = primary["text"]
    if primary.get("person") and primary["kind"] == "interview_answer":
        answer = f"{answer} (captured from {primary['person']}'s exit interview)"

    citations = [
        {"source": h["source"], "artifact_id": h["artifact_id"], "kind": h["kind"]}
        for h in hits
    ]
    stale_warning = any(h["artifact_id"] == "DOC-RUNBOOK" for h in hits)

    with conn:
        conn.execute("""
            INSERT INTO chat_messages (project_id, role, text, answer, echo_says, suggested_contact, stale_warning, citations_json, created_at)
            VALUES (?, 'echo', ?, ?, ?, NULL, ?, ?, ?)
        """, (p_id, answer, answer, answer, 1 if stale_warning else 0, json.dumps(citations), now))

    conn.close()
    return {
        "answer": answer,
        "citations": citations,
        "stale_warning": stale_warning,
        "disclaimer": "Retrieval-first: answers come only from stored evidence.",
    }

# ----------------------------------------------------------------------------
# CONNECTORS & RESET
# ----------------------------------------------------------------------------
@app.get("/api/connectors")
def get_connectors():
    return {"connectors": get_connectors_status()}

@app.post("/api/reset")
def reset_demo():
    seed_demo_data(reset=True)
    return {"status": "demo benchmark state reset"}

# ----------------------------------------------------------------------------
# SERVE PRODUCTION FRONTEND
# ----------------------------------------------------------------------------
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
dist_dir = os.path.join(frontend_dir, "dist")
dist_assets = os.path.join(dist_dir, "assets")

if os.path.exists(dist_assets):
    app.mount("/assets", StaticFiles(directory=dist_assets), name="assets")

@app.get("/")
def serve_frontend_root():
    if os.path.exists(os.path.join(dist_dir, "index.html")):
        return FileResponse(os.path.join(dist_dir, "index.html"))
    if os.path.exists(os.path.join(frontend_dir, "index.html")):
        return FileResponse(os.path.join(frontend_dir, "index.html"))
    return {"service": "Echo Knowledge-Risk Engine", "docs": "/docs"}
