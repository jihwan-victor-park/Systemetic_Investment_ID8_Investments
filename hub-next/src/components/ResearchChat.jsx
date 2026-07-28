'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import InlineMarkdown from './InlineMarkdown';
import BlockMarkdown from './BlockMarkdown';
import HubSearchPanel from './HubSearchPanel';
import { useJobs } from '@/context/JobsContext';
import styles from './ResearchChat.module.css';

const POLL_MS = 5000;

function newId() {
  return (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

// Collapsed by default -- this is raw model chain-of-thought / per-angle
// research, kept for QA (e.g. catching a cross-company fact conflation before
// trusting a score) rather than as something to read on every result.
function ReasoningPanel({ label, text }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <div className={styles.reasoning}>
      <button type="button" className={styles.moreToggle} onClick={() => setOpen((v) => !v)}>
        {open ? 'Hide' : 'Show'} {label}
      </button>
      {open && <pre className={styles.reasoningBox}>{text}</pre>}
    </div>
  );
}

// Renders the Stage 1 fit result the same way the hub's own company pages do
// (score, verdict, per-dimension evidence) but compact -- full detail with the
// click-to-expand subcategory breakdown lives on the hub page this links to.
function Stage1Result({ data }) {
  const fit = data.fit || {};
  return (
    <div>
      <p className={styles.resultScore}>
        {fit.fit_score != null ? fit.fit_score.toFixed(1) : '—'} / 4.0
        {fit.raw_score != null && <span className={styles.resultScoreRaw}> (raw {fit.raw_score.toFixed(1)})</span>}
        {data.verdict && <span className={styles.resultVerdict}> — {data.verdict}</span>}
      </p>
      {fit.research_flag && (
        <p className={styles.integrityWarning}>⚠ {fit.research_flag}</p>
      )}
      {fit.hard_auto_pass && fit.hard_auto_pass_reason && (
        <p className={styles.resultNote}><em>Hard auto-pass: {fit.hard_auto_pass_reason}</em></p>
      )}
      {fit.rationale && (
        <p className={styles.resultBody}><InlineMarkdown text={fit.rationale} /></p>
      )}
      {fit.confidence && <p className={styles.resultNote}>Confidence: {fit.confidence}</p>}
      {data.hub_path && (
        <Link href={data.hub_path} className={styles.resultLink}>View full screen (all dimensions + evidence) →</Link>
      )}
      <ReasoningPanel label="reasoning (chain of thought)" text={fit.reasoning} />
    </div>
  );
}

function Stage2Result({ data }) {
  const memo = data.memo || {};
  const body = memo.sections?.memo || '(no memo synthesized)';
  return (
    <div>
      {memo.final_score != null && (
        <p className={styles.resultScore}>{memo.final_score} / 100</p>
      )}
      <BlockMarkdown text={body} />
      {memo.sources?.length > 0 && (
        <>
          <div className={styles.sourcesLabel}>Sources</div>
          <ol className={styles.sourcesList}>
            {memo.sources.map((s) => (
              <li key={s}><a href={s} target="_blank" rel="noopener noreferrer">{s}</a></li>
            ))}
          </ol>
        </>
      )}
      <ReasoningPanel label="raw per-angle research (chain of thought)" text={memo.sections?.raw_research} />
    </div>
  );
}

function AssistantBubble({ msg }) {
  return (
    <div className={styles.row} data-role="assistant">
      <div className={styles.bubble} data-role="assistant">
        <div className={styles.bubbleLabel}>ID8 Research</div>
        {msg.status === 'pending' && (
          <div className={styles.pending}>
            <span className={styles.spinner} aria-hidden="true" />
            Researching <strong>{msg.label}</strong> — Stage {msg.stage}. This can take several minutes at max research depth.
          </div>
        )}
        {msg.status === 'clarification' && (
          <div>{msg.question}</div>
        )}
        {msg.status === 'error' && (
          <div className={styles.error}>Research failed: {msg.error}</div>
        )}
        {msg.status === 'complete' && msg.stage === 1 && <Stage1Result data={msg} />}
        {msg.status === 'complete' && msg.stage === 2 && <Stage2Result data={msg} />}
      </div>
    </div>
  );
}

function UserBubble({ msg }) {
  return (
    <div className={styles.row} data-role="user">
      <div className={styles.bubble} data-role="user">
        <div>{msg.display}</div>
        {msg.meta && <div className={styles.userMeta}>{msg.meta}</div>}
      </div>
    </div>
  );
}

export default function ResearchChat() {
  const [mode, setMode] = useState('research');
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [stage, setStage] = useState(1);
  const [showMore, setShowMore] = useState(false);
  const [domain, setDomain] = useState('');
  const [round, setRound] = useState('');
  const [leadInvestors, setLeadInvestors] = useState('');
  const [hq, setHq] = useState('');
  const [sending, setSending] = useState(false);
  const cancelledRef = useRef(false);
  const endRef = useRef(null);
  const { startJob, reportTerminal } = useJobs();

  useEffect(() => () => { cancelledRef.current = true; }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages]);

  function patchMessage(id, patch) {
    if (cancelledRef.current) return;
    setMessages((m) => m.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg)));
  }

  async function poll(jobId, msgId) {
    for (;;) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      if (cancelledRef.current) return;
      let data;
      try {
        const res = await fetch(`/api/research-chat/${jobId}`, { cache: 'no-store' });
        data = await res.json();
        if (!res.ok) throw new Error(data.error || `poll failed (${res.status})`);
      } catch (err) {
        patchMessage(msgId, { status: 'error', error: err.message });
        return;
      }
      if (data.status === 'complete') {
        patchMessage(msgId, { ...data });
        reportTerminal(jobId, { status: 'complete', verdict: data.verdict });
        return;
      }
      if (data.status === 'error') {
        patchMessage(msgId, { status: 'error', error: data.error || 'research failed' });
        reportTerminal(jobId, { status: 'error', error: data.error || 'research failed' });
        return;
      }
      // still running — keep polling
    }
  }

  async function send(e) {
    e.preventDefault();
    const input = text.trim();
    if (!input || sending) return;

    // If the last turn was a clarification question, re-send that exchange as
    // context so "it's this one: lassie.ai" resolves against "which company?"
    // instead of being parsed alone and failing again. One prior exchange
    // only -- see chat_intent.py's docstring for why this isn't full history.
    let context;
    if (stage === 1) {
      const last = messages[messages.length - 1];
      if (last?.role === 'assistant' && last.status === 'clarification') {
        const prevUser = messages[messages.length - 2];
        context = [
          prevUser?.display ? `Previous message: ${prevUser.display}` : null,
          `Assistant asked: ${last.question}`,
        ].filter(Boolean).join('\n');
      }
    }

    // Stage 1: the box is a free-text message, parsed server-side into a
    // company (+ optional context) -- that's the "smarter" chat path. Stage 2
    // doesn't have that parsing yet, so the box is still read as a literal
    // company name there, same as the advanced fields below it.
    const body = stage === 1
      ? { message: input, stage, context }
      : { name: input, stage, domain: domain || undefined, round: round || undefined, leadInvestors: leadInvestors || undefined, hq };
    const meta = stage === 2 ? [round, domain, leadInvestors, hq].filter(Boolean).join(' · ') : '';

    const userMsg = { id: newId(), role: 'user', display: `${input} — Stage ${stage}`, meta };
    const pendingId = newId();
    setMessages((m) => [...m, userMsg, { id: pendingId, role: 'assistant', status: 'pending', stage, label: input }]);
    setSending(true);
    setText('');

    try {
      const res = await fetch('/api/research-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || `request failed (${res.status})`);
      if (data.status === 'needs_clarification') {
        patchMessage(pendingId, { status: 'clarification', question: data.clarification_question });
        return;
      }
      if (data.name) patchMessage(pendingId, { label: data.name });
      startJob(data.job_id, {
        status: 'running', type: 'chat', label: `${data.name || input} — Stage ${stage}`,
        createdAt: new Date().toISOString(),
      });
      await poll(data.job_id, pendingId);
    } catch (err) {
      patchMessage(pendingId, { status: 'error', error: err.message });
    } finally {
      if (!cancelledRef.current) setSending(false);
    }
  }

  return (
    <div className={styles.chat}>
      <div className={styles.modeTabs}>
        <button type="button" className={mode === 'research' ? styles.modeActive : ''} onClick={() => setMode('research')}>
          Research a company
        </button>
        <button type="button" className={mode === 'search' ? styles.modeActive : ''} onClick={() => setMode('search')}>
          Search the Hub
        </button>
      </div>

      {mode === 'search' ? (
        <HubSearchPanel />
      ) : (
        <>
      <div className={styles.history}>
        {messages.length === 0 && (
          <div className={styles.empty}>
            Stage 1: just say what to look into — e.g. "look into Ramp's Series D" — and send.
            Results are saved to the hub and show up in Qualified Deals.
            Stage 2 (deep research memo) still needs the company name typed directly; that gets
            smarter later. Both run the real research pipeline at max depth — expect several
            minutes per company. Looking for something already in the Hub instead? Switch to
            "Search the Hub" above.
          </div>
        )}
        {messages.map((msg) => (msg.role === 'user'
          ? <UserBubble key={msg.id} msg={msg} />
          : <AssistantBubble key={msg.id} msg={msg} />))}
        <div ref={endRef} />
      </div>

      <form className={styles.form} onSubmit={send}>
        <div className={styles.mainRow}>
          <input
            className={styles.input}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={stage === 1 ? 'e.g. "look into Ramp\'s Series D, led by Founders Fund"' : 'Company name (e.g. Ramp)'}
            disabled={sending}
          />
          <select className={styles.select} value={stage} onChange={(e) => setStage(Number(e.target.value))} disabled={sending}>
            <option value={1}>Stage 1 — fit check</option>
            <option value={2}>Stage 2 — deep research</option>
          </select>
          <button className={styles.send} type="submit" disabled={sending || !text.trim()}>
            {sending ? 'Researching…' : 'Send'}
          </button>
        </div>
        {stage === 2 && (
          <>
            <button type="button" className={styles.moreToggle} onClick={() => setShowMore((v) => !v)}>
              {showMore ? 'Hide details' : 'Add details (domain, round, lead investor, HQ)'}
            </button>
            {showMore && (
              <div className={styles.moreRow}>
                <input className={styles.inputSmall} value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="Domain" disabled={sending} />
                <input className={styles.inputSmall} value={round} onChange={(e) => setRound(e.target.value)} placeholder="Round (e.g. Series C)" disabled={sending} />
                <input className={styles.inputSmall} value={leadInvestors} onChange={(e) => setLeadInvestors(e.target.value)} placeholder="Lead investor(s)" disabled={sending} />
                <input className={styles.inputSmall} value={hq} onChange={(e) => setHq(e.target.value)} placeholder="HQ" disabled={sending} />
              </div>
            )}
          </>
        )}
      </form>
        </>
      )}
    </div>
  );
}
