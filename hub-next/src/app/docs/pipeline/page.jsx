import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'Pipeline', description: 'Companies ID8 is actively working right now.' };

export const dynamic = 'force-dynamic';

export default async function PipelinePage() {
  const [companies, session] = await Promise.all([listCompanies(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.stage === 'pipeline')
    .map((c) => companyToRow(c, { basePath: '/docs/pipeline', canEdit }));

  return (
    <>
      <h1>Pipeline</h1>
      <p>Companies ID8 is actively working right now. Move one to Qualified Deals once it clears the Stage 1 rubric, or back to Watchlist if it cools off.</p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or stage…"
        emptyMessage="Nothing in the pipeline yet."
      />
    </>
  );
}
