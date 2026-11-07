import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Users,
  Target,
  FileCode2,
  HelpCircle,
  Sparkles,
  Info,
  RefreshCw,
} from 'lucide-react';
import MetricCard from '../common/MetricCard';
import LoadingState from '../common/LoadingState';
import ErrorBox from '../common/ErrorBox';
import PageHeader from '../common/PageHeader';
import RiskTable from './RiskTable';
import ArtifactDetailDrawer from './ArtifactDetailDrawer';
import { echoApi } from '../../api';

export default function RiskMap({ onNavigateToInterview, activeProject, refreshKey }) {
  const [data, setData] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [showFormulaInfo, setShowFormulaInfo] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setErr(null);
    try {
      const pId = activeProject?.id;
      const [riskRes, artRes] = await Promise.all([
        echoApi.getRiskMap(pId),
        echoApi.getArtifacts(pId).catch(() => ({ artifacts: [], edges: [] })),
      ]);
      setData(riskRes);
      setGraphData(artRes);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeProject?.id, refreshKey]);

  if (loading && !data) {
    return <LoadingState label="Computing deterministic risk scores from live data..." />;
  }

  if (err && !data) {
    return (
      <ErrorBox
        msg={err}
        hint="Is the backend running on port 8000? Run: uvicorn main:app --reload --port 8000"
        onRetry={loadData}
      />
    );
  }

  const leaverName = data?.leaver?.name || 'Departing Lead';
  const repoName = data?.artifacts?.[0]?.repo || activeProject?.name?.split('—')[0]?.trim() || 'core-platform';

  return (
    <div className="space-y-6 fade-in">
      {/* Page Header */}
      <PageHeader
        title="Knowledge Risk Map"
        subtitle={`Tracking single-owner hotspots and tacit knowledge exposure for leaver: ${leaverName} (${data?.leaver?.role || 'Lead Engineer'})`}
        badge={activeProject?.mode === 'live' ? 'Live Git Scanned' : 'Deterministic Benchmark'}
        actions={
          <button
            onClick={loadData}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-purple-600' : 'text-slate-400'}`} />
            <span>Recalculate Scores</span>
          </button>
        }
      />

      {/* Metric Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="High-Risk Artifacts"
          value={data?.high_risk_count ?? 0}
          subtext="Deterministic risk score ≥ 30%"
          icon={ShieldAlert}
          accent="rose"
          badge={data?.high_risk_count > 0 ? 'Action required' : 'Low exposure'}
        />

        <MetricCard
          label="Bus-Factor = 1 Hotspots"
          value={data?.bus_factor_violations?.length ?? 0}
          subtext="≥80% sole leaver authorship"
          icon={Users}
          accent="amber"
          badge={data?.bus_factor_violations?.length > 0 ? 'No redundancy' : 'Redundant'}
        />

        <MetricCard
          label="Identified Knowledge Gaps"
          value={
            data?.gaps_planted && data.gaps_planted.length > 0
              ? `${data.gaps_detected?.length ?? 0} / ${data.gaps_planted.length}`
              : `${data?.high_risk_count ?? 0} gaps`
          }
          subtext={
            data?.gaps_planted && data.gaps_planted.length > 0
              ? '100% benchmark ground truth coverage'
              : 'Gaps needing exit interview documentation'
          }
          icon={Target}
          accent="purple"
          badge={data?.gaps_planted && data.gaps_planted.length > 0 ? 'Benchmark' : 'Live'}
        />

        <MetricCard
          label="Monitored Artifacts"
          value={data?.artifacts?.length ?? 0}
          subtext={`Tracked across ${repoName}`}
          icon={FileCode2}
          accent="blue"
        />
      </div>

      {/* Formula Explanation Callout */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Scoring Formula:
            </span>
            <code className="text-xs font-mono font-medium text-purple-700 bg-purple-50 px-2.5 py-1 rounded-md border border-purple-200">
              Risk = OwnershipConcentration × Criticality × (1 − DocCoverage) × RecencyWeight
            </code>
          </div>

          <button
            onClick={() => setShowFormulaInfo(!showFormulaInfo)}
            className="text-xs text-purple-600 hover:text-purple-700 font-medium inline-flex items-center gap-1 self-start sm:self-auto"
          >
            <Info className="w-3.5 h-3.5" />
            <span>{showFormulaInfo ? 'Hide factor definitions' : 'Inspect factor definitions'}</span>
          </button>
        </div>

        {showFormulaInfo && (
          <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs text-slate-600">
            <div>
              <span className="font-semibold text-slate-900 block">Ownership Concentration:</span>
              <span>{leaverName}'s commit count fraction out of total historical touches for this artifact.</span>
            </div>
            <div>
              <span className="font-semibold text-slate-900 block">Criticality (1-5):</span>
              <span>Normalized severity scale based on module imports and operational centrality.</span>
            </div>
            <div>
              <span className="font-semibold text-slate-900 block">Doc Coverage Gap:</span>
              <span>(1 - DocCoverage). 100% gap if zero runbook or documentation exists.</span>
            </div>
            <div>
              <span className="font-semibold text-slate-900 block">Recency Weight:</span>
              <span>1.0 for ≤7d, 0.7 for ≤30d, 0.4 for ≤90d, 0.15 for stale legacy code.</span>
            </div>
          </div>
        )}
      </div>

      {/* Risk Table */}
      <RiskTable
        artifacts={data?.artifacts}
        plantedGaps={data?.gaps_planted}
        leaverName={leaverName}
        repoName={repoName}
        onSelectArtifact={(artifact) => setSelectedArtifact(artifact)}
      />

      {/* Slide-over Artifact Detail Drawer */}
      <ArtifactDetailDrawer
        artifact={selectedArtifact}
        graphData={graphData}
        isOpen={Boolean(selectedArtifact)}
        onClose={() => setSelectedArtifact(null)}
        onNavigateToInterview={onNavigateToInterview}
        leaverName={leaverName}
      />
    </div>
  );
}
