import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { findInvestorSources } from '@/lib/companyIndex';
import { isSeriesAOrEarlier } from '@/lib/seriesRank';

export const metadata = {
  title: 'Top 10 VC Deals',
  description: 'Deals sourced from a Tier 1 VC’s own portfolio, Series A or earlier — the Radar Category bucket.',
};

export const dynamic = 'force-dynamic';

// Cross-cutting view, not a stage of its own. A company shows up here in
// either of two ways:
//   1. The pipeline's own Attio automation already classified the deal as
//      "Radar" (deal_intelligence/firestore_push.py's push_company_from_attio
//      writes this verbatim onto origin.attioStage -- series Seed through
//      Series A, sourced from a Top 10 VC's portfolio -- but never maps it to
//      one of the Hub's own stage buckets, so today it silently falls back to
//      Qualified with no distinction). This is the authoritative signal once
//      Attio has actually tagged a deal.
//   2. Falling back to a same-effect heuristic (Tier 1 VC portfolio match +
//      Series A-or-earlier round) for anything not yet Attio-tagged this way
//      -- isSeriesAOrEarlier treats a blank/unrecorded round as included,
//      since most companies don't have one yet (see lib/seriesRank.js).
// Either way, the company can also be filed under Watchlist/Pipeline/
// Qualified/New at the same time; companyToRow resolves each row's own
// report link via its real stage since there's no single fixed basePath here.
export default async function Top10VcDealsPage() {
  const [companies, tier1, partners, session] = await Promise.all([
    listCompanies(),
    listTopVCs(),
    listPartnerVCs(),
    auth(),
  ]);
  const canEdit = session?.user?.role === 'internal';

  const rows = companies
    .filter((c) => {
      const attioRadarTagged = (c.origin?.attioStage || '').trim().toLowerCase() === 'radar';
      if (attioRadarTagged) return true;
      if (!isSeriesAOrEarlier(c.round)) return false;
      return findInvestorSources(c.name, tier1, partners).some((m) => m.source === 'Tier 1 VC');
    })
    .map((c) => companyToRow(c, { canEdit, tier1, partners }));

  return (
    <>
      <h1>Top 10 VC Deals</h1>
      <p>
        Every company sourced from one of ID8&rsquo;s Tier 1 VCs&rsquo; own portfolios, at Series A or earlier —
        the same population the Radar Category classification applies to. A company can appear here and in its own
        stage table (Watchlist/Pipeline/Qualified/New) at the same time; this view is a filter across all of them,
        not a fifth stage.
      </p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company, series, or Radar Category…"
        emptyMessage="No Tier 1-sourced, Series A-or-earlier deals recorded yet."
      />
    </>
  );
}
