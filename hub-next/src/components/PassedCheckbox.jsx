'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

// A dedicated column instead of only living inside the Stage cell's
// multiselect (Oscar, 2026-08-06: "I believe that it will be better to have
// a checkbox for passed (as a column) instead of being a category itself.
// But keep the passed view, just that we have completely there.") -- the
// /docs/passed tab stays (companyToRow still resolves it via
// STAGE_BASEPATH), this is just a faster glance/toggle than opening the
// full Stage dropdown. Full-array PATCH via updateCompanyTags (same route
// StageMultiSelect already uses), 'passed' added/removed while every other
// tag stays exactly as it was.
export default function PassedCheckbox({ slug, tags: initialTags, canEdit }) {
  const router = useRouter();
  const [tags, setTags] = useState(initialTags || []);
  const [saving, setSaving] = useState(false);
  const checked = tags.includes('passed');

  if (!canEdit) return checked ? <span title="Passed">✓</span> : null;

  async function toggle() {
    const prev = tags;
    const next = checked ? tags.filter((t) => t !== 'passed') : [...tags, 'passed'];
    setTags(next);
    setSaving(true);
    try {
      const res = await fetch(`/api/companies/${slug}/tags`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: next }),
      });
      if (!res.ok) throw new Error('save-failed');
      router.refresh();
    } catch {
      setTags(prev);
    } finally {
      setSaving(false);
    }
  }

  return <input type="checkbox" checked={checked} disabled={saving} onChange={toggle} aria-label="Passed" />;
}
