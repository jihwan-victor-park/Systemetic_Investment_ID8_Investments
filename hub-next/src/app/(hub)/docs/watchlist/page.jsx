import { auth } from '@/auth';
import DealsListSection from '@/components/DealsListSection';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { buildInvestorIndex, partnerDomainIndex } from '@/lib/companyIndex';
import { TAG_OPTIONS } from '@/lib/stages';

export const metadata = { title: 'Watchlist', description: 'Companies ID8 is keeping an eye on but isn\'t actively working yet.' };

export const dynamic = 'force-dynamic';

export default async function WatchlistPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const watchlist = companies.filter((c) => c.stage === 'watchlist');
  // Built once server-side and handed down as a small name -> matches map --
  // NOT the raw tier1/partners arrays, which would ship the entire multi-MB
  // portfolio dataset to the browser just for this cross-reference (see
  // buildInvestorIndex's own comment in lib/companyIndex.js).
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = partnerDomainIndex(partners);

  return (
    <>
      <h1>Watchlist</h1>
      <p>Companies ID8 is keeping an eye on but isn't actively working yet. Move one to Pipeline or Qualified Deals with the Stage dropdown once it's worth picking up.</p>
      <DealsListSection
        companies={watchlist}
        basePath="/docs/watchlist"
        canEdit={canEdit}
        investorIndex={investorIndex}
        domainIndex={domainIndex}
        defaultSort={{ key: 'dealDate', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing on the watchlist yet."
        tagFilterOptions={TAG_OPTIONS}
      />
    </>
  );
}
