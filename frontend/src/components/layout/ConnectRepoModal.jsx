import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  FolderGit2,
  GitBranch,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Search,
  Lock,
  Globe,
  RefreshCw,
  LogOut,
  KeyRound
} from 'lucide-react';
import { echoApi } from '../../api';

// Canonical GitHub Logo Mark
function GitHubMark({ className = "w-4 h-4" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

export default function ConnectRepoModal({ isOpen, onClose, onRepoScanned }) {
  const [activeSource, setActiveSource] = useState('github'); // 'github' | 'local'

  // GitHub Auth State
  const [authStatus, setAuthStatus] = useState(null);
  const [loadingAuth, setLoadingAuth] = useState(false);
  const [tokenInput, setTokenInput] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  // GitHub Repos & Branches
  const [repos, setRepos] = useState([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [branches, setBranches] = useState([]);
  const [selectedBranch, setSelectedBranch] = useState('main');
  const [loadingBranches, setLoadingBranches] = useState(false);

  // Ingestion Job & Feedback
  const [leaverName, setLeaverName] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobStep, setJobStep] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Local Git Fallback State
  const [localPath, setLocalPath] = useState('');
  const [scanningLocal, setScanningLocal] = useState(false);

  // Load GitHub Auth Status
  const checkGitHub = useCallback(async () => {
    setLoadingAuth(true);
    try {
      const res = await echoApi.getGitHubStatus();
      setAuthStatus(res);
      if (res.authenticated) {
        loadRepositories();
      }
    } catch {
      setAuthStatus({ authenticated: false });
    } finally {
      setLoadingAuth(false);
    }
  }, []);

  const loadRepositories = async () => {
    setLoadingRepos(true);
    setError(null);
    try {
      const res = await echoApi.getGitHubRepositories({ perPage: 100 });
      setRepos(res.repositories || []);
    } catch (err) {
      setError(`Failed to load repositories: ${err.message}`);
    } finally {
      setLoadingRepos(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setSuccess(null);
      checkGitHub();
    }
  }, [isOpen, checkGitHub]);

  // Load branches when a repo is selected
  useEffect(() => {
    if (!selectedRepo) {
      setBranches([]);
      return;
    }
    const [owner, name] = selectedRepo.full_name.split('/');
    setLoadingBranches(true);
    setSelectedBranch(selectedRepo.default_branch || 'main');
    echoApi.getGitHubBranches(owner, name)
      .then((res) => {
        setBranches(res.branches || []);
      })
      .catch((e) => {
        setBranches([{ name: selectedRepo.default_branch || 'main' }]);
      })
      .finally(() => setLoadingBranches(false));
  }, [selectedRepo]);

  if (!isOpen) return null;

  // Connect GitHub
  const handleConnect = async (e) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    setConnecting(true);
    setError(null);
    try {
      await echoApi.connectGitHub(tokenInput.trim(), 'pat');
      setTokenInput('');
      await checkGitHub();
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify your token.');
    } finally {
      setConnecting(false);
    }
  };

  // Disconnect GitHub
  const handleDisconnect = async () => {
    setDisconnecting(true);
    setError(null);
    try {
      await echoApi.disconnectGitHub();
      setAuthStatus({ authenticated: false });
      setRepos([]);
      setSelectedRepo(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setDisconnecting(false);
    }
  };

  // Poll Ingestion Status
  const pollJobStatus = (jobId) => {
    const interval = setInterval(async () => {
      try {
        const job = await echoApi.getIngestionStatus(jobId);
        setJobProgress(job.progress || 0);
        setJobStep(job.step || 'Processing repository...');

        if (job.status === 'completed') {
          clearInterval(interval);
          setIngesting(false);
          setSuccess(`Ingested ${job.artifacts_count || 0} artifacts and ${job.authors_count || 0} commit contributors!`);
          setTimeout(() => {
            if (onRepoScanned) onRepoScanned(job.project_id || 'proj-live');
            onClose();
          }, 1400);
        } else if (job.status === 'failed') {
          clearInterval(interval);
          setIngesting(false);
          setError(job.error_message || 'Ingestion failed.');
        }
      } catch (err) {
        clearInterval(interval);
        setIngesting(false);
        setError(`Telemetry error: ${err.message}`);
      }
    }, 1200);
  };

  // Ingest GitHub Repo
  const handleIngestGitHub = async (e) => {
    e.preventDefault();
    if (!selectedRepo) return;
    setIngesting(true);
    setError(null);
    setSuccess(null);
    setJobProgress(10);
    setJobStep('Queueing repository ingestion...');

    const [owner, name] = selectedRepo.full_name.split('/');
    try {
      const res = await echoApi.ingestGitHubRepository({
        owner,
        repo: name,
        branch: selectedBranch,
        leaver_name: leaverName.trim() || null,
        project_id: 'proj-live',
      });

      if (res.job_id) {
        pollJobStatus(res.job_id);
      } else {
        // Synchronous fallback
        setSuccess('Repository ingested successfully!');
        setTimeout(() => {
          if (onRepoScanned) onRepoScanned('proj-live');
          onClose();
        }, 1200);
      }
    } catch (err) {
      setIngesting(false);
      setError(err.message || 'Failed to start ingestion.');
    }
  };

  // Local Path Ingestion Fallback
  const handleScanLocal = async (e) => {
    e.preventDefault();
    setScanningLocal(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await echoApi.scanGitRepository(localPath.trim() || '.', leaverName.trim() || null);
      setSuccess(`Scanned ${res.artifacts_count} artifacts and ${res.authors?.length || 0} real contributors!`);
      setTimeout(() => {
        if (onRepoScanned) onRepoScanned(res.project_id);
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message || 'Failed to scan repository.');
    } finally {
      setScanningLocal(false);
    }
  };

  // Filter repos by search
  const filteredRepos = repos.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return r.full_name.toLowerCase().includes(q) || (r.description && r.description.toLowerCase().includes(q));
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg overflow-hidden fade-in">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitHubMark className="w-5 h-5 text-slate-900" />
            <h3 className="text-base font-semibold text-slate-900">Connect Repository</h3>
          </div>
          <button
            onClick={onClose}
            disabled={ingesting || scanningLocal}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Source Navigation Tabs */}
        <div className="flex border-b border-slate-200 bg-slate-50/50 px-6 pt-2">
          <button
            onClick={() => setActiveSource('github')}
            className={`pb-2.5 px-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
              activeSource === 'github'
                ? 'border-purple-600 text-purple-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <GitHubMark className="w-3.5 h-3.5" />
            <span>GitHub Integration</span>
          </button>
          <button
            onClick={() => setActiveSource('local')}
            className={`pb-2.5 px-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
              activeSource === 'local'
                ? 'border-purple-600 text-purple-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FolderGit2 className="w-3.5 h-3.5 text-slate-500" />
            <span>Local Directory</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-4 text-xs text-slate-600 max-h-[75vh] overflow-y-auto">
          {error && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span className="flex-1">{error}</span>
            </div>
          )}

          {success && (
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {/* TAB 1: GITHUB INTEGRATION */}
          {activeSource === 'github' && (
            <div className="space-y-4">
              {loadingAuth ? (
                <div className="p-8 text-center text-slate-400">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-purple-600" />
                  <span>Checking GitHub connection...</span>
                </div>
              ) : !authStatus?.authenticated ? (
                /* Connect View */
                <form onSubmit={handleConnect} className="space-y-3">
                  <div className="p-3.5 rounded-xl border border-purple-100 bg-purple-50/60 text-purple-900 space-y-1">
                    <span className="font-semibold block text-xs">Connect your GitHub Account</span>
                    <p className="text-[11px] text-purple-700 leading-relaxed">
                      Provide a Personal Access Token or fine-grained token with <code className="font-mono bg-purple-100 px-1 py-0.5 rounded">repo</code> (read-only) scope.
                      Echo uses this to inspect commits, diffs, and authorship without write access.
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      GitHub Access Token
                    </label>
                    <div className="relative">
                      <KeyRound className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                      <input
                        type="password"
                        placeholder="ghp_... or github_pat_..."
                        value={tokenInput}
                        onChange={(e) => setTokenInput(e.target.value)}
                        className="w-full pl-8 pr-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-xs text-slate-900 focus:outline-none focus:border-purple-500 focus:bg-white transition font-mono"
                      />
                    </div>
                    <span className="text-[11px] text-slate-400 mt-1 block">
                      Credentials are stored securely in backend SQLite and never exposed to the browser.
                    </span>
                  </div>

                  <div className="pt-2 flex justify-end">
                    <button
                      type="submit"
                      disabled={connecting || !tokenInput.trim()}
                      className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50 rounded-lg shadow-xs transition"
                    >
                      {connecting ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Validating Token...</span>
                        </>
                      ) : (
                        <>
                          <GitHubMark className="w-3.5 h-3.5" />
                          <span>Authenticate with GitHub</span>
                        </>
                      )}
                    </button>
                  </div>
                </form>
              ) : (
                /* Authenticated Repository Selection */
                <form onSubmit={handleIngestGitHub} className="space-y-3">
                  {/* Connected Profile Bar */}
                  <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      {authStatus.user?.avatar_url ? (
                        <img
                          src={authStatus.user.avatar_url}
                          alt="avatar"
                          className="w-7 h-7 rounded-full border border-slate-200"
                        />
                      ) : (
                        <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center font-bold text-slate-600">
                          {authStatus.user?.login?.[0]?.toUpperCase()}
                        </div>
                      )}
                      <div>
                        <span className="font-semibold text-slate-900 block leading-tight">
                          {authStatus.user?.name || authStatus.user?.login}
                        </span>
                        <span className="text-[11px] text-slate-500">
                          @{authStatus.user?.login} · {authStatus.auth_type?.toUpperCase()}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleDisconnect}
                      disabled={disconnecting || ingesting}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition"
                      title="Disconnect GitHub account"
                    >
                      <LogOut className="w-3 h-3" />
                      <span>{disconnecting ? 'Disconnecting...' : 'Disconnect'}</span>
                    </button>
                  </div>

                  {/* Repository Search & Selection */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-semibold text-slate-700">
                        Select Repository
                      </label>
                      <button
                        type="button"
                        onClick={loadRepositories}
                        disabled={loadingRepos}
                        className="text-[11px] text-purple-600 hover:text-purple-700 inline-flex items-center gap-1"
                      >
                        <RefreshCw className={`w-2.5 h-2.5 ${loadingRepos ? 'animate-spin' : ''}`} />
                        <span>Refresh</span>
                      </button>
                    </div>

                    <div className="relative mb-2">
                      <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                      <input
                        type="text"
                        placeholder="Search your repositories..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 transition"
                      />
                    </div>

                    <div className="border border-slate-200 rounded-lg max-h-40 overflow-y-auto divide-y divide-slate-100 bg-white">
                      {loadingRepos ? (
                        <div className="p-4 text-center text-slate-400">
                          <Loader2 className="w-4 h-4 animate-spin mx-auto mb-1 text-purple-600" />
                          <span>Loading repositories...</span>
                        </div>
                      ) : filteredRepos.length === 0 ? (
                        <div className="p-4 text-center text-slate-400 text-xs">
                          No repositories found.
                        </div>
                      ) : (
                        filteredRepos.map((repo) => {
                          const isSel = selectedRepo?.id === repo.id;
                          return (
                            <button
                              key={repo.id}
                              type="button"
                              onClick={() => setSelectedRepo(repo)}
                              className={`w-full text-left p-2.5 flex items-center justify-between text-xs transition ${
                                isSel ? 'bg-purple-50/80 text-purple-900 font-medium' : 'hover:bg-slate-50 text-slate-700'
                              }`}
                            >
                              <div className="min-w-0 pr-2">
                                <div className="flex items-center gap-1.5 truncate">
                                  {repo.private ? (
                                    <Lock className="w-3 h-3 text-amber-600 shrink-0" />
                                  ) : (
                                    <Globe className="w-3 h-3 text-slate-400 shrink-0" />
                                  )}
                                  <span className="truncate">{repo.full_name}</span>
                                </div>
                                {repo.description && (
                                  <p className="text-[10px] text-slate-400 truncate mt-0.5">
                                    {repo.description}
                                  </p>
                                )}
                              </div>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 shrink-0 font-mono">
                                {repo.default_branch}
                              </span>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>

                  {/* Branch & Leaver Options */}
                  {selectedRepo && (
                    <div className="grid grid-cols-2 gap-3 pt-1">
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">
                          Branch
                        </label>
                        <div className="relative">
                          <select
                            value={selectedBranch}
                            onChange={(e) => setSelectedBranch(e.target.value)}
                            disabled={loadingBranches || ingesting}
                            className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-900 focus:outline-none focus:border-purple-500 font-mono"
                          >
                            {branches.map((b) => (
                              <option key={b.name} value={b.name}>
                                {b.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">
                          Departing Lead (Optional)
                        </label>
                        <input
                          type="text"
                          placeholder="Auto-detected if blank"
                          value={leaverName}
                          onChange={(e) => setLeaverName(e.target.value)}
                          disabled={ingesting}
                          className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500"
                        />
                      </div>
                    </div>
                  )}

                  {/* Ingestion Progress Bar */}
                  {ingesting && (
                    <div className="p-3 rounded-xl bg-purple-50 border border-purple-200 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-purple-900 flex items-center gap-1.5">
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-600" />
                          <span>{jobStep || 'Ingesting...'}</span>
                        </span>
                        <span className="font-mono text-purple-700 font-bold">{jobProgress}%</span>
                      </div>
                      <div className="w-full bg-purple-200/60 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-purple-600 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${jobProgress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="pt-2 flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={onClose}
                      disabled={ingesting}
                      className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 transition"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={ingesting || !selectedRepo}
                      className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 rounded-lg shadow-xs transition"
                    >
                      {ingesting ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Ingesting...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>Ingest GitHub Repository</span>
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}

          {/* TAB 2: LOCAL DIRECTORY FALLBACK */}
          {activeSource === 'local' && (
            <form onSubmit={handleScanLocal} className="space-y-4">
              <p className="text-xs text-slate-500 leading-relaxed">
                Echo scans any local Git repository path or subdirectory, extracts real commit authors from <code className="font-mono text-purple-700 bg-purple-50 px-1 py-0.5 rounded">git log</code>, reconstructs file ownership concentrations, and calculates auditable risk scores.
              </p>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Local Repository Path or Subdirectory
                </label>
                <input
                  type="text"
                  placeholder=". (current workspace) or /path/to/repo"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:bg-white transition"
                />
                <span className="text-[11px] text-slate-400 mt-0.5 block">
                  Leave blank or &apos;.&apos; to scan the current ECHO workspace.
                </span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Departing Lead Name (Optional)
                </label>
                <input
                  type="text"
                  placeholder="Auto-detected from top code author if empty"
                  value={leaverName}
                  onChange={(e) => setLeaverName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:bg-white transition"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={scanningLocal}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 rounded-lg shadow-xs transition"
                >
                  {scanningLocal ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Scanning Git History...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Scan &amp; Ingest Repository</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
