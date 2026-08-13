import { auth } from '@/auth';
import DealsListSection from '@/components/DealsListSection';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { buildInvestorIndex, investorDomainIndex } from '@/lib/companyIndex';

export const metadata = { title: 'Deal Pipeline', description: 'Companies ID8 is actively working right now.' };

export const dynamic = 'force-dynamic';

export default async function PipelinePage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  // Additive (2026-07-30, matching Qualified Deals/Radar's own pattern):
  // a company shows up here either because its primary stage IS Pipeline,
  // or because it's carrying the 'pipeline' tag independently via
  // StageMultiSelect -- see lib/stages.js's TAGS comment.
  const pipeline = companies.filter((c) => c.stage === 'pipeline' || c.tags?.includes('pipeline'));
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = investorDomainIndex(tier1, partners);

  return (
    <>
      <h1>Deal Pipeline</h1>
      {/* No subtitle here (Oscar, 2026-08-13) -- the table is the page; the
          stage names in each row's own multiselect already say what moving a
          deal between buckets means. `metadata.description` above still
          carries the same sentence for the browser/sidebar. */}
      <DealsListSection
        companies={pipeline}
        basePath="/docs/pipeline"
        canEdit={canEdit}
        investorIndex={investorIndex}
        domainIndex={domainIndex}
        defaultSort={{ key: 'dealDate', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing in the pipeline yet."
        hidePassed
      />
    </>
  );
}
