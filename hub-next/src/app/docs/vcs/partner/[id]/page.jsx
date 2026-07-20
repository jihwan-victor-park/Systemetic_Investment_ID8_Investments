import Link from 'next/link';
import { notFound } from 'next/navigation';
import { auth } from '@/auth';
import { H2 } from '@/components/Prose';
import { getPartnerVC } from '@/lib/partnerVCs';
import { listCompanies } from '@/lib/companies';
import { buildCompanyIndex } from '@/lib/companyIndex';
import ArrayFieldEditor from '@/components/ArrayFieldEditor';
import InlineTextField from '@/components/InlineTextField';
import PartnerPortfolioSection from '@/components/PartnerPortfolioSection';

export const dynamic = 'force-dynamic';

export async function generateMetadata({ params }) {
  const { id } = await params;
  const vc = await getPartnerVC(id);
  return { title: vc ? vc.name : 'VC not found' };
}

const NEWS_FIELDS = [
  { key: 'company', label: 'Company', required: true, placeholder: 'Company name' },
  { key: 'daysAgo', label: 'When', placeholder: 'e.g. 3d ago' },
];

export default async function PartnerVCPage({ params }) {
  const { id } = await params;
  const [vc, session, companies] = await Promise.all([getPartnerVC(id), auth(), listCompanies()]);
  if (!vc) notFound();
  const canEdit = session?.user?.role === 'internal';
  const companyIndex = buildCompanyIndex(companies);
  const newsDisplay = vc.news.map((n) => `${n.company}${n.daysAgo ? ` — ${n.daysAgo}` : ''}`);

  return (
    <>
      <p><Link href="/docs/vcs">← VCs</Link></p>
      <h1>{vc.website ? <a href={`https://${vc.website}`} target="_blank" rel="noopener noreferrer">{vc.name} ↗</a> : vc.name}</h1>
      <p>
        Partner VC{vc.sector ? ` · ${vc.sector}` : ''}
        {vc.website ? <> · {vc.website}</> : null}
      </p>
      <p>
        Tracked by <InlineTextField endpoint="/api/partner-vcs" id={vc.id} field="trackedBy" value={vc.trackedBy} canEdit={canEdit} placeholder="Which partner" />
        {' · Contact '}
        <InlineTextField endpoint="/api/partner-vcs" id={vc.id} field="contact" value={vc.contact} canEdit={canEdit} placeholder="e.g. A. Rivera" />
      </p>
      <p><em>Illustrative placeholder — this VC&rsquo;s portfolio and relationship data aren&rsquo;t synced from Attio yet; everything below is typed in by hand.</em></p>

      <PartnerPortfolioSection
        vcId={vc.id}
        vcName={vc.name}
        portfolio={vc.portfolio}
        companyIndex={companyIndex}
        canEdit={canEdit}
      />

      <H2>News</H2>
      <ArrayFieldEditor
        endpoint="/api/partner-vcs"
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
