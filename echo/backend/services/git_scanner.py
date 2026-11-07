"""
Echo Real Git Scanner Engine
Scans any local Git repository (commits, authors, file touches, recency, doc coverage)
and computes real, deterministic risk scores and ownership concentration.
"""

import os
import subprocess
from datetime import datetime, timezone
from database import get_db

def run_git(args, cwd=None):
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception as e:
        return None

def recency_weight(days: int) -> float:
    if days <= 7: return 1.0
    if days <= 30: return 0.7
    if days <= 90: return 0.4
    return 0.15

def scan_git_repository(repo_path: str = None, project_id: str = "proj-live", leaver_name: str = None):
    # Default to the root repository path of the workspace
    if not repo_path or repo_path in [".", "./"]:
        # Find git root
        root = run_git(["rev-parse", "--show-toplevel"])
        repo_path = os.path.abspath(root if root else os.path.join(os.path.dirname(__file__), "..", ".."))
    else:
        repo_path = os.path.abspath(repo_path)

    # 1. Verify git repo
    is_git = run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_path)
    if is_git != "true":
        raise ValueError(f"Directory {repo_path} is not a valid Git repository")

    repo_name = os.path.basename(repo_path)
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path) or "main"
    remote_url = run_git(["config", "--get", "remote.origin.url"], cwd=repo_path) or repo_path

    now = datetime.now(timezone.utc).isoformat()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # 2. Get tracked files from git
    ls_files = run_git(["ls-files"], cwd=repo_path) or ""
    tracked_files = [f.strip() for f in ls_files.splitlines() if f.strip()]

    # Strictly filter out binaries, pyc, node_modules, locks, caches
    ignored_substrings = [
        ".pyc", "__pycache__", ".venv", "node_modules", ".git/", "dist/",
        ".DS_Store", "package-lock.json", ".gitattributes", ".gitignore"
    ]
    filtered_files = [
        f for f in tracked_files
        if not any(ign in f for ign in ignored_substrings)
    ]

    # 3. Get all authors and commit counts from real git log
    shortlog = run_git(["shortlog", "-sn", "--no-merges", "HEAD"], cwd=repo_path) or ""
    authors = []
    for line in shortlog.splitlines():
        line = line.strip()
        if not line: continue
        parts = line.split("\t")
        if len(parts) == 2:
            count = int(parts[0].strip())
            name = parts[1].strip()
            authors.append({"name": name, "commits": count})

    if not authors:
        authors = [{"name": "Developer", "commits": 1}]

    # Count author file touches across repository to identify primary code author
    author_file_counts = {}
    for f in filtered_files:
        f_author = run_git(["log", "-n", "1", "--format=%an", "--", f], cwd=repo_path)
        if f_author:
            author_file_counts[f_author] = author_file_counts.get(f_author, 0) + 1

    if author_file_counts:
        sorted_authors = sorted(author_file_counts.items(), key=lambda x: -x[1])
        primary_leaver = leaver_name or sorted_authors[0][0]
        successor_name = sorted_authors[1][0] if len(sorted_authors) > 1 else (authors[0]["name"] if authors[0]["name"] != primary_leaver else "Successor")
    else:
        primary_leaver = leaver_name or authors[0]["name"]
        successor_name = authors[1]["name"] if len(authors) > 1 else "Successor"

    conn = get_db()
    with conn:
        # Create or update real project
        conn.execute("""
            INSERT OR REPLACE INTO projects (id, name, description, mode, is_active, created_at)
            VALUES (?, ?, ?, 'live', 1, ?)
        """, (project_id, f"{repo_name} — Live Git Workspace", f"Scanned from real git repository branch: {branch}", now))

        # Mark others inactive so live project is default active!
        conn.execute("UPDATE projects SET is_active = 0 WHERE id != ?", (project_id,))

        # Repository
        conn.execute("""
            INSERT OR REPLACE INTO repositories (id, project_id, name, path_or_url, branch, source_type, status, last_synced_at)
            VALUES (?, ?, ?, ?, ?, 'git', 'synced', ?)
        """, (f"repo-{project_id}", project_id, repo_name, remote_url, branch, now))

        # Team members
        conn.execute("DELETE FROM team_members WHERE project_id = ?", (project_id,))
        for i, a in enumerate(authors[:5]):
            is_l = 1 if a["name"].lower() == primary_leaver.lower() else 0
            is_s = 1 if a["name"].lower() == successor_name.lower() and not is_l else (1 if i == 1 and not is_l else 0)
            is_m = 1 if i == 2 else 0
            member_id = a["name"].lower().replace(" ", "_")
            role = "Lead Engineer (Departing)" if is_l else ("Engineer (Successor)" if is_s else "Engineering Manager" if is_m else "Contributor")
            conn.execute("""
                INSERT OR REPLACE INTO team_members (id, project_id, name, email, role, is_leaver, is_successor, is_manager)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (member_id, project_id, a["name"], f"{member_id}@example.com", role, is_l, is_s, is_m))

        # Artifacts
        conn.execute("DELETE FROM artifacts WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM contributions WHERE artifact_id IN (SELECT id FROM artifacts WHERE project_id = ?)", (project_id,))

        scanned_count = 0
        for fpath in filtered_files:
            ext = os.path.splitext(fpath)[1].lower()
            atype = "module"
            if ext in [".md", ".rst", ".txt"]: atype = "document"
            elif ext in [".sh", ".bash"]: atype = "script"
            elif ext in [".json", ".yaml", ".yml", ".toml"]: atype = "config"

            # Last touch timestamp from git
            last_ts_str = run_git(["log", "-n", "1", "--format=%ct", "--", fpath], cwd=repo_path)
            last_ts = int(last_ts_str) if last_ts_str and last_ts_str.isdigit() else now_ts
            days_since = max(0, (now_ts - last_ts) // 86400)

            # File contributors from git
            file_shortlog = run_git(["shortlog", "-sn", "--no-merges", "HEAD", "--", fpath], cwd=repo_path) or ""
            file_authors = {}
            for fl in file_shortlog.splitlines():
                parts = fl.strip().split("\t")
                if len(parts) == 2:
                    file_authors[parts[1].strip()] = int(parts[0].strip())

            if not file_authors:
                file_authors[primary_leaver] = 1

            # Criticality based on path importance
            criticality = 3
            if any(k in fpath for k in ["main.py", "database.py", "run.sh", "risk_engine", "App.jsx"]):
                criticality = 5
            elif atype in ["module", "script"]:
                criticality = 4

            # Documentation coverage
            full_path = os.path.join(repo_path, fpath)
            doc_coverage = 0.8 if atype == "document" else 0.2
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                        content = fp.read()
                        if '"""' in content or "/**" in content or "# Description" in content:
                            doc_coverage = min(1.0, doc_coverage + 0.5)
                except Exception:
                    pass

            art_id = f"FILE-{scanned_count+1:02d}"
            title = f"{fpath} — {atype}"

            conn.execute("""
                INSERT INTO artifacts (id, project_id, repo_id, type, title, path, criticality, doc_coverage, days_since_touch, repo, is_planted_gap, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (art_id, project_id, f"repo-{project_id}", atype, title, fpath, criticality, doc_coverage, days_since, repo_name, now))

            # Store contributions
            for author_name, commit_cnt in file_authors.items():
                m_id = author_name.lower().replace(" ", "_")
                conn.execute("""
                    INSERT OR IGNORE INTO team_members (id, project_id, name, email, role, is_leaver, is_successor, is_manager)
                    VALUES (?, ?, ?, ?, 'Contributor', 0, 0, 0)
                """, (m_id, project_id, author_name, f"{m_id}@example.com"))
                conn.execute("""
                    INSERT INTO contributions (artifact_id, person_id, count)
                    VALUES (?, ?, ?)
                """, (art_id, m_id, commit_cnt))

            scanned_count += 1

        # Handover Package for Live Project
        leaver_id = primary_leaver.lower().replace(" ", "_")
        succ_id = successor_name.lower().replace(" ", "_")

        pkg_id = f"pkg-{project_id}"
        conn.execute("""
            INSERT OR REPLACE INTO handover_packages (id, project_id, leaver_id, successor_id, manager_id, status)
            VALUES (?, ?, ?, ?, 'manager', 'pending_manager_approval')
        """, (pkg_id, project_id, leaver_id, succ_id))

        # Dynamic onboarding tasks
        conn.execute("DELETE FROM onboarding_tasks WHERE package_id = ?", (pkg_id,))
        live_tasks = [
            (pkg_id, 1, "1-2", f"Clone and setup {repo_name} development environment", "Initial code check", 0, 1),
            (pkg_id, 1, "3-4", f"Review high-risk modules with sole authorship by {primary_leaver}", "Eliminate single points of failure", 0, 2),
            (pkg_id, 1, "5", f"Handover architecture walkthrough with {primary_leaver}", "Capture unwritten operational knowledge", 0, 3),
            (pkg_id, 2, "1-3", "Submit first test or bugfix pull request", "Verify test suites and build scripts", 0, 4),
            (pkg_id, 2, "4-5", f"Assume primary ownership of {repo_name} releases", "Full handover sign-off", 0, 5),
        ]
        conn.executemany("""
            INSERT INTO onboarding_tasks (package_id, week, days, task, why, is_completed, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, live_tasks)

        # Dynamic who to ask
        conn.execute("DELETE FROM who_to_ask WHERE package_id = ?", (pkg_id,))
        live_contacts = [
            (pkg_id, "Core Architecture & Backend", f"{primary_leaver} (until exit) then {successor_name}", "high"),
            (pkg_id, "Build & Deployment Scripts", successor_name, "high"),
        ]
        conn.executemany("""
            INSERT INTO who_to_ask (package_id, area, contact, confidence)
            VALUES (?, ?, ?, ?)
        """, live_contacts)

    conn.close()
    return {"status": "scanned", "project_id": project_id, "artifacts_count": scanned_count, "authors": authors}
