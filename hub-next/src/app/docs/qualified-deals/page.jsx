import Link from 'next/link';
import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'Qualified Deals', description: 'Every deal that has cleared the Stage 1 rubric screen.' };

export const dynamic = 'force-dynamic';

export default async function QualifiedDealsPage() {
  const [companies, session] = await Promise.all([listCompanies(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.stage === 'qualified')
    .map((c) => companyToRow(c, { basePath: '/docs/qualified-deals', canEdit }));

  return (
    <>
      <h1>Qualified Deals</h1>
      <p>
        Every deal that reaches the Qualified stage gets scored by{' '}
        <Link href="/docs/projects/intelligence">Deal Intelligence</Link>'s weekly Stage 1 screen against the ID8
        rubric — this list populates automatically as those runs complete, no manual step required. Move a company to
        Watchlist or Pipeline with the Stage dropdown if it belongs somewhere else.
      </p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'date', dir: 'desc' }}
        searchPlaceholder="Filter by company or stage…"
        emptyMessage="No qualified deals yet."
      />
    </>
  );
}
