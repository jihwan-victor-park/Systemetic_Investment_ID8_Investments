import Link from 'next/link';
import SortableTable from '@/components/SortableTable';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'Qualified Deals', description: 'Every deal Deal Intelligence has screened, updated automatically each run.' };

export const dynamic = 'force-dynamic';

// Shorter labels than the company docs' own frontmatter titles (which carry a
// PitchBook category suffix, e.g. "Pocket (Business/Productivity Software)") —
// the company page's own H1 shows the full title; only this table doesn't.
const COMPANY_SHORT_NAME = {
  heypocket: 'Pocket',
  warp: 'Warp',
  getpie: 'PieTech',
};

const displayName = (c) => COMPANY_SHORT_NAME[c.slug] || c.name;

const COLUMNS = [
  {
    key: 'company',
    label: 'Company',
    sortValue: (c) => displayName(c).toLowerCase(),
    render: (c) => displayName(c),
  },
  {
    key: 'score',
    label: 'Score',
    sortValue: (c) => c.latestScreen?.fitScore ?? null,
    filterValue: (c) => (c.latestScreen?.fitScore != null ? String(c.latestScreen.fitScore) : ''),
    render: (c) => (c.latestScreen?.fitScore != null ? `${c.latestScreen.fitScore.toFixed(1)} / 4` : '—'),
  },
  {
    key: 'stage',
    label: 'Stage',
    sortValue: (c) => c.latestScreen?.roundStage?.toLowerCase() || '',
    render: (c) => c.latestScreen?.roundStage || '—',
  },
  {
    key: 'date',
    label: 'Screened',
    sortValue: (c) => c.latestScreen?.date || '',
    render: (c) => (c.latestScreen ? c.latestScreen.date.slice(0, 10) : '—'),
  },
  {
    key: 'report',
    label: 'Report',
    render: (c) => <Link href={`/docs/qualified-deals/${c.slug}`}>View screen →</Link>,
  },
];

export default async function QualifiedDealsPage() {
  const companies = await listCompanies();

  return (
    <>
      <h1>Qualified Deals</h1>
      <p>
        Every deal that reaches the Qualified stage gets scored by{' '}
        <Link href="/docs/projects/intelligence">Deal Intelligence</Link>'s weekly Stage 1 screen against the ID8
        rubric — this list populates automatically as those runs complete, no manual step required.
      </p>
      <SortableTable
        columns={COLUMNS}
        rows={companies}
        rowKey={(c) => c.slug}
        defaultSort={{ key: 'date', dir: 'desc' }}
        searchPlaceholder="Filter by company or stage…"
        emptyMessage="No screened deals yet."
      />
    </>
  );
}
