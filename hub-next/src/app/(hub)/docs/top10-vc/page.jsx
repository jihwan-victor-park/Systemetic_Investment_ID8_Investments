import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const metadata = { title: 'Top 10 VCs', description: 'Every company on ID8’s Top 10 VC list, across every stage.' };

export const dynamic = 'force-dynamic';

// Not a stage -- a cross-cutting view over every company already in a stage
// bucket (Watchlist/Pipeline/Qualified/Radar/Invested), filtered to
// company.top10VC. There is no Attio field or tag behind this: "Top 10 VC" is
// a fixed, hand-maintained list of company names, seeded onto company.top10VC
// by a one-time name-match backfill (see
// deal_intelligence/firestore_push.py's backfill_top10_vc) -- not something
// that re-syncs on its own. This page has no write path of its own, it just
// filters what's already there, same shared row-builder
// (companyToRow/STAGE_TABLE_COLUMNS) every other stage table uses, with
// basePath omitted so each row still links to wherever that company's own
// real stage page lives.
export default async function Top10VCPage() {
  const [companies, tier1, partners, session] = await Promise.all([
    listCompanies(),
    listTopVCs(),
    listPartnerVCs(),
    auth(),
  ]);
  const canEdit = session?.user?.role === 'internal';
  const rows = companies
    .filter((c) => c.top10VC)
    .map((c) => companyToRow(c, { canEdit, tier1, partners }));

  return (
    <>
      <h1>Top 10 VCs</h1>
      <p>
        Every company on ID8&rsquo;s Top 10 VC list &mdash; not a stage of its own. A company keeps whatever
        real stage it&rsquo;s at and just shows up here too. This isn&rsquo;t synced from Attio; it&rsquo;s a
        fixed list of company names, seeded in once.
      </p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="No companies matched to the Top 10 VC list yet."
      />
    </>
  );
}
