import { notFound } from 'next/navigation';
import { auth } from '@/auth';
import { getCompany } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { findInvestorMatches } from '@/lib/companyIndex';
import ScreenView from '@/components/ScreenView';
import FitScoreScreenView from '@/components/FitScoreScreenView';
import RadarHeatBreakdown from '@/components/RadarHeatBreakdown';
import TrackNewRoundForm from '@/components/TrackNewRoundForm';
import CompanyInlineField from '@/components/CompanyInlineField';
import InvestorRelationships from '@/components/InvestorRelationships';
import RunAnalysisButton from '@/components/RunAnalysisButton';
import StartStage2Button from '@/components/StartStage2Button';
import MemoView from '@/components/MemoView';
import StageSelect from '@/components/StageSelect';
import StageMultiSelect from '@/components/StageMultiSelect';
import styles from './CompanyDetailPage.module.css';

// $32,000,000 -> "$32M" -- this page is the only place roundSize is shown as
// currency (deal_intelligence's own capital-clock math is the only other
// consumer, and that stays a raw number there). Whole millions when the
// figure is round (the common case for a reported deal size), one decimal
// otherwise (e.g. $2.5M).
function formatRoundSize(n) {
  if (!n) return null;
  const millions = n / 1_000_000;
  return `$${Number.isInteger(millions) ? millions : millions.toFixed(1)}M`;
}

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
  const roundSizeLabel = formatRoundSize(company.roundSize);

  return (
    <>
      <h1>{company.name}</h1>
      <p>
        <a href={`https://${company.website}`} target="_blank" rel="noopener noreferrer">{company.website}</a>
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
      {/* "At a glance" facts (2026-07-30, Oscar: "should mention the company
          like the partner vc thing and more overall data"; redesigned as a
          real card 2026-08-06, Oscar: "put better cards, this doesn't look
          professional" -- the stage tables already show Partner VC / Radar
          Category / Deal Date per row (companyStageColumns.jsx), but the one
          page meant to be the real company profile showed none of it above
          the fold, only a full Tier 1/Partner VC breakdown scrolled far
          below (InvestorRelationships). This is a summary, not a
          replacement -- InvestorRelationships below still has the full
          deal-by-deal table. The round-size figure gets its own large stat
          tile rather than sitting mid-sentence (Oscar: "on the number per
          each company it should say like what that number in Millions
          is"). */}
      {(company.round || company.hq || company.radarCategory || tier1Matches.length > 0 || partnerMatches.length > 0
        || company.investors?.length > 0) && (
        <div className={styles.card}>
          <div className={styles.statGrid}>
            {company.round && (
              <div className={styles.stat}>
                <span className={styles.statLabel}>Round</span>
                {roundSizeLabel
                  ? <span className={styles.statValueLarge}>{roundSizeLabel}</span>
                  : <span className={styles.statValue}>{company.round}</span>}
                <span className={styles.statSub}>
                  {roundSizeLabel && company.round}
                  {company.roundDate && `${roundSizeLabel ? ' · ' : ''}closed ${company.roundDate.slice(0, 10)}`}
                </span>
              </div>
            )}
            {company.hq && (
              <div className={styles.stat}>
                <span className={styles.statLabel}>HQ</span>
                <span className={styles.statValue}>{company.hq}</span>
              </div>
            )}
            {company.radarCategory && (
              <div className={styles.stat}>
                <span className={styles.statLabel}>Radar Category</span>
                <span className={styles.statValue}>{company.radarCategory}</span>
              </div>
            )}
            {(tier1Matches.length > 0 || partnerMatches.length > 0) && (
              <div className={styles.stat}>
                <span className={styles.statLabel}>Partner VC</span>
                <span className={styles.statValue}>{[...tier1Matches.map((m) => m.firm.name), ...partnerMatches.map((m) => m.firm.name)].join(', ')}</span>
              </div>
            )}
          </div>
          {/* Investors on this deal + Top 10 / Tier 1 (33) match attributes
              (2026-08-05) -- written by deal_intelligence/import_attio_deals_csv.py
              off the Attio Deals export's own Lead/New/Investors columns. A
              DIFFERENT question from the "Partner VC" stat above (which asks
              "is this company in one of OUR tracked VCs' own portfolios") --
              this asks "did one of the fixed Top 10 / Tier 1 (33) firms
              actually invest in this company's round," via
              deal_intelligence/tier1_firms.py's match_top10()/match_tier1_33(),
              the first thing that ever calls the latter. tier1_33Investors
              is the broader 33-firm list; top10Investors is always a subset
              of it. */}
          {company.investors?.length > 0 && (
            <>
              <div className={styles.cardSectionLabel}>Investors</div>
              <div className={styles.badgeRow}>{company.investors.join(', ')}</div>
              {company.top10Investors?.length > 0 && (
                <div className={styles.badgeRow}>
                  <span className="badge badge--gate">Top 10 VC</span> {company.top10Investors.join(', ')}
                </div>
              )}
              {company.tier1_33Investors?.length > 0 && (
                <div className={styles.badgeRow}>
                  <span className="badge badge--co">Tier 1 (33)</span> {company.tier1_33Investors.join(', ')}
                </div>
              )}
            </>
          )}
        </div>
      )}
      {company.description && <p>{company.description}</p>}
      {/* Per-row editing moved here from the stage tables' old "Also In"
          column (2026-07-28) -- those tables briefly used this same tag data
          as a page-level filter (SortableTable's old tagFilterOptions),
          removed 2026-07-29 in favor of the generic filterGroups (Stage,
          Radar's keyword chips). See lib/stages.js's TAGS comment for the
          auto-add mechanism this overrides by hand.
          Switched from the plain tags-only TagsSelect to StageMultiSelect
          (2026-07-30) once TAGS widened to every public stage -- this is now
          the SAME control the stage tables use for their Stage column, so a
          company's full multi-stage membership can be edited from its own
          page too, not just tag membership on top of a stage set elsewhere.
          'new' still needs the single-value StageSelect (see
          companyStageColumns.jsx's own comment on why). */}
      <p>
        <strong>Stage:</strong>{' '}
        {company.stage === 'new'
          ? <StageSelect slug={company.slug} stage={company.stage} canEdit={canEdit} />
          : <StageMultiSelect slug={company.slug} stage={company.stage} tags={company.tags} canEdit={canEdit} />}
      </p>
      {/* Radar alerts (2026-08-05) -- a company auto-dropped from the Radar
          tab (radar/page.jsx's `!c.radar?.droppedAt` filter) used to vanish
          with no visible reason. Surfaced here, on the one page a dropped
          company is still reachable from (its own detail page, per
          radar_state.py's own "reversible, never deletes anything"
          convention). The full score breakdown (RadarHeatBreakdown, below,
          2026-08-06) is where growthTier/marketHeat actually live now --
          this card is just the two things worth flagging before you even
          get there. */}
      {company.radar && (company.radar.droppedAt || company.radar.hazard?.distressFlag) && (
        <div className={styles.card}>
          {company.radar.droppedAt && (
            <div className={styles.badgeRow}>
              <span className="badge badge--below">Dropped from Radar</span>
              {company.radar.droppedAt.slice(0, 10)} — {company.radar.dropReason || 'no reason recorded'}
            </div>
          )}
          {company.radar.hazard?.distressFlag && (
            <div className={styles.badgeRow}>
              <span className="badge badge--below">Distress signal{company.radar.hazard.distressSignals?.length === 1 ? '' : 's'}</span>
              {company.radar.hazard.distressSignals?.join(', ') || 'active'}
            </div>
          )}
        </div>
      )}
      {fit && <FitScoreScreenView fit={fit} />}
      {company.radar && <RadarHeatBreakdown radar={company.radar} />}
      {/* Run Analysis (Stage 1) only while there's no screen yet -- once one
          exists, this becomes Start Stage 2 (deep research) instead. Same
          gate the stage tables' actions cell uses (companyStageColumns.jsx).
          A company promoted straight from a VC portfolio (PromoteToPipeline)
          lands on this exact page with zero screens yet, and Run Analysis is
          what starts Stage 1 without going back to a list first. */}
      {canEdit && (
        <p>
          {company.screens.length === 0
            ? <RunAnalysisButton slug={company.slug} name={company.name} />
            : <StartStage2Button slug={company.slug} name={company.name} />}
        </p>
      )}
      {company.memos.map((memo) => (
        <MemoView key={memo.id} memo={memo} />
      ))}
      {company.screens.map((screen) => (
        <ScreenView key={screen.id} screen={screen} canEdit={canEdit} slug={company.slug} />
      ))}
      {canEdit && <TrackNewRoundForm slug={company.slug} />}
      <InvestorRelationships tier1Matches={tier1Matches} partnerMatches={partnerMatches} />
    </>
  );
}
