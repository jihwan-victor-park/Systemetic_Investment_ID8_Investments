import { companyToRow, STAGE_TABLE_COLUMNS } from './companyStageColumns';
import { radarHeatBreakdown, bestFitScore, radarHotnessFromScore } from '@/lib/radarHeatScore';
import { formatPredictedWindow, formatNextScan, nextScanReason } from '@/lib/radar';
import { matchedKeywords } from '@/lib/radarRuleMatch';
import RadarHeatPopover from './RadarHeatPopover';

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

// `radarCategory` dropped from Radar's own table (Oscar, 2026-07-29 notes:
// "eliminate radar category column") -- scoped to Radar only via this
// filter, not removed from STAGE_TABLE_COLUMNS itself, so Watchlist/
// Pipeline/Qualified Deals (which share that same column list) keep it.
export const RADAR_TABLE_COLUMNS = [
  ...STAGE_TABLE_COLUMNS.slice(0, STAGE_COL_INDEX),
  { key: 'predictedWindow', label: 'Predicted Window', sortable: true },
  { key: 'nextScan', label: 'Next Scan', sortable: true },
  { key: 'heat', label: 'Heat', sortable: true, defaultDir: 'desc' },
  ...STAGE_TABLE_COLUMNS.slice(STAGE_COL_INDEX),
].filter((c) => c.key !== 'radarCategory');

// `radarConfig` ({hotWindowMonths, hotThreshold, watchFloor},
// lib/radarConfig.js) and `keywords` ([{term}], lib/radarRules.js) come
// from the Radar page/board, alongside the same investorIndex/domainIndex
// every stage table already builds once per page load.
//
// Heat prefers `company.radar.hazard.heatPoints` (2026-07-29, 0-100 scale)
// -- the real, Python-computed kernel/peak-decay hazard number
// (deal_intelligence/radar_hazard.py, written by radar_state.py) -- and
// falls back to the old live JS timing+fit calc (lib/radarHeatScore.js,
// its own small 0-12 scale) only for a company that hasn't been through
// the new pipeline yet (no `radar.hazard` written), so nothing goes blank
// mid-migration.
//
// "Hot" on the persisted-hazard path is the INTERSECTION of two
// deliberately separate gates (Oscar, 2026-07-29) -- heatPoints clearing
// hotThreshold (timing: is it actually close to raising) AND
// `radar.access.accessPass` (syndicate: does ID8 have a real route in,
// deal_intelligence/radar_access.py). Blending the two into one number was
// explicitly rejected -- see that module's docstring -- because a company
// can score high on either axis for reasons that don't imply anything
// about the other. The old JS fallback path keeps its old score-only
// behavior (no `radar.access` exists for an unmigrated company).
export function radarCompanyToRow(c, opts) {
  const { radarConfig, keywords = [] } = opts;
  const base = companyToRow(c, opts);
  const scanReason = nextScanReason(c);

  const persistedHeat = c.radar?.hazard?.heatPoints;
  const hasPersistedHazard = typeof persistedHeat === 'number';
  // Heat Score Signal Framework (radar.marketHeat) is Radar's primary/
  // hegemonic score as of 2026-08-05 (Oscar's own call) -- shown here as
  // `score` whenever it has at least one of its 16 signals computed.
  // Hot/Cold classification below is UNCHANGED, still driven by the
  // hazard model's own heatPoints+access gate: watchFloor/hotThreshold
  // are calibrated against hazard's distribution, not marketHeat's (see
  // radar_market_heat.py's own module docstring for why swapping that
  // over needs its own real-company validation first) -- so a company can
  // show a marketHeat number that doesn't match its badge color until
  // that recalibration happens. The tooltip says so explicitly rather
  // than hiding the mismatch.
  const marketHeat = c.radar?.marketHeat;
  const hasMarketHeat = typeof marketHeat?.normalizedScore === 'number';
  // `heatLines`: an array, one entry per popover line (RadarHeatPopover),
  // rather than one `·`-joined string -- replaces the old native `title`
  // tooltip (Oscar, 2026-08-06: "hover it and you see the full explanation
  // of the score, and it doesn't go off unless you press it").
  let score, hot, heatLines;
  if (hasPersistedHazard) {
    const { p90, p180, confidence, familiesActive, dataCoverage } = c.radar.hazard;
    const access = c.radar?.access;
    const hazardScore = persistedHeat;
    const timingPass = hazardScore >= radarConfig.hotThreshold;
    hot = timingPass && !!access?.accessPass;
    // Confidence + data coverage sit right next to the score itself, not
    // buried after families/access (Isabella, 2026-07-30: "Heat Score: 81 /
    // Confidence: Medium / Data coverage: 68%") -- a partner glancing at
    // this popover should see, before anything else, how much to trust the
    // number they just read. `dataCoverage` may be absent on a company
    // scanned before this field existed (radar_hazard.compute() didn't emit
    // it pre-2026-07-30) -- omitted rather than shown as "0%", since that
    // company's coverage was never unmeasured-and-zero, just unmeasured.
    const coveragePct = typeof dataCoverage === 'number' ? Math.round(dataCoverage * 100) : null;
    const confidenceLabel = confidence ? confidence[0].toUpperCase() + confidence.slice(1) : 'Unknown';
    score = hasMarketHeat ? marketHeat.normalizedScore : hazardScore;
    heatLines = [
      hasMarketHeat
        ? `Signal Framework ${marketHeat.normalizedScore} (${marketHeat.pointsAvailable}/100 pts scored)${marketHeat.roundAnnouncedFlag ? ' · round already announced, suppressed' : ''}`
        : null,
      `Hazard model ${hazardScore} · Confidence ${confidenceLabel}${coveragePct != null ? ` · Data coverage ${coveragePct}%` : ''}`,
      `P180 ${Math.round(p180 * 100)}% · P90 ${Math.round(p90 * 100)}%`,
      `Families: ${familiesActive?.length ? familiesActive.join(', ') : 'none'}`,
      `Access: ${access?.level || 'unknown'}`,
      `Classified ${hot ? 'HOT' : 'COLD'} (needs ${radarConfig.hotThreshold}+ AND syndicate access)`,
    ].filter(Boolean);
  } else {
    const fitScore = bestFitScore(c, base.meta?.bestInvestorFitScore);
    const breakdown = radarHeatBreakdown(c, radarConfig, fitScore);
    score = breakdown.total;
    hot = radarHotnessFromScore(score, radarConfig) === 'hot';
    heatLines = [`Timing ${breakdown.timing} + Fit ${breakdown.fit} = ${score} (hot at ${radarConfig.hotThreshold}+)`];
  }

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
        <RadarHeatPopover
          score={score}
          hot={hot}
          lines={heatLines}
          nextScanDate={c.radar?.schedule?.nextScanAt ? formatNextScan(c) : null}
          nextScanReason={scanReason}
        />
      ),
    },
  };
}
