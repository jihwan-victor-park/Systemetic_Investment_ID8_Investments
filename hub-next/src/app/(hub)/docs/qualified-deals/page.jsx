import Link from 'next/link';
import { auth } from '@/auth';
import DealsListSection from '@/components/DealsListSection';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { buildInvestorIndex } from '@/lib/companyIndex';

export const metadata = { title: 'Qualified Deals', description: 'Every deal that has cleared the Stage 1 rubric screen.' };

export const dynamic = 'force-dynamic';

export default async function QualifiedDealsPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  // Additive: a company shows up here either because its primary stage IS
  // Qualified (the old, still-supported behavior) OR because it's carrying
  // the `qualified` tag independently -- auto-added by
  // deal_intelligence/firestore_push.py whenever a screen clears the 3.0
  // gate, regardless of whatever stage that company actually lives in (e.g.
  // a company parked in Pipeline that also clears the gate shows up here
  // too). See lib/stages.js's TAGS comment.
  const qualified = companies.filter((c) => c.stage === 'qualified' || c.tags?.includes('qualified'));
  const investorIndex = buildInvestorIndex(tier1, partners);

  return (
    <>
      <h1>Qualified Deals</h1>
      <p>
        Every deal that reaches the Qualified stage gets scored by{' '}
        <Link href="/docs/projects/intelligence">Deal Intelligence</Link>'s weekly Stage 1 screen against the ID8
        rubric — this list populates automatically as those runs complete, no manual step required. Move a company to
        Watchlist or Pipeline with the Stage dropdown if it belongs somewhere else.
      </p>
      <DealsListSection
        companies={qualified}
        basePath="/docs/qualified-deals"
        canEdit={canEdit}
        investorIndex={investorIndex}
        defaultSort={{ key: 'date', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="No qualified deals yet."
      />
    </>
  );
}
