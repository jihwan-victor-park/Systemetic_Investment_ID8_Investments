import Link from 'next/link';
import SortableTable from '@/components/SortableTable';
import { listDealResearchDecks } from '@/lib/dealResearchDecks';

export const metadata = { title: 'Deal Summaries', description: 'Companies ID8 has done real research work on.' };

export const dynamic = 'force-dynamic';

const COLUMNS = [
  {
    key: 'company',
    label: 'Company',
    sortValue: (d) => d.companyName?.toLowerCase() || '',
    render: (d) => <Link href={`/docs/deals/${d.id}`}>{d.companyName}</Link>,
  },
  {
    key: 'thesis',
    label: 'Thesis',
    filterValue: (d) => d.thesis || '',
    render: (d) => d.thesis,
  },
  {
    key: 'stage',
    label: 'Stage',
    sortValue: (d) => d.stage?.toLowerCase() || '',
    render: (d) => d.stage,
  },
  {
    key: 'date',
    label: 'Date',
    sortValue: (d) => d.createdAt || '',
    render: (d) => (d.createdAt ? d.createdAt.slice(0, 10) : '—'),
  },
];

export default async function DealsPage() {
  const decks = await listDealResearchDecks();

  return (
    <>
      <h1>Deal Summaries</h1>
      <p>Companies ID8 has done real diligence work on — this populates as investment memos and deal summaries are created.</p>
      <SortableTable
        columns={COLUMNS}
        rows={decks}
        rowKey={(d) => d.id}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or thesis…"
        emptyMessage="No deal summaries yet."
      />
    </>
  );
}
