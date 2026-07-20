'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import SortableTable from './SortableTable';
import { companyHref, lookupFitScore, lookupStage } from '@/lib/companyIndex';
import { STAGES, STAGE_LABELS } from '@/lib/stages';
import styles from './PortfolioTable.module.css';

const COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'industry', label: 'Industry', sortable: true },
  { key: 'series', label: 'Series', sortable: true },
  { key: 'score', label: 'Fit score', sortable: true },
  { key: 'pipeline', label: 'Pipeline', sortable: true },
  { key: 'actions', label: '' },
];

// Portfolio, shown as the same sortable/searchable table every other deal
// list in the hub uses (Watchlist/Pipeline/Qualified Deals) rather than a
// plain bullet list -- this is also what makes a 100+ company portfolio
// actually usable in List view, not just in the Graph.
export default function PortfolioTable({ endpoint, id, field, items, companyIndex, canEdit, addLabel, vcName }) {
  const router = useRouter();
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('');
  const [series, setSeries] = useState('');
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
    persist([...(items || []), { company: name.trim(), industry: industry.trim(), series: series.trim() }]);
    setName('');
    setIndustry('');
    setSeries('');
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

  const rows = (items || []).map((p, i) => {
    const href = companyHref(companyIndex, p.company) || `/docs/vcs/company/${encodeURIComponent(p.company)}`;
    const fitScore = lookupFitScore(companyIndex, p.company);
    const stage = lookupStage(companyIndex, p.company);
    return {
      key: i,
      sort: { company: p.company.toLowerCase(), industry: p.industry || '', series: p.series || '', score: fitScore ?? -1, pipeline: stage || '' },
      search: { company: p.company, industry: p.industry || '', series: p.series || '' },
      cells: {
        company: <Link href={href}>{p.company}</Link>,
        industry: p.industry || '—',
        series: p.series || '—',
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
              {STAGES.map((s) => (
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
          <input className={styles.input} value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="Industry" />
          <input className={styles.input} value={series} onChange={(e) => setSeries(e.target.value)} placeholder="Series" />
          <button className={styles.add} type="submit" disabled={saving}>{addLabel || 'Add'}</button>
          {error && <span className={styles.error}>{error}</span>}
        </form>
      )}
    </div>
  );
}
