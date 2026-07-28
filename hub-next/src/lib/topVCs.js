import 'server-only';
import { unstable_cache, revalidateTag } from 'next/cache';
import { db, isoDate } from './firestore';

const COLLECTION = 'topVCs';
// Same force-dynamic/no-route-cache reasoning as partnerVCs.js's own
// CACHE_SECONDS comment -- fetched alongside listPartnerVCs() on nearly
// every page.
const CACHE_SECONDS = 60;

// Every field beyond the original {name, tier, sector, website, note} is
// optional and defaults to empty/null here -- rows created before this
// feature shipped read back exactly as they did before, no migration needed.
function _mapVC(doc) {
  const d = doc.data();
  return {
    id: doc.id,
    name: d.name,
    tier: d.tier,
    sector: d.sector || '',
    website: d.website || '',
    note: d.note || '',
    fund: d.fund || null,
    // Manually-typed placeholder -- there is no live Attio sync for VC
    // relationship data. Surfaced in the UI as an explicitly manual field.
    attio: d.attio || null,
    deals: d.deals || [],
    totalInvestments: d.totalInvestments ?? null,
    news: d.news || [],
    createdAt: isoDate(d.createdAt),
  };
}

export const listTopVCs = unstable_cache(async () => {
  const snap = await db().collection(COLLECTION).orderBy('tier').orderBy('name').get();
  return snap.docs.map(_mapVC);
}, ['list-top-vcs'], { tags: ['top-vcs'], revalidate: CACHE_SECONDS });

export const getTopVC = unstable_cache(async (id) => {
  const doc = await db().collection(COLLECTION).doc(id).get();
  return doc.exists ? _mapVC(doc) : null;
}, ['get-top-vc'], { tags: ['top-vcs'], revalidate: CACHE_SECONDS });

export async function addTopVC({ name, tier, sector, website, note }) {
  const ref = await db().collection(COLLECTION).add({
    name,
    tier,
    sector: sector || '',
    website: website || '',
    note: note || '',
    createdAt: new Date(),
  });
  revalidateTag('top-vcs');
  return ref.id;
}

// Merge-patch for everything beyond the original add form -- fund
// characteristics, the Attio-relationship placeholder, and the deals/news
// lists. Callers send the whole nested object/array on every edit (the admin
// UI mutates its local copy, then PATCHes the full value back), so a shallow
// Firestore merge is enough; no dot-notation field paths needed.
export async function updateTopVC(id, patch) {
  const ref = db().collection(COLLECTION).doc(id);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('vc-not-found');
  await ref.set(patch, { merge: true });
  revalidateTag('top-vcs');
  return { id };
}

export async function deleteTopVC(id) {
  await db().collection(COLLECTION).doc(id).delete();
  revalidateTag('top-vcs');
}
