'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import InlineMarkdown from './InlineMarkdown';
import BlockMarkdown from './BlockMarkdown';
import styles from './ResearchChat.module.css';

const POLL_MS = 5000;

function newId() {
  return (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
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
    </div>
  );
}

function AssistantBubble({ msg }) {
  return (
    <div className={styles.row} data-role="assistant">
      <div className={styles.bubble} data-role="assistant">
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
      if (data.status === 'complete') { patchMessage(msgId, { ...data }); return; }
      if (data.status === 'error') { patchMessage(msgId, { status: 'error', error: data.error || 'research failed' }); return; }
      // still running — keep polling
    }
  }

  async function send(e) {
    e.preventDefault();
    const input = text.trim();
    if (!input || sending) return;

    // Stage 1: the box is a free-text message, parsed server-side into a
    // company (+ optional context) -- that's the "smarter" chat path. Stage 2
    // doesn't have that parsing yet, so the box is still read as a literal
    // company name there, same as the advanced fields below it.
    const body = stage === 1
      ? { message: input, stage }
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
      await poll(data.job_id, pendingId);
    } catch (err) {
      patchMessage(pendingId, { status: 'error', error: err.message });
    } finally {
      if (!cancelledRef.current) setSending(false);
    }
  }

  return (
    <div className={styles.chat}>
      <div className={styles.history}>
        {messages.length === 0 && (
          <div className={styles.empty}>
            Stage 1: just say what to look into — e.g. "look into Ramp's Series D" — and send.
            Results are saved to the hub and show up in Qualified Deals.
            Stage 2 (deep research memo) still needs the company name typed directly; that gets
            smarter later. Both run the real research pipeline at max depth — expect several
            minutes per company.
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
    </div>
  );
}
