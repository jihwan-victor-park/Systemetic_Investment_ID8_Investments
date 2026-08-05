import { auth } from '@/auth';
import DealsListSection from '@/components/DealsListSection';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { buildInvestorIndex, investorDomainIndex } from '@/lib/companyIndex';

export const metadata = { title: 'Rejected', description: 'Deals ID8 passed on, kept for the record.' };

export const dynamic = 'force-dynamic';

// Additive, same pattern as every other stage tab (see lib/stages.js's TAGS
// comment): a company shows up here either because its primary stage IS
// 'rejected' or because it's carrying the 'rejected' tag independently.
// 'rejected' is deliberately additive rather than a stage that replaces
// whatever a company's real working stage was (Oscar, 2026-08-05: "without
// taking off the double tag to those that have already been categorized" --
// a deal Passed on one round while sitting in Pipeline/Qualified on an
// earlier or later round keeps that stage; this tag is layered on top, not
// swapped in). See deal_intelligence/import_attio_deals_csv.py, the only
// writer of this tag today -- it's stamped when a company's CURRENT (most
// recent by Deal Date) Attio record reads "Passed", never touching stage.
export default async function RejectedPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const rejected = companies.filter((c) => c.stage === 'rejected' || c.tags?.includes('rejected'));
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = investorDomainIndex(tier1, partners);

  return (
    <>
      <h1>Rejected</h1>
      <p>Deals ID8 passed on. Kept here for the record rather than deleted -- a company can still carry its real working stage (Pipeline, Qualified, etc.) alongside this tag if it was active before being passed on.</p>
      <DealsListSection
        companies={rejected}
        basePath="/docs/rejected"
        canEdit={canEdit}
        investorIndex={investorIndex}
        domainIndex={domainIndex}
        defaultSort={{ key: 'dealDate', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing rejected yet."
      />
    </>
  );
}
