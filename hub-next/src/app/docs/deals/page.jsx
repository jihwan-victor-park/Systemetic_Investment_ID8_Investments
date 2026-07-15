import Link from 'next/link';
import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import DeleteButton from '@/components/DeleteButton';
import { listDealResearchDecks } from '@/lib/dealResearchDecks';

export const metadata = { title: 'Deal Summaries', description: 'Companies ID8 has done real research work on.' };

export const dynamic = 'force-dynamic';

const COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'thesis', label: 'Thesis' },
  { key: 'stage', label: 'Stage', sortable: true },
  { key: 'date', label: 'Date', sortable: true },
  { key: 'actions', label: '' },
];

function toRow(d, canEdit) {
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
      actions: canEdit ? (
        <DeleteButton
          url={`/api/deals/${d.id}`}
          confirmMessage={`Remove the deal summary for ${d.companyName}?`}
        />
      ) : null,
    },
  };
}

export default async function DealsPage() {
  const [decks, session] = await Promise.all([listDealResearchDecks(), auth()]);
  const canEdit = session?.user?.role === 'internal';

  return (
    <>
      <h1>Deal Summaries</h1>
      <p>Companies ID8 has done real diligence work on — this populates as investment memos and deal summaries are created.</p>
      <SortableTable
        columns={COLUMNS}
        rows={decks.map((d) => toRow(d, canEdit))}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or thesis…"
        emptyMessage="No deal summaries yet."
      />
    </>
  );
}
