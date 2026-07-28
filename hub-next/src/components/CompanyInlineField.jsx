'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './RoundInput.module.css';

// Generic blur-to-save inline field for a single top-level company field,
// keyed by slug -- same optimistic-save shape as RoundInput/StageSelect, just
// parameterized over which PATCH route and body field to use so new
// per-company fields (Radar Category, PitchBook URL, ...) don't each need
// their own near-identical component. `renderAs="link"` is for URL fields:
// non-editors get a clickable link instead of the raw string.
export default function CompanyInlineField({
  slug,
  apiSegment,
  field,
  value,
  canEdit,
  placeholder,
  renderAs = 'text',
  linkLabel = 'Open ↗',
}) {
  const router = useRouter();
  const [val, setVal] = useState(value || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!canEdit) {
    if (renderAs === 'link' && value) {
      return <a href={value} target="_blank" rel="noopener noreferrer">{linkLabel}</a>;
    }
    return <span>{value || '—'}</span>;
  }

  async function save() {
    const next = val.trim();
    if (next === (value || '')) return;
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`/api/companies/${slug}/${apiSegment}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: next }),
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
        type="text"
        className={styles.input}
        value={val}
        disabled={saving}
        placeholder={placeholder || '—'}
        onChange={(e) => setVal(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur();
        }}
      />
      {error && <span className={styles.error}>{error}</span>}
    </span>
  );
}
