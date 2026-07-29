import 'server-only';
import { unstable_cache, revalidateTag } from 'next/cache';
import { db } from './firestore';

// The Radar keyword store -- click-to-filter chips on the Radar tab
// (docs/radar/page.jsx via RadarKeywordFilter.jsx), NOT a hide/exclusion
// list anymore (that admin panel -- live preview, "Excluded"/"Pinned"
// sections, per-company excludes, "keep anyway" -- was removed 2026-07-29;
// Oscar: "we don't have to take into account the admin table anymore
// because it shouldn't exist"). What's kept is just the growing list of
// terms itself -- his boss keeps adding new ones over time -- so clicking a
// keyword filters the visible table down to matches (lib/radarRuleMatch.js's
// matchedKeywords), it never removes a row from the table on its own.
// One document, not one-doc-per-keyword: the list is small (tens of
// entries) and always read as a unit, same reasoning as before.
const DOC_REF = () => db().collection('radarRules').doc('current');

function normalizeKeywords(data) {
  return (data?.keywords || []).map((k) => (typeof k === 'string' ? { term: k } : k)).filter((k) => k.term);
}

export const getRadarKeywords = unstable_cache(
  async () => {
    const snap = await DOC_REF().get();
    return snap.exists ? normalizeKeywords(snap.data()) : [];
  },
  ['radar-keywords'],
  { tags: ['radar-rules'] }
);

async function readRaw() {
  const snap = await DOC_REF().get();
  return snap.exists ? snap.data() : { keywords: [] };
}

export async function addKeywordRule(term, addedBy) {
  const clean = (term || '').trim().toLowerCase();
  if (!clean) throw new Error('empty-term');
  const data = await readRaw();
  const keywords = normalizeKeywords(data);
  if (!keywords.some((k) => k.term === clean)) {
    keywords.push({ term: clean, addedBy: addedBy || null, addedAt: new Date().toISOString() });
  }
  await DOC_REF().set({ keywords }, { merge: true });
  revalidateTag('radar-rules');
}

export async function removeKeywordRule(term) {
  const clean = (term || '').trim().toLowerCase();
  const data = await readRaw();
  const keywords = normalizeKeywords(data).filter((k) => k.term !== clean);
  await DOC_REF().set({ keywords }, { merge: true });
  revalidateTag('radar-rules');
}
