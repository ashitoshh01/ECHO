import React, { useState, useEffect } from 'react';
import {
  Package,
  Calendar,
  AlertTriangle,
  Repeat,
  Users,
  ScrollText,
  RefreshCw,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Sparkles,
  ExternalLink,
} from 'lucide-react';
import PageHeader from '../common/PageHeader';
import LoadingState from '../common/LoadingState';
import ErrorBox from '../common/ErrorBox';
import MetricCard from '../common/MetricCard';
import HandoverTimeline from './HandoverTimeline';
import LandmineCard from './LandmineCard';
import DecisionLog from './DecisionLog';
import { echoApi } from '../../api';

export default function Handover({ active, onNavigateToInterview, activeProject, refreshKey }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [approving, setApproving] = useState(false);
  const [activeSection, setActiveSection] = useState('all'); // 'all' | 'onboarding' | 'landmines' | 'loops' | 'contacts' | 'decisions'

  const loadHandover = async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await echoApi.getHandoverPackage(activeProject?.id);
      setData(res);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHandover();
  }, [activeProject?.id, refreshKey]);

  useEffect(() => {
    if (active) {
      loadHandover();
    }
  }, [active]);

  const handleToggleApproval = async () => {
    if (approving) return;
    setApproving(true);
    try {
      const isCurrentlyApproved = data?.status === 'approved';
      if (!isCurrentlyApproved) {
        await echoApi.approveHandover(data?.manager?.name || 'Engineering Manager', activeProject?.id);
      }
      await loadHandover();
    } catch (e) {
      alert(`Approval update failed: ${e.message}`);
    } finally {
      setApproving(false);
    }
  };

  if (loading && !data) {
    return <LoadingState label="Assembling successor handover package from live knowledge graph..." />;
  }

  if (err && !data) {
    return (
      <ErrorBox
        msg={err}
        hint="Ensure backend is running: uvicorn main:app --reload --port 8000"
        onRetry={loadHandover}
      />
    );
  }

  const answeredLandmines = (data?.landmines || []).filter((l) => l.captured).length;
  const totalLandmines = data?.landmines?.length || 0;
  const isApproved = data?.status === 'approved';
  const hasPackage = Boolean(data?.package_id);

  // Dynamic calculations
  const weeksArray = (data?.onboarding_path || []).map((t) => t.week);
  const totalWeeks = weeksArray.length > 0 ? Math.max(...weeksArray) : 0;
  const tasksCount = data?.onboarding_path?.length || 0;

  const successorName = data?.successor?.name || 'Successor';
  const managerName = data?.manager?.name || 'Engineering Manager';
  const leaverName = data?.leaver?.name || 'Departing Lead';

  return (
    <div className="space-y-6 fade-in">
      {/* Page Header */}
      <PageHeader
        title={hasPackage ? `Handover Package for ${successorName}` : 'Handover Package'}
        subtitle={
          hasPackage
            ? `Successor package curated from ${leaverName}'s knowledge graph & exit interview · Reviewed by ${managerName}`
            : 'No handover package generated yet. Handover packages are automatically generated when a repository is ingested.'
        }
        badge={!hasPackage ? 'Not Generated' : isApproved ? 'Approved by Manager' : 'Pending Manager Review'}
        actions={
          <div className="flex items-center gap-2">
            {/* Real Approval Toggle Button */}
            <button
              onClick={handleToggleApproval}
              disabled={approving || isApproved || !hasPackage}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition shadow-xs ${
                !hasPackage
                  ? 'bg-slate-50 text-slate-400 border-slate-200 cursor-not-allowed'
                  : isApproved
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200 cursor-default'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
              }`}
            >
              <CheckCircle2
                className={`w-3.5 h-3.5 ${isApproved ? 'text-emerald-600' : 'text-slate-400'}`}
              />
              <span>
                {!hasPackage
                  ? 'No Package'
                  : isApproved
                  ? `Signed off by ${managerName}`
                  : approving
                  ? 'Signing off...'
                  : 'Sign Off / Approve'}
              </span>
            </button>

            <button
              onClick={loadHandover}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition shadow-xs"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-purple-600' : 'text-slate-400'}`}
              />
              <span>Refresh Package</span>
            </button>
          </div>
        }
      />

      {/* Dynamic Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Onboarding Path"
          value={tasksCount > 0 ? `${totalWeeks} Week${totalWeeks > 1 ? 's' : ''}` : '0 Weeks'}
          subtext={`${tasksCount} structured milestone tasks`}
          icon={Calendar}
          accent="purple"
        />

        <MetricCard
          label="Landmines Defused"
          value={`${answeredLandmines} / ${totalLandmines}`}
          subtext="Single-owner traps addressed"
          icon={AlertTriangle}
          accent={answeredLandmines === totalLandmines && totalLandmines > 0 ? 'emerald' : 'amber'}
          badge={answeredLandmines === totalLandmines && totalLandmines > 0 ? 'All Captured' : 'In Progress'}
        />

        <MetricCard
          label="Decisions Extracted"
          value={data?.decision_log?.length ?? 0}
          subtext="Captured from exit interview rationales"
          icon={ScrollText}
          accent="blue"
        />

        <MetricCard
          label="Package Status"
          value={!hasPackage ? 'None' : isApproved ? 'Approved' : 'Pending'}
          subtext={!hasPackage ? 'No package generated yet' : isApproved ? `Signed off by ${managerName}` : 'Awaiting EM sign-off'}
          icon={ShieldCheck}
          accent={!hasPackage ? 'slate' : isApproved ? 'emerald' : 'amber'}
        />
      </div>

      {/* Navigation Filter Tabs */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 border-b border-slate-200">
        {[
          { id: 'all', label: 'Complete Document' },
          { id: 'onboarding', label: '🗓 Onboarding Path' },
          { id: 'landmines', label: '💣 Critical Landmines' },
          { id: 'loops', label: '🔁 Open Loops' },
          { id: 'contacts', label: '👤 Who to Ask' },
          { id: 'decisions', label: '📜 Decision Log' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveSection(tab.id)}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition shrink-0 ${
              activeSection === tab.id
                ? 'bg-purple-50 text-purple-700 border border-purple-200'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Handover Sections */}
      <div className="space-y-8">
        {/* 1. Onboarding Path */}
        {(activeSection === 'all' || activeSection === 'onboarding') && (
          <section className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-purple-600" />
                <h3 className="text-sm font-semibold text-slate-900">
                  🗓 Successor Onboarding Plan
                </h3>
              </div>
              <span className="text-xs text-slate-400">Click tasks to toggle completed state (saved to database)</span>
            </div>
            <HandoverTimeline
              onboardingPath={data?.onboarding_path || []}
              onTaskToggled={loadHandover}
            />
          </section>
        )}

        {/* 2. Critical Landmines */}
        {(activeSection === 'all' || activeSection === 'landmines') && (
          <section className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-500" />
                <h3 className="text-sm font-semibold text-slate-900">
                  💣 High-Risk Landmines &amp; Captured Insights
                </h3>
              </div>
              <span className="text-xs text-slate-400">
                {answeredLandmines} of {totalLandmines} captured
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {(data?.landmines || []).length === 0 ? (
                <div className="col-span-3 p-8 text-center text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl bg-white">
                  No high-risk landmines detected yet.
                </div>
              ) : (
                (data?.landmines || []).map((l, idx) => (
                  <LandmineCard
                    key={l.artifact_id}
                    landmine={l}
                    rank={idx + 1}
                    onNavigateToInterview={onNavigateToInterview}
                    leaverName={leaverName}
                  />
                ))
              )}
            </div>
          </section>
        )}

        {/* 3. Open Loops & Contacts Grid */}
        {(activeSection === 'all' || activeSection === 'loops' || activeSection === 'contacts') && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Open Loops */}
            {(activeSection === 'all' || activeSection === 'loops') && (
              <section className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
                <div className="flex items-center gap-2 mb-3">
                  <Repeat className="w-4 h-4 text-amber-500" />
                  <h3 className="text-sm font-semibold text-slate-900">🔁 Active Open Loops</h3>
                </div>
                {data?.open_loops?.length === 0 ? (
                  <p className="text-xs text-slate-400 italic py-4 text-center">No open loops recorded.</p>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {(data?.open_loops || []).map((loop) => (
                      <div key={loop.id} className="py-2.5 first:pt-0 last:pb-0">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-xs font-medium text-slate-800 leading-snug">
                            {loop.title}
                          </span>
                          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 shrink-0">
                            {loop.artifact_id}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-1">
                          Current Owner: <span className="text-slate-600 font-medium capitalize">{loop.owner_id}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* Who to Ask */}
            {(activeSection === 'all' || activeSection === 'contacts') && (
              <section className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
                <div className="flex items-center gap-2 mb-3">
                  <Users className="w-4 h-4 text-purple-600" />
                  <h3 className="text-sm font-semibold text-slate-900">👤 Subject Matter Contacts</h3>
                </div>
                {data?.who_to_ask?.length === 0 ? (
                  <p className="text-xs text-slate-400 italic py-4 text-center">No specific contacts assigned.</p>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {(data?.who_to_ask || []).map((w, idx) => (
                      <div key={idx} className="py-2.5 first:pt-0 last:pb-0 flex items-center justify-between text-xs">
                        <div>
                          <div className="font-medium text-slate-900">{w.area}</div>
                          <div className="text-slate-500 mt-0.5">
                            Reach out to: <span className="font-medium text-purple-700">{w.contact}</span>
                          </div>
                        </div>
                        <span
                          className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
                            w.confidence === 'high'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}
                        >
                          {w.confidence} confidence
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}
          </div>
        )}

        {/* 4. Decision Log */}
        {(activeSection === 'all' || activeSection === 'decisions') && (
          <section className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <ScrollText className="w-4 h-4 text-purple-600" />
                <h3 className="text-sm font-semibold text-slate-900">
                  📜 Captured Architectural Decisions Log
                </h3>
              </div>
              <span className="text-xs text-slate-400">
                Auto-extracted from exit interview rationales
              </span>
            </div>
            <DecisionLog
              decisions={data?.decision_log || []}
              leaverName={leaverName}
            />
          </section>
        )}
      </div>
    </div>
  );
}
