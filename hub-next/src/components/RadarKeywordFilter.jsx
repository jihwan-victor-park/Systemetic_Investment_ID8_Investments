'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { MIN_KEYWORD_LENGTH } from '@/lib/radarRuleMatch';
import styles from './RadarKeywordFilter.module.css';

// Click-to-filter keyword chips for the Radar tab -- replaces the old
// RadarRulesAdmin.jsx board (live preview, "Excluded from Radar"/"Pinned
// past every rule" panels). Clicking a chip no longer hides anything on its
// own; RadarBoard.jsx (the parent) filters the Hot/Cold tables down to
// whichever chips are active. The keyword LIST itself is still a persisted,
// growing store (lib/radarRules.js) -- Oscar's boss keeps adding new
// off-thesis terms over time -- so this also carries a minimal inline
// add/remove for that store, gated the same `canEdit` way every other
// editable control in the hub is.
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
    <div className={styles.row}>
      <span className={styles.label}>Keywords</span>
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
  );
}
