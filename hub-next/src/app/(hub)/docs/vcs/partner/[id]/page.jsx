import Link from 'next/link';
import { notFound } from 'next/navigation';
import { auth } from '@/auth';
import { H2 } from '@/components/Prose';
import { getPartnerVC } from '@/lib/partnerVCs';
import { listCompanies } from '@/lib/companies';
import { buildCompanyIndex } from '@/lib/companyIndex';
import ArrayFieldEditor from '@/components/ArrayFieldEditor';
import ContactChip from '@/components/ContactChip';
import PartnerPortfolioSection from '@/components/PartnerPortfolioSection';
import { isSectorInScope } from '@/lib/sectorRelevance';
import styles from './page.module.css';

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
  // Cheap fund-level pre-filter, ahead of ever pulling this fund's individual
  // portfolio companies -- the same hard-rule keyword check the portfolio
  // table uses, run here against the fund's OWN Attio description/category.
  // A false here doesn't hide anything (deliberately no auto-collapse of the
  // portfolio section below); it's a flag for a human to weigh, since a
  // fund's own one-line blurb is a weaker signal than its actual portfolio.
  const maybeOffThesis = !isSectorInScope({ description: vc.description, category: vc.attioCategories });

  return (
    <>
      <p><Link href="/docs/vcs">← VCs</Link></p>
      <div className={styles.head}>
        <div>
          <h1>{vc.name}</h1>
          <p className={styles.sub}>
            Partner VC{vc.sector ? ` · ${vc.sector}` : ''}
            {vc.attioCategories ? ` · ${vc.attioCategories}` : ''}
            {vc.website ? <> · <a href={`https://${vc.website}`} target="_blank" rel="noopener noreferrer">{vc.website}</a></> : null}
            {vc.connectionStrength ? ` · Connection: ${vc.connectionStrength}` : ''}
          </p>
          {vc.description && <p className={styles.description}>{vc.description}</p>}
          {maybeOffThesis && (
            <p className={styles.offThesis}>
              ⚠ This fund&rsquo;s own description matches an off-thesis keyword (e.g. biotech) — worth a second look before investing time in its portfolio.
            </p>
          )}
        </div>
        <ContactChip endpoint="/api/partner-vcs" id={vc.id} trackedBy={vc.trackedBy} contact={vc.contact} canEdit={canEdit} />
      </div>

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
