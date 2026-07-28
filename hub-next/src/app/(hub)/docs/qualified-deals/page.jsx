import Link from 'next/link';
import { auth } from '@/auth';
import DealsListSection from '@/components/DealsListSection';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const metadata = { title: 'Qualified Deals', description: 'Every deal that has cleared the Stage 1 rubric screen.' };

export const dynamic = 'force-dynamic';

export default async function QualifiedDealsPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const qualified = companies.filter((c) => c.stage === 'qualified');

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
        tier1={tier1}
        partners={partners}
        defaultSort={{ key: 'date', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="No qualified deals yet."
      />
    </>
  );
}
