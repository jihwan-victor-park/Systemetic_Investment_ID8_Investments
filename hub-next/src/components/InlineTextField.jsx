'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './InlineTextField.module.css';

// Generic blur-to-save text field for a single top-level string field on a
// VC doc (e.g. domain) -- same optimistic-save shape as RoundInput, but not
// hardcoded to companies/round so both Tier 1 and Partner VC detail pages
// can reuse it against their own endpoint.
export default function InlineTextField({ endpoint, id, field, value, canEdit, placeholder }) {
  const router = useRouter();
  const [val, setVal] = useState(value || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!canEdit) return <span>{value || '—'}</span>;

  async function save() {
    const next = val.trim();
    if (next === (value || '')) return;
    setSaving(true);
    setError('');
    try {
      const res = await fetch(endpoint, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, [field]: next }),
      });
      if (!res.ok) throw new Error('save-failed');
      router.refresh();
    } catch {
      setVal(value || '');
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  return (
    <span className={styles.wrap}>
      <input
        className={styles.input}
        style={{ width: `${Math.max(val.length, (placeholder || '').length, 1) + 1}ch` }}
        value={val}
        disabled={saving}
        placeholder={placeholder || '—'}
        onChange={(e) => setVal(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
      />
      {error && <span className={styles.error}>{error}</span>}
    </span>
  );
}
