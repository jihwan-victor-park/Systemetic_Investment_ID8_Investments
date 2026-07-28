import Link from 'next/link';
import StageSelect from './StageSelect';
import PartnerVcPopover from './PartnerVcPopover';
import DeleteButton from './DeleteButton';
import { allInvestorMatches } from '@/lib/companyIndex';
import { radarHotness, formatPredictedWindow, formatNextScan, nextScanReason } from '@/lib/radar';
import { STAGE_BASEPATH } from '@/lib/stages';
import styles from './companyStageColumns.module.css';

// A SEPARATE column set from companyStageColumns.jsx's STAGE_TABLE_COLUMNS/
// companyToRow, not a modification of them -- every other stage table
// (Watchlist/Pipeline/Qualified/Invested/Admin/Top10VC/Hot Deals) still
// imports that original pair unchanged. Radar drops Radar Category/Score/
// Screened (a Radar-stage company usually has no Stage 1 screen yet -- see
// radar/page.jsx's own header copy -- so those are mostly "—" here) in
// favor of the new mandate/clock/schedule columns radar_state.py computes
// (RADAR_PLAN.md Parts I/III/VI/VIII).
export const RADAR_TABLE_COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'series', label: 'Series', sortable: true },
  { key: 'dealDate', label: 'Deal Date', sortable: true },
  { key: 'predictedWindow', label: 'Predicted Window', sortable: true },
  { key: 'nextScan', label: 'Next Scan', sortable: true },
  { key: 'hotness', label: 'Hot / Cold', sortable: true },
  { key: 'partnerVc', label: 'Partner VC', sortable: true },
  { key: 'stage', label: 'Stage', sortable: true },
  { key: 'report', label: 'Report' },
  { key: 'actions', label: '' },
];

// No RunAnalysisButton/RoundInput/radarCategory inline-edit here -- a
// Radar-stage company doesn't have a Stage 1 screen to (re)run in the usual
// sense (it arrives cold per RADAR_PLAN.md §1.5a, watched for its NEXT
// round instead), and Series is Attio-sourced/read-only context on this
// table rather than a hand-edited field the way it is on the live-pipeline
// stage tables.
export function radarCompanyToRow(c, { canEdit, investorIndex = {}, domainIndex = {} }) {
  const basePath = STAGE_BASEPATH.radar;
  const matches = allInvestorMatches(investorIndex, c.name, domainIndex, c.investorDomains);
  const partnerVc = matches.length ? matches.map((m) => m.via).join(', ') : null;
  const hotness = radarHotness(c);
  const reason = nextScanReason(c);

  return {
    key: c.slug,
    tags: c.tags || [],
    sort: {
      company: c.name.toLowerCase(),
      series: c.round || '',
      dealDate: c.roundDate || '',
      predictedWindow: c.radar?.clock?.predictedWindowOpen || '',
      nextScan: c.radar?.schedule?.nextScanAt || '',
      hotness: hotness || '',
      partnerVc: partnerVc || '',
      stage: c.stage,
    },
    search: {
      company: c.name,
      series: c.round || '',
    },
    cells: {
      company: (
        <>
          <Link href={`${basePath}/${c.slug}`}>{c.name}</Link>
          {c.website && (
            <>
              {' ('}
              <a href={`https://${c.website}`} target="_blank" rel="noopener noreferrer">{c.website}</a>
              {')'}
            </>
          )}
        </>
      ),
      series: c.round || '—',
      dealDate: c.roundDate ? c.roundDate.slice(0, 10) : '—',
      predictedWindow: formatPredictedWindow(c),
      nextScan: <span title={reason || ''}>{formatNextScan(c)}</span>,
      hotness: hotness ? (
        <span className={`badge ${hotness === 'hot' ? 'badge--hot' : 'badge--cold'}`}>{hotness === 'hot' ? 'Hot' : 'Cold'}</span>
      ) : '—',
      partnerVc: matches.length === 0 ? '—' : <PartnerVcPopover matches={matches} />,
      stage: <StageSelect slug={c.slug} stage={c.stage} canEdit={canEdit} />,
      report: <Link href={`${basePath}/${c.slug}`}>View screen →</Link>,
      actions: canEdit ? (
        <span className={styles.actions}>
          <DeleteButton
            url={`/api/companies/${c.slug}`}
            confirmMessage={`Remove ${c.name} from the directory? This also deletes its screen history.`}
          />
        </span>
      ) : null,
    },
  };
}
