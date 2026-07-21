import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const metadata = { title: 'Deal Pipeline', description: 'Companies ID8 is actively working right now.' };

export const dynamic = 'force-dynamic';

export default async function PipelinePage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.stage === 'pipeline')
    .map((c) => companyToRow(c, { basePath: '/docs/pipeline', canEdit, tier1, partners }));

  return (
    <>
      <h1>Deal Pipeline</h1>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing in the pipeline yet."
      />
    </>
  );
}
