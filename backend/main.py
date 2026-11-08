"""
Echo: A Knowledge-Risk Engine for Seamless Team Handovers
Backend API powered by SQLite persistent storage, real Git scanner,
native GitHub integration, and deterministic knowledge-risk engine.
"""

import os
import math
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Body, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from database import init_db, get_db, get_active_project, reset_database
from fixtures.demo_seed import seed_demo_data, DEMO_PROJECT_ID
from services.risk_engine import calculate_project_risk
from services.interview_engine import (
    sync_project_questions,
    retrieve_answers,
    get_knowledge_entries,
)
from services.connectors import get_connectors_status
from services.git_scanner import scan_git_repository
from services import github_service as gh_svc
from services.asi_service import (
    get_asi_status,
    query_asi1,
    update_asi_env,
)

app = FastAPI(title="Echo — Knowledge-Risk Engine", version="0.3.0")

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

# ----------------------------------------------------------------------------
# REQUEST MODELS
# ----------------------------------------------------------------------------
class ProjectSelectIn(BaseModel):
    project_id: str

class GitScanIn(BaseModel):
    repo_path: Optional[str] = None
    leaver_name: Optional[str] = None

class GitHubConnectIn(BaseModel):
    token: str = Field(..., description="GitHub Personal Access Token, OAuth token, or App token")
    auth_type: Optional[str] = Field("token", description="Type of credential: 'token', 'pat', 'oauth', 'app'")

class GitHubIngestIn(BaseModel):
    owner: Optional[str] = Field(None, description="Repository owner or organization")
    repo: Optional[str] = Field(None, description="Repository name")
    url: Optional[str] = Field(None, description="GitHub repository URL (e.g. https://github.com/owner/repo)")
    branch: Optional[str] = Field("main", description="Branch name to clone and analyze")
    leaver_name: Optional[str] = Field(None, description="Optional name of departing engineer")
    project_id: Optional[str] = Field(None, description="Target project ID")
    sync: Optional[bool] = Field(False, description="Whether to wait synchronously for ingestion")

class AnswerIn(BaseModel):
    question_id: str
    artifact_id: str
    answer: str
    submitted_by: Optional[str] = None

class AskIn(BaseModel):
    question: str
    asker: Optional[str] = None
    project_id: Optional[str] = None

class AiConfigIn(BaseModel):
    api_key: str
    model: Optional[str] = "asi1"


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
        "version": "0.3.0",
        "database": "sqlite_connected",
        "active_project": active,
        "mode": active.get("mode") if active else None,
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

@app.get("/api/projects/{project_id}/commits")
def get_project_commits(project_id: str):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM commits WHERE project_id = ? ORDER BY committed_at DESC LIMIT 50",
        (project_id,)
    ).fetchall()
    conn.close()
    return {"commits": [dict(r) for r in rows]}

@app.get("/api/team-members")
def get_team_members(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id")
    if not p_id:
        return {"team_members": []}
    conn = get_db()
    rows = conn.execute("SELECT * FROM team_members WHERE project_id = ?", (p_id,)).fetchall()
    conn.close()
    return {"team_members": [dict(r) for r in rows]}

# ----------------------------------------------------------------------------
# GITHUB INTEGRATION: AUTHENTICATION
# ----------------------------------------------------------------------------
@app.get("/api/github/status")
def get_github_status():
    """Returns GitHub authentication status, connected user, scopes, and rate limits."""
    return gh_svc.get_github_connection_status()

@app.post("/api/github/connect")
def connect_github(payload: GitHubConnectIn):
    """
    Validates and stores GitHub credentials.
    Access tokens are never logged and never returned in API responses.
    """
    try:
        res = gh_svc.save_github_credentials(payload.token, payload.auth_type or "token")
        return res
    except PermissionError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"GitHub authentication failed: {gh_svc.redact_secrets(str(e))}")

@app.post("/api/github/disconnect")
def disconnect_github_endpoint():
    """Disconnects GitHub integration and clears stored credentials."""
    return gh_svc.disconnect_github()

# ----------------------------------------------------------------------------
# GITHUB INTEGRATION: REPOSITORY SELECTION
# ----------------------------------------------------------------------------
@app.get("/api/github/repositories")
def get_github_repositories(
    search: Optional[str] = Query(None, description="Search filter for repository name or description"),
    visibility: Optional[str] = Query(None, description="Repository visibility: 'all', 'public', or 'private'"),
    sort: str = Query("updated", description="Sort order: 'updated', 'pushed', or 'full_name'"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Items per page")
):
    """Lists accessible GitHub repositories for the authenticated user."""
    try:
        return gh_svc.list_accessible_repositories(
            search=search,
            visibility=visibility,
            sort=sort,
            page=page,
            per_page=per_page
        )
    except PermissionError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to list repositories: {gh_svc.redact_secrets(str(e))}")

@app.get("/api/github/repositories/{owner}/{repo}")
def get_github_repo_metadata(owner: str, repo: str):
    """Fetches metadata, default branch, permissions, and size for a GitHub repository."""
    try:
        return gh_svc.get_repository_metadata(owner, repo)
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, gh_svc.redact_secrets(str(e)))

@app.get("/api/github/repositories/{owner}/{repo}/branches")
def get_github_repo_branches(owner: str, repo: str):
    """Lists available branches for a GitHub repository."""
    try:
        branches = gh_svc.list_repository_branches(owner, repo)
        return {"branches": branches, "count": len(branches)}
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, gh_svc.redact_secrets(str(e)))

# ----------------------------------------------------------------------------
# GITHUB INTEGRATION: INGESTION & BACKGROUND PROCESSING
# ----------------------------------------------------------------------------
@app.post("/api/repositories/github/ingest", status_code=status.HTTP_202_ACCEPTED)
def ingest_github_repository(
    payload: GitHubIngestIn,
    background_tasks: BackgroundTasks
):
    """
    Ingests a GitHub repository directly into Echo:
    1. Validates repository URL and authorization
    2. Validates ownership and branch
    3. Creates ingestion job record
    4. Executes isolated cloning, commits extraction, risk analysis, and question generation
    5. Returns job tracking ID and status
    """
    # URL or (owner, repo) parsing & SSRF validation
    owner = payload.owner
    repo = payload.repo

    if payload.url:
        try:
            owner, repo = gh_svc.validate_github_url(payload.url)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    elif owner and repo:
        try:
            owner = gh_svc.validate_owner_or_repo_name(owner, "Owner")
            repo = gh_svc.validate_owner_or_repo_name(repo, "Repository")
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Either a GitHub 'url' or both 'owner' and 'repo' must be provided."
        )

    # Validate branch
    try:
        branch = gh_svc.validate_branch_name(payload.branch or "main")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    # Pre-flight check: Verify repository existence and permissions
    try:
        repo_meta = gh_svc.get_repository_metadata(owner, repo)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"GitHub repository '{owner}/{repo}' not found.")
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Access denied for repository '{owner}/{repo}': {str(e)}")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Verification failed: {gh_svc.redact_secrets(str(e))}")

    # Defense-in-depth: Verify repository permissions
    perms = repo_meta.get("permissions") or {}
    if not perms.get("pull", True):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Access denied for repository '{owner}/{repo}': Read/pull permission required."
        )

    # Defense-in-depth: Verify repository size limit
    size_kb = repo_meta.get("size_kb", 0)
    if size_kb > gh_svc.MAX_REPO_SIZE_KB:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Repository size ({size_kb // 1024} MB) exceeds maximum allowed size ({gh_svc.MAX_REPO_SIZE_KB // 1024} MB)"
        )

    # Project ID
    project_id = payload.project_id or "proj-live"

    # Create tracked job
    job_id = gh_svc.create_ingestion_job(project_id, owner, repo, branch)

    # Run synchronously if explicitly requested (e.g. for testing)
    if payload.sync:
        gh_svc.run_github_ingest_pipeline(job_id, owner, repo, branch, payload.leaver_name, project_id)
        job_data = gh_svc.get_job_status(job_id)
        if job_data and job_data["status"] == "failed":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, job_data.get("error_message") or "Ingestion failed")
        return JSONResponse(status_code=status.HTTP_200_OK, content=job_data)

    # Asynchronous background execution
    background_tasks.add_task(
        gh_svc.run_github_ingest_pipeline,
        job_id,
        owner,
        repo,
        branch,
        payload.leaver_name,
        project_id
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "job_id": job_id,
            "status": "queued",
            "message": f"GitHub repository '{owner}/{repo}' ingestion queued for background processing.",
            "project_id": project_id,
            "repository": f"{owner}/{repo}",
            "branch": branch
        }
    )

@app.get("/api/repositories/github/ingest/{job_id}/status")
@app.get("/api/repositories/ingest/{job_id}/status")
def get_ingestion_job_status(job_id: str):
    """Returns current status, progress percentage, step, and results of an ingestion job."""
    job = gh_svc.get_job_status(job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Ingestion job '{job_id}' not found.")
    return job

# ----------------------------------------------------------------------------
# RISK MAP & ARTIFACTS
# ----------------------------------------------------------------------------
@app.get("/api/risk-map")
def get_risk_map(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id")
    return calculate_project_risk(p_id)

@app.get("/api/artifacts")
def get_artifacts(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id")
    if not p_id:
        return {"artifacts": [], "edges": []}
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
    p_id = project_id or (get_active_project() or {}).get("id")
    if not p_id:
        raise HTTPException(404, f"Artifact {artifact_id} not found")
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
    p_id = project_id or (get_active_project() or {}).get("id")
    if not p_id:
        return {
            "leaver": None,
            "questions": [],
            "time_budget_minutes": 15,
            "note": "No active project."
        }
    sync_project_questions(p_id, limit=limit)
    conn = get_db()
    leaver_row = conn.execute("SELECT * FROM team_members WHERE project_id = ? AND is_leaver = 1", (p_id,)).fetchone()
    leaver = dict(leaver_row) if leaver_row else None
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
    p_id = project_id or (get_active_project() or {}).get("id")
    if not p_id:
        return {
            "leaver": None,
            "questions": [],
            "time_budget_minutes": 15,
            "note": "No active project."
        }
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
    p_id = project_id or (get_active_project() or {}).get("id")
    if not p_id:
        return {"answers": [], "total": 0}
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
    p_id = project_id or (get_active_project() or {}).get("id")
    empty_package = {
        "package_id": None,
        "successor": None,
        "manager": None,
        "status": None,
        "approved_at": None,
        "approved_by": None,
        "onboarding_path": [],
        "landmines": [],
        "open_loops": [],
        "who_to_ask": [],
        "decision_log": [],
        "coverage": {
            "gaps_detected": 0,
            "interview_answers_captured": 0
        }
    }
    if not p_id:
        return empty_package

    conn = get_db()
    pkg_row = conn.execute("SELECT * FROM handover_packages WHERE project_id = ?", (p_id,)).fetchone()
    if not pkg_row:
        conn.close()
        return empty_package

    pkg_id = pkg_row["id"]

    # Successor & Manager
    succ_row = conn.execute("SELECT * FROM team_members WHERE id = ? AND project_id = ?", (pkg_row["successor_id"], p_id)).fetchone()
    if not succ_row:
        succ_row = conn.execute("SELECT * FROM team_members WHERE project_id = ? AND is_successor = 1", (p_id,)).fetchone()
    successor = dict(succ_row) if succ_row else None

    mgr_row = conn.execute("SELECT * FROM team_members WHERE project_id = ? AND is_manager = 1", (p_id,)).fetchone()
    manager = dict(mgr_row) if mgr_row else None

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
# ASK ECHO (AI ASSISTANT & RETRIEVAL)
# ----------------------------------------------------------------------------
@app.get("/api/ai/status")
def get_ai_status_endpoint():
    return get_asi_status()

@app.post("/api/ai/config")
def update_ai_config_endpoint(payload: AiConfigIn):
    success = update_asi_env(payload.api_key, payload.model)
    if not success:
        raise HTTPException(500, "Failed to update configuration in .env")
    return get_asi_status()

@app.get("/api/conversations")
def get_conversations(project_id: Optional[str] = None):
    p_id = project_id or (get_active_project() or {}).get("id")
    if not p_id:
        return {"messages": []}
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
        col_names = r.keys()
        messages.append({
            "id": r["id"],
            "role": r["role"],
            "text": r["text"],
            "answer": r["answer"],
            "echo_says": r["echo_says"],
            "suggested_contact": r["suggested_contact"],
            "stale_warning": bool(r["stale_warning"]),
            "citations": cit,
            "ai_provider": r["ai_provider"] if "ai_provider" in col_names else "asi1",
            "ai_model": r["ai_model"] if "ai_model" in col_names else "asi1",
            "created_at": r["created_at"],
        })
    return {"messages": messages}

@app.post("/api/ask")
async def ask_echo_endpoint(payload: AskIn):
    p_id = payload.project_id or (get_active_project() or {}).get("id")
    if not p_id:
        raise HTTPException(400, "No active project. Please ingest a repository first.")

    now = datetime.now(timezone.utc).isoformat()
    import json

    conn = get_db()

    # Save user message
    with conn:
        conn.execute("""
            INSERT INTO chat_messages (project_id, role, text, created_at)
            VALUES (?, 'user', ?, ?)
        """, (p_id, payload.question.strip(), now))

    # Fetch recent conversation turns
    history_rows = conn.execute("""
        SELECT role, text, answer, echo_says FROM chat_messages 
        WHERE project_id = ? ORDER BY id DESC LIMIT 6
    """, (p_id,)).fetchall()
    conversation_history = [dict(h) for h in reversed(history_rows)]

    # Query ASI:One AI with full project context
    result = await query_asi1(
        question=payload.question,
        project_id=p_id,
        asker=payload.asker,
        conversation_history=conversation_history
    )

    content = result.get("answer") or result.get("echo_says") or ""
    answer = result.get("answer")
    echo_says = result.get("echo_says")
    citations = result.get("citations") or []
    suggested_contact = result.get("suggested_contact")
    stale_warning = 1 if result.get("stale_warning") else 0
    ai_provider = result.get("ai_provider", "asi1")
    ai_model = result.get("ai_model", "asi1")

    # Save Echo response
    with conn:
        conn.execute("""
            INSERT INTO chat_messages (
                project_id, role, text, answer, echo_says, suggested_contact,
                stale_warning, citations_json, ai_provider, ai_model, created_at
            )
            VALUES (?, 'echo', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p_id,
            content,
            answer,
            echo_says,
            suggested_contact,
            stale_warning,
            json.dumps(citations),
            ai_provider,
            ai_model,
            datetime.now(timezone.utc).isoformat()
        ))

    conn.close()
    return result

# ----------------------------------------------------------------------------
# CONNECTORS & RESET
# ----------------------------------------------------------------------------
@app.get("/api/connectors")
def get_connectors():
    return {"connectors": get_connectors_status()}

@app.post("/api/reset")
def reset_database_endpoint():
    return reset_database()

@app.post("/api/demo/seed")
def seed_demo_endpoint():
    seed_demo_data(reset=False)
    sync_project_questions(DEMO_PROJECT_ID)
    return {"status": "demo benchmark state seeded", "project_id": DEMO_PROJECT_ID}

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
