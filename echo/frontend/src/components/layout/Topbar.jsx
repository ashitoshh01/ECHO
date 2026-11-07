import React from 'react';
import {
  Menu,
  ChevronRight,
  GitBranch,
  Search,
  Bell,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Sparkles,
  User,
  ShieldCheck,
  FolderGit2,
  Layers,
  ArrowRightLeft,
  Plus
} from 'lucide-react';

export default function Topbar({
  activeTab,
  onOpenMobile,
  onResetDemo,
  resetting,
  backendStatus = 'online', // 'checking' | 'online' | 'offline'
  onRetryConnection,
  projects = [],
  activeProject,
  onSelectProject,
  onOpenConnectModal,
  successor,
  leaver,
}) {
  const isLiveMode = activeProject?.mode === 'live';

  const pageTitles = {
    risk: 'Knowledge Risk Map',
    interview: `Exit Interview (${leaver?.name || 'Departing Lead'})`,
    handover: `Successor Package (${successor?.name || 'Successor'})`,
    ask: 'Ask Echo AI Assistant',
  };

  const isOnline = backendStatus === 'online';
  const isChecking = backendStatus === 'checking';

  // Toggle between demo and live mode
  const handleToggleMode = () => {
    if (!onSelectProject || projects.length < 2) return;
    const targetProject = projects.find((p) =>
      isLiveMode ? p.mode === 'demo' : p.mode === 'live'
    );
    if (targetProject) {
      onSelectProject(targetProject.id);
    }
  };

  return (
    <header className="h-16 bg-white/95 backdrop-blur-xs border-b border-slate-200/80 sticky top-0 z-30 px-4 sm:px-6 flex items-center justify-between">
      {/* Left: Mobile hamburger + Mode Pill + Project Selector + Breadcrumbs */}
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={onOpenMobile}
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Dynamic Mode Switcher Pill */}
        <button
          onClick={handleToggleMode}
          className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border transition shadow-2xs ${
            isLiveMode
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100'
              : 'bg-purple-50 text-purple-800 border-purple-200 hover:bg-purple-100'
          }`}
          title="Click to toggle between Live Git Ingestion and Benchmark Rubric Dataset"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isLiveMode ? 'bg-emerald-500 animate-pulse' : 'bg-purple-600'
            }`}
          />
          <span>{isLiveMode ? 'Live Git: ECHO' : 'Benchmark Rubric'}</span>
          <ArrowRightLeft className="w-3 h-3 text-slate-400 ml-0.5" />
        </button>

        {/* Breadcrumbs */}
        <nav className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
          <span className="hidden md:inline text-slate-400">Project:</span>
          
          {/* Project dropdown */}
          <div className="relative inline-flex items-center">
            <select
              value={activeProject?.id || ''}
              onChange={(e) => onSelectProject && onSelectProject(e.target.value)}
              className="appearance-none pl-6 pr-6 py-1 text-xs font-semibold rounded-md bg-slate-100/80 text-slate-800 border border-slate-200/80 cursor-pointer focus:outline-none focus:ring-1 focus:ring-purple-500 font-mono"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name.split('—')[0].trim()} ({p.mode === 'live' ? 'Live Git' : 'Demo'})
                </option>
              ))}
            </select>
            <FolderGit2 className="w-3.5 h-3.5 text-slate-500 absolute left-1.5 pointer-events-none" />
          </div>

          <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
          <span className="text-slate-900 font-semibold truncate max-w-[140px] sm:max-w-none">
            {pageTitles[activeTab] || 'Overview'}
          </span>
        </nav>
      </div>

      {/* Right: Connect Repo button, Actual Health Status, Reset shortcut, Successor badge */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Ingest Repo Button */}
        <button
          onClick={onOpenConnectModal}
          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg transition shadow-2xs"
          title="Scan and ingest a real Git repository"
        >
          <Plus className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Ingest Git Repo</span>
        </button>

        {/* Real Backend Connection Badge */}
        <button
          onClick={onRetryConnection}
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition cursor-pointer ${
            isOnline
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100/70'
              : isChecking
              ? 'bg-amber-50 text-amber-700 border-amber-200'
              : 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100'
          }`}
          title={isOnline ? 'SQLite persistent database online on port 8000' : 'Backend connection error. Click to retry.'}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isOnline ? 'bg-emerald-500 animate-pulse' : isChecking ? 'bg-amber-500 animate-spin' : 'bg-rose-500'
            }`}
          />
          <span className="hidden md:inline font-medium text-[11px]">
            {isOnline ? 'API :8000 (SQLite)' : isChecking ? 'Connecting...' : 'API Offline (Retry)'}
          </span>
        </button>

        {/* Reset Demo button */}
        <button
          onClick={onResetDemo}
          disabled={resetting}
          className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-slate-900 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition shadow-xs disabled:opacity-50"
          title="Reset benchmark state to pristine demo run"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${resetting ? 'animate-spin text-purple-600' : 'text-slate-400'}`} />
          <span>Reset</span>
        </button>

        {/* Dynamic User / Successor context badge */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-200/80">
          <div className="w-7 h-7 rounded-full bg-purple-100 border border-purple-200 flex items-center justify-center text-xs font-semibold text-purple-700 uppercase">
            {successor?.name ? successor.name.charAt(0) : 'S'}
          </div>
          <div className="hidden xl:block text-left">
            <div className="text-xs font-semibold text-slate-800 leading-none">
              {successor?.name || 'Successor'}
            </div>
            <div className="text-[10px] text-slate-400 leading-none mt-0.5">
              {successor?.role?.split(' ')[0] || 'Successor'}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
