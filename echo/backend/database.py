"""
Echo Knowledge-Risk Engine — SQLite Database Layer
Persistent storage for projects, repositories, artifacts, team members,
risk assessments, interview answers, decisions, handovers, chats,
GitHub credentials, commits, and asynchronous ingestion jobs.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "echo.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            mode TEXT DEFAULT 'demo', -- 'demo' or 'live'
            is_active INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS repositories (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            path_or_url TEXT,
            branch TEXT DEFAULT 'main',
            source_type TEXT DEFAULT 'git', -- 'git', 'github', 'demo'
            status TEXT DEFAULT 'synced',
            last_synced_at TEXT,
            owner TEXT,
            repo_id_github INTEGER,
            default_branch TEXT,
            description TEXT,
            is_private INTEGER DEFAULT 0,
            html_url TEXT,
            size_kb INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS team_members (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL,
            is_leaver INTEGER DEFAULT 0,
            is_successor INTEGER DEFAULT 0,
            is_manager INTEGER DEFAULT 0,
            avatar_url TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            repo_id TEXT,
            type TEXT NOT NULL, -- 'module', 'pull_request', 'ticket', 'chat_thread', 'document'
            title TEXT NOT NULL,
            path TEXT,
            criticality INTEGER NOT NULL, -- 1-5
            doc_coverage REAL NOT NULL, -- 0.0 - 1.0
            days_since_touch INTEGER NOT NULL,
            repo TEXT,
            is_planted_gap INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS contributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artifact_id TEXT NOT NULL,
            person_id TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE,
            FOREIGN KEY(person_id) REFERENCES team_members(id) ON DELETE CASCADE,
            UNIQUE(artifact_id, person_id)
        );

        CREATE TABLE IF NOT EXISTS graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            source TEXT NOT NULL,
            relation TEXT NOT NULL,
            target TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS interview_questions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            evidence TEXT NOT NULL,
            gap_type TEXT NOT NULL,
            risk_score REAL NOT NULL,
            question TEXT NOT NULL,
            rationale TEXT,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS interview_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            evidence TEXT,
            question TEXT,
            answer TEXT NOT NULL,
            submitted_by TEXT,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(question_id) REFERENCES interview_questions(id) ON DELETE CASCADE,
            FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            rationale TEXT NOT NULL,
            extracted_from_answer_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS handover_packages (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            leaver_id TEXT NOT NULL,
            successor_id TEXT NOT NULL,
            manager_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending_manager_approval', -- 'pending_manager_approval', 'approved'
            approved_at TEXT,
            approved_by TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS onboarding_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id TEXT NOT NULL,
            week INTEGER NOT NULL,
            days TEXT NOT NULL,
            task TEXT NOT NULL,
            why TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY(package_id) REFERENCES handover_packages(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS open_loops (
            id TEXT PRIMARY KEY,
            package_id TEXT NOT NULL,
            title TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            FOREIGN KEY(package_id) REFERENCES handover_packages(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS who_to_ask (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id TEXT NOT NULL,
            area TEXT NOT NULL,
            contact TEXT NOT NULL,
            confidence TEXT NOT NULL, -- 'high', 'low'
            FOREIGN KEY(package_id) REFERENCES handover_packages(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            role TEXT NOT NULL, -- 'user', 'echo'
            text TEXT,
            answer TEXT,
            echo_says TEXT,
            suggested_contact TEXT,
            stale_warning INTEGER DEFAULT 0,
            citations_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS connectors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL, -- 'git', 'github', 'slack', 'jira', 'docs'
            status TEXT NOT NULL, -- 'connected', 'disconnected', 'not_configured'
            details TEXT,
            last_sync_at TEXT
        );

        CREATE TABLE IF NOT EXISTS github_credentials (
            id TEXT PRIMARY KEY DEFAULT 'default',
            auth_type TEXT NOT NULL, -- 'pat', 'oauth', 'app'
            token TEXT NOT NULL,
            username TEXT,
            name TEXT,
            avatar_url TEXT,
            scopes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            repo_owner TEXT,
            repo_name TEXT,
            branch TEXT,
            status TEXT NOT NULL, -- 'queued', 'cloning', 'analyzing', 'completed', 'failed'
            step TEXT,
            progress INTEGER DEFAULT 0,
            artifacts_count INTEGER DEFAULT 0,
            authors_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS commits (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            author_name TEXT NOT NULL,
            author_email TEXT,
            committed_at TEXT NOT NULL,
            message TEXT,
            files_changed_count INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)

        # Migration: ensure newly added columns exist in older SQLite databases
        repo_cols = [r["name"] for r in conn.execute("PRAGMA table_info(repositories)").fetchall()]
        needed_repo_cols = {
            "owner": "TEXT",
            "repo_id_github": "INTEGER",
            "default_branch": "TEXT",
            "description": "TEXT",
            "is_private": "INTEGER DEFAULT 0",
            "html_url": "TEXT",
            "size_kb": "INTEGER DEFAULT 0"
        }
        for col, col_type in needed_repo_cols.items():
            if col not in repo_cols:
                conn.execute(f"ALTER TABLE repositories ADD COLUMN {col} {col_type};")

    conn.close()

def get_active_project():
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE is_active = 1 LIMIT 1").fetchone()
    if not row:
        row = conn.execute("SELECT * FROM projects ORDER BY created_at ASC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

def reset_database(clear_credentials: bool = False):
    """
    Safely and transactionally deletes all application data in strict dependency order,
    resets auto-increment counters, and verifies referential integrity.
    Preserves database schema and table definitions.
    """
    conn = get_db()
    cleared_tables = [
        "chat_messages",
        "who_to_ask",
        "open_loops",
        "onboarding_tasks",
        "handover_packages",
        "decisions",
        "interview_answers",
        "interview_questions",
        "graph_edges",
        "contributions",
        "artifacts",
        "commits",
        "ingestion_jobs",
        "team_members",
        "repositories",
        "projects",
        "connectors",
    ]
    if clear_credentials:
        cleared_tables.append("github_credentials")

    try:
        with conn:
            for table in cleared_tables:
                conn.execute(f"DELETE FROM {table};")
            conn.execute("DELETE FROM sqlite_sequence;")

            # Verify referential integrity
            fk_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
            if fk_violations:
                raise RuntimeError(f"Foreign key integrity violation during reset: {fk_violations}")
        return {
            "status": "success",
            "message": "Database successfully reset to clean slate",
            "cleared_tables": cleared_tables,
            "sequences_reset": True,
        }
    finally:
        conn.close()
