import React from 'react';
import {
  Sparkles,
  User,
  AlertTriangle,
  HelpCircle,
  ExternalLink,
  Link2,
  FileText,
  Clock,
  ShieldCheck,
} from 'lucide-react';

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const isUnknown = message.role === 'echo' && message.answer === null;
  const content = isUser
    ? message.text
    : (message.answer || message.echo_says || message.text);

  return (
    <div className={`flex gap-3 text-xs leading-relaxed ${isUser ? 'justify-end' : 'justify-start'}`}>
      {/* Echo Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 text-white flex items-center justify-center shrink-0 shadow-xs shadow-purple-500/20 mt-0.5">
          <Sparkles className="w-4 h-4" />
        </div>
      )}

      {/* Message Content Container */}
      <div
        className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 transition shadow-xs ${
          isUser
            ? 'bg-slate-900 text-white rounded-tr-xs'
            : isUnknown
            ? 'bg-amber-50/60 border border-amber-200 text-slate-800 rounded-tl-xs'
            : 'bg-white border border-slate-200/80 text-slate-800 rounded-tl-xs'
        }`}
      >
        {/* Unknown Warning Banner */}
        {isUnknown && (
          <div className="flex items-center gap-1.5 text-amber-800 font-semibold mb-2 pb-2 border-b border-amber-200/60 text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span>Honesty Fallback: No Verified Evidence</span>
          </div>
        )}

        {/* Message Text */}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {content}
        </div>

        {/* Stale Documentation Warning */}
        {message.stale_warning && (
          <div className="mt-3 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center gap-2">
            <Clock className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Caution: Referenced documentation has not been touched in 8+ months.</span>
          </div>
        )}

        {/* Citations List */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-100 space-y-1.5">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
              <Link2 className="w-3 h-3 text-purple-600" />
              <span>Grounded Evidence Citations:</span>
            </div>
            <div className="space-y-1">
              {message.citations.map((c, idx) => (
                <div
                  key={idx}
                  className="p-2 rounded-lg bg-slate-50 border border-slate-200/60 flex items-center justify-between gap-2 text-xs text-slate-700"
                >
                  <div className="flex items-center gap-1.5 truncate">
                    <FileText className="w-3.5 h-3.5 text-purple-500 shrink-0" />
                    <span className="font-medium truncate">{c.source}</span>
                  </div>
                  <div className="flex items-center gap-1 shrink-0 font-mono text-[10px]">
                    <span className="px-1.5 py-0.5 rounded bg-slate-200/70 text-slate-600">
                      {c.kind}
                    </span>
                    {c.artifact_id && (
                      <span className="px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                        {c.artifact_id}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Suggested Contact Referral */}
        {message.suggested_contact && (
          <div className="mt-2.5 p-2 rounded-lg bg-purple-50 border border-purple-200 text-xs text-purple-900 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-purple-600" />
              <span>Suggested Domain Expert:</span>
              <span className="font-semibold capitalize">{message.suggested_contact}</span>
            </div>
            <span className="text-[10px] text-purple-600 font-medium">Platform Engineering</span>
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-purple-100 text-purple-700 font-semibold flex items-center justify-center shrink-0 border border-purple-200 mt-0.5 text-xs">
          M
        </div>
      )}
    </div>
  );
}

