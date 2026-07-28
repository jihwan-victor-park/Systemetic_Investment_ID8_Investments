// Thin formatters over `company.radar` (RADAR_PLAN.md Part VIII's schema,
// written by deal_intelligence/radar_state.py) -- no calculation happens
// here, unlike rubricMath.js. There's no client-side interactive preview
// of the mandate screen or capital clock in this v1, so there's nothing
// that needs to independently reproduce that math; `hotness` itself is
// computed once server-side in Python and denormalized onto the doc, same
// reasoning as `latestScreen`'s denormalization (see companies.js).

// 'hot' | 'cold' | null (mandate failed, or mandate passed but there's no
// clock estimate yet -- e.g. no headcount lookup has succeeded).
export function radarHotness(c) {
  return c.radar?.hotness ?? null;
}

// A short label for the mandate-screen verdict column -- not yet screened
// (no radar object at all -- a company just moved to Radar, or backfill/
// the Attio-import hook hasn't run for it yet), Pass, or Fail with its
// reason.
export function mandateVerdictLabel(c) {
  const mandate = c.radar?.mandate;
  if (!mandate) return 'Not yet screened';
  if (mandate.pass) return 'Pass';
  return `Fail — ${mandate.failReason || 'unknown reason'}`;
}

export function formatPredictedWindow(c) {
  const open = c.radar?.clock?.predictedWindowOpen;
  return open ? open.slice(0, 7) : '—'; // YYYY-MM, a window not a single day
}

export function formatNextScan(c) {
  const next = c.radar?.schedule?.nextScanAt;
  return next ? next.slice(0, 10) : '—';
}

export function nextScanReason(c) {
  return c.radar?.schedule?.nextScanReason || null;
}
