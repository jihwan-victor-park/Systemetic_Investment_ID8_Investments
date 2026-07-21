import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { findInvestorSources } from '@/lib/companyIndex';

export const metadata = { title: 'Top 10 VCs', description: 'Every company sourced from a Tier 1 VC’s portfolio, across every stage.' };

export const dynamic = 'force-dynamic';

// Cross-cutting view, not a stage of its own -- a company keeps whatever
// stage it's actually at (Watchlist/Pipeline/Qualified/Radar/Invested) and
// just shows up here too if it's in a Tier 1 firm's recorded portfolio. Same
// findInvestorSources lookup Hot Deals and every stage table already use;
// basePath is omitted from companyToRow so each row still links to the
// company's own real stage page rather than a single fixed tab.
export default async function Top10VCPage() {
  const [companies, tier1, partners, session] = await Promise.all([
    listCompanies(),
    listTopVCs(),
    listPartnerVCs(),
    auth(),
  ]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => findInvestorSources(c.name, tier1, partners).some((m) => m.source === 'Tier 1 VC'))
    .map((c) => companyToRow(c, { canEdit, tier1, partners }));

  return (
    <>
      <h1>Top 10 VCs</h1>
      <p>
        Every company in the directory, at any stage, that shows up in one of ID8&rsquo;s Tier 1 VCs&rsquo; own
        portfolios &mdash; a view across the existing stages, not a stage of its own. Manage the Tier 1 list itself
        from <a href="/docs/admin">Admin</a>.
      </p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="No companies matched to a Tier 1 VC yet."
      />
    </>
  );
}
