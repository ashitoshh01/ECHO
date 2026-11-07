"""
Echo Knowledge-Risk Engine — SQLite Database Layer
Persistent storage for projects, repositories, artifacts, team members,
risk assessments, interview answers, decisions, handovers, and chats.
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
        """)
    conn.close()

def get_active_project():
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE is_active = 1 LIMIT 1").fetchone()
    if not row:
        row = conn.execute("SELECT * FROM projects ORDER BY created_at ASC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

