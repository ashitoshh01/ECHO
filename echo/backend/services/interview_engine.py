"""
Echo Interview & Knowledge Retrieval Engine
Generates evidence-grounded interview questions and performs retrieval-first Q&A
backed by SQLite persistent storage.
"""

import math
import re
from datetime import datetime, timezone
from database import get_db
from services.risk_engine import calculate_project_risk

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

def classify_gap(artifact: dict, risk: dict) -> str:
    if artifact["type"] == "chat_thread":
        return "solo_external_contact"
    if artifact["type"] == "pull_request" and "#" in artifact["title"] and risk["components"]["doc_gap"] > 0.5:
        return "unexplained_change"
    if artifact["type"] in ["module", "script"] and risk["components"]["doc_gap"] >= 0.7 and risk["bus_factor_one"]:
        return "undocumented_single_owner"
    if artifact["type"] == "ticket" and "silently" in artifact["title"].lower():
        return "quiet_failure"
    # Default for single-owner high risk code
    if risk["bus_factor_one"] and risk["risk_score"] > 0.3:
        return "undocumented_single_owner"
    return None

def sync_project_questions(project_id: str, limit: int = 6):
    if not project_id:
        return
    risk_data = calculate_project_risk(project_id)
    ranked = risk_data["artifacts"]
    
    conn = get_db()
    existing_q_rows = conn.execute(
        "SELECT id, artifact_id FROM interview_questions WHERE project_id = ?",
        (project_id,)
    ).fetchall()

    if existing_q_rows:
        conn.close()
        return

    art_rows = conn.execute("SELECT * FROM artifacts WHERE project_id = ?", (project_id,)).fetchall()
    art_map = {a["id"]: dict(a) for a in art_rows}

    generated = []
    q_idx = 1
    for r in ranked:
        art = art_map.get(r["artifact_id"])
        if not art: continue
        gap = classify_gap(art, r)
        if not gap: continue

        q_id = f"Q{q_idx}"
        q_text = QUESTION_TEMPLATES[gap].format(title=art["title"])
        rationale = (
            f"Generated from evidence: ownership concentration "
            f"{r['components']['ownership_concentration']}, doc gap "
            f"{r['components']['doc_gap']}, risk {r['risk_pct']}%."
        )

        generated.append((
            q_id, project_id, art["id"], art["title"], gap, r["risk_score"], q_text, rationale, q_idx
        ))
        q_idx += 1
        if len(generated) >= limit:
            break

    with conn:
        conn.executemany("""
            INSERT OR REPLACE INTO interview_questions
            (id, project_id, artifact_id, evidence, gap_type, risk_score, question, rationale, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, generated)

    conn.close()

STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "by", "what", "why", "how", "who", "where", "when", "which", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "it", "its", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "their"
}

def tokenize(s: str, filter_stops: bool = True):
    tokens = set(re.findall(r"[a-z0-9]+", s.lower()))
    if filter_stops:
        content_tokens = {t for t in tokens if t not in STOP_WORDS}
        return content_tokens if content_tokens else tokens
    return tokens

def get_knowledge_entries(project_id: str):
    if not project_id:
        return []
    conn = get_db()
    # 1. Interview answers
    ans_rows = conn.execute("""
        SELECT a.artifact_id, a.evidence, a.answer, a.submitted_by, q.question
        FROM interview_answers a
        JOIN interview_questions q ON a.question_id = q.id
        WHERE q.project_id = ?
    """, (project_id,)).fetchall()

    # 2. Decisions
    dec_rows = conn.execute("""
        SELECT artifact_id, decision, rationale
        FROM decisions
        WHERE project_id = ?
    """, (project_id,)).fetchall()

    # 3. Documented artifacts
    art_rows = conn.execute("""
        SELECT id, title, doc_coverage
        FROM artifacts
        WHERE project_id = ? AND doc_coverage > 0.5
    """, (project_id,)).fetchall()

    conn.close()

    entries = []
    for a in ans_rows:
        entries.append({
            "source": f"Exit interview — {a['evidence'] or a['artifact_id']}",
            "artifact_id": a["artifact_id"],
            "kind": "interview_answer",
            "person": a["submitted_by"] or "Leaver",
            "text": a["answer"],
        })

    for d in dec_rows:
        entries.append({
            "source": f"Decision log — {d['artifact_id']}",
            "artifact_id": d["artifact_id"],
            "kind": "decision",
            "person": "Leaver",
            "text": f"{d['decision']} Rationale: {d['rationale']}"
        })

    for ar in art_rows:
        entries.append({
            "source": f"Documentation — {ar['title']}",
            "artifact_id": ar["id"],
            "kind": "docs",
            "person": None,
            "text": ar["title"]
        })

    return entries

def retrieve_answers(question: str, project_id: str, top_k: int = 3):
    qt = tokenize(question, filter_stops=True)
    if not qt:
        return []
    entries = get_knowledge_entries(project_id)
    scored = []
    for e in entries:
        et = tokenize(e["text"] + " " + e["source"], filter_stops=True)
        overlap = len(qt & et)
        if overlap > 0:
            score = overlap / (1 + math.log(1 + len(et)))
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:top_k]]

