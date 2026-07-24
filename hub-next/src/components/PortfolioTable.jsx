'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import SortableTable from './SortableTable';
import DescriptionPopover from './DescriptionPopover';
import FitScorePopover from './FitScorePopover';
import RaiseProbabilityPopover from './RaiseProbabilityPopover';
import RunAnalysisButton from './RunAnalysisButton';
import { companyHref, lookupFitScore, lookupStage, lookupSlug } from '@/lib/companyIndex';
import { PUBLIC_STAGES, STAGE_LABELS } from '@/lib/stages';
import styles from './PortfolioTable.module.css';

// A VC can back a company across more than one round -- roundInvested and
// investorSince are comma-separated in lockstep when that happens (e.g.
// "Series C, Series E" / "2021-10-21, 2023-01-19"), so each round shows next
// to the date it actually closed on rather than one date for every round.
function formatRoundsWithDates(roundStr, dateStr) {
  if (!roundStr) return '—';
  const rounds = roundStr.split(',').map((s) => s.trim()).filter(Boolean);
  const dates = (dateStr || '').split(',').map((s) => s.trim()).filter(Boolean);
  return rounds.map((r, i) => (dates[i] ? `${r} · ${dates[i]}` : r)).join(', ');
}

const COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'category', label: 'Category', sortable: true },
  { key: 'industry', label: 'Industry', sortable: true },
  { key: 'description', label: 'Description', sortable: false },
  { key: 'roundInvested', label: 'Round invested', sortable: true },
  { key: 'latestRound', label: 'Latest round', sortable: true },
  { key: 'fitTier', label: 'Stage 0 fit', sortable: true, defaultDir: 'desc' },
  { key: 'probability', label: 'Raise prob. (3mo)', sortable: true, defaultDir: 'desc' },
  { key: 'score', label: 'Fit score', sortable: true },
  { key: 'pipeline', label: 'Pipeline', sortable: true },
  { key: 'actions', label: '' },
];

// Ordering for sorting the Stage 0 tier + raise-probability badges (higher =
// more interesting, so a `desc` sort surfaces the best track candidates first).
const TIER_RANK = { track_priority: 5, track: 4, monitor: 3, too_early: 2, drop: 1 };
const RAISE_RANK = { imminent: 4, high: 3, medium: 2, low: 1 };
const TIER_LABEL = {
  track_priority: 'Track — priority', track: 'Track', monitor: 'Monitor',
  too_early: 'Too early', drop: 'Drop',
};

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
  // is shown instead once it does). Never fires on its own. `round` is
  // required by the API (createCompanyFromPortfolio) -- passed here from
  // whatever this row already knows (the Stage 0-researched current stage,
  // or the on-file latest round), so the common case needs no extra prompt;
  // a row with neither surfaces 'invalid-round' below rather than silently
  // creating a pipeline company with a blank Series.
  async function addToPipeline(company, stage, round) {
    if (!stage) return;
    setAddingCompany(company);
    setPipelineError(null);
    try {
      const res = await fetch('/api/companies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: company, stage, sourceVCName: vcName, round }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const message = body.error === 'already-exists'
          ? 'A company with this name is already added (check for a name mismatch)'
          : body.error === 'invalid-round'
            ? 'No known round for this company — add one in the portfolio table first'
            : 'Failed — try again';
        throw new Error(message);
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
    const slug = lookupSlug(companyIndex, p.company);
    // Stage 0 Portfolio Fit results (deal_intelligence/portfolio_fit.py write_back).
    // latestRound is updated in place to the researched current round when the
    // stage pass found one; latestRoundOnFile then holds the original PitchBook
    // value, shown on hover as provenance.
    const raiseBand = p.fitRaiseProbability || '';
    const roundResearched = Boolean(p.latestRoundOnFile) && p.latestRoundOnFile !== p.latestRound;
    return {
      key: i,
      sort: {
        company: p.company.toLowerCase(),
        category: p.category || '',
        industry: p.industry || '',
        roundInvested: p.roundInvested || '',
        latestRound: p.latestRound || '',
        fitTier: TIER_RANK[p.fitTier] ?? -1,
        probability: RAISE_RANK[raiseBand] ?? -1,
        score: p.fitScore ?? fitScore ?? -1,
        pipeline: stage || '',
      },
      search: { company: p.company, category: p.category || '', industry: p.industry || '', description: p.description || '', roundInvested: p.roundInvested || '', latestRound: p.latestRound || '' },
      cells: {
        company: <Link href={href}>{p.company}</Link>,
        category: p.category || '—',
        industry: p.industry || '—',
        description: <DescriptionPopover text={p.description} />,
        roundInvested: formatRoundsWithDates(p.roundInvested, p.investorSince),
        latestRound: p.latestRound
          ? <span title={roundResearched ? `Researched current round (was "${p.latestRoundOnFile}" on file in PitchBook)` : undefined}>
              {formatRoundsWithDates(p.latestRound, p.latestRoundDate)}{roundResearched ? ' ✓' : ''}
            </span>
          : '—',
        fitTier: p.fitTier
          ? <span className={styles.fitTier} data-tier={p.fitTier} title={p.fitRationale || ''}>{TIER_LABEL[p.fitTier] || p.fitTier}</span>
          : <span className={styles.muted}>Not scored</span>,
        // Hovering the band explains what it means (fixed thresholds, same
        // for every company) plus, when scored, the two-layer reasoning:
        // the deterministic timing-only starting point and what the
        // model's research moved it to and why.
        probability: <RaiseProbabilityPopover company={p} />,
        // Hovering the score shows the full Stage 0 breakdown (per-dimension
        // evidence, rationale, confidence, current-stage/raise-probability
        // research) -- same depth Stage 1's own screen page shows, per
        // Oscar's ask, but inline so you don't have to leave the portfolio
        // table. A company not yet scored by Stage 0 falls back to the plain
        // Stage 1 score (already-screened pipeline companies), if any.
        score: p.fitScore != null
          ? <FitScorePopover company={p} />
          : (fitScore != null ? `${fitScore.toFixed(1)} / 4` : '—'),
        pipeline: stage ? (
          <span className={styles.stageWithAction}>
            <span className={styles.stageBadge}>{STAGE_LABELS[stage] || stage}</span>
            {canEdit && slug && <RunAnalysisButton slug={slug} name={p.company} />}
          </span>
        ) : canEdit ? (
          <div className={styles.pipelineCell}>
            <select
              className={styles.pipelineSelect}
              disabled={addingCompany === p.company}
              value=""
              onChange={(e) => addToPipeline(p.company, e.target.value, p.fitCurrentStage || p.latestRound || '')}
            >
              <option value="" disabled>Add…</option>
              {PUBLIC_STAGES.map((s) => (
                <option key={s} value={s}>{STAGE_LABELS[s]}</option>
              ))}
            </select>
            {pipelineError?.company === p.company && <span className={styles.error}>{pipelineError.message}</span>}
          </div>
        ) : (
          <span className={styles.muted}>Not added</span>
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
