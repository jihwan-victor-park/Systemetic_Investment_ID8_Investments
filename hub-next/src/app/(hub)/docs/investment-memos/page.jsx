import Link from 'next/link';
import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import DeleteButton from '@/components/DeleteButton';
import { listDealResearchDecks } from '@/lib/dealResearchDecks';

export const metadata = { title: 'Investment Memo', description: 'Full investment memos ID8 has written.' };

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
      company: <Link href={`/docs/investment-memos/${d.id}`}>{d.companyName}</Link>,
      thesis: d.thesis,
      stage: d.stage,
      date: d.createdAt ? d.createdAt.slice(0, 10) : '—',
      actions: canEdit ? (
        <DeleteButton
          url={`/api/deals/${d.id}`}
          confirmMessage={`Remove the investment memo for ${d.companyName}?`}
        />
      ) : null,
    },
  };
}

// Same underlying `dealResearchDecks` collection as Deal Summaries, filtered
// to docType === 'investment-memo' -- see lib/dealResearchDecks.js for why
// this is a split of one collection rather than a separate one.
export default async function InvestmentMemosPage() {
  const [allDecks, session] = await Promise.all([listDealResearchDecks(), auth()]);
  const decks = allDecks.filter((d) => d.docType === 'investment-memo');
  const canEdit = session?.user?.role === 'internal';

  return (
    <>
      <h1>Investment Memo</h1>
      <p>Full investment memos ID8 has written — the deeper counterpart to a <a href="/docs/deals">Deal Summary</a>.</p>
      <SortableTable
        columns={COLUMNS}
        rows={decks.map((d) => toRow(d, canEdit))}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or thesis…"
        emptyMessage="No investment memos yet."
      />
    </>
  );
}
