import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const metadata = { title: 'Top 10 VCs', description: 'Every deal Attio has tagged as sourced from a Top 10 VC, across every stage.' };

export const dynamic = 'force-dynamic';

// Not a stage -- a cross-cutting view over every company already in a stage
// bucket (Watchlist/Pipeline/Qualified/Radar/Invested), filtered to whichever
// ones Attio itself flagged "Top 10 VC" on the deal record. That flag is
// synced onto company.top10VC by every Attio import (see
// deal_intelligence/firestore_push.py's push_company_from_attio) -- this page
// has no write path of its own, it just filters what's already there, same
// shared row-builder (companyToRow/STAGE_TABLE_COLUMNS) every other stage
// table uses, with basePath omitted so each row still links to wherever that
// company's own real stage page lives.
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
        Every company whose Attio deal is tagged &ldquo;Top 10 VC&rdquo; &mdash; synced automatically on every
        Attio import, not a stage of its own. A company keeps whatever real stage it&rsquo;s at and just shows
        up here too.
      </p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="No deals tagged Top 10 VC in Attio yet."
      />
    </>
  );
}
