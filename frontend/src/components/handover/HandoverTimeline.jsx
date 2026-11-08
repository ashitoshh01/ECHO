import React, { useState } from 'react';
import { Calendar, CheckCircle2, Circle, ArrowRight } from 'lucide-react';
import { echoApi } from '../../api';

export default function HandoverTimeline({ onboardingPath = [], onTaskToggled }) {
  const [togglingId, setTogglingId] = useState(null);

  const handleToggle = async (step) => {
    if (togglingId) return;
    setTogglingId(step.id);
    try {
      if (step.id) {
        await echoApi.toggleOnboardingTask(step.id);
      }
      if (onTaskToggled) onTaskToggled();
    } catch (e) {
      console.error('Failed to toggle task:', e);
    } finally {
      setTogglingId(null);
    }
  };

  if (onboardingPath.length === 0) {
    return (
      <div className="p-8 text-center text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl bg-white">
        No onboarding tasks generated yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {onboardingPath.map((step, idx) => {
        const isDone = Boolean(step.is_completed);
        return (
          <div
            key={step.id || idx}
            onClick={() => handleToggle(step)}
            className={`p-4 rounded-xl border transition cursor-pointer flex items-start gap-3.5 ${
              isDone
                ? 'bg-slate-50 border-slate-200/60 opacity-80'
                : 'bg-white border-slate-200/80 hover:border-slate-300/80 shadow-xs'
            }`}
          >
            {/* Checkbox button */}
            <button
              type="button"
              className="mt-0.5 text-slate-400 hover:text-purple-600 transition shrink-0"
            >
              {isDone ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ) : (
                <Circle className="w-5 h-5 text-slate-300" />
              )}
            </button>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                  Week {step.week} · Days {step.days}
                </span>
                <span className={`text-xs text-slate-400 ${isDone ? 'line-through' : ''}`}>
                  Phase {step.week === 1 ? 'Orientation & Shadowing' : 'Independent Execution'}
                </span>
              </div>

              <div
                className={`text-sm font-semibold transition ${
                  isDone ? 'text-slate-500 line-through' : 'text-slate-900'
                }`}
              >
                {step.task}
              </div>

              <div className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
                <span className="font-medium text-slate-600">Rationale:</span>
                <span>{step.why}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
