# Echo — Demo Run & Presentation Guide
## We Code Coders · Hackathon submission · Companion to the Backend + Frontend prototypes

---

## 1. Run instructions (end to end)

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
#   -> API docs: http://localhost:8000/docs

# 2. Frontend
cd ../frontend
npm run dev
#   -> open http://localhost:3000
```

**Backup during the demo:** keep `http://localhost:8000/docs` open in a second browser tab — if the UI ever hiccups you can demo every endpoint straight from Swagger. Before the judges arrive, click "Reset demo" in the Exit Interview tab so answers start empty.

---

## 2. The 2-minute judge demo script (mapped to rubric)

| Time | Action | Say this | Rubric section |
|---|---|---|---|
| 0:00–0:20 | **Risk Map** tab | "When Aarav resigns, most teams summarize what he wrote down. Echo instead finds what only he *knows*. This map runs continuously — scores use a transparent, deterministic formula, not a black box." | Problem understanding (25) |
| 0:20–0:50 | Point at the top 3 artifacts + bus-factor badges; show formula banner | "nightly_sync.py: one owner, zero docs, high criticality, touched 3 days ago. That's a landmine waiting to go off." Show `gaps detected 4/4 planted`. | Technical plan (20) |
| 0:50–1:20 | **Exit Interview** tab | "The questions aren't a generic HR form — each is generated from evidence in Aarav's own commits." Answer the retry question: *"we chose 7 because the vendor API rate-limited us"* → decision auto-logged. | Solution (25) + Originality (15) |
| 1:20–1:40 | **Handover** tab → Refresh | "Meera gets a personalized package, not a PDF: a two-week path, landmines with the captured answer attached, open loops, who-to-ask." | Solution (25) |
| 1:40–2:00 | **Ask Echo** tab. Ask **"Why is the retry limit 7?"** → cited answer. Then **"What is the wifi password?"** → *Unknown — suggested contact: priya* | "Every answer is cited. And when we don't know, Echo says so — it never invents an answer to a new joiner. That's the trust layer." | Originality (15) closer |

### One-line closing
> "A summary repeats what's written. Echo detects what's *missing* — that's the shift from summarization to knowledge-risk management."

---

## 3. Likely judge Q&A (rehearse these)

**Q: Isn't this just another RAG chatbot?**
A: No. RAG answers questions about what exists. Echo's core is **gap detection** — it surfaces what's *absent* (single-owner modules, unexplained changes, undocumented processes) and drives an interview about those gaps. The chat is just the delivery layer.

**Q: What about privacy?**
A: Read-only connectors, admin-authorized sources only, personal DMs excluded by default, full audit logging, and the leaver approves everything before publication (human-in-the-loop is a design principle, not a bolt-on).

**Q: Won't the LLM hallucinate?**
A: Retrieval-first: answers come only from stored evidence with citations. If retrieval returns nothing relevant, the system is *required* to say "unknown" and suggest who might know. You just saw that fallback live.

**Q: Why deterministic risk scoring instead of ML?**
A: Transparency and trust. Managers must be able to defend "why is this flagged high-risk" to the leaver. The formula — Ownership Concentration × Criticality × (1 − Doc Coverage) × Recency — is auditable, and ML can layer on top later.

**Q: Does this scale beyond a demo repo?**
A: The architecture is connector-based (GitHub/Slack/Jira APIs → normalized events → graph). The MVP uses seeded data and PostgreSQL + pgvector to stay simple; Neo4j and live connectors are the documented upgrade path. Nothing here requires new research — that's the feasibility story.

**Q: How do you know it works?**
A: We measure gap coverage: we planted 4 known knowledge gaps in the demo data and the risk map detects all 4 (`gaps_detected` vs `gaps_planted` in the API). We also track question relevance and answer citation accuracy — metrics from our evaluation plan.

---

## 4. Metrics the prototype already reports

- **Gap coverage:** `GET /api/risk-map` → `gaps_detected: [4 of 4 planted gaps]`
- **Bus-factor violations:** `bus_factor_violations` list (single-owner artifacts)
- **Interview capture:** `interview_answers_captured` in `GET /api/handover` coverage block
- **Honesty behavior:** `POST /api/ask` returns `answer: null` + `suggested_contact` on no-evidence questions

---

## 5. Submission checklist

- [ ] Export the written proposal as **PDF**
- [ ] Upload PDF to Google Drive, share as **"Anyone with the link: Viewer"**
- [ ] Paste the link into the **Google Form**
- [ ] **Every team member submits individually**
- [ ] Test the full demo on a machine with internet (frontend loads React/Tailwind from CDN) **and** a backup (phone hotspot) — also screenshot each tab as a fallback if the laptop fails
- [ ] Reset demo state before presenting
