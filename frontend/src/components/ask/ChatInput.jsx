import React, { useState } from 'react';
import { Send, Sparkles, CornerDownLeft } from 'lucide-react';

export default function ChatInput({
  onSend,
  busy,
  suggestedQueries = [
    'Why is the retry limit 7?',
    'What is the wifi password?',
    'How does nightly sync work?',
  ],
}) {
  const [input, setInput] = useState('');

  const handleSend = (textToSend) => {
    const text = (typeof textToSend === 'string' ? textToSend : input).trim();
    if (!text || busy) return;
    setInput('');
    onSend(text);
  };

  return (
    <div className="border-t border-slate-200/80 bg-white/95 backdrop-blur-xs pt-3 pb-2">
      {/* Quick query chips */}
      <div className="flex flex-wrap items-center gap-1.5 mb-2.5">
        <span className="text-[11px] font-medium text-slate-400 mr-1 flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-purple-600" />
          <span>Quick queries:</span>
        </span>
        {suggestedQueries.map((q, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(q)}
            disabled={busy}
            className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 bg-slate-50 text-slate-600 hover:text-purple-700 hover:border-purple-300 hover:bg-purple-50/50 transition disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Input box */}
      <div className="relative flex items-center">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleSend();
            }
          }}
          disabled={busy}
          placeholder='Ask anything about the codebase... (e.g. "Why is the retry limit 7?")'
          className="w-full pl-4 pr-12 py-3 rounded-xl border border-slate-200 bg-white text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition shadow-xs disabled:opacity-50"
        />

        <button
          onClick={() => handleSend()}
          disabled={busy || !input.trim()}
          className="absolute right-2 p-2 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white transition shadow-xs disabled:cursor-not-allowed"
          title="Send message"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>

      <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 px-1">
        <span>Grounded on stored commits, tickets &amp; exit interview answers.</span>
        <span className="hidden sm:inline font-mono">Press Enter to send</span>
      </div>
    </div>
  );
}

