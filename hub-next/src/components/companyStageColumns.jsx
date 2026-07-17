import Link from 'next/link';
import StageSelect from './StageSelect';
import RoundInput from './RoundInput';
import DeleteButton from './DeleteButton';
import RunAnalysisButton from './RunAnalysisButton';
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
  { key: 'partnerVc', label: 'Partner VC', sortable: true },
  { key: 'score', label: 'Score', sortable: true },
  { key: 'stage', label: 'Stage', sortable: true },
  { key: 'date', label: 'Screened', sortable: true },
  { key: 'report', label: 'Report' },
  { key: 'actions', label: '' },
];

export function companyToRow(c, { basePath, canEdit }) {
  const name = displayName(c);
  const score = c.latestScreen?.fitScore ?? null;
  const partnerVc = c.origin?.leadInvestors || null;
  return {
    key: c.slug,
    sort: {
      company: name.toLowerCase(),
      series: c.round || '',
      partnerVc: partnerVc || '',
      score,
      stage: c.stage,
      date: c.latestScreen?.date || '',
    },
    search: {
      company: name,
      series: c.round || '',
    },
    cells: {
      company: c.website ? (
        <>
          {name} (<a href={`https://${c.website}`} target="_blank" rel="noopener noreferrer">{c.website}</a>)
        </>
      ) : name,
      series: <RoundInput slug={c.slug} round={c.round} canEdit={canEdit} />,
      partnerVc: partnerVc || '—',
      score: score != null ? `${score.toFixed(1)} / 4` : '—',
      stage: <StageSelect slug={c.slug} stage={c.stage} canEdit={canEdit} />,
      date: c.latestScreen ? c.latestScreen.date.slice(0, 10) : '—',
      report: <Link href={`${basePath}/${c.slug}`}>View screen →</Link>,
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
