import React, { useState } from 'react';
import {
  FileText,
  CheckCircle2,
  Edit3,
  Sparkles,
  CornerDownLeft,
  AlertCircle,
  HelpCircle,
  ExternalLink,
  Tag,
  ArrowRight
} from 'lucide-react';
import { RiskBadge } from '../common/RiskBadge';

export default function InterviewQuestionCard({
  question,
  index,
  savedAnswer,
  isSaved,
  onSaveAnswer,
  saving,
}) {
  const [answerText, setAnswerText] = useState(savedAnswer || '');
  const [isEditing, setIsEditing] = useState(false);

  const categoryLabels = {
    undocumented_single_owner: 'Undocumented & Single Owner',
    unexplained_change: 'Unexplained Change',
    solo_external_contact: 'Solo External Relationship',
    quiet_failure: 'Quiet Failure Mode',
  };

  const textLower = (answerText || '').toLowerCase();
  const hasDecisionSignal = ['because', 'we chose', 'so that', 'option'].some((k) =>
    textLower.includes(k)
  );

  const handleSave = () => {
    if (!answerText.trim() || saving) return;
    onSaveAnswer(question, answerText.trim());
    setIsEditing(false);
  };

  return (
    <div
      id={`question-${question.artifact_id}`}
      className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs transition hover:border-slate-300/80"
    >
      {/* Question Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-purple-100 text-purple-700 font-bold text-xs flex items-center justify-center">
            {index + 1}
          </span>
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            {categoryLabels[question.gap_type] || question.gap_type}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400">
            {question.artifact_id}
          </span>
          <RiskBadge score={question.risk_score} size="sm" />
        </div>
      </div>

      {/* Question Prompt */}
      <div className="mt-3.5">
        <h3 className="text-sm font-semibold text-slate-900 leading-snug">
          {question.question}
        </h3>
      </div>

      {/* Grounded Evidence Banner */}
      <div className="mt-2.5 p-2.5 rounded-lg bg-slate-50 border border-slate-200/60 flex items-start gap-2 text-xs text-slate-600">
        <FileText className="w-4 h-4 text-purple-600 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-slate-700">Grounded Evidence: </span>
          <span className="font-mono text-slate-800">{question.evidence}</span>
          {question.rationale && (
            <p className="text-[11px] text-slate-500 mt-0.5">{question.rationale}</p>
          )}
        </div>
      </div>

      {/* Answer Area */}
      <div className="mt-4">
        {isSaved && !isEditing ? (
          /* Saved State */
          <div className="p-3.5 rounded-xl bg-emerald-50/70 border border-emerald-200 text-xs">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-emerald-950 flex items-center gap-2">
                    <span>Answer captured &amp; indexed in knowledge graph</span>
                    <span className="text-[10px] font-normal px-2 py-0.2 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                      Linked to {question.artifact_id}
                    </span>
                  </div>
                  <blockquote className="mt-1.5 text-slate-800 italic bg-white/70 p-2.5 rounded-lg border border-emerald-100 text-xs leading-relaxed">
                    &ldquo;{savedAnswer || answerText}&rdquo;
                  </blockquote>
                </div>
              </div>

              <button
                onClick={() => {
                  setAnswerText(savedAnswer || '');
                  setIsEditing(true);
                }}
                className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-purple-600 hover:bg-white px-2.5 py-1 rounded-lg border border-slate-200 bg-white/80 transition shadow-2xs shrink-0"
              >
                <Edit3 className="w-3 h-3" />
                <span>Edit</span>
              </button>
            </div>
          </div>
        ) : (
          /* Input Textarea */
          <div className="space-y-2.5">
            <div className="relative">
              <textarea
                rows={3}
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    handleSave();
                  }
                }}
                placeholder="Type your explanation... (e.g. 'we chose 7 because the vendor API rate-limited us')"
                className="w-full rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition leading-relaxed"
              />
            </div>

            {/* Real-time Decision Signal Pill */}
            {hasDecisionSignal && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-50 border border-purple-200 text-purple-800 text-[11px] fade-in">
                <Sparkles className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                <span className="font-semibold">Architectural rationale detected:</span>
                <span>This will be automatically extracted into the successor Decision Log.</span>
              </div>
            )}

            {/* Actions Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <div className="text-[11px] text-slate-400">
                <span>Tip: Press </span>
                <kbd className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 font-mono text-[10px] text-slate-600">
                  ⌘ + Enter
                </kbd>
                <span> to save</span>
              </div>

              <div className="flex items-center gap-2">
                {isEditing && (
                  <button
                    onClick={() => setIsEditing(false)}
                    className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-800 transition"
                  >
                    Cancel
                  </button>
                )}

                <button
                  onClick={handleSave}
                  disabled={!answerText.trim() || saving}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-xs transition"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{saving ? 'Saving...' : 'Save Answer'}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

