'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { STAGE_LABELS } from '@/lib/stages';
import styles from './StageSelect.module.css';

// Inline dropdown that moves a company between Watchlist / Pipeline /
// Qualified Deals from wherever it's listed. Optimistic: flips immediately,
// reverts on failure. On success it calls router.refresh() so the row
// actually leaves the table it no longer belongs to (each stage's table only
// shows companies currently in that stage).
export default function StageSelect({ slug, stage, canEdit }) {
  const router = useRouter();
  const [value, setValue] = useState(stage);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!canEdit) return <span>{STAGE_LABELS[value] || value}</span>;

  async function onChange(e) {
    const next = e.target.value;
    const prev = value;
    setValue(next);
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`/api/companies/${slug}/stage`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: next }),
      });
      if (!res.ok) throw new Error('save-failed');
      router.refresh();
    } catch {
      setValue(prev);
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  return (
    <span className={styles.wrap}>
      <select className={styles.select} value={value} disabled={saving} onChange={onChange}>
        {Object.entries(STAGE_LABELS).map(([key, label]) => (
          <option key={key} value={key}>{label}</option>
        ))}
      </select>
      {error && <span className={styles.error}>{error}</span>}
    </span>
  );
}
