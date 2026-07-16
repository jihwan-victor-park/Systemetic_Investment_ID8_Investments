import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'New Deals', description: 'Companies pulled in from Attio that haven\'t been triaged into Watchlist/Pipeline/Qualified yet.' };

export const dynamic = 'force-dynamic';

export default async function NewDealsPage() {
  const [companies, session] = await Promise.all([listCompanies(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.stage === 'new')
    .map((c) => companyToRow(c, { basePath: '/docs/new-deals', canEdit }));

  return (
    <>
      <h1>New Deals</h1>
      <p>Companies pulled in from Attio that haven't been triaged yet. Move one to Watchlist, Pipeline, or Qualified Deals with the Stage dropdown.</p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or stage…"
        emptyMessage="Nothing new to triage."
      />
    </>
  );
}
