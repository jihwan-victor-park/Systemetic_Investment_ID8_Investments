import Link from 'next/link';
import { notFound } from 'next/navigation';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { findInvestorMatches } from '@/lib/companyIndex';
import InvestorRelationships from '@/components/InvestorRelationships';

export const dynamic = 'force-dynamic';

export async function generateMetadata({ params }) {
  const { slug } = await params;
  return { title: decodeURIComponent(slug) };
}

// By-Investment drill-in -- not a company ID8 has screened itself, just
// somewhere in a VC's recorded portfolio (Tier 1's deals[] or a partner's
// portfolio[]). `slug` is an encodeURIComponent'd company name, matched
// case-insensitively against both -- no separate collection needed.
export default async function VCPortfolioCompanyPage({ params }) {
  const { slug } = await params;
  const companyName = decodeURIComponent(slug);
  const [tier1, partners] = await Promise.all([listTopVCs(), listPartnerVCs()]);
  const { tier1Matches, partnerMatches } = findInvestorMatches(companyName, tier1, partners);

  if (tier1Matches.length === 0 && partnerMatches.length === 0) notFound();

  const rep = tier1Matches[0]?.d;
  const repEntry = partnerMatches[0]?.entry;
  const repIndustry = rep?.industry || repEntry?.industry;
  const repCategory = repEntry?.category;
  const repDescription = repEntry?.description;
  const repPitchbookUrl = repEntry?.pitchbookUrl;

  return (
    <>
      <p><Link href="/docs/vcs">← VCs</Link></p>
      <h1>{companyName}</h1>
      <p>
        {[repIndustry, repCategory, rep && rep.type && rep.date ? `last deal ${rep.type}, ${rep.date}${rep.size ? ` (${rep.size})` : ''}` : null]
          .filter(Boolean).join(' · ') || 'No deal detail recorded.'}
        {repPitchbookUrl && (
          <>
            {' · '}
            <a href={repPitchbookUrl} target="_blank" rel="noopener noreferrer">PitchBook ↗</a>
          </>
        )}
      </p>
      {repDescription && <p>{repDescription}</p>}

      <InvestorRelationships tier1Matches={tier1Matches} partnerMatches={partnerMatches} />
    </>
  );
}
