# Echo Frontend (React + Tailwind) — Working Prototype

A single-file frontend that consumes the Echo FastAPI backend. No build step needed — just one `index.html` using CDN React + Tailwind. Save it in `frontend/index.html`, start the backend (`uvicorn main:app --port 8000`), then open the file in a browser (or serve it: `python -m http.server 3000` → http://localhost:3000).

> ⚠️ Because of browser CORS on `file://`, the easiest zero-setup path is: `cd frontend && python -m http.server 3000` and open http://localhost:3000. The backend already allows origin `*`.

## index.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Echo — Knowledge-Risk Engine</title>
<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { background: #0b0f1a; font-family: Inter, ui-sans-serif, system-ui; }
  ::-webkit-scrollbar { width: 8px; height: 8px; }
  ::-webkit-scrollbar-thumb { background: #2a3550; border-radius: 8px; }
  .glow { box-shadow: 0 0 24px rgba(56,189,248,.15); }
</style>
</head>
<body>
<div id="root"></div>

<script type="text/babel">
const { useState, useEffect, useRef } = React;
const API = "http://localhost:8000";

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  return res.json();
}

function riskColor(pct) {
  if (pct >= 50) return { bar: "bg-rose-500", text: "text-rose-400", badge: "bg-rose-500/15 text-rose-300 border-rose-500/40" };
  if (pct >= 30) return { bar: "bg-amber-500", text: "text-amber-400", badge: "bg-amber-500/15 text-amber-300 border-amber-500/40" };
  return { bar: "bg-emerald-500", text: "text-emerald-400", badge: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" };
}

/* ---------------- Risk Map Tab ---------------- */
function RiskMap() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/risk-map").then(setData).catch(e => setErr(e.message)); }, []);

  if (err) return <ErrorBox msg={err} hint="Is the backend running on port 8000? Run: uvicorn main:app --reload --port 8000" />;
  if (!data) return <Loading label="Computing risk scores…" />;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat label="High-risk artifacts" value={data.high_risk_count} accent="text-rose-400" />
        <Stat label="Bus-factor = 1" value={data.bus_factor_violations.length} accent="text-amber-400" />
        <Stat label="Planted gaps detected" value={`${data.gaps_detected.length} / ${data.gaps_planted.length}`} accent="text-sky-400" />
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-400 font-mono">
        Risk = OwnershipConcentration × Criticality × (1 − DocCoverage) × RecencyWeight
      </div>

      <div className="space-y-3">
        {data.artifacts.map(a => {
          const c = riskColor(a.risk_pct);
          return (
            <div key={a.artifact_id} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 glow">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-slate-100 font-medium">{a.title}</div>
                  <div className="text-xs text-slate-500 mt-1 uppercase tracking-wide">{a.type}</div>
                </div>
                <div className="flex gap-2 shrink-0">
                  {a.bus_factor_one && (
                    <span className="text-xs px-2 py-1 rounded-full border border-rose-500/40 bg-rose-500/10 text-rose-300">⚠ Bus factor 1</span>
                  )}
                  <span className={`text-sm font-bold px-2.5 py-1 rounded-lg ${c.text}`}>{a.risk_pct}%</span>
                </div>
              </div>
              <div className="mt-3 h-2 rounded-full bg-slate-800 overflow-hidden">
                <div className={`h-full rounded-full ${c.bar}`} style={{ width: Math.min(100, a.risk_pct * 2) + "%" }}></div>
              </div>
              <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>ownership {a.components.ownership_concentration}</span>
                <span>criticality {a.components.criticality}</span>
                <span>doc gap {a.components.doc_gap}</span>
                <span>recency ×{a.components.recency_weight}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------- Exit Interview Tab ---------------- */
function Interview() {
  const [data, setData] = useState(null);
  const [answers, setAnswers] = useState({});
  const [saved, setSaved] = useState({});
  const [err, setErr] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(15 * 60);
  useEffect(() => { api("/api/interview/questions?limit=6").then(setData).catch(e => setErr(e.message)); }, []);
  useEffect(() => {
    if (!data) return;
    const t = setInterval(() => setSecondsLeft(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [data]);

  if (err) return <ErrorBox msg={err} />;
  if (!data) return <Loading label="Generating evidence-based questions…" />;

  const mins = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const secs = String(secondsLeft % 60).padStart(2, "0");

  async function submit(q) {
    const answer = answers[q.id] || "";
    if (!answer.trim()) return;
    await api("/api/interview/answers", {
      method: "POST",
      body: JSON.stringify({ question_id: q.id, artifact_id: q.artifact_id, answer }),
    });
    setSaved(s => ({ ...s, [q.id]: true }));
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div>
          <div className="text-slate-100 font-semibold">Exit Interview — Aarav</div>
          <div className="text-xs text-slate-500">Every question is tied to real evidence from his commits, tickets and chats.</div>
        </div>
        <div className={`font-mono text-2xl px-3 py-1 rounded-lg ${secondsLeft < 120 ? "text-rose-400" : "text-sky-400"}`}>{mins}:{secs}</div>
      </div>

      {data.questions.map((q, i) => (
        <div key={q.id} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 glow">
          <div className="flex items-center gap-2 text-xs">
            <span className="px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-300 border border-sky-500/30">Q{i + 1}</span>
            <span className="px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/30">{q.gap_type}</span>
            <span className="text-slate-500">risk {Math.round(q.risk_score * 100)}%</span>
          </div>
          <div className="mt-3 text-slate-100">{q.question}</div>
          <div className="mt-2 text-xs text-slate-500">📎 Evidence: {q.evidence}</div>
          {saved[q.id] ? (
            <div className="mt-3 text-sm text-emerald-400">✓ Answer stored & linked to {q.artifact_id}</div>
          ) : (
            <div className="mt-3 flex gap-2">
              <textarea
                rows="2"
                className="flex-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-100 text-sm p-2 focus:outline-none focus:border-sky-500"
                placeholder="Type your answer… (mention 'because' / 'we chose' to auto-log a decision)"
                value={answers[q.id] || ""}
                onChange={e => setAnswers(a => ({ ...a, [q.id]: e.target.value }))}
              />
              <button onClick={() => submit(q)}
                className="self-end px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium">
                Save
              </button>
            </div>
          )}
        </div>
      ))}
      <button
        onClick={async () => { await api("/api/reset", { method: "POST" }); setSaved({}); setAnswers({}); setSecondsLeft(15 * 60); }}
        className="text-xs text-slate-500 hover:text-slate-300 underline">Reset demo (clear answers)</button>
    </div>
  );
}

/* ---------------- Handover Tab ---------------- */
function Handover() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const load = () => api("/api/handover").then(setData).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);

  if (err) return <ErrorBox msg={err} />;
  if (!data) return <Loading label="Assembling successor package…" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-slate-100 font-semibold text-lg">Handover package for {data.successor.name}</div>
          <div className="text-xs text-slate-500">{data.status.replace(/_/g, " ")} · approved by {data.manager.name}</div>
        </div>
        <button onClick={load} className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:border-sky-500">↻ Refresh</button>
      </div>

      <Section title="🗓 Two-week onboarding path">
        {data.onboarding_path.map((s, i) => (
          <div key={i} className="flex gap-3 py-2 border-b border-slate-800/60 last:border-0">
            <span className="text-xs text-sky-400 font-mono shrink-0 w-20">W{s.week} D{s.days}</span>
            <div>
              <div className="text-sm text-slate-200">{s.task}</div>
              <div className="text-xs text-slate-500">{s.why}</div>
            </div>
          </div>
        ))}
      </Section>

      <Section title="💣 Landmines">
        {data.landmines.map((l, i) => {
          const c = riskColor(l.risk_pct);
          return (
            <div key={l.artifact_id} className="rounded-lg border border-slate-800 bg-slate-800/40 p-3">
              <div className="flex justify-between items-center">
                <div className="text-sm text-slate-200 font-medium">#{i + 1} {l.title}</div>
                <span className={`text-xs font-bold ${c.text}`}>{l.risk_pct}%</span>
              </div>
              <div className={`mt-2 text-xs ${l.captured ? "text-emerald-400" : "text-rose-400"}`}>
                {l.captured ? "✓ Captured from interview: “" + l.captured + "”" : "✗ Not yet captured — run the interview"}
              </div>
            </div>
          );
        })}
      </Section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Section title="🔁 Open loops">
          {data.open_loops.map(o => (
            <div key={o.id} className="text-sm text-slate-300 py-1.5 border-b border-slate-800/60 last:border-0">
              <span className="text-amber-400 mr-2">•</span>{o.title}
            </div>
          ))}
        </Section>
        <Section title="👤 Who to ask">
          {data.who_to_ask.map((w, i) => (
            <div key={i} className="text-sm py-1.5 border-b border-slate-800/60 last:border-0">
              <span className="text-slate-200">{w.area}</span>
              <span className="text-slate-500"> → </span>
              <span className="text-slate-300">{w.contact}</span>
              <span className={`ml-2 text-xs ${w.confidence === "high" ? "text-emerald-400" : "text-amber-400"}`}>({w.confidence})</span>
            </div>
          ))}
        </Section>
      </div>

      <Section title="📜 Decision log">
        {data.decision_log.length === 0 && <div className="text-sm text-slate-500">No decisions captured yet — complete the interview.</div>}
        {data.decision_log.map((d, i) => (
          <div key={i} className="rounded-lg border border-slate-800 bg-slate-800/40 p-3 text-sm">
            <div className="text-slate-300">{d.decision}</div>
            <div className="text-xs text-slate-500 mt-1">Rationale: {d.rationale}</div>
          </div>
        ))}
      </Section>
    </div>
  );
}

/* ---------------- Ask Echo Tab ---------------- */
function AskEcho() {
  const [messages, setMessages] = useState([
    { role: "echo", text: "Hi Meera! Ask me anything about the project. I answer only from stored evidence — if I don't know, I'll tell you who does." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function send() {
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setMessages(m => [...m, { role: "user", text: q }]);
    setBusy(true);
    try {
      const r = await api("/api/ask", { method: "POST", body: JSON.stringify({ question: q }) });
      setMessages(m => [...m, { role: "echo", ...r }]);
    } catch (e) {
      setMessages(m => [...m, { role: "echo", answer: null, echo_says: "Backend error: " + e.message, citations: [] }]);
    }
    setBusy(false);
  }

  return (
    <div className="flex flex-col h-[70vh]">
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${m.role === "user"
              ? "bg-sky-600 text-white rounded-br-sm"
              : "bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-sm glow"}`}>
              {m.role === "echo" && m.answer === null && (
                <div className="flex items-center gap-2 text-amber-400 font-medium mb-1">
                  <span>⚠</span> Unknown
                </div>
              )}
              <div>{m.role === "echo" ? (m.answer || m.echo_says) : m.text}</div>
              {m.stale_warning && <div className="mt-2 text-xs text-amber-400">⚠ Some sources may be stale — the runbook hasn't been updated in 8 months.</div>}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-3 border-t border-slate-700/60 pt-2">
                  <div className="text-xs text-slate-500 mb-1">Sources:</div>
                  {m.citations.map((c, j) => (
                    <div key={j} className="text-xs text-sky-400">🔗 {c.source} <span className="text-slate-600">({c.kind})</span></div>
                  ))}
                </div>
              )}
              {m.suggested_contact && (
                <div className="mt-2 text-xs text-violet-300">💡 Suggested contact: {m.suggested_contact}</div>
              )}
            </div>
          </div>
        ))}
        {busy && <div className="text-slate-500 text-sm">Echo is searching evidence…</div>}
        <div ref={endRef} />
      </div>
      <div className="mt-3 flex gap-2">
        <input
          className="flex-1 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 px-4 py-3 text-sm focus:outline-none focus:border-sky-500"
          placeholder='Try: "Why is the retry limit 7?" or "What is the wifi password?"'
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
        />
        <button onClick={send} disabled={busy}
          className="px-5 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-40 text-white font-medium">Send</button>
      </div>
    </div>
  );
}

/* ---------------- Shared bits ---------------- */
function Stat({ label, value, accent }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 glow">
      <div className={`text-3xl font-bold ${accent}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}
function Section({ title, children }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="text-sm font-semibold text-slate-200 mb-3">{title}</div>
      <div>{children}</div>
    </div>
  );
}
function Loading({ label }) {
  return <div className="text-slate-500 animate-pulse">{label}</div>;
}
function ErrorBox({ msg, hint }) {
  return (
    <div className="rounded-xl border border-rose-800 bg-rose-950/40 p-4 text-rose-300 text-sm">
      <div className="font-semibold">Backend not reachable</div>
      <div className="mt-1">{msg}</div>
      {hint && <div className="mt-2 text-rose-400/70">{hint}</div>}
    </div>
  );
}

/* ---------------- App shell ---------------- */
const TABS = [
  { id: "risk", label: "Risk Map", icon: "🗺", comp: RiskMap },
  { id: "interview", label: "Exit Interview", icon: "🎤", comp: Interview },
  { id: "handover", label: "Handover", icon: "📦", comp: Handover },
  { id: "ask", label: "Ask Echo", icon: "💬", comp: AskEcho },
];

function App() {
  const [tab, setTab] = useState("risk");
  const Active = TABS.find(t => t.id === tab).comp;
  return (
    <div className="min-h-screen text-slate-200">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center font-bold text-white">E</div>
            <div>
              <div className="font-semibold text-white">Echo</div>
              <div className="text-xs text-slate-500">Knowledge-Risk Engine for Seamless Team Handovers</div>
            </div>
          </div>
          <div className="text-xs text-slate-500 hidden md:block">We Code Coders · Hackathon prototype</div>
        </div>
        <div className="max-w-5xl mx-auto px-4 flex gap-1">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm rounded-t-lg border-b-2 transition ${tab === t.id
                ? "border-sky-500 text-sky-300 bg-slate-900/40"
                : "border-transparent text-slate-500 hover:text-slate-300"}`}>
              <span className="mr-1">{t.icon}</span>{t.label}
            </button>
          ))}
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Active />
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
</script>
</body>
</html>
```

## Demo flow (2-minute judge story)

1. **Risk Map** — open first. Show high-risk count, bus-factor badges, and the transparent formula. Say: *"This runs continuously, not just at exit."*
2. **Exit Interview** — questions reference real artifacts ("In PR #214 you changed the retry limit 3 → 7 with no explanation…"). Answer the retry question with *"we chose 7 because the vendor API rate-limited us"* → auto-logged as a decision.
3. **Handover** — landmine shows the captured answer in green; decision log populated. Click **Refresh**.
4. **Ask Echo** — ask **"Why is the retry limit 7?"** → cited answer from Aarav's interview. Then ask **"What is the wifi password?"** → *Unknown — suggested contact: priya*. That honesty moment is your originality closer.
5. Mention the evaluation hook: the backend reports `gaps_detected` vs `gaps_planted` (gap coverage metric from Section 8).

## Rubric coverage in this frontend

| Rubric area | Where the UI shows it |
|---|---|
| Problem understanding (25) | Risk Map stat cards + formula banner |
| Solution (25) | All 4 tabs = the 5 pillars visually |
| Technical plan (20) | Deterministic score components shown per artifact |
| Originality (15) | Evidence badges on questions, "Unknown → ask Priya" fallback |
| Feasibility (15) | Two files, no build step, runs on any laptop |

Troubleshooting: if tabs show "Backend not reachable", confirm `uvicorn main:app --port 8000` is running and open the frontend via `http://localhost:3000` (not `file://`), or change `const API` in the file to `"http://127.0.0.1:8000"`.
