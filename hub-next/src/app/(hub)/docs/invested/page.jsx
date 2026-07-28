import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { buildInvestorIndex, partnerDomainIndex } from '@/lib/companyIndex';
import { TAG_OPTIONS } from '@/lib/stages';

export const metadata = { title: 'Invested', description: 'Companies ID8 has actually put money into.' };

export const dynamic = 'force-dynamic';

export default async function InvestedPage() {
  const [companies, tier1, partners, session] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = partnerDomainIndex(partners);
  const rows = companies
    .filter((c) => c.stage === 'invested')
    .map((c) => companyToRow(c, { basePath: '/docs/invested', canEdit, investorIndex, domainIndex }));

  return (
    <>
      <h1>Invested</h1>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'dealDate', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing marked Invested yet."
        tagFilterOptions={TAG_OPTIONS}
      />
    </>
  );
}
