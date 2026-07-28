import Link from 'next/link';
import StageSelect from './StageSelect';
import RoundInput from './RoundInput';
import CompanyInlineField from './CompanyInlineField';
import PartnerVcPopover from './PartnerVcPopover';
import DeleteButton from './DeleteButton';
import RunAnalysisButton from './RunAnalysisButton';
import { investorMatchesFromIndex } from '@/lib/companyIndex';
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
  { key: 'radarCategory', label: 'Radar Category', sortable: true },
  { key: 'score', label: 'Score', sortable: true },
  { key: 'stage', label: 'Stage', sortable: true },
  { key: 'date', label: 'Screened', sortable: true },
  { key: 'report', label: 'Report' },
  { key: 'actions', label: '' },
];

// `basePath` is optional -- callers with a single fixed stage (Watchlist,
// Deal Pipeline, Qualified Deals, Radar, Invested, or Admin's Needs Triage
// table) pass their own page's path; a cross-cutting view spanning multiple
// stages could omit it and let each row resolve its own via c.stage instead.
export function companyToRow(c, { basePath, canEdit, investorIndex = {} }) {
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
  const matches = investorMatchesFromIndex(investorIndex, c.name);
  const partnerVc = matches.length ? matches.map((m) => m.via).join(', ') : null;
  return {
    key: c.slug,
    sort: {
      company: name.toLowerCase(),
      series: c.round || '',
      dealDate: c.roundDate || '',
      partnerVc: partnerVc || '',
      radarCategory: c.radarCategory || '',
      score,
      stage: c.stage,
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
      dealDate: c.roundDate ? c.roundDate.slice(0, 10) : '—',
      partnerVc: matches.length === 0 ? '—' : <PartnerVcPopover matches={matches} />,
      radarCategory: (
        <CompanyInlineField
          slug={c.slug}
          apiSegment="radar-category"
          field="radarCategory"
          value={c.radarCategory}
          canEdit={canEdit}
          placeholder="—"
        />
      ),
      score: score != null ? `${score.toFixed(1)} / 4` : '—',
      stage: <StageSelect slug={c.slug} stage={c.stage} canEdit={canEdit} />,
      date: c.latestScreen ? c.latestScreen.date.slice(0, 10) : '—',
      report: <Link href={`${resolvedBasePath}/${c.slug}`}>View screen →</Link>,
      actions: canEdit ? (
        <span className={styles.actions}>
          <RunAnalysisButton slug={c.slug} name={name} />
          <DeleteButton
            url={`/api/companies/${c.slug}`}
            confirmMessage={`Remove ${name} from the directory? This also deletes its screen history.`}
          />
        </span>
      ) : null,
    },
  };
}
