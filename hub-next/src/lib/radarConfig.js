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

const DEFAULTS = { hotWindowMonths: 3, hotThreshold: 5 };

export const getRadarConfig = unstable_cache(
  async () => {
    const snap = await DOC_REF().get();
    if (!snap.exists) return { ...DEFAULTS };
    const data = snap.data();
    return {
      hotWindowMonths: Number(data.hotWindowMonths) || DEFAULTS.hotWindowMonths,
      hotThreshold: Number(data.hotThreshold) || DEFAULTS.hotThreshold,
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
  next.updatedAt = new Date().toISOString();
  next.updatedBy = updatedBy || null;
  await DOC_REF().set(next, { merge: true });
  revalidateTag('radar-config');
  return { ...DEFAULTS, ...next };
}
