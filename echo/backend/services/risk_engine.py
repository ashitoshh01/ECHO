"""
Echo Deterministic Knowledge-Risk Engine
Calculates auditable risk scores from live SQLite records:
Risk = OwnershipConcentration x Criticality x (1 - DocCoverage) x RecencyWeight
"""

from database import get_db

def recency_weight(days: int) -> float:
    if days <= 7: return 1.0
    if days <= 30: return 0.7
    if days <= 90: return 0.4
    return 0.15

def calculate_project_risk(project_id: str):
    conn = get_db()
    
    # 1. Get leaver
    leaver_row = conn.execute(
        "SELECT * FROM team_members WHERE project_id = ? AND is_leaver = 1 LIMIT 1",
        (project_id,)
    ).fetchone()

    if not leaver_row:
        # Fallback to first member
        leaver_row = conn.execute(
            "SELECT * FROM team_members WHERE project_id = ? LIMIT 1",
            (project_id,)
        ).fetchone()

    leaver = dict(leaver_row) if leaver_row else {"id": "unknown", "name": "Team Member", "role": "Engineer"}
    leaver_id = leaver["id"]

    # 2. Get artifacts
    art_rows = conn.execute(
        "SELECT * FROM artifacts WHERE project_id = ?",
        (project_id,)
    ).fetchall()

    # 3. Get contributions
    contrib_rows = conn.execute("""
        SELECT c.artifact_id, c.person_id, c.count
        FROM contributions c
        JOIN artifacts a ON c.artifact_id = a.id
        WHERE a.project_id = ?
    """, (project_id,)).fetchall()

    contributions_map = {}
    for r in contrib_rows:
        art_id = r["artifact_id"]
        if art_id not in contributions_map:
            contributions_map[art_id] = {}
        contributions_map[art_id][r["person_id"]] = r["count"]

    conn.close()

    ranked = []
    planted_gaps = []
    detected_gaps = []

    for a in art_rows:
        art_id = a["id"]
        counts = contributions_map.get(art_id, {})
        total_commits = sum(counts.values())
        leaver_commits = counts.get(leaver_id, 0)

        oc = (leaver_commits / total_commits) if total_commits > 0 else 0.0
        crit = a["criticality"] / 5.0
        doc = a["doc_coverage"]
        rec = recency_weight(a["days_since_touch"])

        risk = oc * crit * (1.0 - doc) * rec
        bus_factor_one = oc >= 0.8
        is_planted = bool(a["is_planted_gap"])

        if is_planted:
            planted_gaps.append(art_id)
            if risk > 0.15:
                detected_gaps.append(art_id)

        ranked.append({
            "artifact_id": art_id,
            "title": a["title"],
            "type": a["type"],
            "repo": a["repo"],
            "risk_score": round(risk, 3),
            "risk_pct": round(risk * 100, 1),
            "components": {
                "ownership_concentration": round(oc, 2),
                "criticality": round(crit, 2),
                "doc_gap": round(1.0 - doc, 2),
                "recency_weight": rec,
            },
            "bus_factor_one": bus_factor_one,
            "is_planted_gap": is_planted,
        })

    # Sort descending by risk score
    ranked.sort(key=lambda x: -x["risk_score"])

    high_risk_count = len([r for r in ranked if r["risk_pct"] >= 30])
    bus_factor_violations = [r["artifact_id"] for r in ranked if r["bus_factor_one"]]

    return {
        "leaver": leaver,
        "artifacts": ranked,
        "high_risk_count": high_risk_count,
        "bus_factor_violations": bus_factor_violations,
        "gaps_detected": detected_gaps,
        "gaps_planted": planted_gaps,
        "formula": "Risk = OwnershipConcentration x Criticality x (1 - DocCoverage) x RecencyWeight",
    }

