import Link from 'next/link';
import StageSelect from './StageSelect';
import StageMultiSelect from './StageMultiSelect';
import PassedCheckbox from './PassedCheckbox';
import RoundInput from './RoundInput';
import CompanyInlineField from './CompanyInlineField';
import PartnerVcPopover from './PartnerVcPopover';
import DeleteButton from './DeleteButton';
import RunAnalysisButton from './RunAnalysisButton';
import StartStage2Button from './StartStage2Button';
import { allInvestorMatches } from '@/lib/companyIndex';
import { STAGE_BASEPATH } from '@/lib/stages';
import styles from './companyStageColumns.module.css';

// Shorter labels than the company docs' own frontmatter titles (which carry a
// PitchBook category suffix, e.g. "Pocket (Business/Productivity Software)") --
// the company page's own H1 shows the full title; only these tables don't.
const COMPANY_SHORT_NAME = {
  heypocket: 'Pocket',
  warp: 'Warp',
  getpie: 'PieTech',
};

const displayName = (c) => COMPANY_SHORT_NAME[c.slug] || c.name;

// Shared by the Watchlist / Pipeline / Qualified Deals list pages -- same
// shape of data (a company with a latest Stage 1 screen), just filtered to a
// different `stage` and linked at a different basePath. Not a client
// component itself; it's called from Server Component pages, so the
// StageSelect element it builds here is a plain (serializable) React element
// by the time it reaches SortableTable.
export const STAGE_TABLE_COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'series', label: 'Series', sortable: true },
  // The round's close date, off Attio's 'deal_date' slug (see
  // deal_intelligence/firestore_push.py / lib/companies.js's `roundDate`) --
  // distinct from the 'Screened' column below, which is when WE looked at
  // the deal, not when it actually closed. Added 2026-07-28 per Oscar's ask.
  { key: 'dealDate', label: 'Deal Date', sortable: true },
  { key: 'partnerVc', label: 'Partner VC', sortable: true },
  // No 'radarCategory' column (Oscar, 2026-08-13: "eliminate the column of
  // radar category of all the deals tabs") -- Radar's own table dropped it
  // back on 2026-07-29 and this removes it from the rest (Watchlist /
  // Pipeline / Qualified Deals / Invested / Passed / Top 10 VCs / Admin's
  // Needs Triage). The FIELD itself stays: it's still shown on the company
  // detail page, still filterable in Hub Search, still editable via
  // /api/companies/[slug]/radar-category, and still feeds radarRuleMatch's
  // keyword scan. `sort.radarCategory`/`search.radarCategory` below stay too
  // -- SortableTable ignores sort keys with no matching column, and keeping
  // the search key means the free-text filter still matches on category.
  { key: 'score', label: 'Score', sortable: true },
  { key: 'stage', label: 'Stage', sortable: true },
  // Dedicated column, not just a pill inside the Stage multiselect (Oscar,
  // 2026-08-06) -- a faster glance/toggle than opening that dropdown. The
  // /docs/passed tab (STAGE_BASEPATH.passed) still exists independently.
  { key: 'passed', label: 'Passed', sortable: true },
  { key: 'date', label: 'Screened', sortable: true },
  { key: 'report', label: 'Report' },
  { key: 'actions', label: '' },
];

// `basePath` is optional -- callers with a single fixed stage (Watchlist,
// Deal Pipeline, Qualified Deals, Radar, Invested, or Admin's Needs Triage
// table) pass their own page's path; a cross-cutting view spanning multiple
// stages could omit it and let each row resolve its own via c.stage instead.
export function companyToRow(c, { basePath, canEdit, investorIndex = {}, domainIndex = {} }) {
  const name = displayName(c);
  const resolvedBasePath = basePath || STAGE_BASEPATH[c.stage] || STAGE_BASEPATH.qualified;
  const score = c.latestScreen?.fitScore ?? null;
  // Live cross-reference against every VC's recorded portfolio, same lookup
  // Hot Deals uses -- not `c.origin?.leadInvestors`, which is only ever set
  // at intake time (typed by hand in Research Chat, or copied from the
  // source VC when a portfolio row gets promoted via "Add...") and
  // stays blank for the vast majority of companies that arrive through the
  // regular Deal Intelligence email screen. A company can sit in more than
  // one tracked firm's portfolio at once (e.g. Anduril), so this returns
  // every match, not just the first. `investorIndex` is built once per page
  // load by buildInvestorIndex (see callers) instead of rescanning every
  // firm's portfolio on every row -- see that function's own comment for why.
  // Merged with a domain-match against this company's OWN cap table
  // (c.investorDomains, off Attio -- see companyIndex.js's
  // domainMatchesFromIndex) -- a different question (does this company
  // already have one of our partner VCs as an investor) that feeds the same
  // column. `domainIndex` is built once per page load by investorDomainIndex,
  // same reasoning as investorIndex.
  const matches = allInvestorMatches(investorIndex, c.name, domainIndex, c.investorDomains);
  const partnerVc = matches.length ? matches.map((m) => m.via).join(', ') : null;
  // Best available portfolio-level fit score across every matched firm
  // (Stage 0 Portfolio Fit, Partner VCs only -- see buildInvestorIndex) --
  // exposed via `meta` (not `sort`/`cells`/`filterValues`, which SortableTable
  // itself reads) purely so radarTableColumns.jsx's radarCompanyToRow can
  // reuse this same already-computed `matches` pass for its heat score
  // instead of re-scanning every VC's portfolio a second time per row.
  const bestInvestorFitScore = matches.reduce(
    (best, m) => (m.fitScore != null && (best == null || m.fitScore > best) ? m.fitScore : best),
    null
  );
  return {
    key: c.slug,
    // Consumed by SortableTable's filterGroups (see lib/stages.js's
    // PUBLIC_STAGES) on cross-stage tables like Top 10 VCs/Hot Deals; a
    // no-op on the single-stage tables (Watchlist/Pipeline/...) that don't
    // wire a stage filterGroup in. Per-row stage editing still lives in the
    // `stage` cell below (StageSelect) and on the company detail page.
    filterValues: { stage: c.stage },
    meta: { fitScore: score, bestInvestorFitScore },
    sort: {
      company: name.toLowerCase(),
      series: c.round || '',
      dealDate: c.roundDate || '',
      partnerVc: partnerVc || '',
      radarCategory: c.radarCategory || '',
      score,
      stage: c.stage,
      passed: c.tags?.includes('passed') ? 1 : 0,
      date: c.latestScreen?.date || '',
    },
    search: {
      company: name,
      series: c.round || '',
      radarCategory: c.radarCategory || '',
    },
    cells: {
      // The name itself now goes to the same profile "Report" already links
      // to -- previously only "View screen →" did, so the name was dead text
      // (or, with a website on file, an external link elsewhere entirely).
      company: (
        <>
          <Link href={`${resolvedBasePath}/${c.slug}`}>{name}</Link>
          {c.website && (
            <>
              {' ('}
              <a href={`https://${c.website}`} target="_blank" rel="noopener noreferrer">{c.website}</a>
              {')'}
            </>
          )}
        </>
      ),
      series: <RoundInput slug={c.slug} round={c.round} canEdit={canEdit} />,
      // Editable in place since 2026-08-13 (Oscar: "make it so that the deal
      // date is easily editable") -- it's this table's default sort and 48
      // Attio deals have no date at all, so correcting one shouldn't mean
      // opening Attio. The edit is mirrored back onto Attio's own `deal_date`
      // (lib/companies.js's updateCompanyRoundDate).
      dealDate: (
        <CompanyInlineField
          slug={c.slug}
          apiSegment="deal-date"
          field="roundDate"
          value={c.roundDate}
          canEdit={canEdit}
          inputType="date"
        />
      ),
      partnerVc: matches.length === 0 ? '—' : <PartnerVcPopover matches={matches} />,
      score: score != null ? `${score.toFixed(1)} / 4` : '—',
      // 'new' (Admin's Needs Triage table, which reuses this same function --
      // see its own docstring) is a special case: StageMultiSelect's checked
      // set is built from PUBLIC_STAGES, which deliberately excludes 'new'
      // (lib/stages.js), so it has no way to represent OR clear that value.
      // Needs Triage's actual job is "assign this company its one real
      // stage, replacing 'new' outright" -- StageSelect's single-value
      // dropdown (which already special-cases prepending an out-of-list
      // current value) is the correct control there, not the multiselect.
      stage: c.stage === 'new'
        ? <StageSelect slug={c.slug} stage={c.stage} canEdit={canEdit} />
        : <StageMultiSelect slug={c.slug} stage={c.stage} tags={c.tags} canEdit={canEdit} />,
      passed: <PassedCheckbox slug={c.slug} tags={c.tags} canEdit={canEdit} />,
      date: c.latestScreen ? c.latestScreen.date.slice(0, 10) : '—',
      report: <Link href={`${resolvedBasePath}/${c.slug}`}>View screen →</Link>,
      actions: canEdit ? (
        <span className={styles.actions}>
          {/* Run Analysis (Stage 1) only while there's no screen yet -- once
              one exists, re-running Stage 1 from here no longer applies;
              Start Stage 2 (deep research) takes its place instead. Same
              gate CompanyDetailPage.jsx uses. */}
          {c.latestScreen == null
            ? <RunAnalysisButton slug={c.slug} name={name} />
            : <StartStage2Button slug={c.slug} name={name} />}
          <DeleteButton
            url={`/api/companies/${c.slug}`}
            confirmMessage={`Remove ${name} from the directory? This also deletes its screen history.`}
          />
        </span>
      ) : null,
    },
  };
}
