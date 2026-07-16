import Link from 'next/link';
import StageSelect from './StageSelect';
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

// How a company first showed up: pulled in by the Attio bulk import, kicked
// off from Research Chat / a Run Analysis rerun, or -- the common case for
// every company that predates this field -- unknown, labeled "Legacy" so
// it's honest about "existed before this feature" rather than implying it
// was a manual add.
const ORIGIN_LABELS = { attio: 'Attio', chat: 'Chat', manual: 'Manual' };

function OriginBadge({ origin }) {
  const source = origin?.source;
  const label = ORIGIN_LABELS[source] || 'Legacy';
  const title = origin?.attioStage ? `Attio stage: ${origin.attioStage}` : undefined;
  return <span className={`${styles.origin} ${styles[source] || ''}`} title={title}>{label}</span>;
}

// Shared by the Watchlist / Pipeline / Qualified Deals list pages -- same
// shape of data (a company with a latest Stage 1 screen), just filtered to a
// different `stage` and linked at a different basePath. Not a client
// component itself; it's called from Server Component pages, so the
// StageSelect element it builds here is a plain (serializable) React element
// by the time it reaches SortableTable.
export const STAGE_TABLE_COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'score', label: 'Score', sortable: true },
  { key: 'stage', label: 'Stage', sortable: true },
  { key: 'origin', label: 'Origin', sortable: true },
  { key: 'date', label: 'Screened', sortable: true },
  { key: 'report', label: 'Report' },
  { key: 'actions', label: '' },
];

export function companyToRow(c, { basePath, canEdit }) {
  const name = displayName(c);
  const score = c.latestScreen?.fitScore ?? null;
  return {
    key: c.slug,
    sort: {
      company: name.toLowerCase(),
      score,
      stage: c.stage,
      origin: c.origin?.source || 'zzz-legacy',
      date: c.latestScreen?.date || '',
    },
    search: {
      company: name,
      stage: c.stage,
      origin: ORIGIN_LABELS[c.origin?.source] || 'Legacy',
    },
    cells: {
      company: name,
      score: score != null ? `${score.toFixed(1)} / 4` : '—',
      stage: <StageSelect slug={c.slug} stage={c.stage} canEdit={canEdit} />,
      origin: <OriginBadge origin={c.origin} />,
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
