'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './RoundInput.module.css';

// Generic blur-to-save inline field for a single top-level company field,
// keyed by slug -- same optimistic-save shape as RoundInput/StageSelect, just
// parameterized over which PATCH route and body field to use so new
// per-company fields (Radar Category, PitchBook URL, Deal Date, ...) don't
// each need their own near-identical component. `renderAs="link"` is for URL
// fields: non-editors get a clickable link instead of the raw string.
//
// `inputType="date"` renders a native date picker instead of a text box, for
// Deal Date (2026-08-13). A date input demands an exact YYYY-MM-DD `value` and
// silently renders blank on anything else, so `value` is sliced to 10
// characters here -- Firestore holds some Deal Dates as full ISO timestamps,
// which would otherwise show as an empty picker on a company that definitely
// has a date. It also fires onChange on every keystroke inside the picker,
// where blur-to-save alone would mean picking a date from the calendar popup
// doesn't persist until you click elsewhere, so a date input saves on change
// as well as on blur (save() is a no-op when the value hasn't actually moved).
export default function CompanyInlineField({
  slug,
  apiSegment,
  field,
  value,
  canEdit,
  placeholder,
  renderAs = 'text',
  linkLabel = 'Open ↗',
  inputType = 'text',
}) {
  const isDate = inputType === 'date';
  const normalized = isDate ? String(value || '').slice(0, 10) : (value || '');
  const router = useRouter();
  const [val, setVal] = useState(normalized);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!canEdit) {
    if (renderAs === 'link' && value) {
      return <a href={value} target="_blank" rel="noopener noreferrer">{linkLabel}</a>;
    }
    return <span>{normalized || '—'}</span>;
  }

  // Takes the value to save explicitly: a date input's onChange handler has
  // the new value in hand but React state hasn't caught up yet within the same
  // event, so reading `val` here would save the PREVIOUS date.
  async function save(next = val) {
    const clean = String(next).trim();
    if (clean === normalized) return;
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`/api/companies/${slug}/${apiSegment}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: clean }),
      });
      if (!res.ok) throw new Error('save-failed');
      router.refresh();
    } catch {
      setVal(normalized);
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  return (
    <span className={styles.wrap}>
      <input
        type={inputType}
        className={isDate ? `${styles.input} ${styles.dateInput}` : styles.input}
        value={val}
        disabled={saving}
        placeholder={placeholder || '—'}
        onChange={(e) => {
          setVal(e.target.value);
          if (isDate) save(e.target.value);
        }}
        onBlur={() => save()}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur();
        }}
      />
      {error && <span className={styles.error}>{error}</span>}
    </span>
  );
}
