import { companyToRow, STAGE_TABLE_COLUMNS } from './companyStageColumns';
import { radarHeatBreakdown, bestFitScore, radarHotnessFromScore } from '@/lib/radarHeatScore';
import { formatPredictedWindow, formatNextScan, nextScanReason } from '@/lib/radar';
import { matchedKeywords } from '@/lib/radarRuleMatch';

// Radar's table is now the SAME shape every other stage table uses
// (STAGE_TABLE_COLUMNS/companyToRow from companyStageColumns.jsx) instead of
// a fully separate, bespoke column set -- Oscar: "make the radar table as
// all the rest of the tables but just with the stuff we've said to add on
// radar." Three Radar-only columns get inserted before Stage: Predicted
// Window, Next Scan, and Heat (the hub-configurable score behind the
// Hot/Cold split -- see lib/radarHeatScore.js). Reusing companyToRow also
// means Radar rows automatically pick up Run Analysis / Start Stage 2 in
// Actions, which the old bespoke column set explicitly omitted.
const STAGE_COL_INDEX = STAGE_TABLE_COLUMNS.findIndex((c) => c.key === 'stage');

export const RADAR_TABLE_COLUMNS = [
  ...STAGE_TABLE_COLUMNS.slice(0, STAGE_COL_INDEX),
  { key: 'predictedWindow', label: 'Predicted Window', sortable: true },
  { key: 'nextScan', label: 'Next Scan', sortable: true },
  { key: 'heat', label: 'Heat', sortable: true, defaultDir: 'desc' },
  ...STAGE_TABLE_COLUMNS.slice(STAGE_COL_INDEX),
];

// `radarConfig` ({hotWindowMonths, hotThreshold}, lib/radarConfig.js) and
// `keywords` ([{term}], lib/radarRules.js) come from the Radar page/board,
// alongside the same investorIndex/domainIndex every stage table already
// builds once per page load.
export function radarCompanyToRow(c, opts) {
  const { radarConfig, keywords = [] } = opts;
  const base = companyToRow(c, opts);
  const fitScore = bestFitScore(c, base.meta?.bestInvestorFitScore);
  const { timing, fit, total: score } = radarHeatBreakdown(c, radarConfig, fitScore);
  const hot = radarHotnessFromScore(score, radarConfig) === 'hot';
  const scanReason = nextScanReason(c);

  return {
    ...base,
    filterValues: { ...base.filterValues, keyword: matchedKeywords(c, keywords) },
    meta: { ...base.meta, heatScore: score, hot },
    sort: {
      ...base.sort,
      predictedWindow: c.radar?.clock?.predictedWindowOpen || '',
      nextScan: c.radar?.schedule?.nextScanAt || '',
      heat: score,
    },
    cells: {
      ...base.cells,
      predictedWindow: formatPredictedWindow(c),
      nextScan: <span title={scanReason || ''}>{formatNextScan(c)}</span>,
      heat: (
        <span
          className={`badge ${hot ? 'badge--radar-hot' : 'badge--cold'}`}
          title={`Timing ${timing} + Fit ${fit} = ${score} (hot at ${radarConfig.hotThreshold}+)`}
        >
          {score}
        </span>
      ),
    },
  };
}
