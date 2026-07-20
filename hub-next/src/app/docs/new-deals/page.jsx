import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const metadata = { title: 'New Deals', description: 'Companies pulled in from Attio that haven\'t been triaged into Watchlist/Pipeline/Qualified yet.' };

export const dynamic = 'force-dynamic';

export default async function NewDealsPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.stage === 'new')
    .map((c) => companyToRow(c, { basePath: '/docs/new-deals', canEdit, tier1, partners }));

  return (
    <>
      <h1>New Deals</h1>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing new to triage."
      />
    </>
  );
}
