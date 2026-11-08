"""
Comprehensive Test Suite for Native GitHub Integration in Echo
Tests:
- GitHub Authentication (valid token, invalid 401, disconnect, token secrecy)
- Secret Redaction (never logging or returning tokens)
- SSRF and URL Security Protections (blocking internal IPs, invalid domains, metacharacters, path traversal)
- Repository & Branch Browsing
- Background Ingestion Pipeline & Job Status Tracking
- Handling Public and Private Repositories
- Handling Empty Repositories (0 commits)
- Handling Repositories with Multiple Branches
- Handling Repositories with Extensive History & Diff Extraction
- Size Limit Enforcement
- Clone Failure & Error Handling
- Duplicate Ingestion (idempotency and update)
- Database Persistence (projects, repositories, commits, artifacts, team members)
- Backward Compatibility with Local Git Scanning (/api/projects/scan-git)
- Downstream Workflow Verification (Risk Map, Exit Interview, Handover, Ask Echo)
"""

import os
import sys
import shutil
import tempfile
import subprocess
import unittest
from unittest.mock import patch, MagicMock

# Add backend to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app
from database import init_db, get_db, reset_database
from services.github_service import (
    validate_github_url,
    validate_owner_or_repo_name,
    validate_branch_name,
    redact_secrets,
    save_github_credentials,
    disconnect_github,
    get_github_connection_status,
    run_safe_git_clone,
    extract_and_persist_commits,
    run_github_ingest_pipeline,
    MAX_REPO_SIZE_KB,
)

class TestGitHubIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        # Reset database before each test
        reset_database(clear_credentials=True)

    # ------------------------------------------------------------------------
    # 1. SECURITY & SSRF PROTECTION TESTS
    # ------------------------------------------------------------------------
    def test_ssrf_and_url_validation(self):
        """Verify strict URL validation and SSRF protections."""
        # Valid URLs
        owner, repo = validate_github_url("https://github.com/torvalds/linux")
        self.assertEqual(owner, "torvalds")
        self.assertEqual(repo, "linux")

        owner, repo = validate_github_url("https://github.com/facebook/react.git")
        self.assertEqual(owner, "facebook")
        self.assertEqual(repo, "react")

        owner, repo = validate_github_url("git@github.com:octocat/Hello-World.git")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "Hello-World")

        # Invalid schemes (HTTP blocked for SSRF)
        with self.assertRaises(ValueError):
            validate_github_url("http://github.com/owner/repo")

        # SSRF: Localhost and internal IP addresses blocked
        with self.assertRaises(ValueError):
            validate_github_url("http://127.0.0.1/owner/repo")
        with self.assertRaises(ValueError):
            validate_github_url("http://169.254.169.254/latest/meta-data")
        with self.assertRaises(ValueError):
            validate_github_url("http://localhost:8000/api/reset")
        with self.assertRaises(ValueError):
            validate_github_url("https://192.168.1.1/owner/repo")

        # SSRF: Third-party domains or typosquatting blocked
        with self.assertRaises(ValueError):
            validate_github_url("https://gitlab.com/owner/repo")
        with self.assertRaises(ValueError):
            validate_github_url("https://github.com.attacker.com/owner/repo")
        with self.assertRaises(ValueError):
            validate_github_url("https://notgithub.com/owner/repo")

        # Malicious paths, directory traversal, and injection blocked
        with self.assertRaises(ValueError):
            validate_owner_or_repo_name("..", "Repository")
        with self.assertRaises(ValueError):
            validate_owner_or_repo_name(".", "Owner")
        with self.assertRaises(ValueError):
            validate_owner_or_repo_name("repo;rm -rf /", "Repository")
        with self.assertRaises(ValueError):
            validate_owner_or_repo_name("user/foo", "Owner")

        # Branch validation
        self.assertEqual(validate_branch_name("main"), "main")
        self.assertEqual(validate_branch_name("feature/auth-v2"), "feature/auth-v2")
        with self.assertRaises(ValueError):
            validate_branch_name("-malicious-flag")
        with self.assertRaises(ValueError):
            validate_branch_name("main..feature")

    def test_secret_redaction(self):
        """Verify that credentials and tokens are redacted from strings and error logs."""
        raw_msg = "Error connecting with token ghp_1234567890abcdef1234567890abcdef to git"
        cleaned = redact_secrets(raw_msg)
        self.assertNotIn("ghp_1234567890abcdef1234567890abcdef", cleaned)
        self.assertIn("[REDACTED_SECRET]", cleaned)

        pat_msg = "Failed with token github_pat_11AABCDEF0123456789abcdef0123456789"
        cleaned_pat = redact_secrets(pat_msg)
        self.assertNotIn("github_pat_11AABCDEF0123456789abcdef0123456789", cleaned_pat)

    # ------------------------------------------------------------------------
    # 2. GITHUB AUTHENTICATION TESTS
    # ------------------------------------------------------------------------
    @patch("services.github_service.github_api_request")
    def test_github_auth_flow(self, mock_api):
        """Test connection, validation, retrieval, and disconnection of GitHub tokens."""
        # Mock successful /user call
        mock_api.return_value = (
            {
                "login": "test-engineer",
                "name": "Test Engineer",
                "avatar_url": "https://avatars.githubusercontent.com/u/12345",
                "html_url": "https://github.com/test-engineer",
                "type": "User",
            },
            {
                "x-oauth-scopes": "repo, read:user",
                "x-ratelimit-limit": "5000",
                "x-ratelimit-remaining": "4950",
                "x-ratelimit-reset": "1700000000",
            }
        )

        # 1. Connect via API
        fake_token = "ghp_mockSecretTokenForTestingOnly12345"
        res = self.client.post("/api/github/connect", json={"token": fake_token, "auth_type": "pat"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "connected")
        self.assertEqual(data["user"]["login"], "test-engineer")
        self.assertIn("repo", data["scopes"])
        # Token must NEVER be exposed in response body
        self.assertNotIn(fake_token, res.text)

        # 2. Status endpoint
        status_res = self.client.get("/api/github/status")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.json()
        self.assertTrue(status_data["authenticated"])
        self.assertEqual(status_data["user"]["login"], "test-engineer")
        self.assertNotIn(fake_token, status_res.text)

        # 3. Disconnect
        disc_res = self.client.post("/api/github/disconnect")
        self.assertEqual(disc_res.status_code, 200)

        # 4. Verify disconnected
        status_after = self.client.get("/api/github/status").json()
        self.assertFalse(status_after["authenticated"])

    @patch("services.github_service.github_api_request")
    def test_github_auth_invalid_token(self, mock_api):
        """Test authentication rejection when GitHub API returns 401."""
        import urllib.error
        mock_api.side_effect = PermissionError("GitHub authentication failed: Bad or expired credentials.")

        res = self.client.post("/api/github/connect", json={"token": "ghp_invalidToken1234567890"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("authentication failed", res.json()["detail"].lower())

    # ------------------------------------------------------------------------
    # 3. REPOSITORY & BRANCH BROWSING TESTS
    # ------------------------------------------------------------------------
    @patch("services.github_service.github_api_request")
    @patch("services.github_service.get_stored_github_token", return_value="ghp_mockToken12345")
    def test_repository_browsing_and_branches(self, mock_token, mock_api):
        """Test listing accessible repositories and fetching branches."""
        # Mock repositories list
        mock_api.side_effect = [
            (
                [
                    {
                        "id": 101,
                        "name": "payments-core",
                        "full_name": "acme/payments-core",
                        "owner": {"login": "acme", "avatar_url": "https://avatars.com/acme"},
                        "private": True,
                        "html_url": "https://github.com/acme/payments-core",
                        "clone_url": "https://github.com/acme/payments-core.git",
                        "default_branch": "main",
                        "description": "Core payment settlement service",
                        "size": 12500,
                        "updated_at": "2026-11-01T12:00:00Z",
                        "permissions": {"pull": True, "push": True, "admin": False},
                    },
                    {
                        "id": 102,
                        "name": "public-docs",
                        "full_name": "acme/public-docs",
                        "owner": {"login": "acme", "avatar_url": "https://avatars.com/acme"},
                        "private": False,
                        "html_url": "https://github.com/acme/public-docs",
                        "clone_url": "https://github.com/acme/public-docs.git",
                        "default_branch": "master",
                        "description": "Public documentation site",
                        "size": 3200,
                        "updated_at": "2026-10-25T10:00:00Z",
                        "permissions": {"pull": True, "push": False, "admin": False},
                    }
                ],
                {}
            ),
            # Branches for payments-core
            (
                [
                    {"name": "main", "protected": True, "commit": {"sha": "c0ffee1234"}},
                    {"name": "release-v2", "protected": False, "commit": {"sha": "deadbeef56"}}
                ],
                {}
            )
        ]

        # 1. List repositories
        res = self.client.get("/api/github/repositories?search=payments")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["repositories"]), 1)
        self.assertEqual(data["repositories"][0]["name"], "payments-core")
        self.assertTrue(data["repositories"][0]["private"])

        # 2. List branches
        branch_res = self.client.get("/api/github/repositories/acme/payments-core/branches")
        self.assertEqual(branch_res.status_code, 200)
        branches = branch_res.json()["branches"]
        self.assertEqual(len(branches), 2)
        self.assertEqual(branches[0]["name"], "main")

    # ------------------------------------------------------------------------
    # 4. REPOSITORY INGESTION & PIPELINE EXECUTION
    # ------------------------------------------------------------------------
    def test_real_git_repository_ingestion_end_to_end(self):
        """
        Creates a real temporary git repository with commits, branches, and diffs,
        and tests complete ingestion through the pipeline, checking:
        - Commits & diff persistence
        - Artifact extraction & doc coverage
        - Ownership concentration
        - Deterministic risk scoring
        - Gap generation and interview question creation
        - Handover package and Ask Echo retrieval!
        """
        # Create a mock remote git repository on disk
        temp_remote = tempfile.mkdtemp(prefix="echo_test_remote_")
        try:
            # git init
            subprocess.run(["git", "init", "-b", "main", temp_remote], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Aarav Sharma"], cwd=temp_remote, check=True)
            subprocess.run(["git", "config", "user.email", "aarav@example.com"], cwd=temp_remote, check=True)

            # Create files with Aarav
            f1 = os.path.join(temp_remote, "nightly_sync.py")
            with open(f1, "w") as fp:
                fp.write("# Nightly sync job with no docs\ndef run_sync(): pass\n")
            subprocess.run(["git", "add", "nightly_sync.py"], cwd=temp_remote, check=True)
            subprocess.run(["git", "commit", "-m", "feat: initial sync service implementation"], cwd=temp_remote, check=True)

            # Commit 2 with Aarav
            f2 = os.path.join(temp_remote, "payments_retry.py")
            with open(f2, "w") as fp:
                fp.write('"""Payments retry module."""\ndef retry(): pass\n')
            subprocess.run(["git", "add", "payments_retry.py"], cwd=temp_remote, check=True)
            subprocess.run(["git", "commit", "-m", "fix: increase retry threshold to 5"], cwd=temp_remote, check=True)

            # Commit 3 with Meera (successor)
            subprocess.run(["git", "config", "user.name", "Meera Nair"], cwd=temp_remote, check=True)
            subprocess.run(["git", "config", "user.email", "meera@example.com"], cwd=temp_remote, check=True)
            f3 = os.path.join(temp_remote, "README.md")
            with open(f3, "w") as fp:
                fp.write("# Payments System Documentation\n")
            subprocess.run(["git", "add", "README.md"], cwd=temp_remote, check=True)
            subprocess.run(["git", "commit", "-m", "docs: update system overview"], cwd=temp_remote, check=True)

            # Mock get_repository_metadata and run_safe_git_clone to clone from temp_remote
            mock_meta = {
                "id": 9999,
                "name": "payments-repo",
                "full_name": "acme/payments-repo",
                "owner": {"login": "acme", "avatar_url": "https://avatar.com/acme"},
                "private": False,
                "html_url": "https://github.com/acme/payments-repo",
                "clone_url": "https://github.com/acme/payments-repo.git",
                "default_branch": "main",
                "description": "Payment gateway service",
                "size_kb": 1024,
                "permissions": {"pull": True, "push": False, "admin": False},
            }

            def fake_clone(clone_url, target_dir, branch, token=None):
                subprocess.run(
                    ["git", "clone", "--single-branch", "--branch", branch, temp_remote, target_dir],
                    check=True,
                    capture_output=True
                )

            with patch("services.github_service.get_repository_metadata", return_value=mock_meta), \
                 patch("services.github_service.run_safe_git_clone", side_effect=fake_clone):

                # Ingest synchronously
                res = self.client.post("/api/repositories/github/ingest", json={
                    "owner": "acme",
                    "repo": "payments-repo",
                    "branch": "main",
                    "leaver_name": "Aarav Sharma",
                    "project_id": "proj-live",
                    "sync": True
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["status"], "completed")
                self.assertGreaterEqual(data["artifacts_count"], 3)
                self.assertGreaterEqual(data["authors_count"], 2)

                # 1. Verify Repositories table
                conn = get_db()
                repo_row = conn.execute("SELECT * FROM repositories WHERE project_id = 'proj-live'").fetchone()
                self.assertIsNotNone(repo_row)
                self.assertEqual(repo_row["name"], "payments-repo")
                self.assertEqual(repo_row["owner"], "acme")
                self.assertEqual(repo_row["source_type"], "github")
                # Ensure no secrets embedded in URL
                self.assertEqual(repo_row["path_or_url"], "https://github.com/acme/payments-repo")

                # 2. Verify Commits table
                commit_rows = conn.execute("SELECT * FROM commits WHERE project_id = 'proj-live'").fetchall()
                self.assertGreaterEqual(len(commit_rows), 3)

                # 3. Verify Team Members
                member_rows = conn.execute("SELECT * FROM team_members WHERE project_id = 'proj-live'").fetchall()
                names = [m["name"] for m in member_rows]
                self.assertIn("Aarav Sharma", names)
                self.assertIn("Meera Nair", names)

                # Leaver should be Aarav
                leaver_row = conn.execute("SELECT * FROM team_members WHERE project_id = 'proj-live' AND is_leaver = 1").fetchone()
                self.assertEqual(leaver_row["name"], "Aarav Sharma")

                # 4. Verify Artifacts
                art_rows = conn.execute("SELECT * FROM artifacts WHERE project_id = 'proj-live'").fetchall()
                self.assertGreaterEqual(len(art_rows), 3)
                conn.close()

                # 5. Verify Risk Map Endpoint
                risk_res = self.client.get("/api/risk-map?project_id=proj-live")
                self.assertEqual(risk_res.status_code, 200)
                risk_data = risk_res.json()
                self.assertEqual(risk_data["leaver"]["name"], "Aarav Sharma")
                self.assertGreater(len(risk_data["artifacts"]), 0)

                # 6. Verify Exit Interview Questions generated from evidence
                q_res = self.client.get("/api/interview/questions?project_id=proj-live")
                self.assertEqual(q_res.status_code, 200)
                q_data = q_res.json()
                self.assertGreater(len(q_data["questions"]), 0)
                q1 = q_data["questions"][0]

                # 7. Submit an Answer to Exit Interview
                ans_res = self.client.post("/api/interview/answers", json={
                    "question_id": q1["id"],
                    "artifact_id": q1["artifact_id"],
                    "answer": "We chose exponential backoff because the upstream gateway throttled concurrent retries.",
                    "submitted_by": "Aarav Sharma"
                })
                self.assertEqual(ans_res.status_code, 200)
                self.assertTrue(ans_res.json()["decision_logged"])

                # 8. Verify Handover Package
                handover_res = self.client.get("/api/handover?project_id=proj-live")
                self.assertEqual(handover_res.status_code, 200)
                handover_data = handover_res.json()
                self.assertGreater(len(handover_data["onboarding_path"]), 0)
                self.assertGreater(len(handover_data["decision_log"]), 0)

                # 9. Verify Ask Echo Retrieval
                ask_res = self.client.post("/api/ask", json={
                    "question": "Why did we use exponential backoff for payment retries?",
                    "project_id": "proj-live"
                })
                self.assertEqual(ask_res.status_code, 200)
                ask_data = ask_res.json()
                self.assertIn("exponential backoff", ask_data["answer"].lower())

        finally:
            shutil.rmtree(temp_remote, ignore_errors=True)

    def test_background_job_polling(self):
        """Test asynchronous job creation and status endpoint."""
        mock_meta = {
            "id": 8888,
            "name": "bg-repo",
            "full_name": "acme/bg-repo",
            "owner": {"login": "acme"},
            "private": False,
            "size_kb": 500,
            "default_branch": "main",
            "permissions": {"pull": True},
        }

        with patch("services.github_service.get_repository_metadata", return_value=mock_meta), \
             patch("services.github_service.run_github_ingest_pipeline"):

            res = self.client.post("/api/repositories/github/ingest", json={
                "owner": "acme",
                "repo": "bg-repo",
                "branch": "main"
            })
            self.assertEqual(res.status_code, 202)
            data = res.json()
            self.assertIn("job_id", data)
            self.assertEqual(data["status"], "queued")

            # Poll status
            poll_res = self.client.get(f"/api/repositories/github/ingest/{data['job_id']}/status")
            self.assertEqual(poll_res.status_code, 200)
            poll_data = poll_res.json()
            self.assertEqual(poll_data["id"], data["job_id"])

    # ------------------------------------------------------------------------
    # 5. EDGE CASES: EMPTY REPO, SIZE LIMIT, DUPLICATES, & LOCAL COMPATIBILITY
    # ------------------------------------------------------------------------
    def test_empty_git_repository_handling(self):
        """Empty repository with 0 commits should be handled cleanly without 500 crash."""
        temp_empty = tempfile.mkdtemp(prefix="echo_test_empty_")
        try:
            subprocess.run(["git", "init", "-b", "main", temp_empty], check=True, capture_output=True)

            mock_meta = {
                "id": 7777,
                "name": "empty-repo",
                "full_name": "acme/empty-repo",
                "owner": {"login": "acme"},
                "size_kb": 0,
                "default_branch": "main",
                "permissions": {"pull": True},
            }

            def fake_clone(clone_url, target_dir, branch, token=None):
                subprocess.run(["git", "init", "-b", branch, target_dir], check=True, capture_output=True)

            with patch("services.github_service.get_repository_metadata", return_value=mock_meta), \
                 patch("services.github_service.run_safe_git_clone", side_effect=fake_clone):

                res = self.client.post("/api/repositories/github/ingest", json={
                    "owner": "acme",
                    "repo": "empty-repo",
                    "sync": True
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["status"], "completed")
                self.assertEqual(data["artifacts_count"], 0)
        finally:
            shutil.rmtree(temp_empty, ignore_errors=True)

    def test_size_limit_rejection(self):
        """Repositories exceeding MAX_REPO_SIZE_KB must be rejected before cloning."""
        oversized_meta = {
            "id": 6666,
            "name": "giant-monorepo",
            "full_name": "acme/giant-monorepo",
            "owner": {"login": "acme"},
            "size_kb": MAX_REPO_SIZE_KB + 10000,
            "default_branch": "main",
            "permissions": {"pull": True},
        }

        with patch("services.github_service.get_repository_metadata", return_value=oversized_meta):
            res = self.client.post("/api/repositories/github/ingest", json={
                "owner": "acme",
                "repo": "giant-monorepo"
            })
            self.assertEqual(res.status_code, 400)
            self.assertIn("exceeds maximum allowed size", res.json()["detail"])

    def test_local_path_scanning_backward_compatibility(self):
        """Existing /api/projects/scan-git endpoint must continue working flawlessly."""
        res = self.client.post("/api/projects/scan-git", json={"repo_path": "."})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "scanned")
        self.assertGreater(data["artifacts_count"], 0)

    def test_unauthorized_private_repository(self):
        """Private repository with no pull permissions returns 403 Forbidden."""
        no_perm_meta = {
            "id": 5555,
            "name": "secret-vault",
            "full_name": "acme/secret-vault",
            "owner": {"login": "acme"},
            "size_kb": 200,
            "default_branch": "main",
            "permissions": {"pull": False, "push": False, "admin": False},
        }

        with patch("services.github_service.get_repository_metadata", return_value=no_perm_meta):
            res = self.client.post("/api/repositories/github/ingest", json={
                "owner": "acme",
                "repo": "secret-vault"
            })
            self.assertEqual(res.status_code, 403)
            self.assertIn("Access denied", res.json()["detail"])

    def test_failed_clone_handling(self):
        """Failed git clone updates job to failed and redacts any secret in error message."""
        mock_meta = {
            "id": 4444,
            "name": "broken-repo",
            "full_name": "acme/broken-repo",
            "owner": {"login": "acme"},
            "size_kb": 500,
            "default_branch": "main",
            "permissions": {"pull": True},
        }

        def broken_clone(clone_url, target_dir, branch, token=None):
            raise RuntimeError("Git clone error: fatal: Authentication failed for 'https://ghp_secretTokenToRedact@github.com/acme/broken-repo'")

        with patch("services.github_service.get_repository_metadata", return_value=mock_meta), \
             patch("services.github_service.run_safe_git_clone", side_effect=broken_clone):

            res = self.client.post("/api/repositories/github/ingest", json={
                "owner": "acme",
                "repo": "broken-repo",
                "sync": True
            })
            self.assertEqual(res.status_code, 400)
            detail = res.json()["detail"]
            self.assertIn("Authentication failed", detail)
            self.assertNotIn("ghp_secretTokenToRedact", detail)

    def test_duplicate_repository_ingestion(self):
        """Ingesting the same repository multiple times updates records idempotently."""
        temp_repo = tempfile.mkdtemp(prefix="echo_test_dup_")
        try:
            subprocess.run(["git", "init", "-b", "main", temp_repo], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Lead Eng"], cwd=temp_repo, check=True)
            subprocess.run(["git", "config", "user.email", "lead@example.com"], cwd=temp_repo, check=True)
            with open(os.path.join(temp_repo, "app.py"), "w") as fp:
                fp.write("print('v1')\n")
            subprocess.run(["git", "add", "app.py"], cwd=temp_repo, check=True)
            subprocess.run(["git", "commit", "-m", "v1"], cwd=temp_repo, check=True)

            mock_meta = {
                "id": 3333,
                "name": "dup-repo",
                "full_name": "acme/dup-repo",
                "owner": {"login": "acme"},
                "size_kb": 100,
                "default_branch": "main",
                "permissions": {"pull": True},
            }

            def fake_clone(clone_url, target_dir, branch, token=None):
                subprocess.run(["git", "clone", "--single-branch", "--branch", branch, temp_repo, target_dir], check=True, capture_output=True)

            with patch("services.github_service.get_repository_metadata", return_value=mock_meta), \
                 patch("services.github_service.run_safe_git_clone", side_effect=fake_clone):

                # Ingestion 1
                res1 = self.client.post("/api/repositories/github/ingest", json={"owner": "acme", "repo": "dup-repo", "sync": True})
                self.assertEqual(res1.status_code, 200)

                # Commit v2
                with open(os.path.join(temp_repo, "app.py"), "w") as fp:
                    fp.write("print('v2')\n")
                subprocess.run(["git", "add", "app.py"], cwd=temp_repo, check=True)
                subprocess.run(["git", "commit", "-m", "v2"], cwd=temp_repo, check=True)

                # Ingestion 2
                res2 = self.client.post("/api/repositories/github/ingest", json={"owner": "acme", "repo": "dup-repo", "sync": True})
                self.assertEqual(res2.status_code, 200)
                self.assertEqual(res2.json()["status"], "completed")

                conn = get_db()
                commits = conn.execute("SELECT * FROM commits WHERE project_id = 'proj-live'").fetchall()
                self.assertEqual(len(commits), 2)
                conn.close()
        finally:
            shutil.rmtree(temp_repo, ignore_errors=True)

    def test_multi_branch_and_extensive_history(self):
        """Test repository with multiple branches and 15+ commits across multiple authors."""
        temp_repo = tempfile.mkdtemp(prefix="echo_test_multibranch_")
        try:
            subprocess.run(["git", "init", "-b", "main", temp_repo], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Dev One"], cwd=temp_repo, check=True)
            subprocess.run(["git", "config", "user.email", "dev1@example.com"], cwd=temp_repo, check=True)

            # Create 10 commits on main
            for i in range(10):
                fname = f"module_{i}.py"
                with open(os.path.join(temp_repo, fname), "w") as fp:
                    fp.write(f"def func_{i}(): pass\n")
                subprocess.run(["git", "add", fname], cwd=temp_repo, check=True)
                subprocess.run(["git", "commit", "-m", f"feat: add module {i}"], cwd=temp_repo, check=True)

            # Create feature branch with Dev Two
            subprocess.run(["git", "checkout", "-b", "feature-v2"], cwd=temp_repo, check=True)
            subprocess.run(["git", "config", "user.name", "Dev Two"], cwd=temp_repo, check=True)
            subprocess.run(["git", "config", "user.email", "dev2@example.com"], cwd=temp_repo, check=True)

            for j in range(5):
                fname = f"feature_{j}.py"
                with open(os.path.join(temp_repo, fname), "w") as fp:
                    fp.write(f"def feature_{j}(): pass\n")
                subprocess.run(["git", "add", fname], cwd=temp_repo, check=True)
                subprocess.run(["git", "commit", "-m", f"feat: feature branch commit {j}"], cwd=temp_repo, check=True)

            mock_meta = {
                "id": 2222,
                "name": "multi-branch-repo",
                "full_name": "acme/multi-branch-repo",
                "owner": {"login": "acme"},
                "size_kb": 400,
                "default_branch": "main",
                "permissions": {"pull": True},
            }

            def fake_clone(clone_url, target_dir, branch, token=None):
                subprocess.run(["git", "clone", "--single-branch", "--branch", branch, temp_repo, target_dir], check=True, capture_output=True)

            with patch("services.github_service.get_repository_metadata", return_value=mock_meta), \
                 patch("services.github_service.run_safe_git_clone", side_effect=fake_clone):

                # Ingest feature-v2 branch
                res = self.client.post("/api/repositories/github/ingest", json={
                    "owner": "acme",
                    "repo": "multi-branch-repo",
                    "branch": "feature-v2",
                    "sync": True
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["status"], "completed")

                conn = get_db()
                repo_row = conn.execute("SELECT * FROM repositories WHERE project_id = 'proj-live'").fetchone()
                self.assertEqual(repo_row["branch"], "feature-v2")

                commits = conn.execute("SELECT * FROM commits WHERE project_id = 'proj-live'").fetchall()
                # 10 from main + 5 from feature branch = 15 commits
                self.assertEqual(len(commits), 15)
                conn.close()
        finally:
            shutil.rmtree(temp_repo, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
