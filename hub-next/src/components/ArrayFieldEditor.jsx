'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './ArrayFieldEditor.module.css';

// Generic add/remove editor for an array-of-objects field on a VC doc
// (deals, news, portfolio) -- shared by Tier 1 and Partner VC detail pages.
// `fields` describes the add-form's inputs. `displayItems` is a parallel
// array of *already-rendered* React nodes (same order/length as `items`) --
// NOT a renderItem(item) callback: this is called from Server Component
// pages, which can hand a Client Component pre-built JSX but never a bare
// function (React Server Components can't serialize functions across the
// server->client boundary; next build won't catch it since force-dynamic
// pages skip static generation -- see SortableTable's cells prop for the
// same pattern). `items` itself stays plain, serializable, PATCH-able data.
// Saves by PATCHing the *whole* array back to `endpoint` (the caller's
// updateTopVC/updatePartnerVC merge-patch), same as GroupFieldEditor.
export default function ArrayFieldEditor({ endpoint, id, field, items, displayItems, fields, canEdit, addLabel }) {
  const router = useRouter();
  const emptyDraft = () => Object.fromEntries(fields.map((f) => [f.key, f.type === 'checkbox' ? false : '']));
  const [draft, setDraft] = useState(emptyDraft);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function persist(nextItems) {
    setSaving(true);
    setError('');
    try {
      const res = await fetch(endpoint, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, [field]: nextItems }),
      });
      if (!res.ok) throw new Error('save-failed');
      router.refresh();
    } catch {
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  function add(e) {
    e.preventDefault();
    const requiredOk = fields.every((f) => !f.required || String(draft[f.key] || '').trim());
    if (!requiredOk) return;
    const entry = Object.fromEntries(
      fields.map((f) => [f.key, f.type === 'checkbox' ? !!draft[f.key] : String(draft[f.key] || '').trim()]),
    );
    persist([...(items || []), entry]);
    setDraft(emptyDraft());
  }

  function remove(i) {
    persist(items.filter((_, idx) => idx !== i));
  }

  return (
    <div>
      <ul className={styles.list}>
        {(!items || items.length === 0) && <li className={styles.empty}>Nothing here yet</li>}
        {(items || []).map((item, i) => (
          <li key={i} className={styles.item}>
            <span>{displayItems ? displayItems[i] : item.company}</span>
            {canEdit && (
              <button type="button" className={styles.del} disabled={saving} onClick={() => remove(i)} title="Remove">×</button>
            )}
          </li>
        ))}
      </ul>
      {canEdit && (
        <form className={styles.form} onSubmit={add}>
          {fields.map((f) => (
            f.type === 'checkbox' ? (
              <label key={f.key} className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={!!draft[f.key]}
                  onChange={(e) => setDraft({ ...draft, [f.key]: e.target.checked })}
                />
                {f.label}
              </label>
            ) : (
              <input
                key={f.key}
                className={styles.input}
                value={draft[f.key] || ''}
                placeholder={f.placeholder || f.label}
                onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
              />
            )
          ))}
          <button className={styles.add} type="submit" disabled={saving}>{addLabel || 'Add'}</button>
          {error && <span className={styles.error}>{error}</span>}
        </form>
      )}
    </div>
  );
}
