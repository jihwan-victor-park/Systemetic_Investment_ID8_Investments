'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './RoundInput.module.css';

// Inline-editable Series field -- freeform text (Series A, Series C, Growth,
// etc.), unlike Stage's fixed dropdown. Saves on blur or Enter. Optimistic:
// reverts to the last-saved value on failure, same as StageSelect.
export default function RoundInput({ slug, round, canEdit }) {
  const router = useRouter();
  const [value, setValue] = useState(round || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!canEdit) return <span>{round || '—'}</span>;

  async function save() {
    const next = value.trim();
    if (next === (round || '')) return;
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`/api/companies/${slug}/round`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ round: next }),
      });
      if (!res.ok) throw new Error('save-failed');
      router.refresh();
    } catch {
      setValue(round || '');
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  return (
    <span className={styles.wrap}>
      <input
        type="text"
        className={styles.input}
        value={value}
        disabled={saving}
        placeholder="—"
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur();
        }}
      />
      {error && <span className={styles.error}>{error}</span>}
    </span>
  );
}
