'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { TAGS, TAG_LABELS } from '@/lib/stages';
import styles from './TagsSelect.module.css';

// Pretty multiselect for a company's additive `tags` (qualified/radar) --
// independent of StageSelect's single-value `stage` dropdown. Click the
// pill row to open a small popover of toggleable checkboxes; each toggle
// saves immediately (optimistic, reverts on failure), same convention
// StageSelect/CompanyInlineField already use. `position: fixed` for the
// same reason PartnerVcPopover.module.css uses it -- the stage tables
// render inside SortableTable's .scrollWrap (overflow-x: auto), which
// would otherwise clip an absolutely-positioned panel.
export default function TagsSelect({ slug, tags: initialTags, canEdit }) {
  const router = useRouter();
  const [tags, setTags] = useState(initialTags || []);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef(null);
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    function onDocClick(e) {
      if (triggerRef.current?.contains(e.target) || panelRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  function show() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) setCoords({ top: rect.bottom + 4, left: rect.left });
    setOpen(true);
  }

  async function toggle(tag) {
    const next = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag];
    const prev = tags;
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

  if (!canEdit) {
    if (!tags.length) return <span className={styles.empty}>—</span>;
    return (
      <span className={styles.pills}>
        {tags.map((t) => (
          <span key={t} className={`${styles.pill} ${styles[`pill_${t}`] || ''}`}>{TAG_LABELS[t] || t}</span>
        ))}
      </span>
    );
  }

  return (
    <span className={styles.wrap}>
      <button
        type="button"
        ref={triggerRef}
        className={styles.trigger}
        onClick={() => (open ? setOpen(false) : show())}
        disabled={saving}
      >
        {tags.length ? (
          <span className={styles.pills}>
            {tags.map((t) => (
              <span key={t} className={`${styles.pill} ${styles[`pill_${t}`] || ''}`}>{TAG_LABELS[t] || t}</span>
            ))}
          </span>
        ) : (
          <span className={styles.addLabel}>+ Add tag</span>
        )}
      </button>
      {open && (
        <span ref={panelRef} className={styles.panel} style={{ top: coords.top, left: coords.left }}>
          {TAGS.map((tag) => {
            const checked = tags.includes(tag);
            return (
              <label key={tag} className={styles.option}>
                <input type="checkbox" checked={checked} onChange={() => toggle(tag)} disabled={saving} />
                <span className={`${styles.swatch} ${styles[`pill_${tag}`] || ''}`} />
                {TAG_LABELS[tag] || tag}
              </label>
            );
          })}
        </span>
      )}
    </span>
  );
}
