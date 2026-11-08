import React from 'react';
import {
  Compass,
  Mic,
  Package,
  MessageSquare,
  FolderGit2,
  Settings,
  HelpCircle,
  ShieldAlert,
  ChevronRight,
  ExternalLink,
  Layers,
  Sparkles,
  UserCheck,
  RotateCcw,
  X,
  PlusCircle,
  GitBranch,
  ArrowRightLeft
} from 'lucide-react';

export default function Sidebar({
  activeTab,
  onSelectTab,
  mobileOpen,
  onCloseMobile,
  onOpenSettings,
  onOpenHelp,
  onResetDemo,
  resetting,
  projects = [],
  activeProject,
  onSelectProject,
  onOpenConnectModal,
  leaver,
  successor,
  manager,
}) {
  const isLiveMode = activeProject?.mode === 'live';

  const navItems = [
    {
      id: 'risk',
      label: 'Risk Map',
      icon: Compass,
      badge: 'Live',
      description: 'Deterministic risk engine',
    },
    {
      id: 'interview',
      label: 'Exit Interview',
      icon: Mic,
      badge: '15m',
      description: 'Grounded AI extraction',
    },
    {
      id: 'handover',
      label: 'Handover Package',
      icon: Package,
      badge: null,
      description: 'Personalized successor plan',
    },
    {
      id: 'ask',
      label: 'Ask Echo',
      icon: MessageSquare,
      badge: 'AI',
      description: 'Honest retrieval assistant',
    },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-xs lg:hidden transition-opacity"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-white border-r border-slate-200/80 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full'
        }`}
      >
        {/* Brand / Logo */}
        <div className="h-16 px-5 border-b border-slate-200/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center text-white shadow-xs shadow-purple-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-slate-900 tracking-tight">Echo</span>
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
                  isLiveMode
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-purple-50 text-purple-700 border-purple-200'
                }`}>
                  {isLiveMode ? 'Live Git' : 'Benchmark'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium">Knowledge-Risk Engine</p>
            </div>
          </div>
          {/* Mobile close button */}
          <button
            onClick={onCloseMobile}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {/* Main Views */}
          <div>
            <div className="px-2 mb-2 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Workspace
            </div>
            <nav className="space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      onSelectTab(item.id);
                      if (onCloseMobile) onCloseMobile();
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition ${
                      isActive
                        ? 'bg-purple-50 text-purple-700 border border-purple-200/60 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon
                        className={`w-4 h-4 transition ${
                          isActive ? 'text-purple-600' : 'text-slate-400 group-hover:text-slate-600'
                        }`}
                      />
                      <span>{item.label}</span>
                    </div>
                    {item.badge && (
                      <span
                        className={`text-[10px] font-medium px-1.5 py-0.2 rounded-full ${
                          isActive
                            ? 'bg-purple-100 text-purple-800'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Dynamic Active Projects / Repositories Section */}
          <div>
            <div className="px-2 mb-2 flex items-center justify-between text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <span>Tracked Projects</span>
              <button
                onClick={onOpenConnectModal}
                className="text-[11px] text-purple-600 hover:text-purple-800 font-medium inline-flex items-center gap-1"
                title="Ingest local Git repository"
              >
                <span>+ Ingest</span>
              </button>
            </div>
            <div className="space-y-1">
              {projects.length === 0 ? (
                <div className="p-3 text-center rounded-lg border border-dashed border-slate-200 text-slate-400 text-xs">
                  No projects tracked
                </div>
              ) : (
                projects.map((proj) => {
                  const isSelected = activeProject?.id === proj.id;
                  const isLive = proj.mode === 'live';
                  return (
                    <button
                      key={proj.id}
                      onClick={() => onSelectProject && onSelectProject(proj.id)}
                      className={`w-full text-left flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition ${
                        isSelected
                          ? isLive
                            ? 'bg-emerald-50/70 text-emerald-900 font-medium border border-emerald-200/80 shadow-2xs'
                            : 'bg-purple-50/70 text-purple-900 font-medium border border-purple-200/80 shadow-2xs'
                          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <FolderGit2 className={`w-3.5 h-3.5 ${isSelected ? (isLive ? 'text-emerald-600' : 'text-purple-600') : 'text-slate-400'}`} />
                        <span className="truncate">{proj.name.split('—')[0].trim()}</span>
                      </div>
                      {isSelected && (
                        <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-emerald-500' : 'bg-purple-600'} shrink-0`} title="Active Project" />
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Dynamic Leaver Handoff Context Summary */}
          <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-200/80 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider">
                Leaver Context
              </span>
              <span className="text-[10px] text-slate-400">
                {isLiveMode ? 'Git commit attribution' : activeProject ? 'Benchmark rubric' : 'Clean state'}
              </span>
            </div>
            <div className="text-xs space-y-1.5 text-slate-600">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Departing:</span>
                <span className="font-medium text-slate-800">
                  {leaver ? `${leaver.name} (${leaver.role?.split(' ')[0] || 'Lead'})` : 'None'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Successor:</span>
                <span className="font-medium text-slate-800">
                  {successor ? `${successor.name} (${successor.role?.split(' ')[0] || 'Successor'})` : 'None'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Manager:</span>
                <span className="font-medium text-slate-800">
                  {manager ? `${manager.name} (${manager.role?.split(' ')[0] || 'EM'})` : 'None'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar Footer Controls */}
        <div className="p-3 border-t border-slate-200/80 space-y-1 bg-white">
          <button
            onClick={onResetDemo}
            disabled={resetting}
            className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:text-rose-600 hover:bg-rose-50 transition"
            title="Reset benchmark state: clears answers and decision logs"
          >
            <div className="flex items-center gap-2">
              <RotateCcw className={`w-3.5 h-3.5 ${resetting ? 'animate-spin text-rose-500' : 'text-slate-400'}`} />
              <span>Reset Benchmark State</span>
            </div>
            <span className="text-[10px] text-slate-400">clean</span>
          </button>

          <button
            onClick={onOpenSettings}
            className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition"
          >
            <div className="flex items-center gap-2">
              <Settings className="w-3.5 h-3.5 text-slate-400" />
              <span>Engine &amp; Connectors</span>
            </div>
            <ChevronRight className="w-3 h-3 text-slate-300" />
          </button>

          <button
            onClick={onOpenHelp}
            className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition"
          >
            <div className="flex items-center gap-2">
              <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
              <span>Demo Guide &amp; Rubric</span>
            </div>
            <ExternalLink className="w-3 h-3 text-slate-300" />
          </button>
        </div>
      </aside>
    </>
  );
}
