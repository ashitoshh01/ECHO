import React, { useState, useEffect, useRef } from 'react';
import { Sparkles, Bot, ShieldCheck, RefreshCw } from 'lucide-react';
import PageHeader from '../common/PageHeader';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { echoApi } from '../../api';

export default function AskEcho({ activeProject, successor, refreshKey }) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const scrollRef = useRef(null);

  const successorName = successor?.name || 'Successor';

  const defaultGreeting = {
    role: 'echo',
    text: `Hi ${successorName}! I'm Echo, your knowledge assistant. I answer questions exclusively from verified commits, runbooks, and exit interview answers. If evidence is missing, I won't guess — I'll tell you who to ask instead.`,
    citations: [],
  };

  const loadConversationHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await echoApi.getConversations(activeProject?.id);
      if (res && res.messages && res.messages.length > 0) {
        setMessages(res.messages);
      } else {
        setMessages([defaultGreeting]);
      }
    } catch (e) {
      setMessages([defaultGreeting]);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadConversationHistory();
  }, [activeProject?.id, refreshKey]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const handleSend = async (queryText) => {
    if (!queryText.trim() || busy) return;

    // Append user message immediately for responsive UI
    setMessages((prev) => [...prev, { role: 'user', text: queryText }]);
    setBusy(true);

    try {
      const response = await echoApi.askEcho(queryText, successorName, activeProject?.id);
      setMessages((prev) => [...prev, { role: 'echo', ...response }]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'echo',
          answer: null,
          echo_says: `Error contacting knowledge retrieval engine: ${e.message}`,
          citations: [],
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const clearChat = () => {
    setMessages([defaultGreeting]);
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-10rem)] fade-in">
      {/* Header */}
      <PageHeader
        title="Ask Echo"
        subtitle={`Retrieval-first Q&A assistant grounded in verified project commits, tickets and interview responses`}
        badge="Trust Layer"
        actions={
          <button
            onClick={clearChat}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition shadow-xs"
          >
            <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
            <span>Clear View</span>
          </button>
        }
      />

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-1 py-4 space-y-4">
        {messages.map((m, idx) => (
          <ChatMessage key={m.id || idx} message={m} />
        ))}

        {busy && (
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-purple-50/60 border border-purple-100 text-purple-800 text-xs w-fit">
            <Sparkles className="w-4 h-4 text-purple-600 animate-spin" />
            <span>Echo is searching knowledge graph and decision logs...</span>
          </div>
        )}

        <div ref={scrollRef} />
      </div>

      {/* Input container */}
      <ChatInput
        onSend={handleSend}
        busy={busy}
        suggestedQueries={[
          'Why is the retry limit 7?',
          'What is the wifi password?',
          'How does nightly sync work?',
        ]}
      />
    </div>
  );
}
