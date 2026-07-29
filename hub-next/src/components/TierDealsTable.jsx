'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import SortableTable from './SortableTable';
import { companyHref, lookupStage } from '@/lib/companyIndex';
import { PUBLIC_STAGES, STAGE_LABELS } from '@/lib/stages';

// Read-only cross-reference of a Tier 1 firm's deals[] against ID8's own
// pipeline -- same row shape VCsDirectory.jsx's "By Investment" tab uses,
// scoped to one firm, with a Stage filter so the VCs directory's "N
// qualified/radar →" link (VCsDirectory.jsx's PipelineCell) can land here
// pre-filtered via ?pipeline=qualified,radar. Sits above the raw
// ArrayFieldEditor on the Tier 1 VC page -- that one stays as the actual
// deals[] edit surface, this is purely a "what's actually in our pipeline"
// view on top of it. `companyIndex`/`deals` are plain, RSC-serializable data
// -- companyHref/lookupStage are imported directly here, never passed in as
// function props (see reference_hub_next_rsc_function_props).
const COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'detail', label: 'Detail', sortable: true },
  { key: 'pipeline', label: 'Pipeline', sortable: true },
];

function statusOrHotBadge(d) {
  if (d.status === 'co') return <span className="badge badge--co">Co-invested</span>;
  if (d.status === 'pipe') return <span className="badge badge--pipe">In pipeline</span>;
  if (d.hot) return <span className="badge badge--hot">Hot</span>;
  return '—';
}

function dealToRow(d, companyIndex) {
  const stage = lookupStage(companyIndex, d.company);
  const href = companyHref(companyIndex, d.company) || `/docs/vcs/company/${encodeURIComponent(d.company)}`;
  const detail = [d.type, d.date, d.size].filter(Boolean).join(' · ');
  return {
    key: `${d.company}-${d.date || ''}`,
    filterValues: { stage: stage || '' },
    sort: { company: (d.company || '').toLowerCase(), detail, pipeline: stage || '' },
    search: { company: d.company, detail },
    cells: {
      company: <Link href={href}>{d.company}</Link>,
      detail: detail || '—',
      pipeline: stage ? <span className="badge">{STAGE_LABELS[stage] || stage}</span> : statusOrHotBadge(d),
    },
  };
}

function TierDealsTableInner({ deals, companyIndex }) {
  const searchParams = useSearchParams();
  const initialStageFilter = (searchParams.get('pipeline') || '').split(',').map((s) => s.trim()).filter(Boolean);
  const rows = (deals || []).map((d) => dealToRow(d, companyIndex));

  return (
    <SortableTable
      columns={COLUMNS}
      rows={rows}
      defaultSort={{ key: 'company', dir: 'asc' }}
      searchPlaceholder="Filter investments…"
      emptyMessage="No investments recorded yet."
      filterGroups={[{ key: 'stage', label: 'Pipeline stage', options: PUBLIC_STAGES.map((s) => ({ key: s, label: STAGE_LABELS[s] })) }]}
      initialFilters={initialStageFilter.length ? { stage: initialStageFilter } : undefined}
    />
  );
}

export default function TierDealsTable({ deals, companyIndex }) {
  return (
    <Suspense fallback={null}>
      <TierDealsTableInner deals={deals} companyIndex={companyIndex} />
    </Suspense>
  );
}
