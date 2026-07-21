import Link from 'next/link';
import SortableTable from '@/components/SortableTable';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { buildCompanyIndex, companyHref } from '@/lib/companyIndex';

export const metadata = { title: 'Top 10 VCs', description: 'Every deal recorded across ID8’s Tier 1 VC relationships, in one list.' };

export const dynamic = 'force-dynamic';

const COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'vc', label: 'Top 10 VC', sortable: true },
  { key: 'round', label: 'Round', sortable: true },
  { key: 'size', label: 'Size', sortable: true },
  { key: 'industry', label: 'Industry', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'date', label: 'Date', sortable: true },
];

// Not a stage -- a read-only view that flattens every Tier 1 ("Top 10")
// VC's own `deals` array (see docs/vcs/tier1/[id]/page.jsx's ArrayFieldEditor)
// into one cross-firm list, same as that page shows one firm at a time. Add
// or edit a deal from the firm's own page -- this view has no write path of
// its own, it's just another way to browse data that already lives there.
// `company` links to the real hub page when ID8 has already screened it
// (companyHref), else the same VC-portfolio-only drill-in tier1's own page
// falls back to.
export default async function Top10VCPage() {
  const [tier1, companies] = await Promise.all([listTopVCs(), listCompanies()]);
  const companyIndex = buildCompanyIndex(companies);
  const top10Firms = tier1.filter((vc) => vc.tier === 'Tier 1');

  const rows = top10Firms.flatMap((vc) =>
    (vc.deals || []).map((d, i) => {
      const href = companyHref(companyIndex, d.company) || `/docs/vcs/company/${encodeURIComponent(d.company)}`;
      const statusLabel = d.status === 'co' ? 'Co-invested' : d.status === 'pipe' ? 'In pipeline' : '—';
      return {
        key: `${vc.id}-${i}`,
        sort: {
          company: (d.company || '').toLowerCase(),
          vc: vc.name.toLowerCase(),
          round: d.type || '',
          size: d.size || '',
          industry: d.industry || '',
          status: statusLabel,
          date: d.date || '',
        },
        search: { company: d.company, vc: vc.name, industry: d.industry || '' },
        cells: {
          company: <Link href={href}><strong>{d.company}</strong></Link>,
          vc: <Link href={`/docs/vcs/tier1/${vc.id}`}>{vc.name}</Link>,
          round: d.type || '—',
          size: d.size || '—',
          industry: d.industry || '—',
          status: <>{statusLabel}{d.hot ? ' · Hot' : ''}</>,
          date: d.date || '—',
        },
      };
    }),
  );

  return (
    <>
      <h1>Top 10 VCs</h1>
      <p>
        Every deal recorded across ID8&rsquo;s Tier 1 VC relationships, in one list &mdash; a view across those
        firms&rsquo; own portfolios, not a stage of its own. Add or edit a deal from the firm&rsquo;s own page
        under <Link href="/docs/vcs">VCs</Link>.
      </p>
      <SortableTable
        columns={COLUMNS}
        rows={rows}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company, VC, or industry…"
        emptyMessage="No deals recorded for a Tier 1 VC yet."
      />
    </>
  );
}
