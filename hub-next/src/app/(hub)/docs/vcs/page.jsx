import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { listCompanies } from '@/lib/companies';
import { buildCompanyIndex } from '@/lib/companyIndex';
import VCsDirectory from '@/components/VCsDirectory';

export const metadata = { title: 'VCs', description: "Every VC ID8 has a line into — a partner's own contact, or one of the firm's Tier 1 relationships." };

export const dynamic = 'force-dynamic';

export default async function VCsPage() {
  const [tier1, partners, companies] = await Promise.all([listTopVCs(), listPartnerVCs(), listCompanies()]);
  const companyIndex = buildCompanyIndex(companies);

  return (
    <>
      <h1>VCs</h1>
      <p>Every VC ID8 has a line into — a partner&rsquo;s own contact, or one of the firm&rsquo;s Tier 1 relationships. Maintained from <a href="/docs/admin">Admin</a>.</p>
      <VCsDirectory tier1={tier1} partners={partners} companyIndex={companyIndex} />
    </>
  );
}
