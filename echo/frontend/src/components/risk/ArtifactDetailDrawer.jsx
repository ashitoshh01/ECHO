import React from 'react';
import {
  X,
  FileCode,
  GitPullRequest,
  Ticket,
  MessageSquare,
  FileText,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
  User,
  Clock,
  Layers,
  Sparkles,
  CheckCircle2
} from 'lucide-react';
import { RiskBadge, BusFactorBadge, PlantedGapBadge } from '../common/RiskBadge';
import { getRiskColor } from '../../api';

export default function ArtifactDetailDrawer({
  artifact,
  graphData,
  isOpen,
  onClose,
  onNavigateToInterview,
  leaverName = 'Departing Lead',
}) {
  if (!isOpen || !artifact) return null;

  const color = getRiskColor(artifact.risk_pct);

  const typeIcons = {
    module: FileCode,
    script: FileCode,
    config: FileCode,
    pull_request: GitPullRequest,
    ticket: Ticket,
    chat_thread: MessageSquare,
    document: FileText,
  };

  const TypeIcon = typeIcons[artifact.type] || FileCode;

  // Find edges related to this artifact in graphData
  const relatedEdges = (graphData?.edges || []).filter(
    (e) => e.target === artifact.artifact_id || e.source === artifact.artifact_id
  );

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/30 backdrop-blur-xs">
      <div className="absolute inset-0" onClick={onClose} />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white border-l border-slate-200 shadow-2xl flex flex-col fade-in">
          {/* Header */}
          <div className="p-6 border-b border-slate-200/80 bg-slate-50/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg bg-white border border-slate-200 text-purple-600 shadow-xs">
                  <TypeIcon className="w-4 h-4" />
                </div>
                <div>
                  <span className="text-[11px] font-mono uppercase text-slate-400">
                    {artifact.artifact_id}
                  </span>
                  <span className="text-[11px] font-medium text-slate-500 uppercase ml-2 px-1.5 py-0.5 rounded bg-slate-100">
                    {artifact.type}
                  </span>
                </div>
              </div>

              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <h2 className="text-base font-semibold text-slate-900 mt-3 leading-snug">
              {artifact.title}
            </h2>

            <div className="flex flex-wrap items-center gap-2 mt-3">
              <RiskBadge pct={artifact.risk_pct} size="md" />
              {artifact.bus_factor_one && <BusFactorBadge />}
            </div>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 text-sm">
            {/* Risk Calculation Breakdown */}
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Deterministic Risk Factor Breakdown
              </h3>
              <div className="p-4 bg-slate-50/80 rounded-xl border border-slate-200/80 space-y-3">
                {/* Ownership Concentration */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-500 font-medium">Ownership Concentration ({leaverName})</span>
                    <span className="font-semibold text-slate-800">
                      {Math.round((artifact.components?.ownership_concentration ?? 0) * 100)}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-600 rounded-full"
                      style={{
                        width: `${Math.round((artifact.components?.ownership_concentration ?? 0) * 100)}%`,
                      }}
                    />
                  </div>
                </div>

                {/* Criticality */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-500 font-medium">Criticality Factor</span>
                    <span className="font-semibold text-slate-800">
                      {artifact.components?.criticality != null
                        ? `${Math.round(artifact.components.criticality * 5)} / 5`
                        : '—'}
                    </span>
                  </div>
                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500 rounded-full"
                      style={{
                        width: `${Math.round((artifact.components?.criticality ?? 0) * 100)}%`,
                      }}
                    />
                  </div>
                </div>

                {/* Documentation Gap */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-500 font-medium">Documentation Gap (1 - Coverage)</span>
                    <span className="font-semibold text-slate-800">
                      {Math.round((artifact.components?.doc_gap ?? 0) * 100)}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-rose-500 rounded-full"
                      style={{
                        width: `${Math.round((artifact.components?.doc_gap ?? 0) * 100)}%`,
                      }}
                    />
                  </div>
                </div>

                {/* Recency Multiplier */}
                <div className="pt-2 border-t border-slate-200 flex justify-between items-center text-xs">
                  <span className="text-slate-500 font-medium">Recency Multiplier</span>
                  <span className="font-mono font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                    ×{artifact.components?.recency_weight}
                  </span>
                </div>
              </div>
            </div>

            {/* Knowledge Graph Connections */}
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Knowledge Graph Associations
              </h3>
              {relatedEdges.length > 0 ? (
                <div className="space-y-1.5">
                  {relatedEdges.map((edge, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 p-2.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-700"
                    >
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span className="font-semibold text-slate-900 capitalize">{edge.source}</span>
                      <span className="text-slate-400 font-mono text-[11px] px-1.5 py-0.5 bg-slate-100 rounded">
                        {edge.relation}
                      </span>
                      <span className="text-slate-700 font-mono truncate">{edge.target}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">No direct graph edges recorded for this artifact.</p>
              )}
            </div>

            {/* Leaver Assessment */}
            <div className="p-4 rounded-xl border border-purple-200/80 bg-purple-50/40 space-y-2">
              <div className="flex items-center gap-2 text-purple-800 font-semibold text-xs uppercase tracking-wide">
                <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                <span>Knowledge Extraction Action</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Because this artifact is flagged as high-risk, Echo prioritized it for {leaverName}'s Exit Interview to capture undocumented tacit knowledge before departure.
              </p>
              {onNavigateToInterview && (
                <button
                  onClick={() => {
                    onClose();
                    onNavigateToInterview(artifact.artifact_id);
                  }}
                  className="mt-2 w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition shadow-xs"
                >
                  <span>Go to Exit Interview for this item</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
