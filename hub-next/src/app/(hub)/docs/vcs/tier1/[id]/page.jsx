import Link from 'next/link';
import { notFound } from 'next/navigation';
import { auth } from '@/auth';
import { H2 } from '@/components/Prose';
import { getTopVC } from '@/lib/topVCs';
import { listCompanies } from '@/lib/companies';
import { buildCompanyIndex, companyHref } from '@/lib/companyIndex';
import GroupFieldEditor from '@/components/GroupFieldEditor';
import ArrayFieldEditor from '@/components/ArrayFieldEditor';
import InlineTextField from '@/components/InlineTextField';
import TierDealsTable from '@/components/TierDealsTable';

export const dynamic = 'force-dynamic';

export async function generateMetadata({ params }) {
  const { id } = await params;
  const vc = await getTopVC(id);
  return { title: vc ? vc.name : 'VC not found' };
}

const FUND_FIELDS = [
  { key: 'founded', label: 'Founded', placeholder: 'e.g. 2020' },
  { key: 'aum', label: 'AUM', placeholder: 'e.g. Not publicly disclosed' },
  { key: 'checkSize', label: 'Check size', placeholder: 'e.g. $250K – $2M' },
  { key: 'stageFocus', label: 'Stage focus', placeholder: 'e.g. Seed – Series B' },
  { key: 'geoFocus', label: 'Geography', placeholder: 'e.g. US, bi-coastal' },
];

const ATTIO_FIELDS = [
  { key: 'last', label: 'Last interaction', placeholder: 'e.g. 3 months ago' },
  { key: 'strength', label: 'Connection strength', placeholder: 'Strong / Weak' },
  { key: 'contacts', label: 'Contacts', placeholder: 'e.g. Jane Doe' },
];

const DEAL_FIELDS = [
  { key: 'company', label: 'Company', required: true },
  { key: 'date', label: 'Deal date', placeholder: 'e.g. Jun 2026' },
  { key: 'type', label: 'Deal type', placeholder: 'e.g. Series C' },
  { key: 'size', label: 'Size', placeholder: 'e.g. $300M' },
  { key: 'industry', label: 'Industry', placeholder: 'Industry' },
  { key: 'investors', label: 'Other investors', placeholder: 'Other investors' },
  { key: 'status', label: 'Status', placeholder: 'co / pipe' },
  { key: 'hot', label: 'Hot', type: 'checkbox' },
];

const NEWS_FIELDS = [
  { key: 'text', label: 'Headline', required: true, placeholder: 'Headline' },
  { key: 'href', label: 'URL', placeholder: 'https://…' },
  { key: 'src', label: 'Source', placeholder: 'e.g. TechCrunch' },
];

export default async function Tier1VCPage({ params }) {
  const { id } = await params;
  const [vc, session, companies] = await Promise.all([getTopVC(id), auth(), listCompanies()]);
  if (!vc) notFound();
  const canEdit = session?.user?.role === 'internal';
  // Touching a company should land on wherever ID8 actually tracks it (its
  // real Watchlist/Deal Pipeline/Qualified/Radar/Invested page) when we've
  // screened it ourselves; only fall back to the VC-portfolio-only drill-in
  // when we haven't -- same cross-reference Hot Deals already does.
  const companyIndex = buildCompanyIndex(companies);
  const companyLink = (name) => companyHref(companyIndex, name) || `/docs/vcs/company/${encodeURIComponent(name)}`;

  const dealsDisplay = vc.deals.map((d) => (
    <>
      <Link href={companyLink(d.company)}><strong>{d.company}</strong></Link>
      {[d.type, d.date, d.size].filter(Boolean).length ? ` — ${[d.type, d.date, d.size].filter(Boolean).join(' · ')}` : ''}
      {d.status === 'co' ? ' · Co-invested' : d.status === 'pipe' ? ' · In pipeline' : ''}
      {d.hot ? ' · Hot' : ''}
    </>
  ));
  const newsDisplay = vc.news.map((n) => (n.href ? <a href={n.href} target="_blank" rel="noopener noreferrer">{n.text}</a> : n.text));

  return (
    <>
      <p><Link href="/docs/vcs">← VCs</Link></p>
      <h1>{vc.name}</h1>
      <p>
        Tier 1{vc.sector ? ` · ${vc.sector}` : ''}
        {vc.website ? <> · <a href={`https://${vc.website}`} target="_blank" rel="noopener noreferrer">{vc.website}</a></> : null}
      </p>

      <H2>Fund characteristics</H2>
      <GroupFieldEditor endpoint="/api/top-vcs" id={vc.id} field="fund" value={vc.fund} fields={FUND_FIELDS} canEdit={canEdit} />

      <H2>Relationship</H2>
      <p><em>Manually tracked — not synced from Attio yet.</em></p>
      <GroupFieldEditor endpoint="/api/top-vcs" id={vc.id} field="attio" value={vc.attio} fields={ATTIO_FIELDS} canEdit={canEdit} />

      <H2>Investments</H2>
      <p>
        Total tracked investments:{' '}
        <InlineTextField endpoint="/api/top-vcs" id={vc.id} field="totalInvestments" value={vc.totalInvestments != null ? String(vc.totalInvestments) : ''} canEdit={canEdit} placeholder="e.g. 44" />
        {vc.totalInvestments && vc.deals.length && vc.totalInvestments > vc.deals.length
          ? ` — showing ${vc.deals.length} recorded below`
          : ''}
      </p>
      <TierDealsTable deals={vc.deals} companyIndex={companyIndex} />
      <p><em>Edit the raw list below to add, remove, or correct an investment.</em></p>
      <ArrayFieldEditor
        endpoint="/api/top-vcs"
        id={vc.id}
        field="deals"
        items={vc.deals}
        displayItems={dealsDisplay}
        fields={DEAL_FIELDS}
        canEdit={canEdit}
        addLabel="Add investment"
      />

      <H2>Recent news</H2>
      <ArrayFieldEditor
        endpoint="/api/top-vcs"
        id={vc.id}
        field="news"
        items={vc.news}
        displayItems={newsDisplay}
        fields={NEWS_FIELDS}
        canEdit={canEdit}
        addLabel="Add news item"
      />
    </>
  );
}
