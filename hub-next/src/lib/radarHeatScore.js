// Radar's Hot/Cold split (Oscar, 2026-07-29): not just Python's clock
// proximity anymore -- a company is "hot" when it's BOTH close to raising
// AND something ID8 actually likes, summed into one number against a
// hub-editable threshold (see lib/radarConfig.js). Pure, no I/O, mirrors
// rubricMath.js's style -- the config comes from the caller so this stays
// testable with fabricated inputs.
//
// Timing component (0-6): how close `company.radar.clock.predictedWindowOpen`
// (written by deal_intelligence/radar_state.py) is to today, relative to the
// hub-configured `hotWindowMonths`. Full points once inside the window (or
// already past it -- a window that's opened and gone quiet is still urgent,
// not less), half credit while approaching it, nothing once it's genuinely
// far out. No estimate at all (mandate failed, or no headcount lookup has
// succeeded yet) scores 0 here, same as "far out" -- distinct from the UI
// treating it as "unscored" rather than "known to be cold" (see radar/page.jsx).
const MAX_TIMING_POINTS = 6;
const APPROACHING_TIMING_POINTS = 3;

// Fit component (0-6): the best available "do we like it" signal, scaled
// from a 1-4 rubric to roughly the same range as the timing component so
// neither one side dominates the sum by construction. Prefers the company's
// own Stage 1 screen (`latestScreen.fitScore`) when it has one; a Radar-stage
// company usually doesn't (see radarTableColumns.jsx's old comment), so this
// falls back to the best Stage 0 Portfolio Fit score across every Partner VC
// that already scored it in their own portfolio (bestInvestorFitScore, off
// companyStageColumns.jsx's row `meta` -- built once per page load, not
// re-scanned per company).
const MAX_FIT_POINTS = 6;
const FIT_SCALE = MAX_FIT_POINTS / 4;

const MS_PER_MONTH = 1000 * 60 * 60 * 24 * 30.44;

function monthsUntil(dateStr, today) {
  if (!dateStr) return null;
  const target = new Date(dateStr);
  if (Number.isNaN(target.getTime())) return null;
  return (target.getTime() - today.getTime()) / MS_PER_MONTH;
}

function timingPoints(monthsUntilWindow, hotWindowMonths) {
  if (monthsUntilWindow == null) return 0;
  if (monthsUntilWindow <= hotWindowMonths) return MAX_TIMING_POINTS;
  if (monthsUntilWindow <= hotWindowMonths * 2) return APPROACHING_TIMING_POINTS;
  return 0;
}

function fitPoints(fitScore) {
  return fitScore == null ? 0 : fitScore * FIT_SCALE;
}

// The best "do we like it" signal on file for `c` -- Stage 1 first, Stage 0
// portfolio-fit fallback. Exported separately so callers building a row
// (radarTableColumns.jsx) can pass exactly what they already computed
// instead of this module re-deriving it.
export function bestFitScore(c, bestInvestorFitScore) {
  if (c.latestScreen?.fitScore != null) return c.latestScreen.fitScore;
  return bestInvestorFitScore ?? null;
}

// Exposes the two components separately -- used for the Heat column's hover
// tooltip so a canEdit user tuning `hotThreshold`/`hotWindowMonths` can see
// why a given company landed where it did, not just the final number.
export function radarHeatBreakdown(c, config, fitScore, today = new Date()) {
  const monthsUntilWindow = monthsUntil(c.radar?.clock?.predictedWindowOpen, today);
  const timing = timingPoints(monthsUntilWindow, config.hotWindowMonths);
  const fit = fitPoints(fitScore);
  return { timing, fit, total: Math.round((timing + fit) * 10) / 10 };
}

// `today` defaults to `new Date()` -- callers running inside a Workflow
// script (which bans bare `new Date()`) should pass one in explicitly.
export function radarHeatScore(c, config, fitScore, today = new Date()) {
  return radarHeatBreakdown(c, config, fitScore, today).total;
}

export function radarHotnessFromScore(score, config) {
  return score >= config.hotThreshold ? 'hot' : 'cold';
}
