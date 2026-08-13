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

// `radarCategory` used to be filtered out here, Radar-only (Oscar,
// 2026-07-29: "eliminate radar category column"); as of 2026-08-13 it's gone
// from STAGE_TABLE_COLUMNS itself for every deals tab, so there's nothing
// left to filter.
export const RADAR_TABLE_COLUMNS = [
  ...STAGE_TABLE_COLUMNS.slice(0, STAGE_COL_INDEX),
  { key: 'predictedWindow', label: 'Predicted Window', sortable: true },
  { key: 'nextScan', label: 'Next Scan', sortable: true },
  { key: 'heat', label: 'Heat', sortable: true, defaultDir: 'desc' },
  ...STAGE_TABLE_COLUMNS.slice(STAGE_COL_INDEX),
];

// `radarConfig` ({hotWindowMonths, hotThreshold, watchFloor},
// lib/radarConfig.js) and `keywords` ([{term}], lib/radarRules.js) come
// from the Radar page/board, alongside the same investorIndex/domainIndex
// every stage table already builds once per page load.
//
// Heat prefers `company.radar.marketHeat.normalizedScore` (the Heat Score
// Signal Framework, 0-100 scale, deal_intelligence/radar_market_heat.py --
// Radar's primary/hegemonic score per Oscar's 2026-08-05 call), then
// `company.radar.hazard.heatPoints` (2026-07-29, also 0-100, the real
// Python-computed kernel/peak-decay hazard number written by
// radar_state.py) for a company that has hazard but no marketHeat yet, and
// falls back to the old live JS timing+fit calc (lib/radarHeatScore.js,
// its own small 0-12 scale) only once neither has ever been computed, so
// nothing goes blank mid-migration.
//
// "Hot" is the INTERSECTION of two deliberately separate gates (Oscar,
// 2026-07-29) -- the heat score clearing hotThreshold (timing: is it
// actually close to raising) AND `radar.access.accessPass` (syndicate:
// does ID8 have a real route in, deal_intelligence/radar_access.py).
// Blending the two into one number was explicitly rejected -- see that
// module's docstring -- because a company can score high on either axis
// for reasons that don't imply anything about the other. When access
// hasn't been assessed at all yet (true for every company scored only by
// the 2026-08-06 manual web-research pass -- `radar.access` is written by
// the same Python pipeline call as `radar.hazard`, which that pass never
// ran), the access gate doesn't block hot -- "unknown" isn't "no route in,"
// same missing-isn't-zero convention every signal in this codebase already
// follows. The old JS fallback path (neither marketHeat nor hazard
// computed yet) keeps its own older score-only gate, no access check at all.
export function radarCompanyToRow(c, opts) {
  const { radarConfig, keywords = [] } = opts;
  const base = companyToRow(c, opts);
  const scanReason = nextScanReason(c);

  const persistedHeat = c.radar?.hazard?.heatPoints;
  const hasPersistedHazard = typeof persistedHeat === 'number';
  // Heat Score Signal Framework (radar.marketHeat) is Radar's primary/
  // hegemonic score (Oscar, 2026-08-05, reaffirmed 2026-08-06: hot/cold
  // must actually key off it, not silently fall back to an unrelated
  // 0-12 JS placeholder scale just because hazard hasn't run) -- `score`
  // AND `hot` both prefer marketHeat whenever it exists, regardless of
  // whether this company has also been through the Python hazard pipeline.
  // Previously `score`/`hot` only ever looked at marketHeat INSIDE the
  // `hasPersistedHazard` branch, so the ~50 companies scored via the
  // 2026-08-06 manual web-research pass (marketHeat written, hazard never
  // computed -- that pass never touches radar.hazard at all) fell straight
  // to the JS placeholder below and showed as 0/near-0, never hot even at
  // 80+ (Oscar, 2026-08-06 screenshots).
  const marketHeat = c.radar?.marketHeat;
  const hasMarketHeat = typeof marketHeat?.normalizedScore === 'number';
  // `heatLines`: an array, one entry per popover line (RadarHeatPopover),
  // rather than one `·`-joined string -- replaces the old native `title`
  // tooltip (Oscar, 2026-08-06: "hover it and you see the full explanation
  // of the score, and it doesn't go off unless you press it").
  const signalFrameworkLine = hasMarketHeat
    ? `Signal Framework ${marketHeat.normalizedScore} (${marketHeat.pointsAvailable}/100 pts scored)${marketHeat.roundAnnouncedFlag ? ' · round already announced, suppressed' : ''}`
    : null;

  let score, hot, heatLines;
  if (hasMarketHeat) {
    const access = c.radar?.access;
    // Access hasn't been assessed at all for a marketHeat-only company (see
    // the module-level comment above) -- "unknown" doesn't block hot, only
    // an explicit `accessPass === false` would.
    const accessKnown = typeof access?.accessPass === 'boolean';
    score = marketHeat.normalizedScore;
    hot = score >= radarConfig.hotThreshold && (!accessKnown || access.accessPass);
    heatLines = [signalFrameworkLine];
    if (hasPersistedHazard) {
      const { p90, p180, confidence, familiesActive, dataCoverage } = c.radar.hazard;
      // Confidence + data coverage sit right next to the score itself, not
      // buried after families/access (Isabella, 2026-07-30: "Heat Score: 81
      // / Confidence: Medium / Data coverage: 68%") -- a partner glancing
      // at this popover should see, before anything else, how much to
      // trust the number they just read. `dataCoverage` may be absent on a
      // company scanned before this field existed (radar_hazard.compute()
      // didn't emit it pre-2026-07-30) -- omitted rather than shown as
      // "0%", since that company's coverage was never unmeasured-and-zero,
      // just unmeasured.
      const coveragePct = typeof dataCoverage === 'number' ? Math.round(dataCoverage * 100) : null;
      const confidenceLabel = confidence ? confidence[0].toUpperCase() + confidence.slice(1) : 'Unknown';
      heatLines.push(
        `Hazard model ${persistedHeat} · Confidence ${confidenceLabel}${coveragePct != null ? ` · Data coverage ${coveragePct}%` : ''}`,
        `P180 ${Math.round(p180 * 100)}% · P90 ${Math.round(p90 * 100)}%`,
        `Families: ${familiesActive?.length ? familiesActive.join(', ') : 'none'}`,
      );
    }
    heatLines.push(
      `Access: ${access?.level || (accessKnown ? 'unknown' : 'not yet assessed')}`,
      `Classified ${hot ? 'HOT' : 'COLD'} (needs ${radarConfig.hotThreshold}+${accessKnown ? ' AND syndicate access' : ''})`,
    );
    heatLines = heatLines.filter(Boolean);
  } else if (hasPersistedHazard) {
    // No marketHeat at all yet, but a real hazard scan exists -- same
    // "INTERSECTION of two deliberately separate gates" hot/cold logic
    // this whole function has always used for the hazard-only case.
    const { p90, p180, confidence, familiesActive, dataCoverage } = c.radar.hazard;
    const access = c.radar?.access;
    score = persistedHeat;
    hot = persistedHeat >= radarConfig.hotThreshold && !!access?.accessPass;
    const coveragePct = typeof dataCoverage === 'number' ? Math.round(dataCoverage * 100) : null;
    const confidenceLabel = confidence ? confidence[0].toUpperCase() + confidence.slice(1) : 'Unknown';
    heatLines = [
      `Hazard model ${persistedHeat} · Confidence ${confidenceLabel}${coveragePct != null ? ` · Data coverage ${coveragePct}%` : ''}`,
      `P180 ${Math.round(p180 * 100)}% · P90 ${Math.round(p90 * 100)}%`,
      `Families: ${familiesActive?.length ? familiesActive.join(', ') : 'none'}`,
      `Access: ${access?.level || 'unknown'}`,
      `Classified ${hot ? 'HOT' : 'COLD'} (needs ${radarConfig.hotThreshold}+ AND syndicate access)`,
    ];
  } else {
    const fitScore = bestFitScore(c, base.meta?.bestInvestorFitScore);
    const breakdown = radarHeatBreakdown(c, radarConfig, fitScore);
    score = breakdown.total;
    hot = radarHotnessFromScore(score, radarConfig) === 'hot';
    heatLines = [`Timing ${breakdown.timing} + Fit ${breakdown.fit} = ${score} (hot at ${radarConfig.hotThreshold}+, no hazard scan yet)`];
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
