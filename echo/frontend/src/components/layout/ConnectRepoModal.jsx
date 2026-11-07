import React, { useState } from 'react';
import { X, FolderGit2, GitBranch, Sparkles, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { echoApi } from '../../api';

export default function ConnectRepoModal({ isOpen, onClose, onRepoScanned }) {
  const [repoPath, setRepoPath] = useState('');
  const [leaverName, setLeaverName] = useState('');
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  if (!isOpen) return null;

  const handleScan = async (e) => {
    e.preventDefault();
    setScanning(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await echoApi.scanGitRepository(repoPath.trim() || '.', leaverName.trim() || null);
      setSuccess(`Scanned ${res.artifacts_count} artifacts and ${res.authors?.length || 0} real contributors!`);
      setTimeout(() => {
        if (onRepoScanned) onRepoScanned(res.project_id);
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message || 'Failed to scan repository.');
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl w-full max-w-md overflow-hidden fade-in">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderGit2 className="w-5 h-5 text-purple-600" />
            <h3 className="text-base font-semibold text-slate-900">Ingest Real Repository</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleScan} className="p-6 space-y-4 text-xs text-slate-600">
          <p className="text-xs text-slate-500 leading-relaxed">
            Echo connects directly to your Git repository, extracts real commit authors from <code className="font-mono text-purple-700 bg-purple-50 px-1 py-0.5 rounded">git log</code>, reconstructs file ownership concentrations, and calculates auditable risk scores.
          </p>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Local Repository Path or Subdirectory
            </label>
            <input
              type="text"
              placeholder=". (current ECHO workspace) or /path/to/repo"
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
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

          {error && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {/* Actions */}
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
              disabled={scanning}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 rounded-lg shadow-xs transition"
            >
              {scanning ? (
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
      </div>
    </div>
  );
}

