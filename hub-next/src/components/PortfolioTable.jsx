'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import SortableTable from './SortableTable';
import DescriptionPopover from './DescriptionPopover';
import { companyHref, lookupFitScore, lookupStage } from '@/lib/companyIndex';
import { PUBLIC_STAGES, STAGE_LABELS } from '@/lib/stages';
import styles from './PortfolioTable.module.css';

const COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'category', label: 'Category', sortable: true },
  { key: 'industry', label: 'Industry', sortable: true },
  { key: 'description', label: 'Description', sortable: false },
  { key: 'roundInvested', label: 'Round invested', sortable: true },
  { key: 'latestRound', label: 'Latest round', sortable: true },
  { key: 'probability', label: 'Raise prob. (3mo)', sortable: false },
  { key: 'score', label: 'Fit score', sortable: true },
  { key: 'pipeline', label: 'Pipeline', sortable: true },
  { key: 'actions', label: '' },
];

// Portfolio, shown as the same sortable/searchable table every other deal
// list in the hub uses (Watchlist/Pipeline/Qualified Deals) rather than a
// plain bullet list -- this is also what makes a 100+ company portfolio
// actually usable in List view, not just in the Graph.
//
// `items` must always be the FULL, unfiltered portfolio array -- add()/
// remove() persist against it directly (Firestore has no per-element PATCH
// here, the whole array gets written back), so passing a pre-filtered subset
// would silently delete every hidden entry on the next add or remove. The
// optional `filterFn` (e.g. the sector-relevance toggle) only ever affects
// which rows *display*; row identity (and thus remove(i)'s index) is always
// resolved against the original, unfiltered `items` array.
export default function PortfolioTable({ endpoint, id, field, items, filterFn, companyIndex, canEdit, addLabel, vcName }) {
  const router = useRouter();
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('');
  const [category, setCategory] = useState('');
  const [roundInvested, setRoundInvested] = useState('');
  const [latestRound, setLatestRound] = useState('');
  const [pitchbookUrl, setPitchbookUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [addingCompany, setAddingCompany] = useState(null);
  const [pipelineError, setPipelineError] = useState(null);

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
    if (!name.trim()) return;
    persist([...(items || []), {
      company: name.trim(),
      industry: industry.trim(),
      category: category.trim(),
      roundInvested: roundInvested.trim(),
      latestRound: latestRound.trim(),
      pitchbookUrl: pitchbookUrl.trim(),
    }]);
    setName('');
    setIndustry('');
    setCategory('');
    setRoundInvested('');
    setLatestRound('');
    setPitchbookUrl('');
  }

  function remove(i) {
    persist((items || []).filter((_, idx) => idx !== i));
  }

  // Promotes a portfolio company into the real pipeline at a chosen stage --
  // only offered when companyIndex shows no existing match (a stage badge
  // is shown instead once it does). Never fires on its own.
  async function addToPipeline(company, stage) {
    if (!stage) return;
    setAddingCompany(company);
    setPipelineError(null);
    try {
      const res = await fetch('/api/companies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: company, stage, sourceVCName: vcName }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error === 'already-exists' ? 'A company with this name is already in the pipeline (check for a name mismatch)' : 'Failed — try again');
      }
      router.refresh();
    } catch (err) {
      setPipelineError({ company, message: err.message });
    } finally {
      setAddingCompany(null);
    }
  }

  const rows = (items || [])
    .map((p, i) => ({ p, i })) // capture the true index before filtering
    .filter(({ p }) => !filterFn || filterFn(p))
    .map(({ p, i }) => {
    const href = companyHref(companyIndex, p.company) || `/docs/vcs/company/${encodeURIComponent(p.company)}`;
    const fitScore = lookupFitScore(companyIndex, p.company);
    const stage = lookupStage(companyIndex, p.company);
    return {
      key: i,
      sort: {
        company: p.company.toLowerCase(),
        category: p.category || '',
        industry: p.industry || '',
        roundInvested: p.roundInvested || '',
        latestRound: p.latestRound || '',
        score: fitScore ?? -1,
        pipeline: stage || '',
      },
      search: { company: p.company, category: p.category || '', industry: p.industry || '', description: p.description || '', roundInvested: p.roundInvested || '', latestRound: p.latestRound || '' },
      cells: {
        company: <Link href={href}>{p.company}</Link>,
        category: p.category || '—',
        industry: p.industry || '—',
        description: <DescriptionPopover text={p.description} />,
        roundInvested: p.roundInvested || '—',
        latestRound: p.latestRound || '—',
        // Not built yet -- this is a placeholder column so the layout/data
        // shape is ready before the "probability to raise in 3 months"
        // metric (heat/traffic/coolness indicators) is designed, per Oscar's
        // explicit "don't worry about it yet" on this one.
        probability: <span className={styles.muted}>Coming soon</span>,
        score: fitScore != null ? `${fitScore.toFixed(1)} / 4` : '—',
        pipeline: stage ? (
          <span className={styles.stageBadge}>{STAGE_LABELS[stage] || stage}</span>
        ) : canEdit ? (
          <div className={styles.pipelineCell}>
            <select
              className={styles.pipelineSelect}
              disabled={addingCompany === p.company}
              value=""
              onChange={(e) => addToPipeline(p.company, e.target.value)}
            >
              <option value="" disabled>Add to pipeline…</option>
              {PUBLIC_STAGES.map((s) => (
                <option key={s} value={s}>{STAGE_LABELS[s]}</option>
              ))}
            </select>
            {pipelineError?.company === p.company && <span className={styles.error}>{pipelineError.message}</span>}
          </div>
        ) : (
          <span className={styles.muted}>Not in pipeline</span>
        ),
        actions: canEdit ? (
          <button type="button" className={styles.del} disabled={saving} onClick={() => remove(i)} title="Remove">×</button>
        ) : null,
      },
    };
  });

  return (
    <div>
      <SortableTable
        columns={COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter portfolio…"
        emptyMessage="No portfolio companies yet."
      />
      {canEdit && (
        <form className={styles.form} onSubmit={add}>
          <input className={styles.input} value={name} onChange={(e) => setName(e.target.value)} placeholder="Company name" />
          <input className={styles.input} value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Category" />
          <input className={styles.input} value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="Industry" />
          <input className={styles.input} value={roundInvested} onChange={(e) => setRoundInvested(e.target.value)} placeholder="Round invested" />
          <input className={styles.input} value={latestRound} onChange={(e) => setLatestRound(e.target.value)} placeholder="Latest round" />
          <input className={styles.input} value={pitchbookUrl} onChange={(e) => setPitchbookUrl(e.target.value)} placeholder="PitchBook URL" />
          <button className={styles.add} type="submit" disabled={saving}>{addLabel || 'Add'}</button>
          {error && <span className={styles.error}>{error}</span>}
        </form>
      )}
    </div>
  );
}
