import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';
import { auth } from '@/auth';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { buildCompanyIndex, companyHref, findInvestorMatches } from '@/lib/companyIndex';
import InvestorRelationships from '@/components/InvestorRelationships';
import PromoteToPipeline from '@/components/PromoteToPipeline';
import FitScoreDetail from '@/components/FitScoreDetail';
import { TIER_LABEL, TIER_BADGE_CLASS } from '@/lib/fitTier';

export const dynamic = 'force-dynamic';

export async function generateMetadata({ params }) {
  const { slug } = await params;
  return { title: decodeURIComponent(slug) };
}

// By-Investment drill-in -- not a company ID8 has screened itself, just
// somewhere in a VC's recorded portfolio (Tier 1's deals[] or a partner's
// portfolio[]). `slug` is an encodeURIComponent'd company name, matched
// case-insensitively against both -- no separate collection needed.
//
// A company and a deal should always point to the same place: if this name
// already has a real company doc (promoted via PromoteToPipeline, or arrived
// through the regular Attio/Deal Intelligence path), redirect to ITS profile
// (CompanyDetailPage) instead of rendering this VC-only drill-in -- that page
// now shows the same Stage 0 fit read this one does (see fitTier.js), so
// nothing is lost by landing there instead.
export default async function VCPortfolioCompanyPage({ params }) {
  const { slug } = await params;
  const companyName = decodeURIComponent(slug);
  const [companies, tier1, partners, session] = await Promise.all([
    listCompanies(), listTopVCs(), listPartnerVCs(), auth(),
  ]);
  const href = companyHref(buildCompanyIndex(companies), companyName);
  if (href) redirect(href);

  const { tier1Matches, partnerMatches } = findInvestorMatches(companyName, tier1, partners);

  if (tier1Matches.length === 0 && partnerMatches.length === 0) notFound();

  const canEdit = session?.user?.role === 'internal';

  const rep = tier1Matches[0]?.d;
  const repEntry = partnerMatches[0]?.entry;
  const repIndustry = rep?.industry || repEntry?.industry;
  const repCategory = repEntry?.category;
  const repDescription = repEntry?.description;
  const repPitchbookUrl = repEntry?.pitchbookUrl;

  // Stage 0 Portfolio Fit results live on the individual portfolio entry
  // (deal_intelligence/portfolio_fit.py write_back), not on this page's own
  // data -- a company can sit in more than one VC's portfolio, each scored
  // independently, so this picks the first match that's actually been
  // scored rather than assuming the first (possibly unscored) one has it.
  const scoredMatch = partnerMatches.find((m) => m.entry.fitScore != null);
  const fit = scoredMatch?.entry;

  // Best-effort attribution for "Add..." (origin.leadInvestors) --
  // prefer a Tier 1 relationship, else the first partner match. Purely
  // informational, never gates anything.
  const sourceVCName = tier1Matches[0]?.firm?.name || partnerMatches[0]?.firm?.name;

  // Pre-fill the required round field with whatever's already known -- the
  // Stage 0-researched current stage first (most current), else any
  // partner match's on-file latest/invested round. Still just a default;
  // PromoteToPipeline requires a human to confirm it before it's set.
  const defaultRound = fit?.fitCurrentStage || fit?.latestRound
    || repEntry?.latestRound || repEntry?.roundInvested || '';

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

      {fit && (
        <p>
          <strong>Fit score: {fit.fitScore.toFixed(1)} / 4.0</strong>{' '}
          <span className={`badge ${TIER_BADGE_CLASS[fit.fitTier] || 'badge--borderline'}`}>
            {TIER_LABEL[fit.fitTier] || fit.fitTier}
          </span>
          {' — Latest round: '}{fit.fitCurrentStage || fit.latestRound || '—'}
        </p>
      )}
      {fit && <FitScoreDetail fit={fit} bordered />}

      {canEdit && (
        <PromoteToPipeline companyName={companyName} sourceVCName={sourceVCName} defaultRound={defaultRound} />
      )}

      <InvestorRelationships tier1Matches={tier1Matches} partnerMatches={partnerMatches} />
    </>
  );
}
