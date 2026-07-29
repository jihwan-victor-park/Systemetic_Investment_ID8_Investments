import 'server-only';
import { unstable_cache, revalidateTag } from 'next/cache';
import { db } from './firestore';

// Hub-editable knobs for Radar's Hot/Cold split (see lib/radarHeatScore.js) --
// one small Firestore doc, same "single doc, always read as a unit" reasoning
// as lib/radarRules.js. Deliberately NOT written by
// deal_intelligence/radar_state.py -- that job keeps producing the raw
// clock/mandate timing data, but the hot/cold call itself is made live in
// hub-next off this config, so editing a threshold here takes effect on the
// next page load instead of waiting for the next scan run or a redeploy.
const DOC_REF = () => db().collection('radarConfig').doc('current');

// `watchFloor` (2026-07-29): the Python pipeline's own auto-drop threshold
// (deal_intelligence/radar_state.py's DEFAULT_WATCH_FLOOR) -- a company
// whose real, Python-computed `radar.hazard.heatPoints` sits below this for
// a few consecutive scans stops surfacing on Radar at all. Same doc, same
// "hub-editable, no redeploy" convention as hotWindowMonths/hotThreshold;
// radar_state.py reads this Firestore doc directly (see its own
// _get_watch_floor()), it isn't pushed to Python any other way.
//
// `hotThreshold`/`watchFloor` are on a 0-100 scale as of 2026-07-29
// (radar_hazard.heat_points() rescaled from 0-10 -- "heat score of 80+"
// reads as roughly "P180 as a percent, 80%+"). Only meaningful once a
// company has been through the real Python hazard pipeline
// (`radar.hazard.heatPoints`) -- the old live-JS fallback score
// (lib/radarHeatScore.js) stays on its own small 0-12 scale and will
// simply never clear an 80-point threshold, which is the correct,
// conservative behavior for a company that hasn't been scanned yet, not a
// bug.
// watchFloor: 5, not a rounder-looking number -- matches
// deal_intelligence/radar_state.py's DEFAULT_WATCH_FLOOR exactly (see that
// constant's own comment for why 25 auto-dropped every passing company in
// production the same day it shipped). Keep these two defaults in sync by
// hand; there's no single source of truth across the language boundary.
const DEFAULTS = { hotWindowMonths: 3, hotThreshold: 80, watchFloor: 5 };

export const getRadarConfig = unstable_cache(
  async () => {
    const snap = await DOC_REF().get();
    if (!snap.exists) return { ...DEFAULTS };
    const data = snap.data();
    return {
      hotWindowMonths: Number(data.hotWindowMonths) || DEFAULTS.hotWindowMonths,
      hotThreshold: Number(data.hotThreshold) || DEFAULTS.hotThreshold,
      watchFloor: Number(data.watchFloor) || DEFAULTS.watchFloor,
    };
  },
  ['radar-config'],
  { tags: ['radar-config'] }
);

export async function updateRadarConfig(patch, updatedBy) {
  const next = {};
  if (patch.hotWindowMonths != null) {
    const v = Number(patch.hotWindowMonths);
    if (!Number.isFinite(v) || v <= 0) throw new Error('invalid-hot-window-months');
    next.hotWindowMonths = v;
  }
  if (patch.hotThreshold != null) {
    const v = Number(patch.hotThreshold);
    if (!Number.isFinite(v) || v <= 0) throw new Error('invalid-hot-threshold');
    next.hotThreshold = v;
  }
  if (patch.watchFloor != null) {
    const v = Number(patch.watchFloor);
    if (!Number.isFinite(v) || v <= 0) throw new Error('invalid-watch-floor');
    next.watchFloor = v;
  }
  next.updatedAt = new Date().toISOString();
  next.updatedBy = updatedBy || null;
  await DOC_REF().set(next, { merge: true });
  revalidateTag('radar-config');
  return { ...DEFAULTS, ...next };
}
