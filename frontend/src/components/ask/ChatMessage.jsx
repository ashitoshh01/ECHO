import React from 'react';
import {
  Sparkles,
  User,
  AlertTriangle,
  Link2,
  FileText,
  Clock,
  ShieldCheck,
  Cpu,
} from 'lucide-react';

function renderInline(str) {
  if (!str) return null;
  const parts = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIndex) {
      parts.push(str.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={match.index} className="font-semibold text-slate-900">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={match.index}
          className="px-1.5 py-0.5 rounded bg-slate-100 text-purple-700 font-mono text-[11px] border border-slate-200/60"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={match.index} className="italic text-slate-700">
          {token.slice(1, -1)}
        </em>
      );
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < str.length) {
    parts.push(str.substring(lastIndex));
  }
  return parts.length > 0 ? parts : str;
}

function FormattedContent({ text, isUser }) {
  if (!text) return null;
  if (isUser) {
    return <div className="whitespace-pre-wrap text-sm leading-relaxed">{text}</div>;
  }

  const blocks = text.split(/\n\n+/);
  return (
    <div className="space-y-2.5 leading-relaxed text-slate-800">
      {blocks.map((block, bIdx) => {
        const trimmed = block.trim();
        if (trimmed.startsWith('# ')) {
          return (
            <h3 key={bIdx} className="text-base font-bold text-slate-900 mt-2 mb-1">
              {renderInline(trimmed.replace(/^#\s+/, ''))}
            </h3>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h4 key={bIdx} className="text-sm font-bold text-slate-900 mt-2 mb-1">
              {renderInline(trimmed.replace(/^##\s+/, ''))}
            </h4>
          );
        }
        if (trimmed.startsWith('### ')) {
          return (
            <h5 key={bIdx} className="text-xs font-bold text-slate-800 uppercase tracking-wide mt-2 mb-1">
              {renderInline(trimmed.replace(/^###\s+/, ''))}
            </h5>
          );
        }
        if (trimmed === '---' || trimmed === '***') {
          return <hr key={bIdx} className="border-slate-200/80 my-2" />;
        }

        const lines = trimmed.split('\n');
        const isBulletList = lines.every((l) => l.trim().startsWith('- ') || l.trim().startsWith('* '));
        if (isBulletList) {
          return (
            <ul key={bIdx} className="list-disc pl-4 space-y-1 my-1.5 text-xs sm:text-sm text-slate-700">
              {lines.map((l, lIdx) => (
                <li key={lIdx}>{renderInline(l.trim().replace(/^[-*]\s+/, ''))}</li>
              ))}
            </ul>
          );
        }

        const isNumberedList = lines.every((l) => /^\d+\.\s+/.test(l.trim()));
        if (isNumberedList) {
          return (
            <ol key={bIdx} className="list-decimal pl-4 space-y-1 my-1.5 text-xs sm:text-sm text-slate-700">
              {lines.map((l, lIdx) => (
                <li key={lIdx}>{renderInline(l.trim().replace(/^\d+\.\s+/, ''))}</li>
              ))}
            </ol>
          );
        }

        return (
          <p key={bIdx} className="text-xs sm:text-sm text-slate-800">
            {lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                {renderInline(line)}
                {lIdx < lines.length - 1 && <br />}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const isUnknown = message.role === 'echo' && message.answer === null;
  const isAi = message.role === 'echo' && (message.ai_provider === 'asi1' || message.is_ai);
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
        className={`max-w-[85%] sm:max-w-[78%] rounded-2xl p-4 transition shadow-xs ${
          isUser
            ? 'bg-slate-900 text-white rounded-tr-xs'
            : isUnknown
            ? 'bg-amber-50/60 border border-amber-200 text-slate-800 rounded-tl-xs'
            : 'bg-white border border-slate-200/80 text-slate-800 rounded-tl-xs'
        }`}
      >
        {/* ASI:One AI Header Badge */}
        {!isUser && isAi && !isUnknown && (
          <div className="flex items-center justify-between pb-2 mb-2.5 border-b border-purple-100">
            <div className="flex items-center gap-1.5 text-purple-700 font-semibold text-[11px]">
              <Sparkles className="w-3.5 h-3.5 text-purple-600 animate-pulse" />
              <span>ASI:One AI Engine</span>
              {message.ai_model && (
                <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 border border-purple-200">
                  {message.ai_model}
                </span>
              )}
            </div>
            <span className="text-[10px] text-slate-400 font-medium">Grounded Context</span>
          </div>
        )}

        {/* Unknown Warning Banner */}
        {isUnknown && (
          <div className="flex items-center gap-1.5 text-amber-800 font-semibold mb-2 pb-2 border-b border-amber-200/60 text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span>Honesty Fallback: No Verified Evidence</span>
          </div>
        )}

        {/* Formatted Content */}
        <FormattedContent text={content} isUser={isUser} />

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
