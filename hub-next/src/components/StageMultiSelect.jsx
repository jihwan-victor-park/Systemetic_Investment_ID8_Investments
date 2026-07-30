'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PUBLIC_STAGES, STAGE_LABELS } from '@/lib/stages';
import styles from './StageMultiSelect.module.css';

// Oscar, 2026-07-30: "make sure the stage column is a multiselect, so that a
// deal can be in more than one stage." Reuses the checkbox-popover UI the
// old tags-only TagsSelect had (same CSS, renamed alongside it) but
// reconciles TWO underlying fields into one checked set, rather than editing
// a single array: `stage` (still the one field a
// company's "primary" home resolves from -- basePath lookups, Attio sync via
// updateCompanyStage's pushStageToAttio) and `tags` (additive, see
// lib/stages.js -- now widened to cover every PUBLIC_STAGES value instead of
// just qualified/radar, specifically so this component has something to
// write the non-primary checked stages into).
//
// Checked set = {stage} ∪ (tags ∩ PUBLIC_STAGES). Toggling:
//   - ON a stage that isn't checked: added to `tags` (stage never changes --
//     the company's existing primary stays primary, this is purely additive,
//     same "on top of wherever stage already has it" semantics the
//     qualified/radar auto-tags already used before this component existed).
//   - OFF a tag-only stage: removed from `tags`.
//   - OFF the PRIMARY stage: only allowed if at least one other stage is
//     still checked -- a company must always have exactly one primary. The
//     first remaining tag is PROMOTED (PATCH /stage) and dropped from `tags`
//     so it isn't redundantly listed as both. Two writes, not one
//     transaction (there's no cross-collection transaction across the stage
//     and tags API routes) -- see promoteNewPrimary's own comment for the
//     failure-handling this implies.
//   - OFF the primary stage when it's the ONLY checked stage: blocked,
//     inline error -- there is no "no stage" state.
export default function StageMultiSelect({ slug, stage, tags: initialTags, canEdit }) {
  const router = useRouter();
  const [primary, setPrimary] = useState(stage);
  // `tags` here is already scoped to non-primary stages -- the primary
  // itself is never expected to also sit in the incoming `tags` array under
  // normal operation, but a defensive filter costs nothing and avoids ever
  // double-counting it in the checked set below.
  const [tags, setTags] = useState((initialTags || []).filter((t) => t !== stage));
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef(null);
  const panelRef = useRef(null);

  const checked = [primary, ...tags];

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

  async function patchTags(nextTags) {
    const res = await fetch(`/api/companies/${slug}/tags`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tags: nextTags }),
    });
    if (!res.ok) throw new Error('save-failed');
  }

  async function patchStage(nextStage) {
    const res = await fetch(`/api/companies/${slug}/stage`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage: nextStage }),
    });
    if (!res.ok) throw new Error('save-failed');
  }

  async function addTag(target) {
    const prevTags = tags;
    const nextTags = [...tags, target];
    setTags(nextTags);
    setSaving(true);
    setError('');
    try {
      await patchTags(nextTags);
      router.refresh();
    } catch {
      setTags(prevTags);
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  async function removeTag(target) {
    const prevTags = tags;
    const nextTags = tags.filter((t) => t !== target);
    setTags(nextTags);
    setSaving(true);
    setError('');
    try {
      await patchTags(nextTags);
      router.refresh();
    } catch {
      setTags(prevTags);
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  // Removing the primary stage while at least one tag remains checked --
  // promote the first remaining tag to primary and drop it from `tags` (so
  // it isn't listed twice). Writes `tags` first, THEN `stage`: if the tags
  // write fails, nothing has moved yet and the revert is simple; if the
  // tags write succeeds but the stage write then fails, the new primary
  // would otherwise vanish from the checked set entirely (removed from tags,
  // never promoted) -- so on that specific failure this re-adds it to tags
  // as a best-effort compensation rather than silently losing it, and still
  // surfaces the error so a human notices the promotion itself didn't land.
  async function promotePrimary() {
    const prevPrimary = primary;
    const prevTags = tags;
    const [newPrimary, ...restTags] = tags;
    setPrimary(newPrimary);
    setTags(restTags);
    setSaving(true);
    setError('');
    try {
      await patchTags(restTags);
      try {
        await patchStage(newPrimary);
      } catch (stageErr) {
        await patchTags(prevTags).catch(() => {}); // best-effort compensation, see docstring
        throw stageErr;
      }
      router.refresh();
    } catch {
      setPrimary(prevPrimary);
      setTags(prevTags);
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  async function toggle(target) {
    if (checked.includes(target)) {
      if (target !== primary) { await removeTag(target); return; }
      if (tags.length === 0) { setError('A deal needs at least one stage'); return; }
      await promotePrimary();
      return;
    }
    await addTag(target);
  }

  if (!canEdit) {
    return (
      <span className={styles.pills}>
        {checked.map((s) => (
          <span key={s} className={`${styles.pill} ${styles[`pill_${s}`] || ''}`}>{STAGE_LABELS[s] || s}</span>
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
        <span className={styles.pills}>
          {checked.map((s) => (
            <span key={s} className={`${styles.pill} ${styles[`pill_${s}`] || ''}`}>{STAGE_LABELS[s] || s}</span>
          ))}
        </span>
      </button>
      {error && <span className={styles.error}>{error}</span>}
      {open && (
        <span ref={panelRef} className={styles.panel} style={{ top: coords.top, left: coords.left }}>
          {PUBLIC_STAGES.map((s) => (
            <label key={s} className={styles.option}>
              <input type="checkbox" checked={checked.includes(s)} onChange={() => toggle(s)} disabled={saving} />
              <span className={`${styles.swatch} ${styles[`pill_${s}`] || ''}`} />
              {STAGE_LABELS[s] || s}
            </label>
          ))}
        </span>
      )}
    </span>
  );
}
