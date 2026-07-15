import Link from 'next/link';
import StageSelect from './StageSelect';

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
  { key: 'score', label: 'Score', sortable: true },
  { key: 'stage', label: 'Stage', sortable: true },
  { key: 'date', label: 'Screened', sortable: true },
  { key: 'report', label: 'Report' },
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
      date: c.latestScreen?.date || '',
    },
    search: {
      company: name,
      stage: c.stage,
    },
    cells: {
      company: name,
      score: score != null ? `${score.toFixed(1)} / 4` : '—',
      stage: <StageSelect slug={c.slug} stage={c.stage} canEdit={canEdit} />,
      date: c.latestScreen ? c.latestScreen.date.slice(0, 10) : '—',
      report: <Link href={`${basePath}/${c.slug}`}>View screen →</Link>,
    },
  };
}
