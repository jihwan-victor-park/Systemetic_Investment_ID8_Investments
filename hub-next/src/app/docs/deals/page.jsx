import Link from 'next/link';
import SortableTable from '@/components/SortableTable';
import { listDealResearchDecks } from '@/lib/dealResearchDecks';

export const metadata = { title: 'Deal Summaries', description: 'Companies ID8 has done real research work on.' };

export const dynamic = 'force-dynamic';

const COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'thesis', label: 'Thesis' },
  { key: 'stage', label: 'Stage', sortable: true },
  { key: 'date', label: 'Date', sortable: true },
];

function toRow(d) {
  return {
    key: d.id,
    sort: {
      company: d.companyName?.toLowerCase() || '',
      stage: d.stage?.toLowerCase() || '',
      date: d.createdAt || '',
    },
    search: {
      company: d.companyName || '',
      thesis: d.thesis || '',
      stage: d.stage || '',
    },
    cells: {
      company: <Link href={`/docs/deals/${d.id}`}>{d.companyName}</Link>,
      thesis: d.thesis,
      stage: d.stage,
      date: d.createdAt ? d.createdAt.slice(0, 10) : '—',
    },
  };
}

export default async function DealsPage() {
  const decks = await listDealResearchDecks();

  return (
    <>
      <h1>Deal Summaries</h1>
      <p>Companies ID8 has done real diligence work on — this populates as investment memos and deal summaries are created.</p>
      <SortableTable
        columns={COLUMNS}
        rows={decks.map(toRow)}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or thesis…"
        emptyMessage="No deal summaries yet."
      />
    </>
  );
}
