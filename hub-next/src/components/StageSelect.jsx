'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { STAGE_LABELS, PUBLIC_STAGES } from '@/lib/stages';
import styles from './StageSelect.module.css';

// Inline dropdown that moves a company between Watchlist / Pipeline /
// Qualified Deals / Radar / Invested from wherever it's listed. Optimistic:
// flips immediately, reverts on failure. On success it calls
// router.refresh() so the row actually leaves the table it no longer
// belongs to (each stage's table only shows companies currently in that
// stage).
//
// Options come from PUBLIC_STAGES ('new'/Needs Triage excluded -- it's an
// Attio-import-only holding bucket, never a hand-picked destination). A row
// can still legitimately BE 'new' though (Admin's Needs Triage table renders
// this same component for those rows) -- if the current `stage` isn't in
// PUBLIC_STAGES, it's prepended so the select shows the real current value
// instead of silently rendering blank.
export default function StageSelect({ slug, stage, canEdit }) {
  const router = useRouter();
  const [value, setValue] = useState(stage);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const options = PUBLIC_STAGES.includes(value) ? PUBLIC_STAGES : [value, ...PUBLIC_STAGES];

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
        {options.map((key) => (
          <option key={key} value={key}>{STAGE_LABELS[key] || key}</option>
        ))}
      </select>
      {error && <span className={styles.error}>{error}</span>}
    </span>
  );
}
