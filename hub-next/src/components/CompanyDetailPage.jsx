import { notFound } from 'next/navigation';
import { auth } from '@/auth';
import { getCompany } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { findInvestorMatches } from '@/lib/companyIndex';
import ScreenView from '@/components/ScreenView';
import FitScoreScreenView from '@/components/FitScoreScreenView';
import TrackNewRoundForm from '@/components/TrackNewRoundForm';
import CompanyInlineField from '@/components/CompanyInlineField';
import InvestorRelationships from '@/components/InvestorRelationships';
import RunAnalysisButton from '@/components/RunAnalysisButton';

// Shared by the Watchlist / Pipeline / Qualified Deals detail routes -- a
// company's screen history looks identical regardless of which stage it's
// currently filed under, so each route's page.jsx just re-exports this.
export async function generateCompanyMetadata({ params }) {
  const { slug } = await params;
  const company = await getCompany(slug);
  if (!company) return {};
  return { title: company.name, description: `Deal screens for ${company.name}` };
}

export default async function CompanyDetailPage({ params }) {
  const { slug } = await params;
  const [company, session, tier1, partners] = await Promise.all([
    getCompany(slug),
    auth(),
    listTopVCs(),
    listPartnerVCs(),
  ]);
  if (!company) notFound();
  const { tier1Matches, partnerMatches } = findInvestorMatches(company.name, tier1, partners);
  // A company can be a real ID8 pipeline entry (this page) with NO live
  // Stage 1 screen yet -- promoted straight from a VC portfolio, or arrived
  // through Attio with a Tier 1 relationship on file but never scanned
  // (Oscar's own example: Anduril, tracked and Stage 0-scored via 1789
  // Capital, but with zero Stage 1 screens). Without this, Qualified Deals
  // /Watchlist/Pipeline all silently dropped that Stage 0 read the moment a
  // company crossed over from "VC portfolio drill-in" to "real pipeline
  // entry" -- same fit-score summary VCPortfolioCompanyPage shows, here too.
  const scoredMatch = company.screens.length === 0
    ? partnerMatches.find((m) => m.entry.fitScore != null)
    : null;
  const fit = scoredMatch?.entry;
  // Editing (subcategory scores/findings, dimension evidence, deal rationale)
  // is internal-only -- same role check as /api/top-vcs. These pages are
  // already internal-only end to end (investors are redirected to
  // /investors/research before reaching them), so this only gates whether
  // the edit controls render, not whether the page loads.
  const canEdit = session?.user?.role === 'internal';

  return (
    <>
      <h1>{company.name}</h1>
      <p>
        <a href={`https://${company.website}`} target="_blank" rel="noopener noreferrer">{company.website}</a>
        {' · '}
        <a href={company.screens[0]?.docxPath || `/research/companies/${company.slug}.docx`}>Download latest screen (Word) →</a>
        {' · '}
        <CompanyInlineField
          slug={company.slug}
          apiSegment="pitchbook"
          field="pitchbookUrl"
          value={company.pitchbookUrl}
          canEdit={canEdit}
          placeholder="PitchBook URL"
          renderAs="link"
          linkLabel="PitchBook ↗"
        />
      </p>
      {fit && <FitScoreScreenView fit={fit} />}
      {/* Same "Run Analysis" trigger the stage-table rows already have
          (companyStageColumns.jsx) -- there it's always available (first run
          or re-run), so it is here too. A company promoted straight from a
          VC portfolio (PromoteToPipeline) lands on this exact page with zero
          screens yet, and this is what starts Stage 1 without going back to
          a list first. */}
      {canEdit && <p><RunAnalysisButton slug={company.slug} name={company.name} /></p>}
      {company.screens.map((screen) => (
        <ScreenView key={screen.id} screen={screen} canEdit={canEdit} slug={company.slug} />
      ))}
      {canEdit && <TrackNewRoundForm slug={company.slug} />}
      <InvestorRelationships tier1Matches={tier1Matches} partnerMatches={partnerMatches} />
    </>
  );
}
