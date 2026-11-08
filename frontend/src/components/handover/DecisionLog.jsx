import React from 'react';
import { Sparkles, FileCode, CheckCircle2, Inbox } from 'lucide-react';
import EmptyState from '../common/EmptyState';

export default function DecisionLog({ decisions = [], leaverName = 'Departing Lead' }) {
  if (decisions.length === 0) {
    return (
      <EmptyState
        icon={Sparkles}
        title="No decisions logged yet"
        description={`When ${leaverName} answers exit interview questions containing 'because', 'we chose', or 'so that', decisions are automatically extracted here.`}
      />
    );
  }

  return (
    <div className="space-y-3">
      {decisions.map((d, idx) => (
        <div
          key={d.id || idx}
          className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-xs transition hover:border-slate-300/80"
        >
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
              {d.artifact_id}
            </span>
            <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Extracted Rationale</span>
            </span>
          </div>

          <h4 className="text-xs font-semibold text-slate-800 leading-snug">
            {d.decision}
          </h4>

          <div className="mt-2.5 p-3 rounded-lg bg-slate-50 border-l-3 border-purple-600 text-xs text-slate-700 leading-relaxed italic">
            &ldquo;{d.rationale}&rdquo;
          </div>
        </div>
      ))}
    </div>
  );
}
