import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Bot,
  ShieldCheck,
  RefreshCw,
  Cpu,
  Key,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  X,
  Settings,
} from 'lucide-react';
import PageHeader from '../common/PageHeader';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { echoApi } from '../../api';

export default function AskEcho({ activeProject, successor, refreshKey }) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [aiStatus, setAiStatus] = useState(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [savingKey, setSavingKey] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const scrollRef = useRef(null);

  const successorName = successor?.name || 'Successor';

  const defaultGreeting = {
    role: 'echo',
    text: `Hi ${successorName}! I'm Echo, your knowledge assistant powered by ASI:One. I answer questions with deep grounding across the codebase, commit history, exit interview notes, and architectural decisions. If evidence is missing, I won't guess — I'll tell you who to ask instead.`,
    citations: [],
    ai_provider: 'asi1',
    ai_model: 'asi1',
    is_ai: true,
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

  const loadAiStatus = async () => {
    try {
      const st = await echoApi.getAiStatus();
      setAiStatus(st);
    } catch (e) {
      console.error('Failed to load AI status:', e);
    }
  };

  useEffect(() => {
    loadConversationHistory();
    loadAiStatus();
  }, [activeProject?.id, refreshKey]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const handleSend = async (queryText) => {
    if (!queryText.trim() || busy) return;

    // Append user message immediately
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
          echo_says: `Error contacting ASI:One AI assistant: ${e.message}`,
          citations: [],
          is_ai: false,
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const clearChat = () => {
    setMessages([defaultGreeting]);
  };

  const handleSaveKey = async (e) => {
    e?.preventDefault();
    if (!newKey.trim()) return;
    setSavingKey(true);
    try {
      const updated = await echoApi.updateAiConfig(newKey.trim());
      setAiStatus(updated);
      setSaveSuccess(true);
      setNewKey('');
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      alert(`Failed to save key: ${err.message}`);
    } finally {
      setSavingKey(false);
    }
  };

  // Determine dynamic suggested queries based on active project
  const isEvakili = activeProject?.name?.toLowerCase().includes('evakili') || activeProject?.id === 'proj-live';
  const suggestedQueries = isEvakili
    ? [
        'What features are built in evakili?',
        'Why was staticfiles autocomplete added?',
        'What changes did Ashu make recently?',
        'Who should I ask about Core Architecture?',
      ]
    : [
        'Why is the retry limit 7?',
        'What is the wifi password?',
        'How does nightly sync work?',
      ];

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-10rem)] fade-in">
      {/* Header */}
      <PageHeader
        title="Ask Echo"
        subtitle="Retrieval-first Q&A assistant grounded in verified project commits, tickets and interview responses"
        badge="Trust Layer"
        actions={
          <div className="flex items-center gap-2">
            {/* AI Engine Status Pill */}
            <button
              onClick={() => setShowConfigModal(true)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition shadow-xs ${
                aiStatus?.is_configured
                  ? 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100/70'
                  : 'bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100/70'
              }`}
              title="Click to view or edit ASI:One AI configuration"
            >
              <Sparkles
                className={`w-3.5 h-3.5 ${
                  aiStatus?.is_configured ? 'text-purple-600 animate-pulse' : 'text-amber-600'
                }`}
              />
              <span>
                {aiStatus?.is_configured ? 'ASI:One Active' : 'ASI:One: Set Key in .env'}
              </span>
              {aiStatus?.is_configured && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
              )}
            </button>

            {/* Clear View Button */}
            <button
              onClick={clearChat}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition shadow-xs"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
              <span>Clear View</span>
            </button>
          </div>
        }
      />

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-1 py-4 space-y-4">
        {messages.map((m, idx) => (
          <ChatMessage key={m.id || idx} message={m} />
        ))}

        {busy && (
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-purple-50/80 border border-purple-100 text-purple-800 text-xs w-fit shadow-xs animate-pulse">
            <Sparkles className="w-4 h-4 text-purple-600 animate-spin" />
            <span>Echo is consulting ASI:One AI with full project context &amp; commits...</span>
          </div>
        )}

        <div ref={scrollRef} />
      </div>

      {/* Input container */}
      <ChatInput
        onSend={handleSend}
        busy={busy}
        suggestedQueries={suggestedQueries}
      />

      {/* ASI:One Configuration Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-start justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center font-bold">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 text-sm">ASI:One AI Engine</h3>
                  <p className="text-xs text-slate-500">Autonomous intelligence by Fetch.ai / ASI Alliance</p>
                </div>
              </div>
              <button
                onClick={() => setShowConfigModal(false)}
                className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 my-4 text-xs text-slate-600">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Provider &amp; Model:</span>
                  <span className="font-mono font-medium text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {aiStatus?.model || 'asi1'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">API Endpoint:</span>
                  <span className="font-mono text-[11px] text-slate-600">
                    {aiStatus?.base_url || 'https://api.asi1.ai/v1'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Status:</span>
                  <span className="inline-flex items-center gap-1 font-medium text-emerald-600">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    <span>{aiStatus?.is_configured ? 'Active & Grounded' : 'Needs API Key'}</span>
                  </span>
                </div>
                {aiStatus?.masked_key && (
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Loaded Key:</span>
                    <span className="font-mono text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200 text-[11px]">
                      {aiStatus.masked_key}
                    </span>
                  </div>
                )}
              </div>

              <div className="p-3 rounded-xl bg-purple-50/60 border border-purple-100 text-purple-900">
                <p className="font-medium mb-1">Environment File (.env)</p>
                <p className="text-[11px] text-purple-700 leading-relaxed">
                  Your key is saved in the project's root <code className="bg-purple-100 px-1 py-0.5 rounded font-mono">.env</code> file under <code className="bg-purple-100 px-1 py-0.5 rounded font-mono">ASI1_API_KEY</code>. You can paste or update it directly in the file, or use the form below.
                </p>
              </div>

              <form onSubmit={handleSaveKey} className="space-y-2">
                <label className="block font-medium text-slate-700">Update ASI:One API Key:</label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={newKey}
                    onChange={(e) => setNewKey(e.target.value)}
                    placeholder="sk_..."
                    className="flex-1 px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:border-purple-500 text-xs font-mono"
                  />
                  <button
                    type="submit"
                    disabled={savingKey || !newKey.trim()}
                    className="px-3 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium text-xs transition disabled:opacity-50"
                  >
                    {savingKey ? 'Saving...' : 'Save'}
                  </button>
                </div>
                {saveSuccess && (
                  <p className="text-[11px] text-emerald-600 font-medium">✓ Key successfully saved to .env!</p>
                )}
              </form>
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setShowConfigModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-medium hover:bg-slate-800 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
