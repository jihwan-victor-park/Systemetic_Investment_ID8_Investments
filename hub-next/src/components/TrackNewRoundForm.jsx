'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { PUBLIC_STAGES, STAGE_LABELS, STAGE_BASEPATH } from '@/lib/stages';
import styles from './TrackNewRoundForm.module.css';

// Opt-in second (or third...) tracked round for a company already in the
// pipeline -- see createAdditionalRound in lib/companies.js for the
// dedup/keying logic. Collapsed behind a toggle by default so the common
// case (a company only ever has one round) doesn't add visual noise to
// every company page.
export default function TrackNewRoundForm({ slug }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [round, setRound] = useState('');
  const [stage, setStage] = useState('pipeline');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!open) {
    return (
      <button type="button" className={styles.toggle} onClick={() => setOpen(true)}>
        + Track a new round for this company
      </button>
    );
  }

  async function submit(e) {
    e.preventDefault();
    if (!round.trim()) return;
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`/api/companies/${slug}/rounds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ round: round.trim(), stage }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.error === 'duplicate-round' ? 'That round is already tracked for this company' : 'Failed — try again');
      }
      router.push(`${STAGE_BASEPATH[stage]}/${body.slug}`);
    } catch (err) {
      setSaving(false);
      setError(err.message);
    }
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <input
        className={styles.input}
        value={round}
        onChange={(e) => setRound(e.target.value)}
        placeholder="e.g. Series B"
        disabled={saving}
      />
      <select className={styles.select} value={stage} onChange={(e) => setStage(e.target.value)} disabled={saving}>
        {PUBLIC_STAGES.map((s) => (
          <option key={s} value={s}>{STAGE_LABELS[s]}</option>
        ))}
      </select>
      <button className={styles.submit} type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create'}</button>
      <button type="button" className={styles.cancel} onClick={() => setOpen(false)} disabled={saving}>Cancel</button>
      {error && <span className={styles.error}>{error}</span>}
    </form>
  );
}
