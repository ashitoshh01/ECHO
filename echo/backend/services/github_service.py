"""
Echo Native GitHub Integration Service
Handles secure authentication, repository browsing, branch selection,
SSRF-safe repository cloning, Git history extraction, background ingestion,
and coordination with Echo's risk engine.
"""

import os
import re
import json
import uuid
import shutil
import stat
import tempfile
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

from database import get_db
from services.git_scanner import scan_git_repository
from services.interview_engine import sync_project_questions

# Maximum permitted repository size from GitHub metadata (in KB)
# Default limit: 500 MB (512,000 KB)
MAX_REPO_SIZE_KB = int(os.environ.get("ECHO_MAX_REPO_SIZE_KB", 512000))
CLONE_TIMEOUT_SECONDS = int(os.environ.get("ECHO_CLONE_TIMEOUT_SECONDS", 120))

# ----------------------------------------------------------------------------
# SECURITY & REDACTION UTILITIES
# ----------------------------------------------------------------------------
# Patterns matching common GitHub tokens (classic PATs, fine-grained, OAuth, App)
TOKEN_PATTERNS = [
    re.compile(r'ghp_[A-Za-z0-9_]{10,}'),
    re.compile(r'gho_[A-Za-z0-9_]{10,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{10,}'),
    re.compile(r'ghu_[A-Za-z0-9_]{10,}'),
    re.compile(r'ghs_[A-Za-z0-9_]{10,}'),
    re.compile(r'ghr_[A-Za-z0-9_]{10,}'),
    re.compile(r'(?i)bearer\s+[A-Za-z0-9_.\-~+/=]{10,}'),
    re.compile(r'https?://([^@/\s]+)@github\.com'),
]

def redact_secrets(text: str) -> str:
    """Redacts known GitHub tokens and authorization strings from logs and messages."""
    if not text:
        return text
    clean = str(text)
    for pat in TOKEN_PATTERNS:
        clean = pat.sub("[REDACTED_SECRET]", clean)
    return clean

def validate_owner_or_repo_name(name: str, field_name: str = "Name") -> str:
    """
    Validates GitHub owner (user/org) or repository name.
    Strictly permits only alphanumeric, dash, dot, and underscore.
    Rejects directory traversal ('.', '..') and path separators.
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    name = name.strip()
    if name in [".", ".."]:
        raise ValueError(f"Invalid {field_name}: '{name}' is not permitted")
    if not re.match(r'^[a-zA-Z0-9_\.\-]+$', name):
        raise ValueError(f"Invalid {field_name}: '{name}' contains illegal characters")
    return name

def validate_branch_name(branch: str) -> str:
    """
    Validates Git branch name. Rejects illegal characters, leading dashes,
    and traversal patterns that could be interpreted as flags or malicious refs.
    """
    if not branch or not isinstance(branch, str):
        return "main"
    branch = branch.strip()
    if branch.startswith("-"):
        raise ValueError("Invalid branch name: cannot start with a dash")
    if ".." in branch or "@{" in branch or branch.endswith(".lock"):
        raise ValueError("Invalid branch name: illegal ref format")
    if not re.match(r'^[a-zA-Z0-9_\.\/\-]+$', branch):
        raise ValueError(f"Invalid branch name '{branch}': contains illegal characters")
    return branch

def validate_github_url(url: str) -> Tuple[str, str]:
    """
    Validates GitHub URL for SSRF protection and parses owner and repo.
    Only allows 'https://github.com/{owner}/{repo}' or 'git@github.com:{owner}/{repo}'.
    Rejects IP addresses, internal domains, localhost, custom ports, and arbitrary git hosts.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL must be provided")
    url = url.strip()

    # Handle git SSH shorthand: git@github.com:owner/repo(.git)
    if url.startswith("git@github.com:"):
        path = url.split("git@github.com:", 1)[1]
    else:
        parsed = urllib.parse.urlparse(url)
        # SSRF Check: scheme must be https
        if parsed.scheme.lower() != "https":
            raise ValueError("Only HTTPS GitHub URLs are supported (e.g., https://github.com/owner/repo)")
        
        # SSRF Check: hostname must strictly be github.com
        hostname = (parsed.hostname or "").lower()
        if hostname != "github.com":
            raise ValueError(f"SSRF Protection: Access to host '{hostname}' is blocked. Only 'github.com' is allowed.")
        
        # Disallow non-standard ports or userinfo in URL
        if parsed.port and parsed.port != 443:
            raise ValueError("Non-standard ports are not allowed for GitHub URLs")
        if parsed.username or parsed.password:
            raise ValueError("Credentials must not be embedded in repository URLs")
        
        path = parsed.path.lstrip("/")

    # Normalize path: remove trailing .git and slashes
    if path.endswith(".git"):
        path = path[:-4]
    path = path.strip("/")

    parts = path.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("Repository URL must include both owner and repository name (e.g., https://github.com/owner/repo)")

    owner = validate_owner_or_repo_name(parts[0], "Owner")
    repo = validate_owner_or_repo_name(parts[1], "Repository name")
    return owner, repo

# ----------------------------------------------------------------------------
# AUTHENTICATION & CREDENTIAL MANAGEMENT
# ----------------------------------------------------------------------------
def get_stored_github_token() -> Optional[str]:
    """
    Retrieves stored GitHub token:
    1. First checks SQLite 'github_credentials' table (explicitly connected in app).
    2. Fallback to GITHUB_TOKEN or GH_TOKEN environment variables.
    """
    try:
        conn = get_db()
        row = conn.execute("SELECT token FROM github_credentials WHERE id = 'default' LIMIT 1").fetchone()
        conn.close()
        if row and row["token"]:
            return row["token"].strip()
    except Exception:
        pass

    env_tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env_tok:
        return env_tok.strip()
    return None

def github_api_request(
    endpoint: str,
    token: Optional[str] = None,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 15
) -> Tuple[Any, Dict[str, str]]:
    """
    Makes a safe, validated HTTPS request to GitHub REST API.
    Returns (json_response, response_headers).
    """
    tok = token if token is not None else get_stored_github_token()
    base_url = "https://api.github.com"
    clean_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base_url}{clean_endpoint}"

    if params:
        query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query_string:
            url = f"{url}?{query_string}"

    headers = {
        "User-Agent": "Echo-Knowledge-Risk-Engine",
        "Accept": "application/vnd.github.v3+json",
    }
    if tok:
        headers["Authorization"] = f"Bearer {tok}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            resp_headers = {k.lower(): v for k, v in response.headers.items()}
            raw = response.read().decode("utf-8")
            parsed_json = json.loads(raw) if raw else {}
            return parsed_json, resp_headers
    except urllib.error.HTTPError as e:
        err_msg = ""
        try:
            err_json = json.loads(e.read().decode("utf-8"))
            err_msg = err_json.get("message", "")
        except Exception:
            err_msg = e.reason

        if e.code == 401:
            raise PermissionError("GitHub authentication failed: Bad or expired credentials.")
        elif e.code == 403:
            if "rate limit" in err_msg.lower():
                raise PermissionError("GitHub API rate limit exceeded.")
            raise PermissionError(f"GitHub access forbidden: {err_msg or 'Insufficient permissions'}")
        elif e.code == 404:
            raise FileNotFoundError(f"GitHub resource not found: {endpoint}")
        else:
            raise RuntimeError(f"GitHub API error ({e.code}): {err_msg}")
    except urllib.error.URLError as e:
        raise ConnectionError(f"Failed to connect to GitHub API: {e.reason}")

def validate_token(token: str) -> Dict[str, Any]:
    """Validates GitHub token against the /user endpoint and returns authenticated user info."""
    if not token or not token.strip():
        raise ValueError("GitHub token must not be empty")
    token = token.strip()
    data, headers = github_api_request("/user", token=token)
    scopes_header = headers.get("x-oauth-scopes", "")
    scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]

    rate_limit = {
        "limit": int(headers.get("x-ratelimit-limit", 60)),
        "remaining": int(headers.get("x-ratelimit-remaining", 60)),
        "reset": int(headers.get("x-ratelimit-reset", 0)),
    }

    return {
        "valid": True,
        "user": {
            "login": data.get("login"),
            "name": data.get("name") or data.get("login"),
            "avatar_url": data.get("avatar_url"),
            "html_url": data.get("html_url"),
            "type": data.get("type"),
        },
        "scopes": scopes,
        "rate_limit": rate_limit,
    }

def save_github_credentials(token: str, auth_type: str = "token") -> Dict[str, Any]:
    """Validates and persists GitHub credentials in SQLite."""
    val = validate_token(token)
    user = val["user"]
    scopes_str = ",".join(val["scopes"])
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO github_credentials
            (id, auth_type, token, username, name, avatar_url, scopes, created_at, updated_at)
            VALUES ('default', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (auth_type, token.strip(), user["login"], user["name"], user["avatar_url"], scopes_str, now, now))
        
        # Also update connectors table status
        conn.execute("""
            INSERT OR REPLACE INTO connectors (id, name, type, status, details, last_sync_at)
            VALUES ('conn-github', 'GitHub REST API', 'github', 'connected', ?, ?)
        """, (f"Authenticated as @{user['login']} via {auth_type.upper()}.", now))
    conn.close()

    # Never return the token in output
    return {
        "status": "connected",
        "auth_type": auth_type,
        "user": user,
        "scopes": val["scopes"],
        "rate_limit": val["rate_limit"],
    }

def disconnect_github() -> Dict[str, Any]:
    """Disconnects GitHub integration by removing stored credentials."""
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM github_credentials WHERE id = 'default'")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            UPDATE connectors
            SET status = 'disconnected', details = 'Disconnected by user.', last_sync_at = ?
            WHERE id = 'conn-github'
        """, (now,))
    conn.close()
    return {"status": "disconnected", "message": "GitHub disconnected successfully"}

def get_github_connection_status() -> Dict[str, Any]:
    """Returns honest GitHub connection telemetry without exposing credentials."""
    tok = get_stored_github_token()
    if not tok:
        return {
            "authenticated": False,
            "auth_type": None,
            "user": None,
            "scopes": [],
            "rate_limit": None,
            "message": "GitHub is not connected."
        }

    # Determine auth_type
    conn = get_db()
    row = conn.execute("SELECT * FROM github_credentials WHERE id = 'default'").fetchone()
    conn.close()
    auth_type = row["auth_type"] if row else ("env_token" if os.environ.get("GITHUB_TOKEN") else "token")

    try:
        val = validate_token(tok)
        return {
            "authenticated": True,
            "auth_type": auth_type,
            "user": val["user"],
            "scopes": val["scopes"],
            "rate_limit": val["rate_limit"],
            "message": f"Connected as @{val['user']['login']}"
        }
    except Exception as e:
        return {
            "authenticated": False,
            "auth_type": auth_type,
            "user": None,
            "scopes": [],
            "rate_limit": None,
            "message": f"Connection check failed: {redact_secrets(str(e))}"
        }

# ----------------------------------------------------------------------------
# REPOSITORY & BRANCH SELECTION
# ----------------------------------------------------------------------------
def list_accessible_repositories(
    search: Optional[str] = None,
    visibility: Optional[str] = None,
    sort: str = "updated",
    page: int = 1,
    per_page: int = 30
) -> Dict[str, Any]:
    """Lists accessible GitHub repositories for the authenticated user."""
    tok = get_stored_github_token()
    if not tok:
        raise PermissionError("GitHub credentials required to list repositories. Please connect your GitHub account.")

    per_page = min(max(1, per_page), 100)
    page = max(1, page)

    params: Dict[str, Any] = {
        "sort": sort,
        "direction": "desc",
        "per_page": per_page,
        "page": page,
        "affiliation": "owner,collaborator,organization_member"
    }
    if visibility in ["all", "public", "private"]:
        params["visibility"] = visibility

    repos_data, _ = github_api_request("/user/repos", token=tok, params=params)

    results = []
    search_lower = search.lower().strip() if search else None

    for r in repos_data:
        full_name = r.get("full_name", "")
        name = r.get("name", "")
        description = r.get("description") or ""

        # Filter by search string if requested
        if search_lower:
            if search_lower not in full_name.lower() and search_lower not in description.lower():
                continue

        results.append({
            "id": r.get("id"),
            "name": name,
            "full_name": full_name,
            "owner": {
                "login": (r.get("owner") or {}).get("login"),
                "avatar_url": (r.get("owner") or {}).get("avatar_url"),
            },
            "private": bool(r.get("private")),
            "html_url": r.get("html_url"),
            "clone_url": r.get("clone_url"),
            "default_branch": r.get("default_branch") or "main",
            "description": description,
            "size_kb": r.get("size", 0),
            "updated_at": r.get("updated_at"),
            "permissions": r.get("permissions") or {"pull": True, "push": False, "admin": False},
        })

    return {
        "repositories": results,
        "page": page,
        "per_page": per_page,
        "total_returned": len(results)
    }

def get_repository_metadata(owner: str, repo: str) -> Dict[str, Any]:
    """Fetches metadata for a specific repository and validates read permissions."""
    owner = validate_owner_or_repo_name(owner, "Owner")
    repo = validate_owner_or_repo_name(repo, "Repository")
    tok = get_stored_github_token()

    r, _ = github_api_request(f"/repos/{owner}/{repo}", token=tok)
    
    # Check permissions
    perms = r.get("permissions") or {}
    has_pull = perms.get("pull", True)
    if not has_pull:
        raise PermissionError(f"You do not have read/pull permissions for repository {owner}/{repo}")

    # Check size limit
    size_kb = r.get("size", 0)
    if size_kb > MAX_REPO_SIZE_KB:
        raise ValueError(
            f"Repository size ({size_kb // 1024} MB) exceeds maximum allowed size ({MAX_REPO_SIZE_KB // 1024} MB)"
        )

    return {
        "id": r.get("id"),
        "name": r.get("name"),
        "full_name": r.get("full_name"),
        "owner": {
            "login": (r.get("owner") or {}).get("login"),
            "avatar_url": (r.get("owner") or {}).get("avatar_url"),
        },
        "private": bool(r.get("private")),
        "html_url": r.get("html_url"),
        "clone_url": r.get("clone_url"),
        "default_branch": r.get("default_branch") or "main",
        "description": r.get("description") or "",
        "size_kb": size_kb,
        "updated_at": r.get("updated_at"),
        "permissions": perms,
    }

def list_repository_branches(owner: str, repo: str) -> List[Dict[str, Any]]:
    """Lists available branches for a repository."""
    owner = validate_owner_or_repo_name(owner, "Owner")
    repo = validate_owner_or_repo_name(repo, "Repository")
    tok = get_stored_github_token()

    branches_data, _ = github_api_request(
        f"/repos/{owner}/{repo}/branches",
        token=tok,
        params={"per_page": 100}
    )

    branches = []
    for b in branches_data:
        branches.append({
            "name": b.get("name"),
            "protected": bool(b.get("protected")),
            "commit_sha": (b.get("commit") or {}).get("sha"),
        })
    return branches

# ----------------------------------------------------------------------------
# INGESTION JOBS & BACKGROUND PROCESSING
# ----------------------------------------------------------------------------
def create_ingestion_job(
    project_id: str,
    owner: str,
    repo: str,
    branch: str
) -> str:
    """Creates a tracking record for a background ingestion job."""
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO ingestion_jobs
            (id, project_id, repo_owner, repo_name, branch, status, step, progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'queued', 'Queued for processing', 0, ?, ?)
        """, (job_id, project_id, owner, repo, branch, now, now))
    conn.close()
    return job_id

def update_job_status(
    job_id: str,
    status: str,
    step: str,
    progress: int,
    error_message: Optional[str] = None,
    artifacts_count: int = 0,
    authors_count: int = 0
):
    """Updates job progress, step description, and final results or error."""
    now = datetime.now(timezone.utc).isoformat()
    completed_at = now if status in ["completed", "failed"] else None
    sanitized_error = redact_secrets(error_message) if error_message else None

    conn = get_db()
    with conn:
        conn.execute("""
            UPDATE ingestion_jobs
            SET status = ?, step = ?, progress = ?, error_message = ?,
                artifacts_count = CASE WHEN ? > 0 THEN ? ELSE artifacts_count END,
                authors_count = CASE WHEN ? > 0 THEN ? ELSE authors_count END,
                updated_at = ?, completed_at = COALESCE(?, completed_at)
            WHERE id = ?
        """, (
            status, step, progress, sanitized_error,
            artifacts_count, artifacts_count,
            authors_count, authors_count,
            now, completed_at, job_id
        ))
    conn.close()

def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves current job status from SQLite."""
    conn = get_db()
    row = conn.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)

# ----------------------------------------------------------------------------
# SAFE SUBPROCESS CLONING & PIPELINE REUSE
# ----------------------------------------------------------------------------
def run_safe_git_clone(
    clone_url: str,
    target_dir: str,
    branch: str,
    token: Optional[str] = None
):
    """
    Clones a Git repository safely:
    - Safe argument list (NO shell=True)
    - Enforces clone timeout
    - Disables git hooks to prevent executing malicious repository code
    - Passes authentication securely via GIT_ASKPASS (never writes token to disk or remote URL)
    - Shallow clone with depth 500 for fast, comprehensive ownership history
    """
    cmd = [
        "git",
        "-c", "core.hooksPath=/dev/null",  # Security: Disable hooks
        "clone",
        "--single-branch",
        "--branch", branch,
        "--depth", "500",
        clone_url,
        target_dir
    ]

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"  # Never hang asking for interactive terminal credentials

    askpass_dir = None
    if token:
        # Create an isolated temporary askpass script
        askpass_dir = tempfile.mkdtemp(prefix="echo_askpass_")
        askpass_sh = os.path.join(askpass_dir, "askpass.sh")
        with open(askpass_sh, "w") as fp:
            fp.write('#!/bin/sh\nexec echo "$ECHO_GIT_TOKEN"\n')
        os.chmod(askpass_sh, stat.S_IRWXU)  # Owner-only permissions

        env["GIT_ASKPASS"] = askpass_sh
        env["ECHO_GIT_TOKEN"] = token

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=CLONE_TIMEOUT_SECONDS
        )
        return proc.stdout
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Git clone timed out after {CLONE_TIMEOUT_SECONDS} seconds")
    except subprocess.CalledProcessError as e:
        err = redact_secrets(e.stderr or e.stdout or "Git clone failed")
        raise RuntimeError(f"Git clone error: {err.strip()}")
    finally:
        if askpass_dir and os.path.exists(askpass_dir):
            try:
                shutil.rmtree(askpass_dir, ignore_errors=True)
            except Exception:
                pass

def extract_and_persist_commits(repo_path: str, project_id: str, repo_id: str):
    """
    Extracts commit history and diff statistics for the repository
    and persists them into the 'commits' table.
    """
    try:
        log_output = subprocess.run(
            ["git", "log", "-n", "100", "--format=@@@ECHO_COMMIT@@@%H%x1f%an%x1f%ae%x1f%ct%x1f%s", "--shortstat"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        ).stdout
    except Exception:
        return

    conn = get_db()
    with conn:
        conn.execute("DELETE FROM commits WHERE project_id = ?", (project_id,))

        entries = [e.strip() for e in log_output.split("@@@ECHO_COMMIT@@@") if e.strip()]
        for entry in entries:
            lines = entry.splitlines()
            if not lines:
                continue
            meta_line = lines[0]
            parts = meta_line.split("\x1f")
            if len(parts) >= 5:
                sha, author, email, ts_str, msg = parts[0], parts[1], parts[2], parts[3], parts[4]
                try:
                    committed_at = datetime.fromtimestamp(int(ts_str), tz=timezone.utc).isoformat()
                except Exception:
                    committed_at = datetime.now(timezone.utc).isoformat()

                files_changed = 0
                m = re.search(r'(\d+)\s+file[s]?\s+changed', entry)
                if m:
                    files_changed = int(m.group(1))

                conn.execute("""
                    INSERT OR REPLACE INTO commits
                    (id, project_id, repo_id, author_name, author_email, committed_at, message, files_changed_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (sha, project_id, repo_id, author, email, committed_at, msg, files_changed))
    conn.close()

def run_github_ingest_pipeline(
    job_id: str,
    owner: str,
    repo: str,
    branch: str,
    leaver_name: Optional[str] = None,
    project_id: Optional[str] = None
):
    """
    Full background processing pipeline:
    1. Validates repository access & metadata
    2. Creates isolated temporary directory
    3. Securely clones git history
    4. Reuses Echo's existing git scanner engine
    5. Extracts commits & diff metadata
    6. Synchronizes questions & risk scores
    7. Cleans up temporary directory safely
    8. Updates job status to completed or failed
    """
    p_id = project_id or "proj-live"
    temp_dir = None

    try:
        # Step 1: Verification
        update_job_status(job_id, "cloning", "Validating repository and verifying permissions", 10)
        repo_meta = get_repository_metadata(owner, repo)

        # Step 2: Temporary Workspace Isolation
        temp_dir = tempfile.mkdtemp(prefix=f"echo_gh_{owner}_{repo}_")

        # Step 3: Git Clone
        update_job_status(job_id, "cloning", f"Cloning branch '{branch}' into isolated workspace", 30)
        tok = get_stored_github_token()
        clone_url = f"https://github.com/{owner}/{repo}.git"
        run_safe_git_clone(clone_url, temp_dir, branch, token=tok)

        # Step 4: Run existing git scanner engine
        update_job_status(job_id, "analyzing", "Scanning repository commits, file touches, and doc coverage", 60)
        clean_url = f"https://github.com/{owner}/{repo}"
        
        scan_res = scan_git_repository(
            repo_path=temp_dir,
            project_id=p_id,
            leaver_name=leaver_name,
            repo_name=repo,
            remote_url=clean_url,
            branch=branch,
            source_type="github",
            github_meta=repo_meta
        )

        # Step 5: Extract and persist commits
        extract_and_persist_commits(temp_dir, p_id, f"repo-{p_id}")

        # Step 6: Risk Analysis & Knowledge Gap Sync
        update_job_status(job_id, "analyzing", "Calculating deterministic risk scores and interview gaps", 85)
        sync_project_questions(p_id)

        # Step 7: Completed
        artifacts_count = scan_res.get("artifacts_count", 0)
        authors_count = len(scan_res.get("authors", []))
        update_job_status(
            job_id,
            status="completed",
            step="Repository successfully ingested and analyzed",
            progress=100,
            artifacts_count=artifacts_count,
            authors_count=authors_count
        )

    except Exception as e:
        error_msg = redact_secrets(str(e))
        update_job_status(
            job_id,
            status="failed",
            step="Ingestion failed",
            progress=100,
            error_message=error_msg
        )
    finally:
        # Step 8: Safe cleanup of temporary repository files
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
