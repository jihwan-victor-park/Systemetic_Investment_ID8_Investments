// Thin formatters over `company.radar` (RADAR_PLAN.md Part VIII's schema,
// written by deal_intelligence/radar_state.py) -- no calculation happens
// here, unlike rubricMath.js. Hot/Cold itself is no longer one of these:
// that's now computed live in hub-next from a hub-editable config (see
// lib/radarHeatScore.js), not read off `company.radar.hotness` directly, so
// an edited threshold takes effect without a Python redeploy.

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
