import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const metadata = { title: 'Qualified Deals', description: 'Every deal that has cleared the Stage 1 rubric screen.' };

export const dynamic = 'force-dynamic';

export default async function QualifiedDealsPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.stage === 'qualified')
    .map((c) => companyToRow(c, { basePath: '/docs/qualified-deals', canEdit, tier1, partners }));

  return (
    <>
      <h1>Qualified Deals</h1>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'date', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="No qualified deals yet."
      />
    </>
  );
}
