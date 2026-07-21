import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const metadata = {
  title: 'Radar',
  description: 'Series A-or-earlier deals sourced from a Top 10 VC’s own portfolio, per Attio’s Radar classification.',
};

export const dynamic = 'force-dynamic';

// A real stage, same shape as Watchlist/Pipeline/Qualified/New -- Attio sets
// this on Series A-or-earlier deals sourced from a Top 10 VC's portfolio,
// and deal_intelligence/config.py's ATTIO_STAGE_MAP now forwards that
// straight onto stage='radar' when the data pipelines run. An internal user
// can also move any company here by hand via its own StageSelect dropdown.
export default async function RadarPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.stage === 'radar')
    .map((c) => companyToRow(c, { basePath: '/docs/radar', canEdit, tier1, partners }));

  return (
    <>
      <h1>Radar</h1>
      <p>Series A-or-earlier deals sourced from a Top 10 VC&rsquo;s own portfolio &mdash; Attio&rsquo;s own Radar classification.</p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing on Radar yet."
      />
    </>
  );
}
