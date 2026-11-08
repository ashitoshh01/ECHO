"""
Echo ASI:One (ASI1) AI Service
Integrates Fetch.ai / ASI Alliance (ASI:One) OpenAI-compatible API
Grounded with deep project context: git commits, artifacts, exit interviews,
architectural decisions, and handover packages.
"""

import os
import re
import math
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from database import get_db, get_active_project
from services.risk_engine import calculate_project_risk
from services.interview_engine import retrieve_answers, tokenize

logger = logging.getLogger("echo.asi1")

def load_project_env():
    """Dynamically loads .env from project root or backend directory without clobbering system env vars."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / ".env",                    # backend/.env
        here.parent.parent / ".env",             # ECHO/.env (project root)
        Path.cwd() / ".env",
    ]
    for p in candidates:
        if p.is_file():
            load_dotenv(dotenv_path=p, override=False)
            return str(p)
    return None

def get_asi_status() -> Dict[str, Any]:
    """Returns the current ASI:One integration status."""
    env_file = load_project_env()
    api_key = os.getenv("ASI1_API_KEY", "").strip()
    model = os.getenv("ASI1_MODEL", "asi1").strip() or "asi1"
    base_url = os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1").rstrip("/")

    is_placeholder = bool(
        not api_key or
        api_key.lower().startswith("your_") or
        "paste_your" in api_key.lower() or
        api_key == "..."
    )
    is_configured = bool(api_key and not is_placeholder and len(api_key) > 5)

    masked_key = ""
    if api_key and not is_placeholder:
        if len(api_key) <= 8:
            masked_key = "***"
        else:
            masked_key = f"{api_key[:4]}...{api_key[-4:]}"

    return {
        "provider": "asi1",
        "name": "ASI:One AI",
        "model": model,
        "base_url": base_url,
        "is_configured": is_configured,
        "has_key": bool(api_key and not is_placeholder),
        "masked_key": masked_key,
        "env_path": env_file or ".env",
    }

def update_asi_env(api_key: str, model: Optional[str] = None) -> bool:
    """Updates runtime environment and attempts to persist to .env file."""
    cleaned_key = api_key.strip()
    chosen_model = (model or os.getenv("ASI1_MODEL", "asi1")).strip()

    # Always update process environment so changes are active immediately
    os.environ["ASI1_API_KEY"] = cleaned_key
    os.environ["ASI1_MODEL"] = chosen_model

    root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    backend_env = Path(__file__).resolve().parent.parent / ".env"

    content = f"""# ============================================================================
# ECHO KNOWLEDGE-RISK ENGINE — ENVIRONMENT CONFIGURATION
# ============================================================================
#
# ASI:One (ASI1) API Key
# Generated or retrieved from: https://asi1.ai/dashboard/api-keys
#
ASI1_API_KEY={cleaned_key}

# Model to use: 'asi1' (recommended default), 'asi1-mini', or 'asi1-ultra'
ASI1_MODEL={chosen_model}

# ASI:One API Base URL
ASI1_BASE_URL=https://api.asi1.ai/v1
"""
    try:
        if root_env.parent.exists():
            root_env.write_text(content)
        if backend_env.parent.exists() and not backend_env.is_symlink():
            try:
                backend_env.write_text(content)
            except Exception:
                pass
        load_project_env()
    except Exception as e:
        logger.warning(f"Could not persist .env file to disk (normal in containerized production): {e}")

    return True

def build_project_context(project_id: str, question: str = "") -> Dict[str, Any]:
    """
    Assembles comprehensive context from SQLite database for the LLM prompt:
    - Project & Repository info
    - Team roles & leaver/successor assignments
    - Handover package, onboarding tasks, and domain experts ("who to ask")
    - Exit interview questions & answers
    - Recorded architectural decisions & rationales
    - Top critical codebase artifacts & knowledge risk components
    - Recent commits + commits matching search keywords
    - Retrieved evidence hits
    """
    conn = get_db()
    try:
        # 1. Project details
        p_row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        project = dict(p_row) if p_row else {"name": "Unknown", "mode": "demo", "description": ""}

        # Repositories
        repo_rows = conn.execute("SELECT * FROM repositories WHERE project_id = ?", (project_id,)).fetchall()
        repos = [dict(r) for r in repo_rows]

        # 2. Team members
        team_rows = conn.execute("SELECT * FROM team_members WHERE project_id = ?", (project_id,)).fetchall()
        team = [dict(t) for t in team_rows]

        leaver = next((t for t in team if t["is_leaver"]), None)
        successor = next((t for t in team if t["is_successor"]), None)
        manager = next((t for t in team if t["is_manager"] or "manager" in (t["role"] or "").lower()), None)

        # 3. Handover package & who-to-ask
        pkg_row = conn.execute("SELECT * FROM handover_packages WHERE project_id = ?", (project_id,)).fetchone()
        who_to_ask = []
        onboarding_tasks = []
        open_loops = []
        pkg_status = "Not initiated"
        if pkg_row:
            pkg_id = pkg_row["id"]
            pkg_status = pkg_row["status"]
            who_to_ask = [dict(w) for w in conn.execute("SELECT * FROM who_to_ask WHERE package_id = ?", (pkg_id,)).fetchall()]
            onboarding_tasks = [dict(t) for t in conn.execute("SELECT * FROM onboarding_tasks WHERE package_id = ? ORDER BY order_index ASC", (pkg_id,)).fetchall()]
            open_loops = [dict(l) for l in conn.execute("SELECT * FROM open_loops WHERE package_id = ?", (pkg_id,)).fetchall()]

        # 4. Exit interview answers & questions
        ans_rows = conn.execute("""
            SELECT a.question_id, a.artifact_id, a.evidence, a.question, a.answer, a.submitted_by, a.submitted_at,
                   q.gap_type, q.risk_score, q.rationale
            FROM interview_answers a
            JOIN interview_questions q ON a.question_id = q.id
            WHERE q.project_id = ?
            ORDER BY a.id ASC
        """, (project_id,)).fetchall()
        interview_answers = [dict(a) for a in ans_rows]

        # 5. Recorded decisions
        dec_rows = conn.execute("SELECT * FROM decisions WHERE project_id = ? ORDER BY id ASC", (project_id,)).fetchall()
        decisions = [dict(d) for d in dec_rows]

        # 6. Recent commits (top 20)
        recent_commits = [dict(c) for c in conn.execute(
            "SELECT author_name, message, committed_at FROM commits WHERE project_id = ? ORDER BY committed_at DESC LIMIT 20",
            (project_id,)
        ).fetchall()]

        # Keyword-matched commits for question relevance
        q_tokens = tokenize(question, filter_stops=True)
        relevant_commits = []
        if q_tokens:
            for token in list(q_tokens)[:5]:
                match_rows = conn.execute(
                    "SELECT author_name, message, committed_at FROM commits WHERE project_id = ? AND LOWER(message) LIKE ? LIMIT 5",
                    (project_id, f"%{token}%")
                ).fetchall()
                for m in match_rows:
                    m_dict = dict(m)
                    if m_dict not in relevant_commits:
                        relevant_commits.append(m_dict)

        # 7. Codebase artifacts & risk assessment
        risk_data = calculate_project_risk(project_id)
        top_critical_artifacts = [
            a for a in risk_data.get("artifacts", [])
            if a.get("criticality", 0) >= 3 or a.get("bus_factor_one") or a.get("risk_score", 0) > 0.1
        ][:15]

        # 8. Retrieved evidence hits
        hits = retrieve_answers(question, project_id, top_k=5)
    finally:
        conn.close()

    # Build formatted markdown context for LLM
    sections = []

    # Project metadata
    repos_desc = ", ".join([f"{r['name']} ({r.get('branch', 'main')})" for r in repos]) or "None"
    sections.append(f"""### 1. PROJECT METADATA
- Project Name: {project.get('name')}
- Mode: {project.get('mode', 'live')}
- Description: {project.get('description', 'N/A')}
- Repositories: {repos_desc}""")

    # Team Roster & Roles
    team_lines = []
    if leaver:
        team_lines.append(f"- Departing Lead (Leaver): {leaver.get('name')} ({leaver.get('role')}, {leaver.get('email', 'no email')})")
    if successor:
        team_lines.append(f"- Assigned Successor: {successor.get('name')} ({successor.get('role')}, {successor.get('email', 'no email')})")
    if manager:
        team_lines.append(f"- Engineering Manager: {manager.get('name')} ({manager.get('role')})")
    other_members = [t for t in team if t != leaver and t != successor and t != manager]
    if other_members:
        team_lines.append("- Other Contributors: " + ", ".join([f"{t['name']} ({t.get('role', 'contributor')})" for t in other_members]))
    sections.append("### 2. TEAM & HANDOVER ROLES\n" + ("\n".join(team_lines) if team_lines else "None"))

    # Operational Who to Ask
    if who_to_ask:
        w_lines = [f"- Area: {w.get('area')} -> Contact: {w.get('contact')} (Confidence: {w.get('confidence')})" for w in who_to_ask]
        sections.append("### 3. WHO TO ASK (DOMAIN EXPERTS)\n" + "\n".join(w_lines))

    # Captured Exit Interview Answers (Tribal Knowledge)
    if interview_answers:
        ans_lines = []
        for a in interview_answers:
            ans_lines.append(
                f"- Question: \"{a.get('question')}\"\n"
                f"  Evidence: {a.get('evidence')}\n"
                f"  Answer ({a.get('submitted_by', 'Leaver')}): \"{a.get('answer')}\""
            )
        sections.append("### 4. CAPTURED EXIT INTERVIEW KNOWLEDGE\n" + "\n".join(ans_lines))

    # Recorded Decisions
    if decisions:
        dec_lines = [f"- {d.get('decision')} | Rationale: {d.get('rationale')} (Artifact: {d.get('artifact_id')})" for d in decisions]
        sections.append("### 5. ARCHITECTURAL DECISION LOG\n" + "\n".join(dec_lines))

    # Onboarding Tasks & Open Loops
    if onboarding_tasks or open_loops:
        task_lines = []
        for t in onboarding_tasks:
            status = "[COMPLETED]" if t.get("is_completed") else "[PENDING]"
            task_lines.append(f"- {status} Week {t.get('week')} (Days {t.get('days')}): {t.get('task')} — Reason: {t.get('why')}")
        for l in open_loops:
            task_lines.append(f"- [OPEN LOOP] {l.get('title')} (Artifact: {l.get('artifact_id')}, Owner: {l.get('owner_id')})")
        sections.append(f"### 6. HANDOVER PACKAGE (Status: {pkg_status})\n" + "\n".join(task_lines))

    # Relevant & Recent Commits
    commit_lines = []
    if relevant_commits:
        commit_lines.append("**Matched Commits for Query:**")
        for c in relevant_commits[:6]:
            date_str = (c.get('committed_at') or "")[:10]
            commit_lines.append(f"- [{c.get('author_name')}] {c.get('message')} ({date_str})")
    if recent_commits:
        commit_lines.append("**Recent Commit History:**")
        for c in recent_commits[:10]:
            date_str = (c.get('committed_at') or "")[:10]
            commit_lines.append(f"- [{c.get('author_name')}] {c.get('message')} ({date_str})")
    if commit_lines:
        sections.append("### 7. GIT COMMITS & RECENT CODE CHANGES\n" + "\n".join(commit_lines))

    # Critical Artifacts & Knowledge Risks
    if top_critical_artifacts:
        art_lines = []
        for a in top_critical_artifacts[:8]:
            bus = " [BUS FACTOR 1]" if a.get("bus_factor_one") else ""
            art_lines.append(f"- {a.get('title')} | Doc coverage: {int(a.get('doc_coverage', 0) * 100)}% | Risk: {a.get('risk_pct', 0)}%{bus}")
        sections.append("### 8. KEY CODEBASE ARTIFACTS & KNOWLEDGE RISKS\n" + "\n".join(art_lines))

    # Retrieved Specific Hits
    if hits:
        hit_lines = []
        for h in hits:
            hit_lines.append(f"- Source: {h.get('source')} | Artifact: {h.get('artifact_id')} | Content: {h.get('text')}")
        sections.append("### 9. DIRECT RETRIEVED EVIDENCE HITS\n" + "\n".join(hit_lines))

    context_text = "\n\n".join(sections)
    return {
        "context_text": context_text,
        "hits": hits,
        "who_to_ask": who_to_ask,
        "leaver": leaver,
        "successor": successor,
        "project": project,
    }

async def query_asi1(
    question: str,
    project_id: str,
    asker: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Queries ASI:One API grounded in the full project context.
    Falls back gracefully if the API key is not configured or in case of error.
    """
    status = get_asi_status()
    context_data = build_project_context(project_id, question)
    hits = context_data["hits"]
    who_to_ask = context_data["who_to_ask"]
    project = context_data["project"]
    successor = context_data["successor"]

    # Build citations from retrieved hits
    citations = [
        {"source": h["source"], "artifact_id": h["artifact_id"], "kind": h["kind"]}
        for h in hits
    ]
    stale_warning = any(h["artifact_id"] == "DOC-RUNBOOK" for h in hits)

    # Resolve suggested contact
    suggested_contact = None
    if who_to_ask:
        suggested_contact = who_to_ask[0]["contact"]
    else:
        conn = get_db()
        w_row = conn.execute(
            "SELECT contact FROM who_to_ask WHERE package_id = (SELECT id FROM handover_packages WHERE project_id = ?) LIMIT 1",
            (project_id,)
        ).fetchone()
        conn.close()
        suggested_contact = w_row["contact"] if w_row else "Priya"

    # CASE 1: ASI:One API Key is NOT configured
    if not status["is_configured"]:
        logger.info("ASI:One API key not configured. Using deterministic retrieval engine.")
        if hits:
            primary = hits[0]
            answer = primary["text"]
            if primary.get("person") and primary["kind"] == "interview_answer":
                answer = f"{answer} (captured from {primary['person']}'s exit interview)"

            fallback_note = (
                f"{answer}\n\n"
                f"---\n"
                f"💡 *ASI:One AI is integrated and ready. To enable full generative AI reasoning over all "
                f"900+ codebase artifacts and git history, paste your `ASI1_API_KEY` in the `.env` file.*"
            )
            return {
                "answer": answer,
                "echo_says": fallback_note,
                "citations": citations,
                "suggested_contact": None,
                "stale_warning": stale_warning,
                "ai_provider": "asi1",
                "ai_model": status["model"],
                "is_ai": False,
                "status": "awaiting_api_key",
                "disclaimer": "Local retrieval engine (Add ASI1_API_KEY in .env to unlock ASI:One generative AI).",
            }
        else:
            first_contact = suggested_contact.lower().split()[0] if suggested_contact else "priya"
            honesty_msg = (
                f"I don't have verified evidence for that in the local knowledge base. "
                f"I'd ask {suggested_contact} — platform engineer familiar with this subsystem.\n\n"
                f"💡 *Tip: Paste your `ASI1_API_KEY` into `.env` to allow ASI:One to analyze commits, "
                f"recent code changes, and infer answers from the codebase.*"
            )
            return {
                "answer": None,
                "echo_says": honesty_msg,
                "citations": [],
                "suggested_contact": first_contact,
                "stale_warning": False,
                "ai_provider": "asi1",
                "ai_model": status["model"],
                "is_ai": False,
                "status": "awaiting_api_key",
                "disclaimer": "Local honesty fallback.",
            }

    # CASE 2: ASI:One API Key IS configured!
    api_key = os.getenv("ASI1_API_KEY", "").strip()
    base_url = status["base_url"]
    model = status["model"]

    successor_name = asker or (successor.get("name") if successor else "Engineer")
    project_name = project.get("name", "Project")

    system_prompt = f"""You are Echo, the intelligent AI knowledge assistant and engineering handover copilot for '{project_name}', powered by ASI:One.
You are conversing with {successor_name} (the new owner or team engineer).
Your role is to provide clear, technically accurate, grounded answers regarding the codebase, git history, architectural decisions, and exit interview handover context.

CONTEXT & GROUNDING DATA:
{context_data['context_text']}

CRITICAL INSTRUCTIONS:
1. Ground your answers strictly in the verified project context, git commits, exit interviews, and codebase architecture above.
2. Specifically cite file paths, commit authors, commit messages, interview quotes, or architectural decisions whenever relevant.
3. If an answer cannot be determined from the evidence or codebase context (e.g., unknown third-party secrets, undocumented passwords, or out-of-scope topics), be honest, state that no evidence exists, and refer the user to the designated domain expert from 'Who to Ask'.
4. Do not invent passwords or credentials.
5. Keep your tone professional, concise, and helpful to an onboarding engineer."""

    messages = [{"role": "system", "content": system_prompt}]

    # Include recent conversation turns if provided
    if conversation_history:
        for turn in conversation_history[-4:]:
            role = "user" if turn.get("role") == "user" else "assistant"
            content = turn.get("text") or turn.get("answer") or turn.get("echo_says") or ""
            if content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.25,
        "max_tokens": 1200,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        if resp.status_code == 200:
            data = resp.json()
            ai_content = data["choices"][0]["message"]["content"].strip()

            # Check if AI mentioned domain experts
            inferred_contact = None
            for w in who_to_ask:
                contact_first = w["contact"].lower().split()[0]
                if contact_first in ai_content.lower():
                    inferred_contact = contact_first
                    break

            return {
                "answer": ai_content,
                "echo_says": ai_content,
                "citations": citations,
                "suggested_contact": inferred_contact,
                "stale_warning": stale_warning,
                "ai_provider": "asi1",
                "ai_model": model,
                "is_ai": True,
                "status": "success",
                "disclaimer": "Grounded answer generated by ASI:One AI from verified project context & commits.",
            }
        else:
            error_detail = resp.text
            try:
                err_json = resp.json()
                error_detail = err_json.get("error", {}).get("message") or error_detail
            except Exception:
                pass

            logger.error(f"ASI:One API returned error status {resp.status_code}: {error_detail}")

            # Graceful fallback on API error (e.g. 401 invalid key, rate limit)
            fallback_answer = hits[0]["text"] if hits else None
            error_explanation = (
                f"⚠️ **ASI:One API returned an error ({resp.status_code}):** {error_detail}\n\n"
                f"Please check your `ASI1_API_KEY` in `.env`.\n\n"
            )
            if fallback_answer:
                error_explanation += f"**Locally retrieved evidence:**\n{fallback_answer}"

            return {
                "answer": fallback_answer,
                "echo_says": error_explanation,
                "citations": citations,
                "suggested_contact": suggested_contact.lower().split()[0] if suggested_contact else None,
                "stale_warning": stale_warning,
                "ai_provider": "asi1",
                "ai_model": model,
                "is_ai": False,
                "status": "error",
                "error_message": error_detail,
                "disclaimer": f"ASI:One error: {resp.status_code}. Fallback to stored evidence.",
            }

    except httpx.TimeoutException:
        logger.error("ASI:One API request timed out.")
        fallback_answer = hits[0]["text"] if hits else None
        return {
            "answer": fallback_answer,
            "echo_says": "ASI:One API request timed out. Showing locally retrieved evidence.",
            "citations": citations,
            "suggested_contact": suggested_contact.lower().split()[0] if suggested_contact else None,
            "stale_warning": stale_warning,
            "ai_provider": "asi1",
            "ai_model": model,
            "is_ai": False,
            "status": "timeout",
        }
    except Exception as e:
        logger.error(f"Unexpected error communicating with ASI:One: {e}")
        fallback_answer = hits[0]["text"] if hits else None
        return {
            "answer": fallback_answer,
            "echo_says": f"Error contacting ASI:One AI: {str(e)}. Showing locally retrieved evidence.",
            "citations": citations,
            "suggested_contact": suggested_contact.lower().split()[0] if suggested_contact else None,
            "stale_warning": stale_warning,
            "ai_provider": "asi1",
            "ai_model": model,
            "is_ai": False,
            "status": "error",
        }

