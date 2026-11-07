import React from 'react';
import { Clock, CheckCircle2, Award, Sparkles } from 'lucide-react';

export default function InterviewProgress({
  totalQuestions = 6,
  answeredCount = 0,
  secondsLeft = 15 * 60,
  decisionCount = 0,
}) {
  const mins = String(Math.floor(secondsLeft / 60)).padStart(2, '0');
  const secs = String(secondsLeft % 60).padStart(2, '0');
  const pct = totalQuestions > 0 ? Math.round((answeredCount / totalQuestions) * 100) : 0;
  const isUrgent = secondsLeft < 120;

  return (
    <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Left: Progress info */}
        <div className="space-y-1.5 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Knowledge Extraction Progress
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
              {answeredCount} of {totalQuestions} answered ({pct}%)
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden max-w-md">
            <div
              className="h-full bg-gradient-to-r from-purple-500 to-indigo-600 rounded-full transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Right: Metrics + Countdown */}
        <div className="flex items-center gap-4 shrink-0">
          {/* Decision badge */}
          {decisionCount > 0 && (
            <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
              <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
              <span className="font-semibold">{decisionCount}</span>
              <span>decisions logged</span>
            </div>
          )}

          {/* Countdown Timer */}
          <div
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl border transition ${
              isUrgent
                ? 'bg-rose-50 border-rose-200 text-rose-700'
                : 'bg-slate-50 border-slate-200 text-slate-800'
            }`}
          >
            <Clock className={`w-4 h-4 ${isUrgent ? 'text-rose-500 animate-pulse' : 'text-slate-400'}`} />
            <div>
              <div className="font-mono text-base font-bold leading-none">
                {mins}:{secs}
              </div>
              <div className="text-[10px] text-slate-400 leading-none mt-0.5">Time budget</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

