'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { MIN_KEYWORD_LENGTH } from '@/lib/radarRuleMatch';
import styles from './RadarKeywordFilter.module.css';

// Click-to-EXCLUDE keyword chips for the Radar tab -- replaces the old
// RadarRulesAdmin.jsx board (live preview, "Excluded from Radar"/"Pinned
// past every rule" panels) with the same net effect (off-thesis companies
// drop out of the Hot/Cold tables) minus the boxed admin UI. RadarBoard.jsx
// (the parent) hides whichever rows match an active chip and names them in
// an "Excluded by keyword" list right below -- un-toggling the chip is the
// restore, no separate pin needed. The keyword LIST itself is still a
// persisted, growing store (lib/radarRules.js) -- Oscar's boss keeps adding
// new off-thesis terms over time -- so this also carries a minimal inline
// add/remove for that store, gated the same `canEdit` way every other
// editable control in the hub is.
//
// Closed by default (Oscar, 2026-07-29: "not visible right when you open
// the thing") -- a plain <details>/<summary> disclosure, same lightweight
// pattern RadarBoard.jsx's own "Excluded by keyword" results list already
// uses, no extra JS state needed. The summary line itself doubles as a live
// count of how many exclusions are currently active.
export default function RadarKeywordFilter({ keywords, active, onToggle, canEdit }) {
  const router = useRouter();
  const [term, setTerm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const canAdd = term.trim().length >= MIN_KEYWORD_LENGTH && !busy;

  async function addKeyword(e) {
    e.preventDefault();
    if (!canAdd) return;
    setBusy(true);
    setError('');
    try {
      const res = await fetch('/api/radar-rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'addKeyword', term: term.trim() }),
      });
      if (!res.ok) throw new Error('save-failed');
      setTerm('');
      router.refresh();
    } catch {
      setError('Failed — try again');
    } finally {
      setBusy(false);
    }
  }

  async function removeKeyword(t) {
    setBusy(true);
    try {
      const res = await fetch(`/api/radar-rules?term=${encodeURIComponent(t)}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('save-failed');
      router.refresh();
    } catch {
      setError('Failed — try again');
    } finally {
      setBusy(false);
    }
  }

  if (!keywords.length && !canEdit) return null;

  return (
    <details className={styles.details}>
      <summary className={styles.summary}>
        Excluded keywords{active.length > 0 ? ` (${active.length} active)` : ''}
      </summary>
      <div className={styles.row}>
      {keywords.map((k) => (
        <span key={k.term} className={styles.chip} data-active={active.includes(k.term)}>
          <button type="button" className={styles.chipBtn} onClick={() => onToggle(k.term)}>{k.term}</button>
          {canEdit && (
            <button
              type="button"
              className={styles.remove}
              aria-label={`Remove keyword ${k.term}`}
              onClick={() => removeKeyword(k.term)}
              disabled={busy}
            >
              ×
            </button>
          )}
        </span>
      ))}
      {keywords.length === 0 && <span className={styles.empty}>No keywords yet.</span>}
      {canEdit && (
        <form className={styles.addForm} onSubmit={addKeyword}>
          <input
            className={styles.addInput}
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="+ add keyword"
            disabled={busy}
          />
        </form>
      )}
      {error && <span className={styles.error}>{error}</span>}
      </div>
    </details>
  );
}
