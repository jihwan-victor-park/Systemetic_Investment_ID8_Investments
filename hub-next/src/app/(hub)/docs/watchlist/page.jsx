import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const metadata = { title: 'Watchlist', description: 'Companies ID8 is keeping an eye on but isn\'t actively working yet.' };

export const dynamic = 'force-dynamic';

export default async function WatchlistPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.stage === 'watchlist')
    .map((c) => companyToRow(c, { basePath: '/docs/watchlist', canEdit, tier1, partners }));

  return (
    <>
      <h1>Watchlist</h1>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing on the watchlist yet."
      />
    </>
  );
}
