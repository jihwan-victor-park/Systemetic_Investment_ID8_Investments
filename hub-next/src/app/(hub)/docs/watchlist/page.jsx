import { auth } from '@/auth';
import DealsListSection from '@/components/DealsListSection';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { buildInvestorIndex, investorDomainIndex } from '@/lib/companyIndex';

export const metadata = { title: 'Watchlist', description: 'Companies ID8 is keeping an eye on but isn\'t actively working yet.' };

export const dynamic = 'force-dynamic';

export default async function WatchlistPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  // Additive (2026-07-30, matching Qualified Deals/Radar's own pattern):
  // a company shows up here either because its primary stage IS Watchlist,
  // or because it's carrying the 'watchlist' tag independently via
  // StageMultiSelect -- see lib/stages.js's TAGS comment.
  const watchlist = companies.filter((c) => c.stage === 'watchlist' || c.tags?.includes('watchlist'));
  // Built once server-side and handed down as a small name -> matches map --
  // NOT the raw tier1/partners arrays, which would ship the entire multi-MB
  // portfolio dataset to the browser just for this cross-reference (see
  // buildInvestorIndex's own comment in lib/companyIndex.js).
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = investorDomainIndex(tier1, partners);

  return (
    <>
      <h1>Watchlist</h1>
      {/* No subtitle (Oscar, 2026-08-13: "delete the subtitles of all the
          deals tab") -- the table is the page. `metadata.description`
          still carries the same sentence for the browser/sidebar. */}
      <DealsListSection
        companies={watchlist}
        basePath="/docs/watchlist"
        canEdit={canEdit}
        investorIndex={investorIndex}
        domainIndex={domainIndex}
        defaultSort={{ key: 'dealDate', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing on the watchlist yet."
      />
    </>
  );
}
