'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './GroupFieldEditor.module.css';

// Displays a stat-grid of {label, value} pairs for a nested object field
// (fund characteristics, the Attio-relationship placeholder) and, for
// internal users, an "Edit" toggle that swaps the grid for a small form
// PATCHing the whole object back in one write -- same shallow-merge pattern
// as ArrayFieldEditor, just for a fixed set of named fields instead of a list.
export default function GroupFieldEditor({ endpoint, id, field, value, fields, canEdit }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => Object.fromEntries(fields.map((f) => [f.key, value?.[f.key] || ''])));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!canEdit && !value) return null;

  if (!editing) {
    return (
      <div>
        <div className={styles.grid}>
          {fields.map((f) => (
            <div key={f.key} className={styles.cell}>
              <div className={styles.k}>{f.label}</div>
              <div className={styles.v}>{value?.[f.key] || '—'}</div>
            </div>
          ))}
        </div>
        {canEdit && <button type="button" className={styles.editBtn} onClick={() => setEditing(true)}>Edit</button>}
      </div>
    );
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const res = await fetch(endpoint, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, [field]: draft }),
      });
      if (!res.ok) throw new Error('save-failed');
      setEditing(false);
      router.refresh();
    } catch {
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={save}>
      {fields.map((f) => (
        <div key={f.key}>
          <div className={styles.label}>{f.label}</div>
          <input
            className={styles.input}
            value={draft[f.key] || ''}
            placeholder={f.placeholder}
            onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
          />
        </div>
      ))}
      <div className={styles.actions}>
        <button className={styles.save} type="submit" disabled={saving}>Save</button>
        <button className={styles.cancel} type="button" onClick={() => setEditing(false)}>Cancel</button>
        {error && <span className={styles.error}>{error}</span>}
      </div>
    </form>
  );
}
