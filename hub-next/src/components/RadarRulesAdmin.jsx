'use client';

import { useEffect, useMemo, useState } from 'react';
import { matchExclusionRule, previewKeywordMatches, MIN_KEYWORD_LENGTH } from '@/lib/radarRuleMatch';
import styles from './RadarRulesAdmin.module.css';

// Editable relevance-exclusion list for Radar (RADAR_PLAN.md §1.6) --
// same form-plus-list shape as PartnerVCsAdmin/TopVCsAdmin, but the point
// of this one is the live preview: adding a keyword shows exactly which
// currently-visible Radar companies it would drop *before* it's saved, and
// removing one shows what comes back. Nothing here is ever silently lost --
// an excluded company drops into a collapsed section with a "Keep anyway"
// escape hatch that pins it past every current and future rule.
//
// `radarCompanies` is the plain {slug, name, description, radarCategory}
// list for whatever's currently on the Radar tab -- passed down from
// docs/radar/page.jsx (a Server Component) so this preview reflects the
// real, current population without this client component needing its own
// Firestore access.
export default function RadarRulesAdmin({ radarCompanies = [] }) {
  const [rules, setRules] = useState(null);
  const [loading, setLoading] = useState(true);
  const [term, setTerm] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch('/api/radar-rules')
      .then((r) => r.json())
      .then((d) => setRules(d.rules || null))
      .finally(() => setLoading(false));
  }, []);

  const keywordEntries = rules?.keywordEntries || [];
  const keepAnyway = rules?.keepAnyway || [];

  const { visible, excluded } = useMemo(() => {
    if (!rules) return { visible: radarCompanies, excluded: [] };
    const keptSlugs = keepAnyway.map((k) => k.slug);
    const vis = [];
    const exc = [];
    for (const c of radarCompanies) {
      const hit = matchExclusionRule(c, rules, keptSlugs);
      if (hit) exc.push({ company: c, hit });
      else vis.push(c);
    }
    return { visible: vis, excluded: exc };
  }, [radarCompanies, rules, keepAnyway]);

  const preview = useMemo(
    () => previewKeywordMatches(term, visible, rules?.keywords || []),
    [term, visible, rules]
  );

  const canAdd = term.trim().length >= MIN_KEYWORD_LENGTH && !busy;

  async function addRule(e) {
    e.preventDefault();
    if (!canAdd) return;
    setBusy(true);
    const res = await fetch('/api/radar-rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'addKeyword', term: term.trim() }),
    });
    if (res.ok) {
      setRules((r) => ({
        ...r,
        keywords: [...(r?.keywords || []), term.trim().toLowerCase()],
        keywordEntries: [...(r?.keywordEntries || []), { term: term.trim().toLowerCase() }],
      }));
      setTerm('');
    }
    setBusy(false);
  }

  async function removeRule(t) {
    setRules((r) => ({
      ...r,
      keywords: (r?.keywords || []).filter((k) => k !== t),
      keywordEntries: (r?.keywordEntries || []).filter((k) => k.term !== t),
    }));
    await fetch(`/api/radar-rules?action=keyword&term=${encodeURIComponent(t)}`, { method: 'DELETE' });
  }

  async function keepAnywayAdd(company) {
    setRules((r) => ({ ...r, keepAnyway: [...(r?.keepAnyway || []), { slug: company.slug, name: company.name }] }));
    await fetch('/api/radar-rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'keepAnyway', slug: company.slug, name: company.name, keep: true }),
    });
  }

  async function keepAnywayRemove(slug) {
    setRules((r) => ({ ...r, keepAnyway: (r?.keepAnyway || []).filter((k) => k.slug !== slug) }));
    await fetch(`/api/radar-rules?action=keepAnyway&slug=${encodeURIComponent(slug)}`, { method: 'DELETE' });
  }

  if (loading) return <p className={styles.empty}>Loading rules…</p>;

  return (
    <div className={styles.board}>
      <form className={styles.form} onSubmit={addRule}>
        <input
          className={styles.input}
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="e.g. wealth management, staffing agency, crypto…"
        />
        <button className={styles.add} type="submit" disabled={!canAdd}>Add rule</button>
      </form>

      <div className={styles.previewLine} data-state={
        term.trim().length === 0 ? 'idle'
          : term.trim().length < MIN_KEYWORD_LENGTH ? 'warn'
          : preview.length === 0 ? 'clear' : 'hit'
      }>
        {term.trim().length === 0 && 'Start typing to preview a new rule against the companies currently on Radar.'}
        {term.trim().length > 0 && term.trim().length < MIN_KEYWORD_LENGTH && `Type at least ${MIN_KEYWORD_LENGTH} characters.`}
        {term.trim().length >= MIN_KEYWORD_LENGTH && preview.length === 0 && 'No matches among currently-visible companies — safe to add.'}
        {term.trim().length >= MIN_KEYWORD_LENGTH && preview.length > 0 &&
          `Would exclude ${preview.length}: ${preview.map((c) => c.name).join(', ')}.`}
      </div>

      <div className={styles.chips}>
        {keywordEntries.length === 0 && <span className={styles.empty}>No rules yet.</span>}
        {keywordEntries.map((k) => (
          <span className={styles.chip} key={k.term}>
            {k.term}
            <button type="button" onClick={() => removeRule(k.term)} aria-label={`Remove rule ${k.term}`}>×</button>
          </span>
        ))}
      </div>

      <details className={styles.excludedBox}>
        <summary>Excluded from Radar ({excluded.length})</summary>
        {excluded.length === 0 && <div className={styles.empty}>Nothing currently excluded.</div>}
        {excluded.map(({ company, hit }) => (
          <div className={styles.excludedRow} key={company.slug}>
            <div>
              <span className={styles.itemTitle}>{company.name}</span>
              <div className={styles.itemNote}>matched {hit.type} &ldquo;{hit.term}&rdquo;</div>
              {company.description && <div className={styles.itemDescription}>{company.description}</div>}
            </div>
            <button className={styles.keepBtn} type="button" onClick={() => keepAnywayAdd(company)}>Keep anyway</button>
          </div>
        ))}
      </details>

      {keepAnyway.length > 0 && (
        <details className={styles.excludedBox} open>
          <summary>Pinned past every rule ({keepAnyway.length})</summary>
          {keepAnyway.map((k) => (
            <div className={styles.excludedRow} key={k.slug}>
              <span className={styles.itemTitle}>{k.name}</span>
              <button className={styles.keepBtn} type="button" onClick={() => keepAnywayRemove(k.slug)}>Un-pin</button>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}
