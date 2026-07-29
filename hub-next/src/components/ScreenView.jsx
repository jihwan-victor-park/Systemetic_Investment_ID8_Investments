'use client';

import { useState } from 'react';
import { H2 } from '@/components/Prose';
import InlineMarkdown from '@/components/InlineMarkdown';
import DeleteButton from '@/components/DeleteButton';
import { dimensionScore, fitScore } from '@/lib/rubricMath';
import styles from './ScreenView.module.css';

async function patchScreen(slug, screenId, body) {
  const res = await fetch(`/api/research/companies/${slug}/screens/${screenId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'save-failed');
  return data.screen;
}

// Click-to-edit text -- plain rendered text by default, becomes a textarea
// on click for internal users. Saves on blur (if changed) or Enter (single-
// line fields); Escape reverts without saving.
function EditableText({ value, onSave, canEdit, multiline, size, color, placeholder }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!canEdit) {
    return value ? <InlineMarkdown text={value} /> : <span className={styles.placeholder}>{placeholder}</span>;
  }

  if (!editing) {
    return (
      <span
        className={styles.editable}
        role="button"
        tabIndex={0}
        onClick={() => { setDraft(value); setEditing(true); }}
        onKeyDown={(e) => { if (e.key === 'Enter') { setDraft(value); setEditing(true); } }}
      >
        {value ? <InlineMarkdown text={value} /> : <span className={styles.placeholder}>{placeholder || 'Click to add'}</span>}
      </span>
    );
  }

  const commit = async () => {
    if (draft === value) { setEditing(false); return; }
    setSaving(true);
    setError('');
    try {
      await onSave(draft);
      setEditing(false);
    } catch (e) {
      setError(e.message || 'save failed');
    } finally {
      setSaving(false);
    }
  };

  const Tag = multiline ? 'textarea' : 'input';
  return (
    <span className={styles.editWrap}>
      <Tag
        className={styles.editField}
        autoFocus
        value={draft}
        disabled={saving}
        rows={multiline ? 3 : undefined}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Escape') { setDraft(value); setEditing(false); }
          if (e.key === 'Enter' && !multiline) { e.preventDefault(); commit(); }
        }}
      />
      {error && <span className={styles.saveError}>{error}</span>}
    </span>
  );
}

// Hover/focus pop-up showing a subcategory's full fixed 1-4 rubric -- the
// deterministic anchor text authored in deal_intelligence/rubric.py, not a
// per-deal summary. `anchors` is keyed "1".."4" (Firestore map keys are
// strings). Absent on legacy (pre-rubric-v4) subcategories.
function SubcategoryLabel({ label, score, anchors }) {
  const [open, setOpen] = useState(false);
  if (!anchors || !Object.keys(anchors).length) {
    return <span className={styles.subName}>{label}:</span>;
  }
  return (
    <span
      className={styles.subNameWrap}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
    >
      <span className={styles.subName}>{label}:</span>
      {open && (
        <div className={styles.popover} role="tooltip">
          <div className={styles.popoverTitle}>{label} — fixed rubric</div>
          {['1', '2', '3', '4'].map((n) => (
            <div key={n} className={Number(n) === Number(score) ? styles.popoverAnchorActive : styles.popoverAnchor}>
              <span className={styles.popoverScore}>{n}</span>
              <span>{anchors[n]}</span>
            </div>
          ))}
        </div>
      )}
    </span>
  );
}

function SubcategoryRow({ dimKey, sub, canEdit, slug, screenId, onSubUpdate }) {
  const isLegacy = sub.score == null;

  const saveScore = async (n) => {
    onSubUpdate(dimKey, sub.key, { score: n }); // optimistic
    try {
      const screen = await patchScreen(slug, screenId, {
        dimensionKey: dimKey, subcategoryKey: sub.key, field: 'score', value: n,
      });
      onSubUpdate(dimKey, sub.key, null, screen); // reconcile with server truth
    } catch (e) {
      onSubUpdate(dimKey, sub.key, { score: sub.score }); // revert
    }
  };

  const saveFinding = async (text) => {
    onSubUpdate(dimKey, sub.key, { finding: text });
    const screen = await patchScreen(slug, screenId, {
      dimensionKey: dimKey, subcategoryKey: sub.key, field: 'finding', value: text,
    });
    onSubUpdate(dimKey, sub.key, null, screen);
  };

  return (
    <li key={sub.key || sub.name} className={styles.subRow}>
      <SubcategoryLabel label={sub.name} score={sub.score} anchors={sub.anchors} />{' '}
      {!isLegacy && (
        canEdit ? (
          <select
            className={styles.scoreSelect}
            value={sub.score}
            onChange={(e) => saveScore(Number(e.target.value))}
          >
            {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        ) : (
          <span className={styles.subScore}>{sub.score} / 4</span>
        )
      )}{' '}
      {canEdit && !isLegacy ? (
        <EditableText value={sub.finding} canEdit={canEdit} onSave={saveFinding} placeholder="none found" />
      ) : (
        <InlineMarkdown text={sub.finding} />
      )}
    </li>
  );
}

// Renders one company screen using the exact template every hub/docs/research/
// companies/*.md file shares: a dated H2, a bold fit-score-and-verdict line,
// a dimension-scoring list, a Rationale paragraph, a Confidence line, and a
// numbered Sources list. Internal users (canEdit) can edit subcategory
// scores/findings, dimension evidence, and the deal rationale inline --
// edits recompute the owning dimension score and the fit score live.
export default function ScreenView({ screen: initialScreen, canEdit, slug }) {
  const [screen, setScreen] = useState(initialScreen);

  const updateSub = (dimKey, subKey, patch, serverScreen) => {
    if (serverScreen) { setScreen(serverScreen); return; }
    setScreen((prev) => {
      const dimensions = prev.dimensions.map((d) => {
        if (d.key !== dimKey) return d;
        const subcategories = d.subcategories.map((s) => (s.key === subKey ? { ...s, ...patch } : s));
        return { ...d, subcategories, score: dimensionScore(subcategories) };
      });
      return { ...prev, dimensions, fitScore: fitScore(dimensions), rawScore: fitScore(dimensions) };
    });
  };

  const saveEvidence = async (dimKey, text) => {
    setScreen((prev) => ({
      ...prev,
      dimensions: prev.dimensions.map((d) => (d.key === dimKey ? { ...d, evidence: text } : d)),
    }));
    const updated = await patchScreen(slug, screen.id, { dimensionKey: dimKey, field: 'evidence', value: text });
    setScreen(updated);
  };

  const saveRationale = async (text) => {
    setScreen((prev) => ({ ...prev, rationale: text }));
    const updated = await patchScreen(slug, screen.id, { field: 'rationale', value: text });
    setScreen(updated);
  };

  const heading = `Screen — ${screen.date}${screen.roundStage ? ` · ${screen.roundStage}` : ''}`;
  return (
    <div>
      <H2>
        {heading}
        {canEdit && (
          <DeleteButton
            url={`/api/research/companies/${slug}/screens/${screen.id}`}
            confirmMessage={`Delete this screen (${screen.date})? This can't be undone.`}
            title="Delete this screen"
          />
        )}
      </H2>
      <p>
        <strong>
          Fit score: {screen.fitScore != null ? screen.fitScore.toFixed(1) : '—'} / 4.0
          {screen.rawScore != null && ` (raw ${screen.rawScore.toFixed(1)})`}
        </strong>
        {screen.verdict && ` — ${screen.verdict}`}
      </p>
      {screen.hardAutoPassNote && <p><em>{screen.hardAutoPassNote}</em></p>}

      {/* Click a dimension to expand its evidence/rationale detail. Collapsed
          state still shows every score at a glance. */}
      <div className={styles.dimensions}>
        {screen.dimensions.map((d) => (
          <details key={d.key || d.name} className={styles.dim}>
            <summary>
              <span className={styles.summaryLeft}>
                <svg className={styles.chevron} width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                  <path d="M2 0.5 L8 5 L2 9.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                </svg>
                <span className={styles.dimName}>{d.name}</span>
              </span>
              <span className={styles.dimScore}>{d.score != null ? d.score.toFixed(1) : '—'}<em> / 4</em></span>
            </summary>
            <div className={styles.dimEvidence}>
              {/* Dimension-level tier: the synthesis of the point-level findings below. */}
              <EditableText value={d.evidence} canEdit={canEdit} multiline onSave={(text) => saveEvidence(d.key, text)} />
              {/* Point-level tier: one grounded finding per rubric checklist item. */}
              {d.subcategories?.length > 0 && (
                <ul className={styles.subList}>
                  {d.subcategories.map((s) => (
                    <SubcategoryRow
                      key={s.key || s.name}
                      dimKey={d.key}
                      sub={s}
                      canEdit={canEdit}
                      slug={slug}
                      screenId={screen.id}
                      onSubUpdate={updateSub}
                    />
                  ))}
                </ul>
              )}
            </div>
          </details>
        ))}
      </div>

      <p>
        <strong>Rationale</strong>
        <br />
        <EditableText value={screen.rationale} canEdit={canEdit} multiline onSave={saveRationale} />
      </p>

      {screen.confidence && <p><em>Confidence: {screen.confidence}</em></p>}

      {screen.sources?.length > 0 && (
        <>
          <p><strong>Sources</strong></p>
          <ol>
            {screen.sources.map((s) => (
              <li key={s.number}>
                <a href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a>
              </li>
            ))}
          </ol>
        </>
      )}
      <hr />
    </div>
  );
}
